"""Serviços de negócio do MegaEmu Modern.

Este módulo organiza todos os serviços que implementam a lógica de negócio
do sistema, incluindo operações CRUD, validações e processamento de dados.
"""

# Serviços base
from app.services.base import BaseService

# Serviços de usuário
from app.services.user import (
    AuthService,
    UserPreferencesService,
    UserService,
)

# Serviços de sistema
from app.services.system import (
    SystemEmulatorService,
    SystemMetadataService,
    SystemService,
)

# Serviços de jogos
from app.services.game import (
    GameGenreService,
    GameMetadataService,
    GameScreenshotService,
    GameService,
)

# Serviços de ROMs
from app.services.rom import (
    ROMFileService,
    ROMService,
    ROMVerificationService,
)

# Serviços de tarefas
from app.services.task import (
    TaskService,
)

# Serviços de importação e processamento
from app.services.processing import ImportService, VerificationService, FileService, MetadataService

__all__ = [
    # Base
    "BaseService",
    # User
    "UserService",
    "AuthService",
    "UserPreferencesService",
    # System
    "SystemService",
    "SystemEmulatorService",
    "SystemMetadataService",
    # Game
    "GameService",
    "GameGenreService",
    "GameScreenshotService",
    "GameMetadataService",
    # ROM
    "ROMService",
    "ROMFileService",
    "ROMVerificationService",
    # Task
    "TaskService",
    # Processing
    "ImportService",
    "VerificationService",
    "FileService",
    "MetadataService",
]