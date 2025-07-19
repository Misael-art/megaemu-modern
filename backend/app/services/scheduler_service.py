"""Serviço de agendamento de tarefas.

Este módulo implementa funcionalidades para agendamento e execução
de tarefas periódicas e programadas.
"""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass
from enum import Enum

from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.core.database import get_db
from app.models.task import Task
from app.schemas.task import TaskCreate
from app.services.task import TaskService


class ScheduleType(str, Enum):
    """Tipos de agendamento."""
    ONCE = "once"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    INTERVAL = "interval"


@dataclass
class ScheduledTask:
    """Representa uma tarefa agendada."""
    id: str
    name: str
    task_type: str
    schedule_type: ScheduleType
    schedule_data: Dict[str, Any]
    user_id: int
    enabled: bool = True
    last_run: Optional[datetime] = None
    next_run: Optional[datetime] = None
    parameters: Optional[Dict[str, Any]] = None


class SchedulerService:
    """Serviço para gerenciamento de tarefas agendadas."""
    
    def __init__(self):
        self._scheduled_tasks: Dict[str, ScheduledTask] = {}
        self._running = False
        self._scheduler_task: Optional[asyncio.Task] = None
    
    async def start(self):
        """Inicia o serviço de agendamento."""
        if self._running:
            logger.warning("Scheduler já está em execução")
            return
        
        self._running = True
        self._scheduler_task = asyncio.create_task(self._scheduler_loop())
        logger.info("Scheduler iniciado")
    
    async def stop(self):
        """Para o serviço de agendamento."""
        if not self._running:
            return
        
        self._running = False
        if self._scheduler_task:
            self._scheduler_task.cancel()
            try:
                await self._scheduler_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Scheduler parado")
    
    async def add_scheduled_task(
        self,
        task_id: str,
        name: str,
        task_type: str,
        schedule_type: ScheduleType,
        schedule_data: Dict[str, Any],
        user_id: int,
        parameters: Optional[Dict[str, Any]] = None,
        enabled: bool = True
    ) -> ScheduledTask:
        """Adiciona uma nova tarefa agendada.
        
        Args:
            task_id: ID único da tarefa agendada
            name: Nome da tarefa
            task_type: Tipo da tarefa
            schedule_type: Tipo de agendamento
            schedule_data: Dados do agendamento
            user_id: ID do usuário
            parameters: Parâmetros da tarefa
            enabled: Se a tarefa está habilitada
            
        Returns:
            ScheduledTask: Tarefa agendada criada
        """
        scheduled_task = ScheduledTask(
            id=task_id,
            name=name,
            task_type=task_type,
            schedule_type=schedule_type,
            schedule_data=schedule_data,
            user_id=user_id,
            parameters=parameters or {},
            enabled=enabled
        )
        
        # Calcula próxima execução
        scheduled_task.next_run = self._calculate_next_run(scheduled_task)
        
        self._scheduled_tasks[task_id] = scheduled_task
        logger.info(f"Tarefa agendada adicionada: {name} ({task_id})")
        
        return scheduled_task
    
    async def remove_scheduled_task(self, task_id: str) -> bool:
        """Remove uma tarefa agendada.
        
        Args:
            task_id: ID da tarefa agendada
            
        Returns:
            bool: True se removida com sucesso
        """
        if task_id in self._scheduled_tasks:
            del self._scheduled_tasks[task_id]
            logger.info(f"Tarefa agendada removida: {task_id}")
            return True
        return False
    
    async def update_scheduled_task(
        self,
        task_id: str,
        **updates
    ) -> Optional[ScheduledTask]:
        """Atualiza uma tarefa agendada.
        
        Args:
            task_id: ID da tarefa agendada
            **updates: Campos para atualizar
            
        Returns:
            ScheduledTask: Tarefa atualizada ou None se não encontrada
        """
        if task_id not in self._scheduled_tasks:
            return None
        
        scheduled_task = self._scheduled_tasks[task_id]
        
        # Atualiza campos
        for field, value in updates.items():
            if hasattr(scheduled_task, field):
                setattr(scheduled_task, field, value)
        
        # Recalcula próxima execução se necessário
        if 'schedule_type' in updates or 'schedule_data' in updates:
            scheduled_task.next_run = self._calculate_next_run(scheduled_task)
        
        logger.info(f"Tarefa agendada atualizada: {task_id}")
        return scheduled_task
    
    async def get_scheduled_task(self, task_id: str) -> Optional[ScheduledTask]:
        """Obtém uma tarefa agendada.
        
        Args:
            task_id: ID da tarefa agendada
            
        Returns:
            ScheduledTask: Tarefa encontrada ou None
        """
        return self._scheduled_tasks.get(task_id)
    
    async def list_scheduled_tasks(
        self,
        user_id: Optional[int] = None,
        enabled_only: bool = False
    ) -> List[ScheduledTask]:
        """Lista tarefas agendadas.
        
        Args:
            user_id: Filtrar por usuário
            enabled_only: Apenas tarefas habilitadas
            
        Returns:
            List[ScheduledTask]: Lista de tarefas agendadas
        """
        tasks = list(self._scheduled_tasks.values())
        
        if user_id is not None:
            tasks = [t for t in tasks if t.user_id == user_id]
        
        if enabled_only:
            tasks = [t for t in tasks if t.enabled]
        
        return tasks
    
    async def enable_scheduled_task(self, task_id: str) -> bool:
        """Habilita uma tarefa agendada.
        
        Args:
            task_id: ID da tarefa agendada
            
        Returns:
            bool: True se habilitada com sucesso
        """
        if task_id in self._scheduled_tasks:
            self._scheduled_tasks[task_id].enabled = True
            self._scheduled_tasks[task_id].next_run = self._calculate_next_run(
                self._scheduled_tasks[task_id]
            )
            logger.info(f"Tarefa agendada habilitada: {task_id}")
            return True
        return False
    
    async def disable_scheduled_task(self, task_id: str) -> bool:
        """Desabilita uma tarefa agendada.
        
        Args:
            task_id: ID da tarefa agendada
            
        Returns:
            bool: True se desabilitada com sucesso
        """
        if task_id in self._scheduled_tasks:
            self._scheduled_tasks[task_id].enabled = False
            self._scheduled_tasks[task_id].next_run = None
            logger.info(f"Tarefa agendada desabilitada: {task_id}")
            return True
        return False
    
    def _calculate_next_run(self, scheduled_task: ScheduledTask) -> Optional[datetime]:
        """Calcula a próxima execução de uma tarefa.
        
        Args:
            scheduled_task: Tarefa agendada
            
        Returns:
            datetime: Próxima execução ou None se desabilitada
        """
        if not scheduled_task.enabled:
            return None
        
        now = datetime.utcnow()
        schedule_data = scheduled_task.schedule_data
        
        if scheduled_task.schedule_type == ScheduleType.ONCE:
            # Execução única
            run_at = schedule_data.get('run_at')
            if isinstance(run_at, str):
                run_at = datetime.fromisoformat(run_at)
            return run_at if run_at and run_at > now else None
        
        elif scheduled_task.schedule_type == ScheduleType.DAILY:
            # Execução diária
            hour = schedule_data.get('hour', 0)
            minute = schedule_data.get('minute', 0)
            
            next_run = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if next_run <= now:
                next_run += timedelta(days=1)
            
            return next_run
        
        elif scheduled_task.schedule_type == ScheduleType.WEEKLY:
            # Execução semanal
            weekday = schedule_data.get('weekday', 0)  # 0 = segunda
            hour = schedule_data.get('hour', 0)
            minute = schedule_data.get('minute', 0)
            
            days_ahead = weekday - now.weekday()
            if days_ahead <= 0:  # Já passou esta semana
                days_ahead += 7
            
            next_run = now + timedelta(days=days_ahead)
            next_run = next_run.replace(hour=hour, minute=minute, second=0, microsecond=0)
            
            return next_run
        
        elif scheduled_task.schedule_type == ScheduleType.MONTHLY:
            # Execução mensal
            day = schedule_data.get('day', 1)
            hour = schedule_data.get('hour', 0)
            minute = schedule_data.get('minute', 0)
            
            # Próximo mês
            if now.month == 12:
                next_month = now.replace(year=now.year + 1, month=1, day=day)
            else:
                next_month = now.replace(month=now.month + 1, day=day)
            
            next_run = next_month.replace(hour=hour, minute=minute, second=0, microsecond=0)
            
            return next_run
        
        elif scheduled_task.schedule_type == ScheduleType.INTERVAL:
            # Execução por intervalo
            interval_seconds = schedule_data.get('interval_seconds', 3600)
            
            if scheduled_task.last_run:
                return scheduled_task.last_run + timedelta(seconds=interval_seconds)
            else:
                return now + timedelta(seconds=interval_seconds)
        
        return None
    
    async def _scheduler_loop(self):
        """Loop principal do agendador."""
        logger.info("Loop do scheduler iniciado")
        
        while self._running:
            try:
                await self._check_and_execute_tasks()
                await asyncio.sleep(60)  # Verifica a cada minuto
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Erro no loop do scheduler: {e}")
                await asyncio.sleep(60)
        
        logger.info("Loop do scheduler finalizado")
    
    async def _check_and_execute_tasks(self):
        """Verifica e executa tarefas que devem ser executadas."""
        now = datetime.utcnow()
        
        for scheduled_task in self._scheduled_tasks.values():
            if (
                scheduled_task.enabled and
                scheduled_task.next_run and
                scheduled_task.next_run <= now
            ):
                try:
                    await self._execute_scheduled_task(scheduled_task)
                except Exception as e:
                    logger.error(
                        f"Erro ao executar tarefa agendada {scheduled_task.id}: {e}"
                    )
    
    async def _execute_scheduled_task(self, scheduled_task: ScheduledTask):
        """Executa uma tarefa agendada.
        
        Args:
            scheduled_task: Tarefa a ser executada
        """
        logger.info(f"Executando tarefa agendada: {scheduled_task.name}")
        
        # Cria tarefa no banco de dados
        async for db in get_db():
            try:
                task_service = TaskService(db)
                
                task_create = TaskCreate(
                    task_type=scheduled_task.task_type,
                    name=f"[Agendada] {scheduled_task.name}",
                    description=f"Tarefa agendada executada automaticamente",
                    parameters=scheduled_task.parameters or {},
                    user_id=scheduled_task.user_id
                )
                
                # Cria e executa a tarefa
                task = await task_service.create_task(task_create)
                
                # Atualiza informações da tarefa agendada
                scheduled_task.last_run = datetime.utcnow()
                scheduled_task.next_run = self._calculate_next_run(scheduled_task)
                
                logger.info(
                    f"Tarefa agendada executada: {scheduled_task.name} "
                    f"(próxima execução: {scheduled_task.next_run})"
                )
                
                break
                
            except Exception as e:
                logger.error(
                    f"Erro ao criar tarefa agendada {scheduled_task.name}: {e}"
                )
                raise


# Instância global do scheduler
scheduler_service = SchedulerService()