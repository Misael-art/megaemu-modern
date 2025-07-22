"""Factories para criação de serviços complexos.

Implementa factory patterns para instanciação controlada de serviços
com inicialização complexa.
"""

from typing import Callable, TypeAlias
from app.services.rom import ROMService
from app.services.processing import ImportService
from app.services.task import TaskService

def create_rom_service() -> ROMService:
    """Factory para ROMService com inicialização customizada."""
    service = ROMService()
    # Adicionar inicializações complexas aqui, ex: configuração de parsers
    return service

def create_import_service(
    rom_service: ROMService,
    task_service: TaskService
) -> ImportService:
    """Factory para ImportService com dependências injetadas."""
    return ImportService(
        rom_service=rom_service,
        task_service=task_service
    )

# Factory type alias para uso no container
ROMServiceFactory: TypeAlias = Callable[[], ROMService]
ImportServiceFactory: TypeAlias = Callable[[ROMService, TaskService], ImportService]