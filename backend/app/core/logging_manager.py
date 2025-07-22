"""Sistema de logging estruturado avançado.

Este módulo implementa:
- Logging estruturado em formato JSON
- Rotação automática de logs por tamanho e tempo
- Múltiplos handlers (console, arquivo, syslog, webhook)
- Níveis de log configuráveis por módulo
- Filtragem e mascaramento de dados sensíveis
- Correlação de requests com trace IDs
- Métricas de logging
- Log shipping para análise externa
"""

import asyncio
import json
import logging
import logging.handlers
import os
import re
import sys
import time
import traceback
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from threading import local
from typing import Any, Dict, List, Optional, Set, Union, Callable

import aiofiles
import aiohttp
from pydantic import BaseModel


class LogLevel(Enum):
    """Níveis de log."""
    TRACE = 5
    DEBUG = 10
    INFO = 20
    WARNING = 30
    ERROR = 40
    CRITICAL = 50


class LogFormat(Enum):
    """Formatos de log."""
    JSON = "json"
    TEXT = "text"
    STRUCTURED = "structured"


class RotationType(Enum):
    """Tipos de rotação de logs."""
    SIZE = "size"
    TIME = "time"
    BOTH = "both"


class LoggingConfig(BaseModel):
    """Configuração do sistema de logging."""
    # Configurações gerais
    level: LogLevel = LogLevel.INFO
    format: LogFormat = LogFormat.JSON
    
    # Diretório de logs
    log_dir: str = "logs"
    
    # Rotação
    rotation_type: RotationType = RotationType.BOTH
    max_file_size: int = 10 * 1024 * 1024  # 10MB
    max_files: int = 10
    rotation_interval: str = "midnight"  # midnight, H, D, W0-W6
    
    # Handlers
    console_enabled: bool = True
    file_enabled: bool = True
    syslog_enabled: bool = False
    webhook_enabled: bool = False
    
    # Configurações específicas
    console_format: LogFormat = LogFormat.TEXT
    file_format: LogFormat = LogFormat.JSON
    
    # Filtragem
    sensitive_fields: List[str] = [
        "password", "token", "secret", "key", "authorization",
        "cookie", "session", "csrf", "api_key"
    ]
    
    # Níveis por módulo
    module_levels: Dict[str, LogLevel] = {}
    
    # Webhook
    webhook_url: Optional[str] = None
    webhook_timeout: int = 5
    webhook_retry_count: int = 3
    
    # Syslog
    syslog_host: str = "localhost"
    syslog_port: int = 514
    syslog_facility: int = 16  # LOG_LOCAL0
    
    # Performance
    async_logging: bool = True
    buffer_size: int = 1000
    flush_interval: float = 1.0
    
    # Correlação
    enable_correlation: bool = True
    correlation_header: str = "X-Correlation-ID"
    
    # Métricas
    enable_metrics: bool = True
    metrics_interval: int = 60


class LogRecord(BaseModel):
    """Registro de log estruturado."""
    timestamp: str
    level: str
    logger: str
    message: str
    module: Optional[str] = None
    function: Optional[str] = None
    line: Optional[int] = None
    correlation_id: Optional[str] = None
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    request_id: Optional[str] = None
    trace_id: Optional[str] = None
    span_id: Optional[str] = None
    extra: Dict[str, Any] = {}
    exception: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Converte para dicionário."""
        data = self.dict(exclude_none=True)
        return data
    
    def to_json(self) -> str:
        """Converte para JSON."""
        return json.dumps(self.to_dict(), ensure_ascii=False, separators=(',', ':'))


class LogMetrics(BaseModel):
    """Métricas de logging."""
    total_logs: int = 0
    logs_by_level: Dict[str, int] = {}
    logs_by_logger: Dict[str, int] = {}
    errors_count: int = 0
    warnings_count: int = 0
    avg_log_size: float = 0.0
    logs_per_second: float = 0.0
    last_reset: datetime = datetime.now(timezone.utc)
    
    def reset(self):
        """Reseta métricas."""
        self.total_logs = 0
        self.logs_by_level.clear()
        self.logs_by_logger.clear()
        self.errors_count = 0
        self.warnings_count = 0
        self.avg_log_size = 0.0
        self.logs_per_second = 0.0
        self.last_reset = datetime.now(timezone.utc)


class CorrelationContext:
    """Contexto de correlação para rastreamento de requests."""
    
    def __init__(self):
        self._local = local()
    
    def set_correlation_id(self, correlation_id: str):
        """Define ID de correlação."""
        self._local.correlation_id = correlation_id
    
    def get_correlation_id(self) -> Optional[str]:
        """Obtém ID de correlação."""
        return getattr(self._local, 'correlation_id', None)
    
    def set_user_id(self, user_id: str):
        """Define ID do usuário."""
        self._local.user_id = user_id
    
    def get_user_id(self) -> Optional[str]:
        """Obtém ID do usuário."""
        return getattr(self._local, 'user_id', None)
    
    def set_session_id(self, session_id: str):
        """Define ID da sessão."""
        self._local.session_id = session_id
    
    def get_session_id(self) -> Optional[str]:
        """Obtém ID da sessão."""
        return getattr(self._local, 'session_id', None)
    
    def set_request_id(self, request_id: str):
        """Define ID do request."""
        self._local.request_id = request_id
    
    def get_request_id(self) -> Optional[str]:
        """Obtém ID do request."""
        return getattr(self._local, 'request_id', None)
    
    def clear(self):
        """Limpa contexto."""
        for attr in ['correlation_id', 'user_id', 'session_id', 'request_id']:
            if hasattr(self._local, attr):
                delattr(self._local, attr)
    
    @contextmanager
    def correlation_scope(self, correlation_id: Optional[str] = None):
        """Context manager para escopo de correlação."""
        old_correlation_id = self.get_correlation_id()
        
        if correlation_id is None:
            correlation_id = str(uuid.uuid4())
        
        self.set_correlation_id(correlation_id)
        
        try:
            yield correlation_id
        finally:
            if old_correlation_id:
                self.set_correlation_id(old_correlation_id)
            else:
                if hasattr(self._local, 'correlation_id'):
                    delattr(self._local, 'correlation_id')


class SensitiveDataFilter:
    """Filtro para mascarar dados sensíveis."""
    
    def __init__(self, sensitive_fields: List[str]):
        self.sensitive_fields = set(field.lower() for field in sensitive_fields)
        
        # Padrões regex para detectar dados sensíveis
        self.patterns = [
            (re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'), '[EMAIL]'),
            (re.compile(r'\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b'), '[CARD]'),
            (re.compile(r'\b\d{3}-\d{2}-\d{4}\b'), '[SSN]'),
            (re.compile(r'\b(?:\d{1,3}\.){3}\d{1,3}\b'), '[IP]'),
        ]
    
    def filter_dict(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Filtra dicionário mascarando campos sensíveis."""
        if not isinstance(data, dict):
            return data
        
        filtered = {}
        for key, value in data.items():
            if key.lower() in self.sensitive_fields:
                filtered[key] = '[MASKED]'
            elif isinstance(value, dict):
                filtered[key] = self.filter_dict(value)
            elif isinstance(value, list):
                filtered[key] = [self.filter_dict(item) if isinstance(item, dict) else self.filter_value(item) for item in value]
            else:
                filtered[key] = self.filter_value(value)
        
        return filtered
    
    def filter_value(self, value: Any) -> Any:
        """Filtra valor individual."""
        if not isinstance(value, str):
            return value
        
        filtered_value = value
        for pattern, replacement in self.patterns:
            filtered_value = pattern.sub(replacement, filtered_value)
        
        return filtered_value
    
    def filter_message(self, message: str) -> str:
        """Filtra mensagem de log."""
        return self.filter_value(message)


class StructuredFormatter(logging.Formatter):
    """Formatter para logs estruturados."""
    
    def __init__(self, config: LoggingConfig, correlation_context: CorrelationContext):
        super().__init__()
        self.config = config
        self.correlation_context = correlation_context
        self.sensitive_filter = SensitiveDataFilter(config.sensitive_fields)
    
    def format(self, record: logging.LogRecord) -> str:
        """Formata registro de log."""
        # Cria registro estruturado
        log_record = LogRecord(
            timestamp=datetime.fromtimestamp(record.created, timezone.utc).isoformat(),
            level=record.levelname,
            logger=record.name,
            message=self.sensitive_filter.filter_message(record.getMessage()),
            module=record.module if hasattr(record, 'module') else None,
            function=record.funcName if hasattr(record, 'funcName') else None,
            line=record.lineno if hasattr(record, 'lineno') else None,
            correlation_id=self.correlation_context.get_correlation_id(),
            user_id=self.correlation_context.get_user_id(),
            session_id=self.correlation_context.get_session_id(),
            request_id=self.correlation_context.get_request_id()
        )
        
        # Adiciona campos extras
        if hasattr(record, 'extra') and record.extra:
            log_record.extra = self.sensitive_filter.filter_dict(record.extra)
        
        # Adiciona informações de exceção
        if record.exc_info:
            log_record.exception = {
                'type': record.exc_info[0].__name__ if record.exc_info[0] else None,
                'message': str(record.exc_info[1]) if record.exc_info[1] else None,
                'traceback': traceback.format_exception(*record.exc_info)
            }
        
        # Formata baseado no tipo
        if self.config.format == LogFormat.JSON:
            return log_record.to_json()
        elif self.config.format == LogFormat.STRUCTURED:
            return self._format_structured(log_record)
        else:
            return self._format_text(log_record)
    
    def _format_structured(self, record: LogRecord) -> str:
        """Formata como texto estruturado."""
        parts = [
            f"[{record.timestamp}]",
            f"[{record.level}]",
            f"[{record.logger}]"
        ]
        
        if record.correlation_id:
            parts.append(f"[{record.correlation_id}]")
        
        parts.append(record.message)
        
        if record.extra:
            extra_str = " ".join(f"{k}={v}" for k, v in record.extra.items())
            parts.append(f"({extra_str})")
        
        return " ".join(parts)
    
    def _format_text(self, record: LogRecord) -> str:
        """Formata como texto simples."""
        timestamp = datetime.fromisoformat(record.timestamp).strftime("%Y-%m-%d %H:%M:%S")
        return f"{timestamp} [{record.level}] {record.logger}: {record.message}"


class AsyncLogHandler(logging.Handler):
    """Handler assíncrono para logging."""
    
    def __init__(self, target_handler: logging.Handler, buffer_size: int = 1000, flush_interval: float = 1.0):
        super().__init__()
        self.target_handler = target_handler
        self.buffer_size = buffer_size
        self.flush_interval = flush_interval
        self.buffer: List[logging.LogRecord] = []
        self.last_flush = time.time()
        self._lock = asyncio.Lock()
        self._flush_task: Optional[asyncio.Task] = None
    
    def emit(self, record: logging.LogRecord):
        """Adiciona registro ao buffer."""
        if len(self.buffer) >= self.buffer_size:
            # Buffer cheio, força flush
            asyncio.create_task(self._flush_buffer())
        else:
            self.buffer.append(record)
            
            # Verifica se precisa fazer flush por tempo
            if time.time() - self.last_flush >= self.flush_interval:
                asyncio.create_task(self._flush_buffer())
    
    async def _flush_buffer(self):
        """Faz flush do buffer."""
        async with self._lock:
            if not self.buffer:
                return
            
            records_to_flush = self.buffer.copy()
            self.buffer.clear()
            self.last_flush = time.time()
            
            # Processa registros no handler alvo
            for record in records_to_flush:
                try:
                    self.target_handler.emit(record)
                except Exception as e:
                    # Evita recursão infinita
                    print(f"Erro no handler de log: {e}", file=sys.stderr)
    
    async def close(self):
        """Fecha handler."""
        await self._flush_buffer()
        self.target_handler.close()


class WebhookHandler(logging.Handler):
    """Handler para enviar logs via webhook."""
    
    def __init__(self, webhook_url: str, timeout: int = 5, retry_count: int = 3):
        super().__init__()
        self.webhook_url = webhook_url
        self.timeout = timeout
        self.retry_count = retry_count
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Obtém sessão HTTP."""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.timeout)
            )
        return self.session
    
    def emit(self, record: logging.LogRecord):
        """Envia log via webhook."""
        asyncio.create_task(self._send_webhook(record))
    
    async def _send_webhook(self, record: logging.LogRecord):
        """Envia webhook assincronamente."""
        try:
            session = await self._get_session()
            
            # Prepara payload
            payload = {
                'timestamp': datetime.fromtimestamp(record.created, timezone.utc).isoformat(),
                'level': record.levelname,
                'logger': record.name,
                'message': record.getMessage(),
                'module': getattr(record, 'module', None),
                'function': getattr(record, 'funcName', None),
                'line': getattr(record, 'lineno', None)
            }
            
            # Adiciona exceção se houver
            if record.exc_info:
                payload['exception'] = {
                    'type': record.exc_info[0].__name__ if record.exc_info[0] else None,
                    'message': str(record.exc_info[1]) if record.exc_info[1] else None
                }
            
            # Tenta enviar com retry
            for attempt in range(self.retry_count):
                try:
                    async with session.post(self.webhook_url, json=payload) as response:
                        if response.status < 400:
                            break
                        elif attempt == self.retry_count - 1:
                            print(f"Webhook falhou após {self.retry_count} tentativas: {response.status}", file=sys.stderr)
                except Exception as e:
                    if attempt == self.retry_count - 1:
                        print(f"Erro no webhook: {e}", file=sys.stderr)
                    else:
                        await asyncio.sleep(2 ** attempt)  # Backoff exponencial
                        
        except Exception as e:
            print(f"Erro crítico no webhook: {e}", file=sys.stderr)
    
    async def close(self):
        """Fecha handler."""
        if self.session and not self.session.closed:
            await self.session.close()


class LoggingManager:
    """Gerenciador principal do sistema de logging."""
    
    def __init__(self, config: LoggingConfig):
        self.config = config
        self.correlation_context = CorrelationContext()
        self.metrics = LogMetrics()
        self.handlers: List[logging.Handler] = []
        self.async_handlers: List[AsyncLogHandler] = []
        self.webhook_handlers: List[WebhookHandler] = []
        self._metrics_task: Optional[asyncio.Task] = None
        self._setup_logging()
    
    def _setup_logging(self):
        """Configura sistema de logging."""
        # Cria diretório de logs
        log_dir = Path(self.config.log_dir)
        log_dir.mkdir(parents=True, exist_ok=True)
        
        # Configura logger raiz
        root_logger = logging.getLogger()
        root_logger.setLevel(self.config.level.value)
        
        # Remove handlers existentes
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
        
        # Adiciona handlers
        if self.config.console_enabled:
            self._add_console_handler()
        
        if self.config.file_enabled:
            self._add_file_handler()
        
        if self.config.syslog_enabled:
            self._add_syslog_handler()
        
        if self.config.webhook_enabled and self.config.webhook_url:
            self._add_webhook_handler()
        
        # Configura níveis por módulo
        for module_name, level in self.config.module_levels.items():
            logger = logging.getLogger(module_name)
            logger.setLevel(level.value)
    
    def _add_console_handler(self):
        """Adiciona handler para console."""
        handler = logging.StreamHandler(sys.stdout)
        
        # Usa formato específico para console
        config = self.config.copy()
        config.format = self.config.console_format
        
        formatter = StructuredFormatter(config, self.correlation_context)
        handler.setFormatter(formatter)
        
        if self.config.async_logging:
            async_handler = AsyncLogHandler(
                handler,
                self.config.buffer_size,
                self.config.flush_interval
            )
            self.async_handlers.append(async_handler)
            logging.getLogger().addHandler(async_handler)
        else:
            logging.getLogger().addHandler(handler)
        
        self.handlers.append(handler)
    
    def _add_file_handler(self):
        """Adiciona handler para arquivo."""
        log_file = Path(self.config.log_dir) / "app.log"
        
        if self.config.rotation_type in [RotationType.SIZE, RotationType.BOTH]:
            handler = logging.handlers.RotatingFileHandler(
                log_file,
                maxBytes=self.config.max_file_size,
                backupCount=self.config.max_files,
                encoding='utf-8'
            )
        elif self.config.rotation_type == RotationType.TIME:
            handler = logging.handlers.TimedRotatingFileHandler(
                log_file,
                when=self.config.rotation_interval,
                backupCount=self.config.max_files,
                encoding='utf-8'
            )
        else:
            handler = logging.FileHandler(log_file, encoding='utf-8')
        
        # Usa formato específico para arquivo
        config = self.config.copy()
        config.format = self.config.file_format
        
        formatter = StructuredFormatter(config, self.correlation_context)
        handler.setFormatter(formatter)
        
        if self.config.async_logging:
            async_handler = AsyncLogHandler(
                handler,
                self.config.buffer_size,
                self.config.flush_interval
            )
            self.async_handlers.append(async_handler)
            logging.getLogger().addHandler(async_handler)
        else:
            logging.getLogger().addHandler(handler)
        
        self.handlers.append(handler)
    
    def _add_syslog_handler(self):
        """Adiciona handler para syslog."""
        try:
            handler = logging.handlers.SysLogHandler(
                address=(self.config.syslog_host, self.config.syslog_port),
                facility=self.config.syslog_facility
            )
            
            formatter = StructuredFormatter(self.config, self.correlation_context)
            handler.setFormatter(formatter)
            
            logging.getLogger().addHandler(handler)
            self.handlers.append(handler)
            
        except Exception as e:
            print(f"Erro ao configurar syslog: {e}", file=sys.stderr)
    
    def _add_webhook_handler(self):
        """Adiciona handler para webhook."""
        try:
            handler = WebhookHandler(
                self.config.webhook_url,
                self.config.webhook_timeout,
                self.config.webhook_retry_count
            )
            
            # Webhook apenas para erros e críticos
            handler.setLevel(logging.ERROR)
            
            logging.getLogger().addHandler(handler)
            self.webhook_handlers.append(handler)
            
        except Exception as e:
            print(f"Erro ao configurar webhook: {e}", file=sys.stderr)
    
    async def start(self):
        """Inicia gerenciador de logging."""
        if self.config.enable_metrics:
            self._metrics_task = asyncio.create_task(self._metrics_loop())
        
        logging.info("Sistema de logging iniciado")
    
    async def stop(self):
        """Para gerenciador de logging."""
        if self._metrics_task:
            self._metrics_task.cancel()
            try:
                await self._metrics_task
            except asyncio.CancelledError:
                pass
        
        # Fecha handlers assíncronos
        for handler in self.async_handlers:
            await handler.close()
        
        # Fecha handlers webhook
        for handler in self.webhook_handlers:
            await handler.close()
        
        # Fecha handlers normais
        for handler in self.handlers:
            handler.close()
        
        logging.info("Sistema de logging parado")
    
    def get_logger(self, name: str) -> logging.Logger:
        """Obtém logger com nome específico."""
        logger = logging.getLogger(name)
        
        # Aplica nível específico se configurado
        if name in self.config.module_levels:
            logger.setLevel(self.config.module_levels[name].value)
        
        return logger
    
    def set_correlation_id(self, correlation_id: str):
        """Define ID de correlação."""
        self.correlation_context.set_correlation_id(correlation_id)
    
    def get_correlation_id(self) -> Optional[str]:
        """Obtém ID de correlação."""
        return self.correlation_context.get_correlation_id()
    
    def correlation_scope(self, correlation_id: Optional[str] = None):
        """Context manager para escopo de correlação."""
        return self.correlation_context.correlation_scope(correlation_id)
    
    def update_metrics(self, record: logging.LogRecord):
        """Atualiza métricas de logging."""
        if not self.config.enable_metrics:
            return
        
        self.metrics.total_logs += 1
        
        # Contadores por nível
        level = record.levelname
        self.metrics.logs_by_level[level] = self.metrics.logs_by_level.get(level, 0) + 1
        
        # Contadores por logger
        logger_name = record.name
        self.metrics.logs_by_logger[logger_name] = self.metrics.logs_by_logger.get(logger_name, 0) + 1
        
        # Contadores especiais
        if level == 'ERROR':
            self.metrics.errors_count += 1
        elif level == 'WARNING':
            self.metrics.warnings_count += 1
        
        # Tamanho médio (aproximado)
        message_size = len(record.getMessage())
        self.metrics.avg_log_size = (
            (self.metrics.avg_log_size * (self.metrics.total_logs - 1) + message_size) /
            self.metrics.total_logs
        )
    
    async def get_metrics(self) -> LogMetrics:
        """Obtém métricas atuais."""
        # Calcula logs por segundo
        now = datetime.now(timezone.utc)
        time_diff = (now - self.metrics.last_reset).total_seconds()
        
        if time_diff > 0:
            self.metrics.logs_per_second = self.metrics.total_logs / time_diff
        
        return self.metrics
    
    async def _metrics_loop(self):
        """Loop de coleta de métricas."""
        while True:
            try:
                await asyncio.sleep(self.config.metrics_interval)
                
                metrics = await self.get_metrics()
                
                logging.info(
                    "Métricas de logging",
                    extra={
                        'total_logs': metrics.total_logs,
                        'logs_per_second': round(metrics.logs_per_second, 2),
                        'errors_count': metrics.errors_count,
                        'warnings_count': metrics.warnings_count,
                        'avg_log_size': round(metrics.avg_log_size, 2)
                    }
                )
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Erro na coleta de métricas de logging: {e}", file=sys.stderr)


# Instância global
logging_manager: Optional[LoggingManager] = None


def get_logging_manager() -> LoggingManager:
    """Obtém instância global do gerenciador de logging."""
    global logging_manager
    if logging_manager is None:
        config = LoggingConfig()
        logging_manager = LoggingManager(config)
    
    return logging_manager


def get_logger(name: str) -> logging.Logger:
    """Obtém logger configurado."""
    manager = get_logging_manager()
    return manager.get_logger(name)


def set_correlation_id(correlation_id: str):
    """Define ID de correlação global."""
    manager = get_logging_manager()
    manager.set_correlation_id(correlation_id)


def get_correlation_id() -> Optional[str]:
    """Obtém ID de correlação global."""
    manager = get_logging_manager()
    return manager.get_correlation_id()


def correlation_scope(correlation_id: Optional[str] = None):
    """Context manager para escopo de correlação."""
    manager = get_logging_manager()
    return manager.correlation_scope(correlation_id)


# Decorador para logging automático
def logged(
    level: LogLevel = LogLevel.INFO,
    include_args: bool = False,
    include_result: bool = False,
    exclude_args: Optional[List[str]] = None
):
    """Decorador para logging automático de funções.
    
    Args:
        level: Nível do log
        include_args: Se deve incluir argumentos
        include_result: Se deve incluir resultado
        exclude_args: Argumentos a excluir do log
    """
    def decorator(func):
        logger = get_logger(func.__module__)
        exclude_set = set(exclude_args or [])
        
        async def async_wrapper(*args, **kwargs):
            start_time = time.time()
            
            # Log de entrada
            extra = {'function': func.__name__}
            if include_args:
                # Filtra argumentos sensíveis
                safe_kwargs = {
                    k: v for k, v in kwargs.items()
                    if k not in exclude_set
                }
                extra['args'] = safe_kwargs
            
            logger.log(level.value, f"Iniciando {func.__name__}", extra=extra)
            
            try:
                result = await func(*args, **kwargs)
                
                # Log de sucesso
                duration = time.time() - start_time
                extra = {
                    'function': func.__name__,
                    'duration_ms': round(duration * 1000, 2),
                    'status': 'success'
                }
                
                if include_result and result is not None:
                    extra['result'] = str(result)[:1000]  # Limita tamanho
                
                logger.log(level.value, f"Concluído {func.__name__}", extra=extra)
                return result
                
            except Exception as e:
                # Log de erro
                duration = time.time() - start_time
                extra = {
                    'function': func.__name__,
                    'duration_ms': round(duration * 1000, 2),
                    'status': 'error',
                    'error': str(e)
                }
                
                logger.error(f"Erro em {func.__name__}: {e}", extra=extra, exc_info=True)
                raise
        
        def sync_wrapper(*args, **kwargs):
            start_time = time.time()
            
            # Log de entrada
            extra = {'function': func.__name__}
            if include_args:
                safe_kwargs = {
                    k: v for k, v in kwargs.items()
                    if k not in exclude_set
                }
                extra['args'] = safe_kwargs
            
            logger.log(level.value, f"Iniciando {func.__name__}", extra=extra)
            
            try:
                result = func(*args, **kwargs)
                
                # Log de sucesso
                duration = time.time() - start_time
                extra = {
                    'function': func.__name__,
                    'duration_ms': round(duration * 1000, 2),
                    'status': 'success'
                }
                
                if include_result and result is not None:
                    extra['result'] = str(result)[:1000]
                
                logger.log(level.value, f"Concluído {func.__name__}", extra=extra)
                return result
                
            except Exception as e:
                # Log de erro
                duration = time.time() - start_time
                extra = {
                    'function': func.__name__,
                    'duration_ms': round(duration * 1000, 2),
                    'status': 'error',
                    'error': str(e)
                }
                
                logger.error(f"Erro em {func.__name__}: {e}", extra=extra, exc_info=True)
                raise
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator