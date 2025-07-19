"""Serviços para gerenciamento de tarefas.

Este módulo implementa a lógica de negócio para operações relacionadas
a tarefas assíncronas, resultados e monitoramento de progresso.
"""

import asyncio
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, Callable
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.sql import Select

from app.models.task import Task, TaskResult, TaskStatus, TaskPriority, TaskType
from app.models.user import User
from app.schemas.task import (
    TaskCreate,
    TaskUpdate,
    TaskResultCreate,
    TaskResultUpdate,
    TaskFilterParams,
    TaskSearchRequest,
    TaskProgressUpdate,
    TaskRetryRequest,
    TaskCancelRequest,
    TaskBulkOperation,
)
from app.services.base import BaseService
from app.core.config import settings


class TaskService(BaseService[Task, TaskCreate, TaskUpdate]):
    """Serviço para operações com tarefas."""
    
    def __init__(self):
        super().__init__(Task)
        self._running_tasks: Dict[UUID, asyncio.Task] = {}
        self._task_handlers: Dict[TaskType, Callable] = {}
    
    async def get_by_id(
        self,
        db: AsyncSession,
        task_id: UUID,
        *,
        load_relationships: bool = False
    ) -> Optional[Task]:
        """Busca tarefa por ID.
        
        Args:
            db: Sessão do banco de dados
            task_id: ID da tarefa
            load_relationships: Se deve carregar relacionamentos
            
        Returns:
            Tarefa encontrada ou None
        """
        return await self.get(db, task_id, load_relationships=load_relationships)
    
    async def create_task(
        self,
        db: AsyncSession,
        *,
        task_in: TaskCreate
    ) -> Task:
        """Cria uma nova tarefa.
        
        Args:
            db: Sessão do banco de dados
            task_in: Dados da tarefa
            
        Returns:
            Tarefa criada
        """
        # Verifica dependências se especificadas
        if task_in.depends_on:
            for dep_id in task_in.depends_on:
                dep_task = await self.get(db, dep_id)
                if not dep_task:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Tarefa dependente {dep_id} não encontrada"
                    )
        
        # Cria a tarefa
        task = await self.create(db, obj_in=task_in)
        
        # Agenda execução se necessário
        if task_in.scheduled_for and task_in.scheduled_for <= datetime.utcnow():
            await self._schedule_task(db, task)
        elif not task_in.scheduled_for:
            # Executa imediatamente se não agendada
            await self._execute_task(db, task)
        
        return task
    
    async def get_task_with_details(
        self,
        db: AsyncSession,
        *,
        task_id: UUID
    ) -> Optional[Task]:
        """Busca tarefa com todos os detalhes.
        
        Args:
            db: Sessão do banco de dados
            task_id: ID da tarefa
            
        Returns:
            Tarefa com detalhes ou None
        """
        query = (
            select(Task)
            .options(
                selectinload(Task.user),
                selectinload(Task.results),
                selectinload(Task.dependencies),
                selectinload(Task.dependents)
            )
            .where(Task.id == task_id)
        )
        
        result = await db.execute(query)
        return result.scalar_one_or_none()
    
    async def search_tasks(
        self,
        db: AsyncSession,
        *,
        search_request: TaskSearchRequest
    ) -> Dict[str, Any]:
        """Busca tarefas com filtros e paginação.
        
        Args:
            db: Sessão do banco de dados
            search_request: Parâmetros de busca
            
        Returns:
            Resultado da busca com tarefas e metadados
        """
        query = select(Task).options(
            selectinload(Task.user)
        )
        
        # Aplica filtros
        query = self._apply_filters(query, search_request.filters)
        
        # Conta total
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await db.execute(count_query)
        total = total_result.scalar()
        
        # Aplica ordenação
        query = self._apply_sorting(query, search_request.sort_by, search_request.sort_order)
        
        # Aplica paginação
        offset = (search_request.page - 1) * search_request.page_size
        query = query.offset(offset).limit(search_request.page_size)
        
        # Executa query
        result = await db.execute(query)
        tasks = result.scalars().all()
        
        return {
            "items": tasks,
            "total": total,
            "page": search_request.page,
            "page_size": search_request.page_size,
            "total_pages": (total + search_request.page_size - 1) // search_request.page_size
        }
    
    async def get_tasks_by_user(
        self,
        db: AsyncSession,
        *,
        user_id: UUID,
        status: Optional[TaskStatus] = None,
        limit: Optional[int] = None
    ) -> List[Task]:
        """Busca tarefas por usuário.
        
        Args:
            db: Sessão do banco de dados
            user_id: ID do usuário
            status: Status da tarefa (opcional)
            limit: Limite de resultados
            
        Returns:
            Lista de tarefas
        """
        conditions = [Task.user_id == user_id]
        
        if status:
            conditions.append(Task.status == status)
        
        query = (
            select(Task)
            .where(and_(*conditions))
            .order_by(Task.created_at.desc())
        )
        
        if limit:
            query = query.limit(limit)
        
        result = await db.execute(query)
        return result.scalars().all()
    
    async def get_running_tasks(
        self,
        db: AsyncSession
    ) -> List[Task]:
        """Busca tarefas em execução.
        
        Args:
            db: Sessão do banco de dados
            
        Returns:
            Lista de tarefas em execução
        """
        query = (
            select(Task)
            .where(Task.status == TaskStatus.RUNNING)
            .order_by(Task.started_at)
        )
        
        result = await db.execute(query)
        return result.scalars().all()
    
    async def get_pending_tasks(
        self,
        db: AsyncSession,
        *,
        limit: Optional[int] = None
    ) -> List[Task]:
        """Busca tarefas pendentes.
        
        Args:
            db: Sessão do banco de dados
            limit: Limite de resultados
            
        Returns:
            Lista de tarefas pendentes
        """
        query = (
            select(Task)
            .where(Task.status == TaskStatus.PENDING)
            .order_by(Task.priority.desc(), Task.created_at)
        )
        
        if limit:
            query = query.limit(limit)
        
        result = await db.execute(query)
        return result.scalars().all()
    
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
    
    async def retry_task(
        self,
        db: AsyncSession,
        *,
        task_id: UUID,
        retry_request: TaskRetryRequest
    ) -> Task:
        """Reexecuta uma tarefa.
        
        Args:
            db: Sessão do banco de dados
            task_id: ID da tarefa
            retry_request: Parâmetros de reexecução
            
        Returns:
            Tarefa atualizada
            
        Raises:
            HTTPException: Se tarefa não encontrada ou não pode ser reexecutada
        """
        task = await self.get(db, task_id)
        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tarefa não encontrada"
            )
        
        if not task.can_retry:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Tarefa não pode ser reexecutada"
            )
        
        # Incrementa contador de tentativas
        task.retry_count += 1
        
        # Reseta status e progresso
        task.status = TaskStatus.PENDING
        task.progress = 0
        task.status_message = "Aguardando reexecução"
        task.error_message = None
        task.started_at = None
        task.completed_at = None
        
        # Atualiza parâmetros se fornecidos
        if retry_request.parameters:
            task.parameters = retry_request.parameters
        
        # Agenda nova execução
        if retry_request.delay_seconds:
            task.scheduled_for = datetime.utcnow() + timedelta(seconds=retry_request.delay_seconds)
        else:
            await self._execute_task(db, task)
        
        await db.commit()
        await db.refresh(task)
        
        return task
    
    async def cancel_task(
        self,
        db: AsyncSession,
        *,
        task_id: UUID,
        cancel_request: TaskCancelRequest
    ) -> Task:
        """Cancela uma tarefa.
        
        Args:
            db: Sessão do banco de dados
            task_id: ID da tarefa
            cancel_request: Parâmetros de cancelamento
            
        Returns:
            Tarefa cancelada
            
        Raises:
            HTTPException: Se tarefa não encontrada ou não pode ser cancelada
        """
        task = await self.get(db, task_id)
        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tarefa não encontrada"
            )
        
        if task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Tarefa não pode ser cancelada"
            )
        
        # Cancela tarefa em execução
        if task.id in self._running_tasks:
            self._running_tasks[task.id].cancel()
            del self._running_tasks[task.id]
        
        # Atualiza status
        task.status = TaskStatus.CANCELLED
        task.completed_at = datetime.utcnow()
        task.status_message = "Tarefa cancelada"
        
        if cancel_request.reason:
            task.error_message = f"Cancelada: {cancel_request.reason}"
        
        await db.commit()
        await db.refresh(task)
        
        return task
    
    async def bulk_operation(
        self,
        db: AsyncSession,
        *,
        operation: TaskBulkOperation
    ) -> Dict[str, Any]:
        """Executa operação em lote.
        
        Args:
            db: Sessão do banco de dados
            operation: Operação em lote
            
        Returns:
            Resultado da operação
        """
        results = {
            "success_count": 0,
            "error_count": 0,
            "errors": []
        }
        
        for task_id in operation.task_ids:
            try:
                if operation.operation == "cancel":
                    await self.cancel_task(
                        db,
                        task_id=task_id,
                        cancel_request=TaskCancelRequest(reason="Cancelamento em lote")
                    )
                elif operation.operation == "retry":
                    await self.retry_task(
                        db,
                        task_id=task_id,
                        retry_request=TaskRetryRequest()
                    )
                elif operation.operation == "delete":
                    await self.remove(db, task_id)
                
                results["success_count"] += 1
                
            except Exception as e:
                results["error_count"] += 1
                results["errors"].append({
                    "task_id": str(task_id),
                    "error": str(e)
                })
        
        return results
    
    async def get_task_statistics(
        self,
        db: AsyncSession,
        *,
        user_id: Optional[UUID] = None
    ) -> Dict[str, Any]:
        """Obtém estatísticas de tarefas.
        
        Args:
            db: Sessão do banco de dados
            user_id: ID do usuário (opcional)
            
        Returns:
            Estatísticas das tarefas
        """
        base_query = select(Task)
        
        if user_id:
            base_query = base_query.where(Task.user_id == user_id)
        
        # Conta por status
        status_counts = {}
        for status in TaskStatus:
            count_query = select(func.count()).where(
                base_query.whereclause if base_query.whereclause is not None else True,
                Task.status == status
            )
            result = await db.execute(count_query)
            status_counts[status.value] = result.scalar()
        
        # Conta por tipo
        type_counts = {}
        for task_type in TaskType:
            count_query = select(func.count()).where(
                base_query.whereclause if base_query.whereclause is not None else True,
                Task.task_type == task_type
            )
            result = await db.execute(count_query)
            type_counts[task_type.value] = result.scalar()
        
        # Tempo médio de execução
        avg_duration_query = select(func.avg(Task.duration)).where(
            base_query.whereclause if base_query.whereclause is not None else True,
            Task.status == TaskStatus.COMPLETED
        )
        avg_duration_result = await db.execute(avg_duration_query)
        avg_duration = avg_duration_result.scalar() or 0
        
        return {
            "status_counts": status_counts,
            "type_counts": type_counts,
            "average_duration": avg_duration,
            "running_tasks": len(self._running_tasks)
        }
    
    async def _schedule_task(self, db: AsyncSession, task: Task) -> None:
        """Agenda execução da tarefa.
        
        Args:
            db: Sessão do banco de dados
            task: Tarefa para agendar
        """
        # TODO: Implementar agendamento de tarefas
        pass
    
    async def _execute_task(self, db: AsyncSession, task: Task) -> None:
        """Executa uma tarefa.
        
        Args:
            db: Sessão do banco de dados
            task: Tarefa para executar
        """
        # Verifica se handler existe para o tipo de tarefa
        if task.task_type not in self._task_handlers:
            task.status = TaskStatus.FAILED
            task.error_message = f"Handler não encontrado para tipo {task.task_type}"
            await db.commit()
            return
        
        # Atualiza status para executando
        task.status = TaskStatus.RUNNING
        task.started_at = datetime.utcnow()
        task.progress = 0
        await db.commit()
        
        # Cria e executa tarefa assíncrona
        async_task = asyncio.create_task(
            self._run_task_handler(db, task)
        )
        self._running_tasks[task.id] = async_task
        
        try:
            await async_task
        except asyncio.CancelledError:
            task.status = TaskStatus.CANCELLED
        except Exception as e:
            task.status = TaskStatus.FAILED
            task.error_message = str(e)
        finally:
            if task.id in self._running_tasks:
                del self._running_tasks[task.id]
            
            task.completed_at = datetime.utcnow()
            await db.commit()
    
    async def _run_task_handler(
        self,
        db: AsyncSession,
        task: Task
    ) -> None:
        """Executa o handler da tarefa.
        
        Args:
            db: Sessão do banco de dados
            task: Tarefa para executar
        """
        handler = self._task_handlers[task.task_type]
        await handler(db, task)
        
        # Marca como concluída se não houve erro
        if task.status == TaskStatus.RUNNING:
            task.status = TaskStatus.COMPLETED
            task.progress = 100
    
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
        return query.options(
            selectinload(Task.user),
            selectinload(Task.results),
            selectinload(Task.dependencies),
            selectinload(Task.dependents)
        )


class TaskResultService(BaseService[TaskResult, TaskResultCreate, TaskResultUpdate]):
    """Serviço para operações com resultados de tarefas."""
    
    def __init__(self):
        super().__init__(TaskResult)
    
    async def create_result(
        self,
        db: AsyncSession,
        *,
        result_in: TaskResultCreate
    ) -> TaskResult:
        """Cria um novo resultado de tarefa.
        
        Args:
            db: Sessão do banco de dados
            result_in: Dados do resultado
            
        Returns:
            Resultado criado
        """
        return await self.create(db, obj_in=result_in)
    
    async def get_by_task(
        self,
        db: AsyncSession,
        *,
        task_id: UUID
    ) -> List[TaskResult]:
        """Busca resultados por tarefa.
        
        Args:
            db: Sessão do banco de dados
            task_id: ID da tarefa
            
        Returns:
            Lista de resultados
        """
        query = (
            select(TaskResult)
            .where(TaskResult.task_id == task_id)
            .order_by(TaskResult.created_at)
        )
        
        result = await db.execute(query)
        return result.scalars().all()
    
    async def get_latest_result(
        self,
        db: AsyncSession,
        *,
        task_id: UUID
    ) -> Optional[TaskResult]:
        """Busca resultado mais recente da tarefa.
        
        Args:
            db: Sessão do banco de dados
            task_id: ID da tarefa
            
        Returns:
            Resultado mais recente ou None
        """
        query = (
            select(TaskResult)
            .where(TaskResult.task_id == task_id)
            .order_by(TaskResult.created_at.desc())
            .limit(1)
        )
        
        result = await db.execute(query)
        return result.scalar_one_or_none()
    
    def _add_relationship_loading(self, query: Select) -> Select:
        """Adiciona carregamento de relacionamentos.
        
        Args:
            query: Query base
            
        Returns:
            Query com relacionamentos
        """
        return query.options(selectinload(TaskResult.task))