"""Modelos para gerenciamento de tarefas assíncronas.

Define entidades para tarefas em background como importação de DATs,
verificação de ROMs, web scraping e outras operações longas.
"""

from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum as SQLEnum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    Index,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import BaseModel


class TaskStatus(str, Enum):
    """Status de execução da tarefa."""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILURE = "failure"
    CANCELLED = "cancelled"
    RETRY = "retry"
    REVOKED = "revoked"


class TaskPriority(str, Enum):
    """Prioridade da tarefa."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class TaskType(str, Enum):
    """Tipos de tarefas disponíveis."""
    # Importação e processamento
    IMPORT_DAT = "import_dat"
    IMPORT_XML = "import_xml"
    SCAN_ROMS = "scan_roms"
    VERIFY_ROMS = "verify_roms"
    
    # Web scraping
    SCRAPE_GAME_INFO = "scrape_game_info"
    SCRAPE_SCREENSHOTS = "scrape_screenshots"
    SCRAPE_METADATA = "scrape_metadata"
    
    # Manutenção
    CLEANUP_FILES = "cleanup_files"
    BACKUP_DATABASE = "backup_database"
    OPTIMIZE_DATABASE = "optimize_database"
    
    # Processamento de imagens
    GENERATE_THUMBNAILS = "generate_thumbnails"
    COMPRESS_IMAGES = "compress_images"
    
    # Relatórios
    GENERATE_REPORT = "generate_report"
    EXPORT_DATA = "export_data"


class Task(BaseModel):
    """Modelo principal para tarefas assíncronas.
    
    Representa uma tarefa que pode ser executada em background
    pelo sistema de filas (Celery).
    """
    
    __tablename__ = "tasks"
    
    # Informações básicas da tarefa
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
        doc="Nome descritivo da tarefa"
    )
    
    task_type: Mapped[TaskType] = mapped_column(
        SQLEnum(TaskType),
        nullable=False,
        index=True,
        doc="Tipo da tarefa"
    )
    
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        doc="Descrição detalhada da tarefa"
    )
    
    # Identificação externa (Celery)
    celery_task_id: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        unique=True,
        index=True,
        doc="ID da tarefa no Celery"
    )
    
    # Status e prioridade
    status: Mapped[TaskStatus] = mapped_column(
        SQLEnum(TaskStatus),
        nullable=False,
        default=TaskStatus.PENDING,
        index=True,
        doc="Status atual da tarefa"
    )
    
    priority: Mapped[TaskPriority] = mapped_column(
        SQLEnum(TaskPriority),
        nullable=False,
        default=TaskPriority.NORMAL,
        index=True,
        doc="Prioridade de execução"
    )
    
    # Parâmetros e configuração
    parameters: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="{}",
        doc="Parâmetros de entrada da tarefa"
    )

    options: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="{}",
        doc="Opções de configuração da tarefa"
    )
    
    # Progresso e timing
    progress_current: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        doc="Progresso atual (0-100)"
    )
    
    progress_total: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=100,
        doc="Total para cálculo de progresso"
    )
    
    progress_message: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        doc="Mensagem de progresso atual"
    )
    
    # Timestamps de execução
    scheduled_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
        doc="Data/hora agendada para execução"
    )
    
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
        doc="Data/hora de início da execução"
    )
    
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
        doc="Data/hora de conclusão"
    )
    
    # Resultados e erros
    result: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        doc="Resultado da execução da tarefa"
    )
    
    error_message: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        doc="Mensagem de erro se a tarefa falhou"
    )
    
    error_traceback: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        doc="Stack trace do erro"
    )
    
    # Retry e timeout
    retry_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        doc="Número de tentativas realizadas"
    )
    
    max_retries: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=3,
        doc="Número máximo de tentativas"
    )
    
    timeout_seconds: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        doc="Timeout em segundos"
    )
    
    # Relacionamento com usuário
    created_by: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        doc="Usuário que criou a tarefa"
    )
    
    # Relacionamentos
    user: Mapped[Optional["User"]] = relationship(
        "User",
        back_populates="tasks"
    )
    
    task_results: Mapped[list["TaskResult"]] = relationship(
        "TaskResult",
        back_populates="task",
        cascade="all, delete-orphan"
    )
    
    # Índices compostos
    __table_args__ = (
        Index('ix_task_status_priority', 'status', 'priority'),
        Index('ix_task_type_status', 'task_type', 'status'),
        Index('ix_task_scheduled', 'scheduled_at', 'status'),
        Index('ix_task_execution_time', 'started_at', 'completed_at'),
    )
    
    def __repr__(self) -> str:
        return f"<Task(name='{self.name}', type='{self.task_type.value}', status='{self.status.value}')>"
    
    @property
    def progress_percentage(self) -> float:
        """Calcula a porcentagem de progresso."""
        if self.progress_total == 0:
            return 0.0
        return min(100.0, (self.progress_current / self.progress_total) * 100)
    
    @property
    def duration(self) -> Optional[float]:
        """Calcula a duração da execução em segundos."""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None
    
    @property
    def is_running(self) -> bool:
        """Verifica se a tarefa está em execução."""
        return self.status == TaskStatus.RUNNING
    
    @property
    def is_completed(self) -> bool:
        """Verifica se a tarefa foi concluída (sucesso ou falha)."""
        return self.status in [TaskStatus.SUCCESS, TaskStatus.FAILURE, TaskStatus.CANCELLED]
    
    @property
    def can_retry(self) -> bool:
        """Verifica se a tarefa pode ser reexecutada."""
        return (
            self.status == TaskStatus.FAILURE and
            self.retry_count < self.max_retries
        )
    
    def start_execution(self) -> None:
        """Marca o início da execução."""
        self.status = TaskStatus.RUNNING
        self.started_at = datetime.utcnow()
        self.progress_current = 0
        self.progress_message = "Iniciando execução..."
    
    def complete_success(self, result: dict = None) -> None:
        """Marca a tarefa como concluída com sucesso."""
        self.status = TaskStatus.SUCCESS
        self.completed_at = datetime.utcnow()
        self.progress_current = self.progress_total
        self.progress_message = "Concluída com sucesso"
        if result:
            self.result = result
    
    def complete_failure(self, error_message: str, traceback: str = None) -> None:
        """Marca a tarefa como falhada."""
        self.status = TaskStatus.FAILURE
        self.completed_at = datetime.utcnow()
        self.error_message = error_message
        if traceback:
            self.error_traceback = traceback
        self.progress_message = f"Falha: {error_message}"
    
    def cancel(self) -> None:
        """Cancela a tarefa."""
        self.status = TaskStatus.CANCELLED
        self.completed_at = datetime.utcnow()
        self.progress_message = "Tarefa cancelada"
    
    def update_progress(self, current: int, message: str = None) -> None:
        """Atualiza o progresso da tarefa."""
        self.progress_current = min(current, self.progress_total)
        if message:
            self.progress_message = message
    
    def increment_retry(self) -> None:
        """Incrementa o contador de tentativas."""
        self.retry_count += 1
        self.status = TaskStatus.RETRY
        self.started_at = None
        self.completed_at = None
        self.error_message = None
        self.error_traceback = None


class TaskResult(BaseModel):
    """Modelo para resultados detalhados de tarefas.
    
    Armazena resultados específicos e métricas de execução
    para análise e auditoria.
    """
    
    __tablename__ = "task_results"
    
    # Relacionamento com tarefa
    task_id: Mapped[UUID] = mapped_column(
        ForeignKey("tasks.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    # Tipo e categoria do resultado
    result_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        doc="Tipo do resultado (summary, detail, metric, etc.)"
    )
    
    category: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        index=True,
        doc="Categoria do resultado"
    )
    
    # Dados do resultado
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        doc="Nome do resultado"
    )
    
    value: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        doc="Valor do resultado em texto"
    )
    
    numeric_value: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        doc="Valor numérico do resultado"
    )
    
    json_value: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        doc="Valor complexo em JSON"
    )
    
    # Metadados
    unit: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        doc="Unidade de medida (segundos, bytes, etc.)"
    )
    
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        doc="Descrição do resultado"
    )
    
    # Configurações
    is_public: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        doc="Se o resultado é público"
    )
    
    sort_order: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        doc="Ordem de exibição"
    )
    
    # Relacionamentos
    task: Mapped[Task] = relationship(
        "Task",
        back_populates="task_results"
    )
    
    # Índices
    __table_args__ = (
        Index('ix_task_result_type_category', 'result_type', 'category'),
        Index('ix_task_result_numeric', 'numeric_value'),
    )
    
    def __repr__(self) -> str:
        return f"<TaskResult(name='{self.name}', type='{self.result_type}')>"
    
    @property
    def display_value(self) -> str:
        """Retorna o valor formatado para exibição."""
        if self.numeric_value is not None:
            if self.unit:
                return f"{self.numeric_value} {self.unit}"
            return str(self.numeric_value)
        return self.value or "N/A"