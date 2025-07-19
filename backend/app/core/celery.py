"""Configuração do Celery para o MegaEmu.

Este módulo configura o Celery para processamento assíncrono de tarefas,
incluindo importação de ROMs, verificação de arquivos e outras operações
que podem ser executadas em background.
"""

import os
from celery import Celery
from app.core.config import settings

# Configurar o Celery
celery_app = Celery(
    "megaemu",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=[
        "app.tasks.rom_tasks",
        "app.tasks.import_tasks",
        "app.tasks.verification_tasks",
        "app.tasks.maintenance_tasks",
    ]
)

# Configurações do Celery
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 minutos
    task_soft_time_limit=25 * 60,  # 25 minutos
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_routes={
        "app.tasks.rom_tasks.*": {"queue": "roms"},
        "app.tasks.import_tasks.*": {"queue": "imports"},
        "app.tasks.verification_tasks.*": {"queue": "verification"},
        "app.tasks.maintenance_tasks.*": {"queue": "maintenance"},
    },
    task_default_queue="default",
    task_default_exchange="default",
    task_default_exchange_type="direct",
    task_default_routing_key="default",
)

# Configuração de beat schedule para tarefas periódicas
celery_app.conf.beat_schedule = {
    "cleanup-old-tasks": {
        "task": "app.tasks.maintenance_tasks.cleanup_old_tasks",
        "schedule": 3600.0,  # A cada hora
    },
    "verify-rom-integrity": {
        "task": "app.tasks.verification_tasks.verify_all_roms",
        "schedule": 86400.0,  # Diariamente
    },
    "update-game-metadata": {
        "task": "app.tasks.maintenance_tasks.update_game_metadata",
        "schedule": 604800.0,  # Semanalmente
    },
}

if __name__ == "__main__":
    celery_app.start()