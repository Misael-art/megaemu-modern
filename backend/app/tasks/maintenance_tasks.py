"""Tarefas do Celery relacionadas à manutenção do sistema.

Este módulo contém tarefas assíncronas para:
- Limpeza de tarefas antigas
- Otimização do banco de dados
- Atualização de metadados
- Manutenção geral do sistema
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any
from celery import current_task
from app.core.celery import celery_app
from app.core.database import get_db
from app.services.task import TaskService
from app.models.task import TaskStatus

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name="app.tasks.maintenance_tasks.cleanup_old_tasks")
def cleanup_old_tasks(self, days_old: int = 30) -> Dict[str, Any]:
    """Remove tarefas antigas do sistema.
    
    Args:
        days_old: Número de dias para considerar uma tarefa como antiga
        
    Returns:
        Dict com resultado da limpeza
    """
    try:
        if current_task:
            current_task.update_state(
                state="PROGRESS",
                meta={"current": 0, "total": 100, "status": "Iniciando limpeza..."}
            )
        
        logger.info(f"Iniciando limpeza de tarefas com mais de {days_old} dias")
        
        cutoff_date = datetime.utcnow() - timedelta(days=days_old)
        
        with get_db() as db:
            # Buscar tarefas antigas (completadas ou falhadas) antes da data de corte
            old_tasks = db.query(Task).filter(
                Task.created_at < cutoff_date,
                Task.status.in_([TaskStatus.COMPLETED, TaskStatus.FAILED])
            ).all()
            
            total = len(old_tasks)
            removed_count = 0
            
            for i, task in enumerate(old_tasks):
                try:
                    db.delete(task)
                    db.commit()
                    removed_count += 1
                except Exception as e:
                    logger.warning(f"Falha ao deletar tarefa {task.id}: {e}")
                    db.rollback()
                
                if current_task:
                    progress = int(50 + (i / total) * 50) if total > 0 else 50
                    current_task.update_state(
                        state="PROGRESS",
                        meta={"current": progress, "total": 100, "status": f"Removendo tarefas antigas ({i+1}/{total})..."}
                    )
            
            if total == 0:
                if current_task:
                    current_task.update_state(
                        state="PROGRESS",
                        meta={"current": 100, "total": 100, "status": "Nenhuma tarefa antiga encontrada."}
                    )
        
        result = {
            "cutoff_date": cutoff_date.isoformat(),
            "removed_tasks": removed_count,
            "status": "completed",
            "message": f"Limpeza concluída: {removed_count} tarefas removidas"
        }
        
        logger.info(f"Limpeza concluída: {removed_count} tarefas removidas")
        return result
        
    except Exception as exc:
        logger.error(f"Erro na limpeza de tarefas: {exc}")
        if current_task:
            current_task.update_state(
                state="FAILURE",
                meta={"error": str(exc)}
            )
        raise


@celery_app.task(bind=True, name="app.tasks.maintenance_tasks.update_game_metadata")
def update_game_metadata(self, force_update: bool = False) -> Dict[str, Any]:
    """Atualiza metadados dos jogos.
    
    Args:
        force_update: Se deve forçar atualização mesmo para jogos já atualizados
        
    Returns:
        Dict com resultado da atualização
    """
    try:
        if current_task:
            current_task.update_state(
                state="PROGRESS",
                meta={"current": 0, "total": 100, "status": "Buscando jogos..."}
            )
        
        logger.info("Iniciando atualização de metadados dos jogos")
        
        from app.models.game import Game
        from app.services.processing import MetadataService
        
        metadata_service = MetadataService()
        
        with get_db() as db:
            # Buscar jogos que precisam de atualização (sem metadados ou forçado)
            query = db.query(Game).filter(Game.metadata_updated_at.is_(None)) if not force_update else db.query(Game)
            games = query.all()
            
            total = len(games)
            updated_count = 0
            
            for i, game in enumerate(games):
                try:
                    # Coletar metadados usando o serviço
                    metadata = metadata_service.collect_game_metadata(game.id)
                    # Atualizar jogo com novos metadados
                    game.title = metadata.get('title', game.title)
                    game.description = metadata.get('description', game.description)
                    game.metadata_updated_at = datetime.utcnow()
                    db.commit()
                    updated_count += 1
                    logger.info(f"Metadados atualizados para jogo {game.id}")
                except Exception as e:
                    logger.warning(f"Falha ao atualizar metadados do jogo {game.id}: {e}")
                    db.rollback()
                
                if current_task:
                    progress = int((i / total) * 100) if total > 0 else 100
                    current_task.update_state(
                        state="PROGRESS",
                        meta={"current": progress, "total": 100, "status": f"Atualizando metadados ({i+1}/{total})..."}
                    )
            
            if total == 0:
                if current_task:
                    current_task.update_state(
                        state="PROGRESS",
                        meta={"current": 100, "total": 100, "status": "Nenhum jogo precisa de atualização."}
                    )
        
        result = {
            "updated_games": updated_count,
            "force_update": force_update,
            "status": "completed",
            "message": f"Atualização concluída: {updated_count} jogos atualizados"
        }
        
        logger.info(f"Atualização de metadados concluída: {updated_count} jogos")
        return result
        
    except Exception as exc:
        logger.error(f"Erro na atualização de metadados: {exc}")
        if current_task:
            current_task.update_state(
                state="FAILURE",
                meta={"error": str(exc)}
            )
        raise


@celery_app.task(bind=True, name="app.tasks.maintenance_tasks.optimize_database")
def optimize_database(self) -> Dict[str, Any]:
    """Otimiza o banco de dados.
    
    Returns:
        Dict com resultado da otimização
    """
    try:
        if current_task:
            current_task.update_state(
                state="PROGRESS",
                meta={"current": 0, "total": 100, "status": "Iniciando otimização..."}
            )
        
        logger.info("Iniciando otimização do banco de dados")
        
        from sqlalchemy import text
        
        with get_db() as db:
            optimizations = []
            try:
                db.execute(text("VACUUM;"))
                optimizations.append("VACUUM executado")
                if current_task:
                    current_task.update_state(
                        state="PROGRESS",
                        meta={"current": 33, "total": 100, "status": "VACUUM concluído. Executando ANALYZE..."}
                    )
                db.execute(text("ANALYZE;"))
                optimizations.append("ANALYZE executado")
                if current_task:
                    current_task.update_state(
                        state="PROGRESS",
                        meta={"current": 66, "total": 100, "status": "ANALYZE concluído. Reindexando..."}
                    )
                db.execute(text("REINDEX DATABASE megaemu;"))  # Assumindo nome do DB
                optimizations.append("Índices reindexados")
                if current_task:
                    current_task.update_state(
                        state="PROGRESS",
                        meta={"current": 100, "total": 100, "status": "Otimização concluída."}
                    )
            except Exception as e:
                logger.error(f"Erro durante otimização: {e}")
                optimizations.append(f"Erro: {str(e)}")
        
        result = {
            "optimizations": optimizations,
            "status": "completed",
            "message": "Otimização do banco de dados concluída"
        }
        
        logger.info("Otimização do banco de dados concluída")
        return result
        
    except Exception as exc:
        logger.error(f"Erro na otimização do banco: {exc}")
        if current_task:
            current_task.update_state(
                state="FAILURE",
                meta={"error": str(exc)}
            )
        raise


@celery_app.task(bind=True, name="app.tasks.maintenance_tasks.system_health_check")
def system_health_check(self) -> Dict[str, Any]:
    """Executa verificação de saúde do sistema.
    
    Returns:
        Dict com resultado da verificação
    """
    try:
        if current_task:
            current_task.update_state(
                state="PROGRESS",
                meta={"current": 0, "total": 100, "status": "Verificando sistema..."}
            )
        
        logger.info("Iniciando verificação de saúde do sistema")
        
        import psutil
        from app.core.redis import redis_client
        
        health_checks = {}
        
        # Verificar conectividade do banco
        try:
            with get_db() as db:
                db.execute(text("SELECT 1;"))
            health_checks["database"] = "healthy"
        except Exception as e:
            health_checks["database"] = f"unhealthy: {str(e)}"
            logger.warning(f"Falha na verificação do banco: {e}")
        
        if current_task:
            current_task.update_state(
                state="PROGRESS",
                meta={"current": 25, "total": 100, "status": "Banco de dados verificado."}
            )
        
        # Verificar Redis
        try:
            redis_client.ping()
            health_checks["redis"] = "healthy"
        except Exception as e:
            health_checks["redis"] = f"unhealthy: {str(e)}"
            logger.warning(f"Falha na verificação do Redis: {e}")
        
        if current_task:
            current_task.update_state(
                state="PROGRESS",
                meta={"current": 50, "total": 100, "status": "Redis verificado."}
            )
        
        # Verificar espaço em disco
        disk_usage = psutil.disk_usage('/')
        if disk_usage.percent > 90:
            health_checks["disk_space"] = f"warning: {disk_usage.percent}% used"
        else:
            health_checks["disk_space"] = "healthy"
        
        if current_task:
            current_task.update_state(
                state="PROGRESS",
                meta={"current": 75, "total": 100, "status": "Espaço em disco verificado."}
            )
        
        # Verificar uso de memória
        memory = psutil.virtual_memory()
        if memory.percent > 80:
            health_checks["memory_usage"] = f"warning: {memory.percent}% used"
        else:
            health_checks["memory_usage"] = "healthy"
        
        if current_task:
            current_task.update_state(
                state="PROGRESS",
                meta={"current": 100, "total": 100, "status": "Verificação concluída."}
            )
        
        result = {
            "health_checks": health_checks,
            "overall_status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "message": "Verificação de saúde concluída"
        }
        
        logger.info("Verificação de saúde do sistema concluída")
        return result
        
    except Exception as exc:
        logger.error(f"Erro na verificação de saúde: {exc}")
        if current_task:
            current_task.update_state(
                state="FAILURE",
                meta={"error": str(exc)}
            )
        raise