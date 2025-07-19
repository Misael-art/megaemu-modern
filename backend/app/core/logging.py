"""Configuração de logging do MegaEmu Modern.

Configura o sistema de logging usando Loguru com diferentes
níveis, formatação e rotação de arquivos.
"""

import sys
from pathlib import Path
from typing import Dict, Any

from loguru import logger

from app.core.config import settings


def setup_logging() -> None:
    """Configura o sistema de logging da aplicação.
    
    Remove handlers padrão e configura novos com formatação
    personalizada, níveis apropriados e rotação de arquivos.
    """
    # Remove handler padrão do loguru
    logger.remove()
    
    # Configuração de formato
    log_format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
        "<level>{message}</level>"
    )
    
    # Handler para console (stdout)
    logger.add(
        sys.stdout,
        format=log_format,
        level=settings.LOG_LEVEL,
        colorize=True,
        backtrace=True,
        diagnose=True,
    )
    
    # Criar diretório de logs se não existir
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    # Handler para arquivo de logs gerais
    logger.add(
        log_dir / "megaemu.log",
        format=log_format,
        level="INFO",
        rotation="10 MB",
        retention="30 days",
        compression="zip",
        backtrace=True,
        diagnose=True,
    )
    
    # Handler para arquivo de erros
    logger.add(
        log_dir / "errors.log",
        format=log_format,
        level="ERROR",
        rotation="5 MB",
        retention="60 days",
        compression="zip",
        backtrace=True,
        diagnose=True,
    )
    
    # Handler para arquivo de debug (apenas em modo debug)
    if settings.DEBUG:
        logger.add(
            log_dir / "debug.log",
            format=log_format,
            level="DEBUG",
            rotation="50 MB",
            retention="7 days",
            compression="zip",
            backtrace=True,
            diagnose=True,
        )
    
    # Handler para arquivo de acesso/requests
    logger.add(
        log_dir / "access.log",
        format=(
            "{time:YYYY-MM-DD HH:mm:ss.SSS} | "
            "{level: <8} | "
            "{extra[method]} {extra[url]} | "
            "Status: {extra[status_code]} | "
            "Duration: {extra[duration]}ms | "
            "IP: {extra[client_ip]} | "
            "User-Agent: {extra[user_agent]}"
        ),
        level="INFO",
        rotation="20 MB",
        retention="90 days",
        compression="zip",
        filter=lambda record: "access" in record["extra"],
    )
    
    # Handler para arquivo de tarefas assíncronas
    logger.add(
        log_dir / "tasks.log",
        format=(
            "{time:YYYY-MM-DD HH:mm:ss.SSS} | "
            "{level: <8} | "
            "Task: {extra[task_id]} | "
            "Type: {extra[task_type]} | "
            "Status: {extra[task_status]} | "
            "{message}"
        ),
        level="INFO",
        rotation="10 MB",
        retention="30 days",
        compression="zip",
        filter=lambda record: "task" in record["extra"],
    )
    
    # Configurar logging para bibliotecas externas
    configure_external_loggers()
    
    logger.info("Sistema de logging configurado com sucesso")


def configure_external_loggers() -> None:
    """Configura logging para bibliotecas externas.
    
    Ajusta níveis de log para evitar spam de bibliotecas
    como SQLAlchemy, uvicorn, etc.
    """
    import logging
    
    # Configurações específicas por biblioteca
    external_loggers = {
        "sqlalchemy.engine": "WARNING",
        "sqlalchemy.pool": "WARNING",
        "sqlalchemy.dialects": "WARNING",
        "alembic": "INFO",
        "uvicorn": "INFO",
        "uvicorn.access": "WARNING",
        "fastapi": "INFO",
        "celery": "INFO",
        "redis": "WARNING",
        "httpx": "WARNING",
        "playwright": "WARNING",
    }
    
    for logger_name, level in external_loggers.items():
        logging.getLogger(logger_name).setLevel(getattr(logging, level))


def get_logger_with_context(**context: Any) -> Any:
    """Retorna logger com contexto adicional.
    
    Args:
        **context: Contexto adicional para incluir nos logs
        
    Returns:
        Logger configurado com contexto
    """
    return logger.bind(**context)


def log_request(
    method: str,
    url: str,
    status_code: int,
    duration: float,
    client_ip: str,
    user_agent: str,
    user_id: str = None
) -> None:
    """Registra log de requisição HTTP.
    
    Args:
        method: Método HTTP
        url: URL da requisição
        status_code: Código de status da resposta
        duration: Duração da requisição em ms
        client_ip: IP do cliente
        user_agent: User-Agent do cliente
        user_id: ID do usuário (se autenticado)
    """
    context = {
        "access": True,
        "method": method,
        "url": url,
        "status_code": status_code,
        "duration": round(duration, 2),
        "client_ip": client_ip,
        "user_agent": user_agent[:100],  # Limitar tamanho
    }
    
    if user_id:
        context["user_id"] = user_id
    
    logger.bind(**context).info(f"{method} {url} - {status_code}")


def log_task(
    task_id: str,
    task_type: str,
    status: str,
    message: str,
    **extra_context: Any
) -> None:
    """Registra log de tarefa assíncrona.
    
    Args:
        task_id: ID da tarefa
        task_type: Tipo da tarefa
        status: Status da tarefa (started, success, failed, etc.)
        message: Mensagem do log
        **extra_context: Contexto adicional
    """
    context = {
        "task": True,
        "task_id": task_id,
        "task_type": task_type,
        "task_status": status,
        **extra_context
    }
    
    logger.bind(**context).info(message)


def log_database_operation(
    operation: str,
    table: str,
    duration: float = None,
    affected_rows: int = None,
    **extra_context: Any
) -> None:
    """Registra log de operação de banco de dados.
    
    Args:
        operation: Tipo de operação (SELECT, INSERT, UPDATE, DELETE)
        table: Nome da tabela
        duration: Duração da operação em ms
        affected_rows: Número de linhas afetadas
        **extra_context: Contexto adicional
    """
    context = {
        "database": True,
        "operation": operation,
        "table": table,
        **extra_context
    }
    
    if duration is not None:
        context["duration"] = round(duration, 2)
    if affected_rows is not None:
        context["affected_rows"] = affected_rows
    
    message = f"DB {operation} on {table}"
    if duration:
        message += f" ({duration:.2f}ms)"
    if affected_rows is not None:
        message += f" - {affected_rows} rows"
    
    logger.bind(**context).debug(message)


def log_security_event(
    event_type: str,
    client_ip: str,
    user_id: str = None,
    details: Dict[str, Any] = None
) -> None:
    """Registra evento de segurança.
    
    Args:
        event_type: Tipo do evento (login_failed, unauthorized_access, etc.)
        client_ip: IP do cliente
        user_id: ID do usuário (se disponível)
        details: Detalhes adicionais do evento
    """
    context = {
        "security": True,
        "event_type": event_type,
        "client_ip": client_ip,
    }
    
    if user_id:
        context["user_id"] = user_id
    if details:
        context.update(details)
    
    logger.bind(**context).warning(f"Security event: {event_type}")