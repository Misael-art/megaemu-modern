"""Sistema de observabilidade e métricas em tempo real.

Este módulo implementa:
- Coleta de métricas de performance em tempo real
- Dashboard de estatísticas do sistema
- Alertas automáticos para problemas
- Telemetria opcional e configurável
- Relatórios de saúde do sistema
- Monitoramento de recursos (CPU, memória, disco)
- Métricas de aplicação customizadas
- Integração com Prometheus e Grafana
"""

import asyncio
import json
import os
import platform
import psutil
import time
import uuid
from collections import defaultdict, deque
from datetime import datetime, timezone, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable, Union, Set

import aiofiles
import aiohttp
from pydantic import BaseModel
from prometheus_client import (
    Counter, Histogram, Gauge, Summary, Info,
    CollectorRegistry, generate_latest, CONTENT_TYPE_LATEST
)


class MetricType(Enum):
    """Tipos de métricas."""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    SUMMARY = "summary"
    INFO = "info"


class AlertSeverity(Enum):
    """Severidade de alertas."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class HealthStatus(Enum):
    """Status de saúde."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    CRITICAL = "critical"


class ObservabilityConfig(BaseModel):
    """Configuração do sistema de observabilidade."""
    # Coleta de métricas
    metrics_enabled: bool = True
    metrics_interval: int = 10  # segundos
    metrics_retention: int = 3600  # segundos (1 hora)
    
    # Sistema de alertas
    alerts_enabled: bool = True
    alert_cooldown: int = 300  # segundos (5 minutos)
    
    # Telemetria
    telemetry_enabled: bool = False
    telemetry_endpoint: Optional[str] = None
    telemetry_interval: int = 300  # segundos (5 minutos)
    
    # Relatórios de saúde
    health_checks_enabled: bool = True
    health_check_interval: int = 30  # segundos
    
    # Monitoramento de recursos
    system_monitoring_enabled: bool = True
    
    # Prometheus
    prometheus_enabled: bool = True
    prometheus_port: int = 8000
    prometheus_path: str = "/metrics"
    
    # Thresholds para alertas
    cpu_threshold: float = 80.0  # %
    memory_threshold: float = 85.0  # %
    disk_threshold: float = 90.0  # %
    response_time_threshold: float = 1000.0  # ms
    error_rate_threshold: float = 5.0  # %
    
    # Armazenamento
    data_dir: str = "observability"
    export_enabled: bool = True
    export_interval: int = 3600  # segundos (1 hora)


class MetricValue(BaseModel):
    """Valor de métrica com timestamp."""
    timestamp: datetime
    value: Union[float, int, str]
    labels: Dict[str, str] = {}
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class Alert(BaseModel):
    """Alerta do sistema."""
    id: str
    timestamp: datetime
    severity: AlertSeverity
    title: str
    message: str
    metric: str
    value: Union[float, int, str]
    threshold: Union[float, int, str]
    labels: Dict[str, str] = {}
    resolved: bool = False
    resolved_at: Optional[datetime] = None
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class HealthCheck(BaseModel):
    """Verificação de saúde."""
    name: str
    status: HealthStatus
    timestamp: datetime
    duration_ms: float
    message: Optional[str] = None
    details: Dict[str, Any] = {}
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class SystemMetrics(BaseModel):
    """Métricas do sistema."""
    timestamp: datetime
    cpu_percent: float
    memory_percent: float
    memory_used_mb: float
    memory_total_mb: float
    disk_percent: float
    disk_used_gb: float
    disk_total_gb: float
    network_bytes_sent: int
    network_bytes_recv: int
    load_average: List[float]
    process_count: int
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class ApplicationMetrics(BaseModel):
    """Métricas da aplicação."""
    timestamp: datetime
    requests_total: int
    requests_per_second: float
    response_time_avg: float
    response_time_p95: float
    response_time_p99: float
    error_rate: float
    active_connections: int
    database_connections: int
    cache_hit_rate: float
    queue_size: int
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class TelemetryData(BaseModel):
    """Dados de telemetria."""
    timestamp: datetime
    session_id: str
    user_id: Optional[str] = None
    event_type: str
    event_data: Dict[str, Any]
    system_info: Dict[str, str]
    app_version: str
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class MetricCollector:
    """Coletor de métricas customizadas."""
    
    def __init__(self):
        self.metrics: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
        self.prometheus_metrics: Dict[str, Any] = {}
        self.registry = CollectorRegistry()
        
        # Métricas Prometheus padrão
        self._setup_prometheus_metrics()
    
    def _setup_prometheus_metrics(self):
        """Configura métricas Prometheus padrão."""
        self.prometheus_metrics.update({
            'http_requests_total': Counter(
                'http_requests_total',
                'Total HTTP requests',
                ['method', 'endpoint', 'status'],
                registry=self.registry
            ),
            'http_request_duration_seconds': Histogram(
                'http_request_duration_seconds',
                'HTTP request duration',
                ['method', 'endpoint'],
                registry=self.registry
            ),
            'system_cpu_percent': Gauge(
                'system_cpu_percent',
                'CPU usage percentage',
                registry=self.registry
            ),
            'system_memory_percent': Gauge(
                'system_memory_percent',
                'Memory usage percentage',
                registry=self.registry
            ),
            'system_disk_percent': Gauge(
                'system_disk_percent',
                'Disk usage percentage',
                registry=self.registry
            ),
            'application_errors_total': Counter(
                'application_errors_total',
                'Total application errors',
                ['type', 'module'],
                registry=self.registry
            ),
            'database_connections_active': Gauge(
                'database_connections_active',
                'Active database connections',
                registry=self.registry
            ),
            'cache_operations_total': Counter(
                'cache_operations_total',
                'Total cache operations',
                ['operation', 'result'],
                registry=self.registry
            ),
            'task_duration_seconds': Histogram(
                'task_duration_seconds',
                'Task execution duration',
                ['task_type', 'status'],
                registry=self.registry
            )
        })
    
    def record_metric(self, name: str, value: Union[float, int, str], labels: Dict[str, str] = None):
        """Registra métrica customizada."""
        metric_value = MetricValue(
            timestamp=datetime.now(timezone.utc),
            value=value,
            labels=labels or {}
        )
        
        self.metrics[name].append(metric_value)
    
    def increment_counter(self, name: str, labels: Dict[str, str] = None):
        """Incrementa contador Prometheus."""
        if name in self.prometheus_metrics:
            metric = self.prometheus_metrics[name]
            if hasattr(metric, 'labels'):
                metric.labels(**(labels or {})).inc()
            else:
                metric.inc()
    
    def set_gauge(self, name: str, value: float, labels: Dict[str, str] = None):
        """Define valor de gauge Prometheus."""
        if name in self.prometheus_metrics:
            metric = self.prometheus_metrics[name]
            if hasattr(metric, 'labels'):
                metric.labels(**(labels or {})).set(value)
            else:
                metric.set(value)
    
    def observe_histogram(self, name: str, value: float, labels: Dict[str, str] = None):
        """Observa valor em histograma Prometheus."""
        if name in self.prometheus_metrics:
            metric = self.prometheus_metrics[name]
            if hasattr(metric, 'labels'):
                metric.labels(**(labels or {})).observe(value)
            else:
                metric.observe(value)
    
    def get_metrics(self, name: str, since: Optional[datetime] = None) -> List[MetricValue]:
        """Obtém métricas por nome."""
        if name not in self.metrics:
            return []
        
        metrics = list(self.metrics[name])
        
        if since:
            metrics = [m for m in metrics if m.timestamp >= since]
        
        return metrics
    
    def get_prometheus_metrics(self) -> str:
        """Obtém métricas no formato Prometheus."""
        return generate_latest(self.registry).decode('utf-8')
    
    def clear_old_metrics(self, retention_seconds: int):
        """Remove métricas antigas."""
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=retention_seconds)
        
        for name, metric_deque in self.metrics.items():
            # Remove métricas antigas
            while metric_deque and metric_deque[0].timestamp < cutoff:
                metric_deque.popleft()


class AlertManager:
    """Gerenciador de alertas."""
    
    def __init__(self, config: ObservabilityConfig):
        self.config = config
        self.alerts: Dict[str, Alert] = {}
        self.alert_history: deque = deque(maxlen=1000)
        self.cooldowns: Dict[str, datetime] = {}
        self.alert_handlers: List[Callable[[Alert], None]] = []
    
    def add_alert_handler(self, handler: Callable[[Alert], None]):
        """Adiciona handler de alerta."""
        self.alert_handlers.append(handler)
    
    def check_threshold(
        self,
        metric_name: str,
        value: Union[float, int],
        threshold: Union[float, int],
        severity: AlertSeverity,
        title: str,
        message: str,
        labels: Dict[str, str] = None,
        comparison: str = "greater"
    ):
        """Verifica threshold e cria alerta se necessário."""
        if not self.config.alerts_enabled:
            return
        
        alert_key = f"{metric_name}_{severity.value}"
        
        # Verifica cooldown
        if alert_key in self.cooldowns:
            if datetime.now(timezone.utc) < self.cooldowns[alert_key]:
                return
        
        # Verifica condição
        triggered = False
        if comparison == "greater":
            triggered = value > threshold
        elif comparison == "less":
            triggered = value < threshold
        elif comparison == "equal":
            triggered = value == threshold
        
        if triggered:
            self._create_alert(
                metric_name, value, threshold, severity,
                title, message, labels or {}
            )
            
            # Define cooldown
            self.cooldowns[alert_key] = (
                datetime.now(timezone.utc) + 
                timedelta(seconds=self.config.alert_cooldown)
            )
        else:
            # Resolve alerta se existir
            self._resolve_alert(alert_key)
    
    def _create_alert(
        self,
        metric: str,
        value: Union[float, int, str],
        threshold: Union[float, int, str],
        severity: AlertSeverity,
        title: str,
        message: str,
        labels: Dict[str, str]
    ):
        """Cria novo alerta."""
        alert = Alert(
            id=str(uuid.uuid4()),
            timestamp=datetime.now(timezone.utc),
            severity=severity,
            title=title,
            message=message,
            metric=metric,
            value=value,
            threshold=threshold,
            labels=labels
        )
        
        alert_key = f"{metric}_{severity.value}"
        self.alerts[alert_key] = alert
        self.alert_history.append(alert)
        
        # Notifica handlers
        for handler in self.alert_handlers:
            try:
                handler(alert)
            except Exception as e:
                print(f"Erro no handler de alerta: {e}")
    
    def _resolve_alert(self, alert_key: str):
        """Resolve alerta."""
        if alert_key in self.alerts:
            alert = self.alerts[alert_key]
            alert.resolved = True
            alert.resolved_at = datetime.now(timezone.utc)
            del self.alerts[alert_key]
    
    def get_active_alerts(self) -> List[Alert]:
        """Obtém alertas ativos."""
        return list(self.alerts.values())
    
    def get_alert_history(self, limit: int = 100) -> List[Alert]:
        """Obtém histórico de alertas."""
        return list(self.alert_history)[-limit:]


class HealthChecker:
    """Verificador de saúde do sistema."""
    
    def __init__(self):
        self.checks: Dict[str, Callable[[], HealthCheck]] = {}
        self.last_results: Dict[str, HealthCheck] = {}
    
    def register_check(self, name: str, check_func: Callable[[], HealthCheck]):
        """Registra verificação de saúde."""
        self.checks[name] = check_func
    
    async def run_checks(self) -> Dict[str, HealthCheck]:
        """Executa todas as verificações."""
        results = {}
        
        for name, check_func in self.checks.items():
            try:
                start_time = time.time()
                
                if asyncio.iscoroutinefunction(check_func):
                    result = await check_func()
                else:
                    result = check_func()
                
                duration = (time.time() - start_time) * 1000
                result.duration_ms = duration
                
                results[name] = result
                self.last_results[name] = result
                
            except Exception as e:
                results[name] = HealthCheck(
                    name=name,
                    status=HealthStatus.CRITICAL,
                    timestamp=datetime.now(timezone.utc),
                    duration_ms=0,
                    message=f"Erro na verificação: {str(e)}"
                )
        
        return results
    
    def get_overall_status(self) -> HealthStatus:
        """Obtém status geral do sistema."""
        if not self.last_results:
            return HealthStatus.UNHEALTHY
        
        statuses = [check.status for check in self.last_results.values()]
        
        if HealthStatus.CRITICAL in statuses:
            return HealthStatus.CRITICAL
        elif HealthStatus.UNHEALTHY in statuses:
            return HealthStatus.UNHEALTHY
        elif HealthStatus.DEGRADED in statuses:
            return HealthStatus.DEGRADED
        else:
            return HealthStatus.HEALTHY


class SystemMonitor:
    """Monitor de recursos do sistema."""
    
    def __init__(self):
        self.process = psutil.Process()
        self.last_network_stats = psutil.net_io_counters()
        self.last_check_time = time.time()
    
    def get_system_metrics(self) -> SystemMetrics:
        """Obtém métricas do sistema."""
        # CPU
        cpu_percent = psutil.cpu_percent(interval=None)
        
        # Memória
        memory = psutil.virtual_memory()
        
        # Disco
        disk = psutil.disk_usage('/')
        
        # Rede
        network = psutil.net_io_counters()
        
        # Load average (apenas Unix)
        try:
            load_avg = list(os.getloadavg())
        except (OSError, AttributeError):
            load_avg = [0.0, 0.0, 0.0]
        
        # Processos
        process_count = len(psutil.pids())
        
        return SystemMetrics(
            timestamp=datetime.now(timezone.utc),
            cpu_percent=cpu_percent,
            memory_percent=memory.percent,
            memory_used_mb=memory.used / 1024 / 1024,
            memory_total_mb=memory.total / 1024 / 1024,
            disk_percent=disk.percent,
            disk_used_gb=disk.used / 1024 / 1024 / 1024,
            disk_total_gb=disk.total / 1024 / 1024 / 1024,
            network_bytes_sent=network.bytes_sent,
            network_bytes_recv=network.bytes_recv,
            load_average=load_avg,
            process_count=process_count
        )
    
    def get_process_metrics(self) -> Dict[str, Any]:
        """Obtém métricas do processo atual."""
        try:
            return {
                'pid': self.process.pid,
                'cpu_percent': self.process.cpu_percent(),
                'memory_percent': self.process.memory_percent(),
                'memory_rss_mb': self.process.memory_info().rss / 1024 / 1024,
                'memory_vms_mb': self.process.memory_info().vms / 1024 / 1024,
                'num_threads': self.process.num_threads(),
                'num_fds': self.process.num_fds() if hasattr(self.process, 'num_fds') else 0,
                'create_time': self.process.create_time(),
                'status': self.process.status()
            }
        except Exception as e:
            return {'error': str(e)}


class TelemetryCollector:
    """Coletor de telemetria."""
    
    def __init__(self, config: ObservabilityConfig):
        self.config = config
        self.session_id = str(uuid.uuid4())
        self.events: deque = deque(maxlen=1000)
        self.system_info = self._get_system_info()
    
    def _get_system_info(self) -> Dict[str, str]:
        """Obtém informações do sistema."""
        return {
            'platform': platform.platform(),
            'system': platform.system(),
            'release': platform.release(),
            'version': platform.version(),
            'machine': platform.machine(),
            'processor': platform.processor(),
            'python_version': platform.python_version(),
            'hostname': platform.node()
        }
    
    def track_event(
        self,
        event_type: str,
        event_data: Dict[str, Any],
        user_id: Optional[str] = None
    ):
        """Rastreia evento de telemetria."""
        if not self.config.telemetry_enabled:
            return
        
        telemetry_data = TelemetryData(
            timestamp=datetime.now(timezone.utc),
            session_id=self.session_id,
            user_id=user_id,
            event_type=event_type,
            event_data=event_data,
            system_info=self.system_info,
            app_version="1.0.0"  # TODO: Obter da configuração
        )
        
        self.events.append(telemetry_data)
    
    async def send_telemetry(self):
        """Envia dados de telemetria."""
        if not self.config.telemetry_enabled or not self.config.telemetry_endpoint:
            return
        
        if not self.events:
            return
        
        events_to_send = list(self.events)
        self.events.clear()
        
        try:
            async with aiohttp.ClientSession() as session:
                payload = {
                    'events': [event.dict() for event in events_to_send]
                }
                
                async with session.post(
                    self.config.telemetry_endpoint,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status >= 400:
                        print(f"Erro ao enviar telemetria: {response.status}")
                        
        except Exception as e:
            print(f"Erro ao enviar telemetria: {e}")
            # Recoloca eventos na fila em caso de erro
            self.events.extendleft(reversed(events_to_send))


class ObservabilityManager:
    """Gerenciador principal de observabilidade."""
    
    def __init__(self, config: ObservabilityConfig):
        self.config = config
        self.metric_collector = MetricCollector()
        self.alert_manager = AlertManager(config)
        self.health_checker = HealthChecker()
        self.system_monitor = SystemMonitor()
        self.telemetry_collector = TelemetryCollector(config)
        
        self._tasks: List[asyncio.Task] = []
        self._running = False
        
        # Registra verificações de saúde padrão
        self._register_default_health_checks()
        
        # Registra handlers de alerta padrão
        self._register_default_alert_handlers()
    
    def _register_default_health_checks(self):
        """Registra verificações de saúde padrão."""
        def database_check() -> HealthCheck:
            # TODO: Implementar verificação real do banco
            return HealthCheck(
                name="database",
                status=HealthStatus.HEALTHY,
                timestamp=datetime.now(timezone.utc),
                duration_ms=0,
                message="Banco de dados operacional"
            )
        
        def redis_check() -> HealthCheck:
            # TODO: Implementar verificação real do Redis
            return HealthCheck(
                name="redis",
                status=HealthStatus.HEALTHY,
                timestamp=datetime.now(timezone.utc),
                duration_ms=0,
                message="Redis operacional"
            )
        
        def disk_space_check() -> HealthCheck:
            disk = psutil.disk_usage('/')
            status = HealthStatus.HEALTHY
            
            if disk.percent > 95:
                status = HealthStatus.CRITICAL
            elif disk.percent > 90:
                status = HealthStatus.UNHEALTHY
            elif disk.percent > 80:
                status = HealthStatus.DEGRADED
            
            return HealthCheck(
                name="disk_space",
                status=status,
                timestamp=datetime.now(timezone.utc),
                duration_ms=0,
                message=f"Uso do disco: {disk.percent:.1f}%",
                details={'percent': disk.percent, 'free_gb': disk.free / 1024**3}
            )
        
        self.health_checker.register_check("database", database_check)
        self.health_checker.register_check("redis", redis_check)
        self.health_checker.register_check("disk_space", disk_space_check)
    
    def _register_default_alert_handlers(self):
        """Registra handlers de alerta padrão."""
        def log_alert(alert: Alert):
            print(f"[ALERT] {alert.severity.value.upper()}: {alert.title} - {alert.message}")
        
        self.alert_manager.add_alert_handler(log_alert)
    
    async def start(self):
        """Inicia sistema de observabilidade."""
        if self._running:
            return
        
        self._running = True
        
        # Cria diretório de dados
        data_dir = Path(self.config.data_dir)
        data_dir.mkdir(parents=True, exist_ok=True)
        
        # Inicia tarefas
        if self.config.metrics_enabled:
            self._tasks.append(
                asyncio.create_task(self._metrics_collection_loop())
            )
        
        if self.config.health_checks_enabled:
            self._tasks.append(
                asyncio.create_task(self._health_check_loop())
            )
        
        if self.config.telemetry_enabled:
            self._tasks.append(
                asyncio.create_task(self._telemetry_loop())
            )
        
        if self.config.export_enabled:
            self._tasks.append(
                asyncio.create_task(self._export_loop())
            )
        
        print("Sistema de observabilidade iniciado")
    
    async def stop(self):
        """Para sistema de observabilidade."""
        if not self._running:
            return
        
        self._running = False
        
        # Cancela tarefas
        for task in self._tasks:
            task.cancel()
        
        # Aguarda cancelamento
        await asyncio.gather(*self._tasks, return_exceptions=True)
        
        self._tasks.clear()
        
        print("Sistema de observabilidade parado")
    
    async def _metrics_collection_loop(self):
        """Loop de coleta de métricas."""
        while self._running:
            try:
                # Coleta métricas do sistema
                if self.config.system_monitoring_enabled:
                    system_metrics = self.system_monitor.get_system_metrics()
                    
                    # Atualiza métricas Prometheus
                    self.metric_collector.set_gauge('system_cpu_percent', system_metrics.cpu_percent)
                    self.metric_collector.set_gauge('system_memory_percent', system_metrics.memory_percent)
                    self.metric_collector.set_gauge('system_disk_percent', system_metrics.disk_percent)
                    
                    # Verifica thresholds para alertas
                    self.alert_manager.check_threshold(
                        'cpu_usage', system_metrics.cpu_percent, self.config.cpu_threshold,
                        AlertSeverity.HIGH, 'Alto uso de CPU',
                        f'CPU em {system_metrics.cpu_percent:.1f}%'
                    )
                    
                    self.alert_manager.check_threshold(
                        'memory_usage', system_metrics.memory_percent, self.config.memory_threshold,
                        AlertSeverity.HIGH, 'Alto uso de memória',
                        f'Memória em {system_metrics.memory_percent:.1f}%'
                    )
                    
                    self.alert_manager.check_threshold(
                        'disk_usage', system_metrics.disk_percent, self.config.disk_threshold,
                        AlertSeverity.CRITICAL, 'Alto uso de disco',
                        f'Disco em {system_metrics.disk_percent:.1f}%'
                    )
                
                # Limpa métricas antigas
                self.metric_collector.clear_old_metrics(self.config.metrics_retention)
                
                await asyncio.sleep(self.config.metrics_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Erro na coleta de métricas: {e}")
                await asyncio.sleep(self.config.metrics_interval)
    
    async def _health_check_loop(self):
        """Loop de verificações de saúde."""
        while self._running:
            try:
                await self.health_checker.run_checks()
                await asyncio.sleep(self.config.health_check_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Erro nas verificações de saúde: {e}")
                await asyncio.sleep(self.config.health_check_interval)
    
    async def _telemetry_loop(self):
        """Loop de envio de telemetria."""
        while self._running:
            try:
                await self.telemetry_collector.send_telemetry()
                await asyncio.sleep(self.config.telemetry_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Erro no envio de telemetria: {e}")
                await asyncio.sleep(self.config.telemetry_interval)
    
    async def _export_loop(self):
        """Loop de exportação de dados."""
        while self._running:
            try:
                await self._export_data()
                await asyncio.sleep(self.config.export_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Erro na exportação: {e}")
                await asyncio.sleep(self.config.export_interval)
    
    async def _export_data(self):
        """Exporta dados para arquivos."""
        timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
        data_dir = Path(self.config.data_dir)
        
        # Exporta métricas
        metrics_file = data_dir / f"metrics_{timestamp}.json"
        metrics_data = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'system_metrics': self.system_monitor.get_system_metrics().dict(),
            'process_metrics': self.system_monitor.get_process_metrics(),
            'alerts': [alert.dict() for alert in self.alert_manager.get_active_alerts()],
            'health_checks': {name: check.dict() for name, check in self.health_checker.last_results.items()}
        }
        
        async with aiofiles.open(metrics_file, 'w') as f:
            await f.write(json.dumps(metrics_data, indent=2, default=str))
    
    # Métodos públicos para interação
    
    def record_metric(self, name: str, value: Union[float, int, str], labels: Dict[str, str] = None):
        """Registra métrica customizada."""
        self.metric_collector.record_metric(name, value, labels)
    
    def increment_counter(self, name: str, labels: Dict[str, str] = None):
        """Incrementa contador."""
        self.metric_collector.increment_counter(name, labels)
    
    def set_gauge(self, name: str, value: float, labels: Dict[str, str] = None):
        """Define valor de gauge."""
        self.metric_collector.set_gauge(name, value, labels)
    
    def observe_histogram(self, name: str, value: float, labels: Dict[str, str] = None):
        """Observa valor em histograma."""
        self.metric_collector.observe_histogram(name, value, labels)
    
    def track_event(self, event_type: str, event_data: Dict[str, Any], user_id: Optional[str] = None):
        """Rastreia evento de telemetria."""
        self.telemetry_collector.track_event(event_type, event_data, user_id)
    
    def get_dashboard_data(self) -> Dict[str, Any]:
        """Obtém dados para dashboard."""
        return {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'system_metrics': self.system_monitor.get_system_metrics().dict(),
            'process_metrics': self.system_monitor.get_process_metrics(),
            'health_status': self.health_checker.get_overall_status().value,
            'health_checks': {name: check.dict() for name, check in self.health_checker.last_results.items()},
            'active_alerts': [alert.dict() for alert in self.alert_manager.get_active_alerts()],
            'alert_history': [alert.dict() for alert in self.alert_manager.get_alert_history(10)]
        }
    
    def get_prometheus_metrics(self) -> str:
        """Obtém métricas no formato Prometheus."""
        return self.metric_collector.get_prometheus_metrics()


# Instância global
observability_manager: Optional[ObservabilityManager] = None


def get_observability_manager() -> ObservabilityManager:
    """Obtém instância global do gerenciador de observabilidade."""
    global observability_manager
    if observability_manager is None:
        config = ObservabilityConfig()
        observability_manager = ObservabilityManager(config)
    
    return observability_manager


# Decoradores para instrumentação automática
def monitor_performance(metric_name: str = None):
    """Decorador para monitorar performance de funções."""
    def decorator(func):
        name = metric_name or f"{func.__module__}.{func.__name__}"
        manager = get_observability_manager()
        
        async def async_wrapper(*args, **kwargs):
            start_time = time.time()
            
            try:
                result = await func(*args, **kwargs)
                duration = (time.time() - start_time) * 1000
                
                manager.observe_histogram(
                    'task_duration_seconds',
                    duration / 1000,
                    {'task_type': name, 'status': 'success'}
                )
                
                return result
                
            except Exception as e:
                duration = (time.time() - start_time) * 1000
                
                manager.observe_histogram(
                    'task_duration_seconds',
                    duration / 1000,
                    {'task_type': name, 'status': 'error'}
                )
                
                manager.increment_counter(
                    'application_errors_total',
                    {'type': type(e).__name__, 'module': func.__module__}
                )
                
                raise
        
        def sync_wrapper(*args, **kwargs):
            start_time = time.time()
            
            try:
                result = func(*args, **kwargs)
                duration = (time.time() - start_time) * 1000
                
                manager.observe_histogram(
                    'task_duration_seconds',
                    duration / 1000,
                    {'task_type': name, 'status': 'success'}
                )
                
                return result
                
            except Exception as e:
                duration = (time.time() - start_time) * 1000
                
                manager.observe_histogram(
                    'task_duration_seconds',
                    duration / 1000,
                    {'task_type': name, 'status': 'error'}
                )
                
                manager.increment_counter(
                    'application_errors_total',
                    {'type': type(e).__name__, 'module': func.__module__}
                )
                
                raise
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


def track_usage(event_type: str = None):
    """Decorador para rastrear uso de funções."""
    def decorator(func):
        event_name = event_type or f"{func.__module__}.{func.__name__}"
        manager = get_observability_manager()
        
        async def async_wrapper(*args, **kwargs):
            manager.track_event(event_name, {
                'function': func.__name__,
                'module': func.__module__,
                'args_count': len(args),
                'kwargs_count': len(kwargs)
            })
            
            return await func(*args, **kwargs)
        
        def sync_wrapper(*args, **kwargs):
            manager.track_event(event_name, {
                'function': func.__name__,
                'module': func.__module__,
                'args_count': len(args),
                'kwargs_count': len(kwargs)
            })
            
            return func(*args, **kwargs)
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator