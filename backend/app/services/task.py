from typing import List, Optional, Dict, Any, Callable
from uuid import UUID
from datetime import datetime
import asyncio
from threading import Lock
from collections import defaultdict
import queue

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc
from sqlalchemy.orm import selectinload
from sqlalchemy.sql import Select
from fastapi import HTTPException, status

from app.core.database import engine
from app.models.task import Task, TaskStatus, TaskType, TaskPriority
from app.schemas.task import (
    TaskCreate,
    TaskUpdate,
    TaskProgressUpdate,
    TaskFilterParams
)
from app.services.base import BaseService


class TaskService(BaseService[Task, TaskCreate, TaskUpdate]):
    """Serviço para gerenciamento de tarefas."""
    
    def __init__(self):
        super().__init__(Task)
        self._task_handlers: Dict[TaskType, Callable] = {}
        self._progress_callbacks: Dict[str, List[Callable]] = defaultdict(list)
        self._callbacks_lock = Lock()
        self.pending_queue = queue.PriorityQueue()
        self._worker_task = None
    
    async def create_task(
        self,
        db: AsyncSession,
        *,
        task_data: TaskCreate,
        user_id: UUID
    ) -> Task:
        """Cria uma nova tarefa.
        
        Args:
            db: Sessão do banco de dados
            task_data: Dados da tarefa
            user_id: ID do usuário
            
        Returns:
            Tarefa criada
        """
        task_dict = task_data.model_dump()
        task_dict["user_id"] = user_id
        task_dict["status"] = TaskStatus.PENDING
        task_dict["progress"] = 0
        task_dict["created_at"] = datetime.utcnow()
        task_dict["updated_at"] = datetime.utcnow()
        
        task = await self.create(db, obj_in=task_dict)
        
        # Adiciona à fila de execução
        priority = task.priority.value if task.priority else TaskPriority.MEDIUM.value
        self.pending_queue.put((priority, task.id))
        
        return task
    
    async def get_user_tasks(
        self,
        db: AsyncSession,
        *,
        user_id: UUID,
        filters: Optional[TaskFilterParams] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[Task]:
        """Busca tarefas do usuário.
        
        Args:
            db: Sessão do banco de dados
            user_id: ID do usuário
            filters: Filtros opcionais
            skip: Número de registros para pular
            limit: Limite de registros
            
        Returns:
            Lista de tarefas
        """
        query = select(Task).where(Task.user_id == user_id)
        
        if filters:
            query = self._apply_filters(query, filters)
        
        # Ordenação padrão por data de criação (mais recentes primeiro)
        query = query.order_by(desc(Task.created_at))
        
        # Paginação
        query = query.offset(skip).limit(limit)
        
        # Carregamento de relacionamentos
        query = self._add_relationship_loading(query)
        
        result = await db.execute(query)
        return result.scalars().all()
    
    async def update_task_status(
        self,
        db: AsyncSession,
        *,
        task_id: UUID,
        status: TaskStatus,
        status_message: Optional[str] = None
    ) -> Task:
        """Atualiza status da tarefa.
        
        Args:
            db: Sessão do banco de dados
            task_id: ID da tarefa
            status: Novo status
            status_message: Mensagem de status opcional
            
        Returns:
            Tarefa atualizada
            
        Raises:
            HTTPException: Se tarefa não encontrada
        """
        task = await self.get(db, task_id)
        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tarefa não encontrada"
            )
        
        task.status = status
        if status_message:
            task.status_message = status_message
        
        if status == TaskStatus.COMPLETED:
            task.progress = 100
            task.completed_at = datetime.utcnow()
        elif status == TaskStatus.FAILED:
            task.completed_at = datetime.utcnow()
        
        task.updated_at = datetime.utcnow()
        
        await db.commit()
        await db.refresh(task)
        
        return task
    
    async def update_task_progress(
        self,
        db: AsyncSession,
        *,
        task_id: UUID,
        progress_update: TaskProgressUpdate
    ) -> Task:
        """Atualiza progresso da tarefa.
        
        Args:
            db: Sessão do banco de dados
            task_id: ID da tarefa
            progress_update: Dados de progresso
            
        Returns:
            Tarefa atualizada
            
        Raises:
            HTTPException: Se tarefa não encontrada
        """
        task = await self.get(db, task_id)
        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tarefa não encontrada"
            )
        
        # Atualiza progresso
        task.progress = progress_update.progress
        
        if progress_update.status_message:
            task.status_message = progress_update.status_message
        
        if progress_update.current_step:
            task.current_step = progress_update.current_step
        
        if progress_update.total_steps:
            task.total_steps = progress_update.total_steps
        
        # Atualiza timestamp
        task.updated_at = datetime.utcnow()
        
        await db.commit()
        await db.refresh(task)
        
        return task
    
    def register_task_handler(
        self,
        task_type: TaskType,
        handler: Callable[[AsyncSession, Task], None]
    ) -> None:
        """Registra handler para tipo de tarefa.
        
        Args:
            task_type: Tipo da tarefa
            handler: Função handler
        """
        self._task_handlers[task_type] = handler
    
    def register_progress_callback(
        self, 
        task_id: str, 
        callback: Callable[[Dict[str, Any]], None]
    ) -> None:
        """Registra callback de progresso.
        
        Args:
            task_id: ID da tarefa
            callback: Função de callback
        """
        with self._callbacks_lock:
            self._progress_callbacks[task_id].append(callback)
    
    def _apply_filters(self, query: Select, filters: TaskFilterParams) -> Select:
        """Aplica filtros à query.
        
        Args:
            query: Query base
            filters: Filtros
            
        Returns:
            Query com filtros
        """
        conditions = []
        
        if filters.user_id:
            conditions.append(Task.user_id == filters.user_id)
        
        if filters.task_type:
            conditions.append(Task.task_type == filters.task_type)
        
        if filters.status:
            conditions.append(Task.status == filters.status)
        
        if filters.priority:
            conditions.append(Task.priority == filters.priority)
        
        if filters.created_after:
            conditions.append(Task.created_at >= filters.created_after)
        
        if filters.created_before:
            conditions.append(Task.created_at <= filters.created_before)
        
        if filters.completed_after:
            conditions.append(Task.completed_at >= filters.completed_after)
        
        if filters.completed_before:
            conditions.append(Task.completed_at <= filters.completed_before)
        
        if conditions:
            query = query.where(and_(*conditions))
        
        return query
    
    def _apply_sorting(self, query: Select, sort_by: str, sort_order: str) -> Select:
        """Aplica ordenação à query.
        
        Args:
            query: Query base
            sort_by: Campo de ordenação
            sort_order: Ordem (asc/desc)
            
        Returns:
            Query com ordenação
        """
        order_field = getattr(Task, sort_by, Task.created_at)
        
        if sort_order == "desc":
            order_field = order_field.desc()
        
        return query.order_by(order_field)
    
    def _add_relationship_loading(self, query: Select) -> Select:
        """Adiciona carregamento de relacionamentos.
        
        Args:
            query: Query base
            
        Returns:
            Query com relacionamentos
        """
        return query.options(selectinload(Task.results))
    
    async def _execute_task(self, db: AsyncSession, task: Task) -> None:
        """Executa uma tarefa.
        
        Args:
            db: Sessão do banco de dados
            task: Tarefa a ser executada
        """
        try:
            # Atualiza status para executando
            await self.update_task_status(
                db, 
                task_id=task.id, 
                status=TaskStatus.RUNNING
            )
            
            # Executa handler se registrado
            if task.task_type in self._task_handlers:
                handler = self._task_handlers[task.task_type]
                await handler(db, task)
            
            # Marca como concluída se não houve erro
            if task.status == TaskStatus.RUNNING:
                await self.update_task_status(
                    db,
                    task_id=task.id,
                    status=TaskStatus.COMPLETED
                )
                
        except Exception as e:
            # Marca como falha em caso de erro
            await self.update_task_status(
                db,
                task_id=task.id,
                status=TaskStatus.FAILED,
                status_message=str(e)
            )
    
    async def _worker(self):
        """Worker para processar tarefas da fila."""
        while True:
            try:
                priority, task_id = self.pending_queue.get(timeout=1)
                async with AsyncSession(engine) as db:
                    task = await self.get(db, task_id)
                    if task and task.status == TaskStatus.PENDING:
                        await self._execute_task(db, task)
                self.pending_queue.task_done()
            except queue.Empty:
                await asyncio.sleep(0.1)
            except Exception as e:
                print(f"Erro no worker de tarefas: {e}")
                await asyncio.sleep(1)


# Instância global do serviço
task_service = TaskService()