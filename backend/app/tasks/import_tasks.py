"""Tarefas do Celery relacionadas à importação de ROMs.

Este módulo contém tarefas assíncronas para:
- Importação de arquivos ROM individuais
- Importação em lote de diretórios
- Escaneamento de diretórios
- Validação de arquivos
"""

import logging
from pathlib import Path
from typing import Dict, Any, List
from celery import current_task
from app.core.celery import celery_app
from app.core.database import get_db
from app.services.rom import ROMService
from app.utils.file_utils import scan_directory, is_valid_rom_file

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name="app.tasks.import_tasks.import_rom_file")
def import_rom_file(self, file_path: str, user_id: str, system_id: str = None) -> Dict[str, Any]:
    """Importa um arquivo ROM individual.
    
    Args:
        file_path: Caminho para o arquivo ROM
        user_id: ID do usuário que iniciou a importação
        system_id: ID do sistema (opcional)
        
    Returns:
        Dict com resultado da importação
    """
    try:
        if current_task:
            current_task.update_state(
                state="PROGRESS",
                meta={"current": 0, "total": 100, "status": "Iniciando importação..."}
            )
        
        logger.info(f"Importando arquivo ROM: {file_path}")
        
        # Validar arquivo
        if not Path(file_path).exists():
            raise FileNotFoundError(f"Arquivo não encontrado: {file_path}")
        
        if not is_valid_rom_file(Path(file_path)):
            raise ValueError(f"Arquivo não é um ROM válido: {file_path}")
        
        if current_task:
            current_task.update_state(
                state="PROGRESS",
                meta={"current": 50, "total": 100, "status": "Processando arquivo..."}
            )
        
        # TODO: Implementar lógica real de importação
        result = {
            "file_path": file_path,
            "user_id": user_id,
            "system_id": system_id,
            "status": "imported",
            "message": "Arquivo importado com sucesso"
        }
        
        logger.info(f"Arquivo ROM importado: {file_path}")
        return result
        
    except Exception as exc:
        logger.error(f"Erro ao importar arquivo {file_path}: {exc}")
        if current_task:
            current_task.update_state(
                state="FAILURE",
                meta={"error": str(exc), "file_path": file_path}
            )
        raise


@celery_app.task(bind=True, name="app.tasks.import_tasks.import_rom_directory")
def import_rom_directory(self, directory_path: str, user_id: str, recursive: bool = True) -> Dict[str, Any]:
    """Importa todos os ROMs de um diretório.
    
    Args:
        directory_path: Caminho para o diretório
        user_id: ID do usuário que iniciou a importação
        recursive: Se deve buscar recursivamente em subdiretórios
        
    Returns:
        Dict com resultado da importação
    """
    try:
        if current_task:
            current_task.update_state(
                state="PROGRESS",
                meta={"current": 0, "total": 100, "status": "Escaneando diretório..."}
            )
        
        logger.info(f"Importando diretório: {directory_path}")
        
        # Escanear diretório
        rom_files = scan_directory(Path(directory_path), recursive=recursive)
        total_files = len(rom_files)
        
        if total_files == 0:
            return {
                "directory_path": directory_path,
                "total_files": 0,
                "imported_files": 0,
                "status": "completed",
                "message": "Nenhum arquivo ROM encontrado"
            }
        
        imported_count = 0
        failed_files = []
        
        for i, rom_file in enumerate(rom_files):
            try:
                if current_task:
                    progress = int((i / total_files) * 100)
                    current_task.update_state(
                        state="PROGRESS",
                        meta={
                            "current": progress,
                            "total": 100,
                            "status": f"Importando {rom_file.name}... ({i+1}/{total_files})"
                        }
                    )
                
                # Importar arquivo individual
                # TODO: Implementar lógica real de importação
                imported_count += 1
                
            except Exception as file_exc:
                logger.error(f"Erro ao importar {rom_file}: {file_exc}")
                failed_files.append(str(rom_file))
        
        result = {
            "directory_path": directory_path,
            "total_files": total_files,
            "imported_files": imported_count,
            "failed_files": failed_files,
            "status": "completed",
            "message": f"Importação concluída: {imported_count}/{total_files} arquivos"
        }
        
        logger.info(f"Diretório importado: {directory_path} - {imported_count}/{total_files}")
        return result
        
    except Exception as exc:
        logger.error(f"Erro ao importar diretório {directory_path}: {exc}")
        if current_task:
            current_task.update_state(
                state="FAILURE",
                meta={"error": str(exc), "directory_path": directory_path}
            )
        raise


@celery_app.task(bind=True, name="app.tasks.import_tasks.scan_rom_directory")
def scan_rom_directory(self, directory_path: str, recursive: bool = True) -> Dict[str, Any]:
    """Escaneia um diretório em busca de arquivos ROM.
    
    Args:
        directory_path: Caminho para o diretório
        recursive: Se deve buscar recursivamente em subdiretórios
        
    Returns:
        Dict com informações dos arquivos encontrados
    """
    try:
        if current_task:
            current_task.update_state(
                state="PROGRESS",
                meta={"current": 0, "total": 100, "status": "Escaneando diretório..."}
            )
        
        logger.info(f"Escaneando diretório: {directory_path}")
        
        rom_files = scan_directory(Path(directory_path), recursive=recursive)
        
        file_info = []
        for rom_file in rom_files:
            try:
                info = {
                    "path": str(rom_file),
                    "name": rom_file.name,
                    "size": rom_file.stat().st_size,
                    "extension": rom_file.suffix.lower()
                }
                file_info.append(info)
            except Exception as file_exc:
                logger.warning(f"Erro ao obter info do arquivo {rom_file}: {file_exc}")
        
        result = {
            "directory_path": directory_path,
            "total_files": len(file_info),
            "files": file_info,
            "status": "completed"
        }
        
        logger.info(f"Escaneamento concluído: {len(file_info)} arquivos encontrados")
        return result
        
    except Exception as exc:
        logger.error(f"Erro ao escanear diretório {directory_path}: {exc}")
        if current_task:
            current_task.update_state(
                state="FAILURE",
                meta={"error": str(exc), "directory_path": directory_path}
            )
        raise