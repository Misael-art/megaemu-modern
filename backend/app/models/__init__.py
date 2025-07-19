"""Modelos SQLAlchemy para o banco de dados.

Este módulo organiza todos os modelos SQLAlchemy usados para
definir a estrutura do banco de dados e relacionamentos.
"""

# Modelos base
from .base import TimestampMixin, UUIDMixin
from app.core.database import Base

# Modelos de usuário
from .user import (
    User,
    UserPreferences,
    UserRole,
    UserStatus,
)

# Modelos de sistema
from .system import (
    System,
    SystemEmulator,
    SystemMetadata,
)

# Modelos de jogos
from .game import (
    Game,
    GameGenre,
    GameMetadata,
    GameScreenshot,
    GameStatus,
    game_genre_association,
)

# Modelos de ROMs
from .rom import (
    CompressionType,
    ROM,
    ROMFile,
    ROMStatus,
    ROMVerification,
    VerificationSource,
    VerificationType,
)

# Modelos de tarefas
from .task import (
    Task,
    TaskPriority,
    TaskResult,
    TaskStatus,
    TaskType,
)

__all__ = [
    # Base
    "Base",
    "TimestampMixin",
    "UUIDMixin",
    # User
    "User",
    "UserPreferences",
    "UserRole",
    "UserStatus",
    # System
    "System",
    "SystemEmulator",
    "SystemMetadata",
    # Game
    "Game",
    "GameGenre",
    "GameMetadata",
    "GameScreenshot",
    "GameStatus",
    "game_genre_association",
    # ROM
    "ROM",
    "ROMFile",
    "ROMVerification",
    "ROMStatus",
    "CompressionType",
    "VerificationType",
    "VerificationSource",
    # Task
    "Task",
    "TaskResult",
    "TaskStatus",
    "TaskPriority",
    "TaskType",
]