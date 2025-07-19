"""Schemas para tarefas assíncronas e resultados.

Define estruturas de dados para validação e serialização
de operações relacionadas a tarefas, resultados e monitoramento.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import Field, field_validator, computed_field

from app.schemas.base import BaseEntitySchema, BaseSchema, FilterParams, PaginationParams, SortParams


class TaskStatus(str, Enum):
    """Status de uma tarefa."""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILURE = "failure"
    RETRY = "retry"
    REVOKED = "revoked"
    CANCELLED = "cancelled"


class TaskPriority(str, Enum):
    """Prioridade de uma tarefa."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class TaskType(str, Enum):
    """Tipos de tarefas disponíveis."""
    # Importação e verificação
    ROM_IMPORT = "rom_import"
    ROM_VERIFY = "rom_verify"
    ROM_SCAN = "rom_scan"
    DAT_IMPORT = "dat_import"
    
    # Metadados e scraping
    METADATA_FETCH = "metadata_fetch"
    SCREENSHOT_DOWNLOAD = "screenshot_download"
    GAME_INFO_SCRAPE = "game_info_scrape"
    
    # Manutenção e limpeza
    DATABASE_CLEANUP = "database_cleanup"
    FILE_CLEANUP = "file_cleanup"
    CACHE_CLEANUP = "cache_cleanup"
    
    # Backup e exportação
    DATABASE_BACKUP = "database_backup"
    DATA_EXPORT = "data_export"
    
    # Sistema
    SYSTEM_HEALTH_CHECK = "system_health_check"
    INDEX_REBUILD = "index_rebuild"
    
    # Genérico
    CUSTOM = "custom"


class TaskResultType(str, Enum):
    """Tipos de resultados de tarefa."""
    COUNTER = "counter"
    PERCENTAGE = "percentage"
    SIZE = "size"
    DURATION = "duration"
    STATUS = "status"
    MESSAGE = "message"
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"
    FILE_PATH = "file_path"
    URL = "url"
    JSON_DATA = "json_data"


class TaskBase(BaseSchema):
    """Schema base para tarefas."""
    
    name: str = Field(
        min_length=1,
        max_length=255,
        description="Nome da tarefa",
        examples=["Importar ROMs do NES", "Verificar ROMs duplicadas"]
    )
    
    task_type: TaskType = Field(
        description="Tipo da tarefa"
    )
    
    description: Optional[str] = Field(
        default=None,
        max_length=1000,
        description="Descrição detalhada da tarefa"
    )
    
    priority: TaskPriority = Field(
        default=TaskPriority.NORMAL,
        description="Prioridade da tarefa"
    )
    
    parameters: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Parâmetros específicos da tarefa"
    )
    
    # Configurações de retry
    max_retries: int = Field(
        default=3,
        ge=0,
        le=10,
        description="Número máximo de tentativas"
    )
    
    retry_delay_seconds: int = Field(
        default=60,
        ge=0,
        le=3600,
        description="Delay entre tentativas em segundos"
    )
    
    # Timeout
    timeout_seconds: Optional[int] = Field(
        default=None,
        ge=1,
        le=86400,  # 24 horas
        description="Timeout da tarefa em segundos"
    )


class TaskCreate(TaskBase):
    """Schema para criação de tarefa."""
    
    user_id: Optional[UUID] = Field(
        default=None,
        description="ID do usuário que criou a tarefa"
    )
    
    scheduled_for: Optional[datetime] = Field(
        default=None,
        description="Data/hora para execução agendada"
    )
    
    depends_on: Optional[List[UUID]] = Field(
        default=None,
        description="IDs de tarefas das quais esta depende"
    )


class TaskUpdate(BaseSchema):
    """Schema para atualização de tarefa."""
    
    name: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=255,
        description="Nome da tarefa"
    )
    
    description: Optional[str] = Field(
        default=None,
        max_length=1000,
        description="Descrição da tarefa"
    )
    
    priority: Optional[TaskPriority] = Field(
        default=None,
        description="Prioridade da tarefa"
    )
    
    status: Optional[TaskStatus] = Field(
        default=None,
        description="Status da tarefa"
    )
    
    progress_percentage: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=100.0,
        description="Progresso em porcentagem"
    )
    
    progress_message: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Mensagem de progresso"
    )
    
    error_message: Optional[str] = Field(
        default=None,
        max_length=2000,
        description="Mensagem de erro"
    )
    
    result_data: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Dados do resultado"
    )


class TaskResponse(TaskBase, BaseEntitySchema):
    """Schema para resposta de tarefa."""
    
    celery_id: Optional[str] = Field(
        default=None,
        description="ID da tarefa no Celery"
    )
    
    user_id: Optional[UUID] = Field(
        default=None,
        description="ID do usuário que criou a tarefa"
    )
    
    user_name: Optional[str] = Field(
        default=None,
        description="Nome do usuário"
    )
    
    status: TaskStatus = Field(
        description="Status atual da tarefa"
    )
    
    # Progresso
    progress_percentage: float = Field(
        default=0.0,
        ge=0.0,
        le=100.0,
        description="Progresso em porcentagem"
    )
    
    progress_message: Optional[str] = Field(
        default=None,
        description="Mensagem de progresso atual"
    )
    
    # Timestamps
    scheduled_for: Optional[datetime] = Field(
        default=None,
        description="Data/hora agendada para execução"
    )
    
    started_at: Optional[datetime] = Field(
        default=None,
        description="Data/hora de início"
    )
    
    completed_at: Optional[datetime] = Field(
        default=None,
        description="Data/hora de conclusão"
    )
    
    # Resultados e erros
    result_data: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Dados do resultado"
    )
    
    error_message: Optional[str] = Field(
        default=None,
        description="Mensagem de erro"
    )
    
    error_traceback: Optional[str] = Field(
        default=None,
        description="Stack trace do erro"
    )
    
    # Retry
    retry_count: int = Field(
        default=0,
        ge=0,
        description="Número de tentativas realizadas"
    )
    
    next_retry_at: Optional[datetime] = Field(
        default=None,
        description="Data/hora da próxima tentativa"
    )
    
    # Relacionamentos
    results: List["TaskResultResponse"] = Field(
        default_factory=list,
        description="Resultados detalhados da tarefa"
    )
    
    @computed_field
    @property
    def is_completed(self) -> bool:
        """Se a tarefa foi concluída (sucesso ou falha)."""
        return self.status in [TaskStatus.SUCCESS, TaskStatus.FAILURE, TaskStatus.CANCELLED]
    
    @computed_field
    @property
    def is_running(self) -> bool:
        """Se a tarefa está em execução."""
        return self.status in [TaskStatus.RUNNING, TaskStatus.RETRY]
    
    @computed_field
    @property
    def duration_seconds(self) -> Optional[int]:
        """Duração da execução em segundos."""
        if self.started_at and self.completed_at:
            return int((self.completed_at - self.started_at).total_seconds())
        return None
    
    @computed_field
    @property
    def can_retry(self) -> bool:
        """Se a tarefa pode ser reexecutada."""
        return (
            self.status == TaskStatus.FAILURE and
            self.retry_count < self.max_retries
        )


class TaskResultBase(BaseSchema):
    """Schema base para resultados de tarefa."""
    
    result_type: TaskResultType = Field(
        description="Tipo do resultado"
    )
    
    category: str = Field(
        min_length=1,
        max_length=100,
        description="Categoria do resultado",
        examples=["import", "verification", "cleanup", "performance"]
    )
    
    name: str = Field(
        min_length=1,
        max_length=255,
        description="Nome do resultado",
        examples=["files_processed", "errors_found", "execution_time"]
    )
    
    # Valores de diferentes tipos
    text_value: Optional[str] = Field(
        default=None,
        max_length=1000,
        description="Valor textual"
    )
    
    numeric_value: Optional[float] = Field(
        default=None,
        description="Valor numérico"
    )
    
    json_value: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Valor JSON complexo"
    )
    
    # Metadados
    unit: Optional[str] = Field(
        default=None,
        max_length=50,
        description="Unidade de medida",
        examples=["files", "MB", "seconds", "%"]
    )
    
    description: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Descrição do resultado"
    )


class TaskResultCreate(TaskResultBase):
    """Schema para criação de resultado de tarefa."""
    
    task_id: UUID = Field(
        description="ID da tarefa à qual o resultado pertence"
    )


class TaskResultUpdate(BaseSchema):
    """Schema para atualização de resultado de tarefa."""
    
    text_value: Optional[str] = Field(
        default=None,
        max_length=1000,
        description="Valor textual"
    )
    
    numeric_value: Optional[float] = Field(
        default=None,
        description="Valor numérico"
    )
    
    json_value: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Valor JSON complexo"
    )
    
    description: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Descrição do resultado"
    )


class TaskResultResponse(TaskResultBase, BaseEntitySchema):
    """Schema para resposta de resultado de tarefa."""
    
    task_id: UUID = Field(
        description="ID da tarefa à qual o resultado pertence"
    )
    
    @computed_field
    @property
    def display_value(self) -> str:
        """Valor formatado para exibição."""
        if self.text_value:
            return self.text_value
        elif self.numeric_value is not None:
            if self.unit:
                return f"{self.numeric_value} {self.unit}"
            return str(self.numeric_value)
        elif self.json_value:
            return str(self.json_value)
        return "N/A"


class TaskFilterParams(FilterParams):
    """Parâmetros de filtro específicos para tarefas."""
    
    user_id: Optional[UUID] = Field(
        default=None,
        description="Filtrar por usuário"
    )
    
    task_type: Optional[List[TaskType]] = Field(
        default=None,
        description="Filtrar por tipo de tarefa"
    )
    
    status: Optional[List[TaskStatus]] = Field(
        default=None,
        description="Filtrar por status"
    )
    
    priority: Optional[List[TaskPriority]] = Field(
        default=None,
        description="Filtrar por prioridade"
    )
    
    created_after: Optional[datetime] = Field(
        default=None,
        description="Criadas após esta data"
    )
    
    created_before: Optional[datetime] = Field(
        default=None,
        description="Criadas antes desta data"
    )
    
    completed_after: Optional[datetime] = Field(
        default=None,
        description="Completadas após esta data"
    )
    
    completed_before: Optional[datetime] = Field(
        default=None,
        description="Completadas antes desta data"
    )
    
    has_errors: Optional[bool] = Field(
        default=None,
        description="Apenas tarefas com erros"
    )
    
    is_running: Optional[bool] = Field(
        default=None,
        description="Apenas tarefas em execução"
    )
    
    can_retry: Optional[bool] = Field(
        default=None,
        description="Apenas tarefas que podem ser reexecutadas"
    )


class TaskSearchRequest(BaseSchema):
    """Request para busca de tarefas."""
    
    pagination: PaginationParams = Field(
        default_factory=PaginationParams,
        description="Parâmetros de paginação"
    )
    
    sorting: SortParams = Field(
        default_factory=SortParams,
        description="Parâmetros de ordenação"
    )
    
    filters: TaskFilterParams = Field(
        default_factory=TaskFilterParams,
        description="Filtros de busca"
    )
    
    name_search: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=255,
        description="Busca por nome da tarefa"
    )


class TaskStatsResponse(BaseSchema):
    """Schema para estatísticas de tarefas."""
    
    total_tasks: int = Field(
        ge=0,
        description="Total de tarefas"
    )
    
    pending_tasks: int = Field(
        ge=0,
        description="Tarefas pendentes"
    )
    
    running_tasks: int = Field(
        ge=0,
        description="Tarefas em execução"
    )
    
    completed_tasks: int = Field(
        ge=0,
        description="Tarefas concluídas"
    )
    
    failed_tasks: int = Field(
        ge=0,
        description="Tarefas falhadas"
    )
    
    success_rate: float = Field(
        ge=0.0,
        le=100.0,
        description="Taxa de sucesso em porcentagem"
    )
    
    average_duration_seconds: Optional[float] = Field(
        default=None,
        description="Duração média em segundos"
    )
    
    by_type: Dict[TaskType, int] = Field(
        default_factory=dict,
        description="Tarefas por tipo"
    )
    
    by_status: Dict[TaskStatus, int] = Field(
        default_factory=dict,
        description="Tarefas por status"
    )
    
    by_priority: Dict[TaskPriority, int] = Field(
        default_factory=dict,
        description="Tarefas por prioridade"
    )
    
    recent_errors: List[str] = Field(
        default_factory=list,
        description="Erros recentes"
    )


class TaskProgressUpdate(BaseSchema):
    """Schema para atualização de progresso de tarefa."""
    
    progress_percentage: float = Field(
        ge=0.0,
        le=100.0,
        description="Progresso em porcentagem"
    )
    
    progress_message: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Mensagem de progresso"
    )
    
    current_step: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Etapa atual"
    )
    
    total_steps: Optional[int] = Field(
        default=None,
        ge=1,
        description="Total de etapas"
    )
    
    current_step_number: Optional[int] = Field(
        default=None,
        ge=1,
        description="Número da etapa atual"
    )
    
    @field_validator('current_step_number')
    @classmethod
    def validate_current_step_number(cls, v: Optional[int], info) -> Optional[int]:
        """Valida que current_step_number <= total_steps."""
        if v is not None and 'total_steps' in info.data:
            total_steps = info.data['total_steps']
            if total_steps is not None and v > total_steps:
                raise ValueError('Número da etapa atual deve ser <= total de etapas')
        return v


class TaskRetryRequest(BaseSchema):
    """Request para reexecutar uma tarefa."""
    
    reset_retry_count: bool = Field(
        default=False,
        description="Resetar contador de tentativas"
    )
    
    new_parameters: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Novos parâmetros para a tarefa"
    )
    
    priority: Optional[TaskPriority] = Field(
        default=None,
        description="Nova prioridade"
    )


class TaskCancelRequest(BaseSchema):
    """Request para cancelar uma tarefa."""
    
    reason: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Motivo do cancelamento"
    )
    
    force: bool = Field(
        default=False,
        description="Forçar cancelamento mesmo se em execução"
    )


class TaskBulkOperation(BaseSchema):
    """Schema para operações em lote com tarefas."""
    
    task_ids: List[UUID] = Field(
        min_length=1,
        description="IDs das tarefas para operação"
    )
    
    operation: str = Field(
        description="Tipo de operação",
        examples=["cancel", "retry", "delete", "change_priority"]
    )
    
    parameters: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Parâmetros específicos da operação"
    )


class TaskQueueInfo(BaseSchema):
    """Informações sobre a fila de tarefas."""
    
    queue_name: str = Field(
        description="Nome da fila"
    )
    
    pending_tasks: int = Field(
        ge=0,
        description="Tarefas pendentes na fila"
    )
    
    active_tasks: int = Field(
        ge=0,
        description="Tarefas ativas na fila"
    )
    
    scheduled_tasks: int = Field(
        ge=0,
        description="Tarefas agendadas na fila"
    )
    
    failed_tasks: int = Field(
        ge=0,
        description="Tarefas falhadas na fila"
    )
    
    workers_online: int = Field(
        ge=0,
        description="Workers online para esta fila"
    )
    
    estimated_wait_time_seconds: Optional[int] = Field(
        default=None,
        description="Tempo estimado de espera em segundos"
    )


class TaskSystemStatus(BaseSchema):
    """Status do sistema de tarefas."""
    
    total_workers: int = Field(
        ge=0,
        description="Total de workers"
    )
    
    active_workers: int = Field(
        ge=0,
        description="Workers ativos"
    )
    
    queues: List[TaskQueueInfo] = Field(
        default_factory=list,
        description="Informações das filas"
    )
    
    broker_status: str = Field(
        description="Status do broker (Redis)"
    )
    
    result_backend_status: str = Field(
        description="Status do backend de resultados"
    )
    
    last_heartbeat: Optional[datetime] = Field(
        default=None,
        description="Último heartbeat do sistema"
    )

# Rebuild models para resolver referências forward
TaskResponse.model_rebuild()
TaskResultResponse.model_rebuild()