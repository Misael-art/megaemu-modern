"""Tarefas do Celery relacionadas à verificação de ROMs.

Este módulo contém tarefas assíncronas para:
- Verificação de integridade de arquivos
- Detecção de duplicatas
- Validação de checksums
- Verificação em lote
"""

import logging
from pathlib import Path
from typing import Dict, Any, List
from celery import current_task
from app.core.celery import celery_app
from app.core.database import get_db
from app.services.rom import ROMService
from app.utils.file_utils import calculate_file_hash, verify_file_integrity

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name="app.tasks.verification_tasks.verify_rom_integrity")
def verify_rom_integrity(self, rom_id: str) -> Dict[str, Any]:
    """Verifica a integridade de um ROM específico.
    
    Args:
        rom_id: ID do ROM a ser verificado
        
    Returns:
        Dict com resultado da verificação
    """
    try:
        if current_task:
            current_task.update_state(
                state="PROGRESS",
                meta={"current": 0, "total": 100, "status": "Iniciando verificação..."}
            )
        
        logger.info(f"Verificando integridade do ROM {rom_id}")
        
        from app.models.rom import ROM
        
        with get_db() as db:
            rom = db.query(ROM).filter(ROM.id == rom_id).first()
            if not rom:
                raise ValueError(f"ROM {rom_id} não encontrado no banco de dados")
        
        file_path = Path(rom.file_path)
        file_exists = file_path.exists()
        
        if current_task:
            current_task.update_state(
                state="PROGRESS",
                meta={"current": 25, "total": 100, "status": "Verificando existência do arquivo..."}
            )
        
        if not file_exists:
            result = {
                "rom_id": rom_id,
                "status": "invalid",
                "integrity_check": False,
                "hash_match": False,
                "file_exists": False,
                "message": "Arquivo ROM não encontrado"
            }
            logger.warning(f"Arquivo para ROM {rom_id} não existe: {rom.file_path}")
            return result
        
        if current_task:
            current_task.update_state(
                state="PROGRESS",
                meta={"current": 50, "total": 100, "status": "Calculando hash..."}
            )
        
        calculated_hash = calculate_file_hash(str(file_path))
        hash_match = calculated_hash == rom.hash
        integrity_check = verify_file_integrity(str(file_path))
        
        status = "valid" if file_exists and hash_match and integrity_check else "invalid"
        
        result = {
            "rom_id": rom_id,
            "status": status,
            "integrity_check": integrity_check,
            "hash_match": hash_match,
            "file_exists": file_exists,
            "calculated_hash": calculated_hash,
            "stored_hash": rom.hash,
            "message": "ROM verificado com sucesso" if status == "valid" else "Problemas encontrados na verificação"
        }
        
        logger.info(f"ROM {rom_id} verificado com sucesso")
        return result
        
    except Exception as exc:
        logger.error(f"Erro ao verificar ROM {rom_id}: {exc}")
        if current_task:
            current_task.update_state(
                state="FAILURE",
                meta={"error": str(exc), "rom_id": rom_id}
            )
        raise


@celery_app.task(bind=True, name="app.tasks.verification_tasks.verify_all_roms")
def verify_all_roms(self, user_id: str = None) -> Dict[str, Any]:
    """Verifica a integridade de todos os ROMs.
    
    Args:
        user_id: ID do usuário (opcional, para filtrar ROMs)
        
    Returns:
        Dict com resultado da verificação em lote
    """
    try:
        if current_task:
            current_task.update_state(
                state="PROGRESS",
                meta={"current": 0, "total": 100, "status": "Buscando ROMs..."}
            )
        
        logger.info("Iniciando verificação de todos os ROMs")
        
        from app.models.rom import ROM
        
        with get_db() as db:
            query = db.query(ROM)
            if user_id:
                query = query.filter(ROM.user_id == user_id)
            roms = query.all()
            rom_ids = [rom.id for rom in roms]
        
        total_roms = len(rom_ids)
        
        if total_roms == 0:
            return {
                "total_roms": 0,
                "verified_roms": 0,
                "failed_roms": 0,
                "status": "completed",
                "message": "Nenhum ROM encontrado para verificação"
            }
        
        verified_count = 0
        failed_roms = []
        
        for i, rom_id in enumerate(rom_ids):
            try:
                if current_task:
                    progress = int((i / total_roms) * 100)
                    current_task.update_state(
                        state="PROGRESS",
                        meta={
                            "current": progress,
                            "total": 100,
                            "status": f"Verificando ROM {rom_id}... ({i+1}/{total_roms})"
                        }
                    )
                
                # Verificar ROM individual usando a função existente
                verification_result = verify_rom_integrity.delay(rom_id).get()
                if verification_result['status'] == 'valid':
                    verified_count += 1
                else:
                    failed_roms.append(rom_id)
                
            except Exception as rom_exc:
                logger.error(f"Erro ao verificar ROM {rom_id}: {rom_exc}")
                failed_roms.append(rom_id)
        
        result = {
            "total_roms": total_roms,
            "verified_roms": verified_count,
            "failed_roms": len(failed_roms),
            "failed_rom_ids": failed_roms,
            "status": "completed",
            "message": f"Verificação concluída: {verified_count}/{total_roms} ROMs"
        }
        
        logger.info(f"Verificação em lote concluída: {verified_count}/{total_roms}")
        return result
        
    except Exception as exc:
        logger.error(f"Erro na verificação em lote: {exc}")
        if current_task:
            current_task.update_state(
                state="FAILURE",
                meta={"error": str(exc)}
            )
        raise


@celery_app.task(bind=True, name="app.tasks.verification_tasks.check_rom_duplicates")
def check_rom_duplicates(self, user_id: str = None) -> Dict[str, Any]:
    """Verifica duplicatas de ROMs baseado em hash.
    
    Args:
        user_id: ID do usuário (opcional, para filtrar ROMs)
        
    Returns:
        Dict com informações sobre duplicatas encontradas
    """
    try:
        if current_task:
            current_task.update_state(
                state="PROGRESS",
                meta={"current": 0, "total": 100, "status": "Buscando duplicatas..."}
            )
        
        logger.info("Verificando duplicatas de ROMs")
        
        from app.models.rom import ROM
        from collections import defaultdict
        
        with get_db() as db:
            query = db.query(ROM)
            if user_id:
                query = query.filter(ROM.user_id == user_id)
            roms = query.all()
        
        hash_to_roms = defaultdict(list)
        for rom in roms:
            hash_to_roms[rom.hash].append(rom.id)
        
        duplicates = [group for group in hash_to_roms.values() if len(group) > 1]
        
        total_duplicates = len(duplicates)
        
        if current_task:
            current_task.update_state(
                state="PROGRESS",
                meta={"current": 100, "total": 100, "status": "Verificação de duplicatas concluída."}
            )
        
        result = {
            "total_duplicates": len(duplicates),
            "duplicate_groups": duplicates,
            "status": "completed",
            "message": f"Verificação de duplicatas concluída: {len(duplicates)} grupos encontrados"
        }
        
        logger.info(f"Verificação de duplicatas concluída: {len(duplicates)} grupos")
        return result
        
    except Exception as exc:
        logger.error(f"Erro na verificação de duplicatas: {exc}")
        if current_task:
            current_task.update_state(
                state="FAILURE",
                meta={"error": str(exc)}
            )
        raise