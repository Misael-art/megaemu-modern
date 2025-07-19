"""Tarefas assíncronas do Celery para o MegaEmu.

Este pacote contém todas as tarefas que podem ser executadas
em background pelo Celery, incluindo:

- Importação de ROMs
- Verificação de integridade
- Manutenção do sistema
- Processamento de metadados
"""

from .rom_tasks import *
from .import_tasks import *
from .verification_tasks import *
from .maintenance_tasks import *

__all__ = [
    # ROM tasks
    "process_rom",
    "extract_rom_metadata",
    "generate_rom_thumbnail",
    
    # Import tasks
    "import_rom_file",
    "import_rom_directory",
    "scan_rom_directory",
    
    # Verification tasks
    "verify_rom_integrity",
    "verify_all_roms",
    "check_rom_duplicates",
    
    # Maintenance tasks
    "cleanup_old_tasks",
    "update_game_metadata",
    "optimize_database",
]