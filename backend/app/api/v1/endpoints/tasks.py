"""Endpoints de gerenciamento de tarefas assíncronas.

Fornece endpoints para:
- Monitoramento de tarefas em background
- Status e progresso de operações
- Cancelamento de tarefas
- Histórico de execuções
- Agendamento de tarefas
"""

from typing import List, Optional
from uuid import UUID
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_active_user, get_current_active_superuser
from app.models.user import User
from app.schemas.task import (
    TaskResponse,
    TaskCreate,
    TaskUpdate,
    TaskProgressUpdate,
    TaskStatsResponse,
    TaskResultResponse
)
from app.schemas.base import PaginatedResponse
from app.services.task import TaskService
from app.services.scheduler_service import SchedulerService
from app.utils.validation_utils import (
    validate_pagination_params,
    validate_sort_params,
    validate_search_query
)

router = APIRouter()


@router.get("/", response_model=PaginatedResponse[TaskResponse])
async def list_tasks(
    skip: int = Query(0, ge=0, description="Número de registros para pular"),
    limit: int = Query(50, ge=1, le=100, description="Número máximo de registros"),
    search: Optional[str] = Query(None, description="Busca por nome ou descrição da tarefa"),
    task_type: Optional[str] = Query(None, description="Filtrar por tipo de tarefa"),
    status_filter: Optional[str] = Query(None, description="Filtrar por status"),
    user_id: Optional[int] = Query(None, description="Filtrar por usuário (apenas superusers)"),
    date_from: Optional[datetime] = Query(None, description="Data inicial"),
    date_to: Optional[datetime] = Query(None, description="Data final"),
    sort_by: str = Query("created_at", description="Campo para ordenação"),
    sort_order: str = Query("desc", regex="^(asc|desc)$", description="Ordem da classificação"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Lista tarefas com filtros e paginação.
    
    Args:
        skip: Número de registros para pular
        limit: Limite de registros por página
        search: Termo de busca
        task_type: Filtro por tipo de tarefa
        status_filter: Filtro por status
        user_id: Filtro por usuário
        date_from: Data inicial
        date_to: Data final
        sort_by: Campo para ordenação
        sort_order: Ordem da classificação
        current_user: Usuário autenticado
        db: Sessão do banco de dados
        
    Returns:
        PaginatedResponse[TaskResponse]: Lista paginada de tarefas
    """
    # Valida parâmetros
    validate_pagination_params(skip, limit)
    validate_sort_params(sort_by, ["created_at", "updated_at", "started_at", "completed_at", "task_type", "status"])
    
    if search:
        validate_search_query(search)
    
    task_service = TaskService(db)
    
    # Filtros
    filters = {}
    if task_type:
        filters["task_type"] = task_type
    if status_filter:
        filters["status"] = status_filter
    if date_from:
        filters["date_from"] = date_from
    if date_to:
        filters["date_to"] = date_to
    
    # Usuários normais só veem suas próprias tarefas
    if not current_user.is_superuser:
        filters["user_id"] = current_user.id
    elif user_id:
        filters["user_id"] = user_id
    
    # Busca tarefas
    tasks, total = await task_service.list_tasks(
        skip=skip,
        limit=limit,
        search=search,
        filters=filters,
        sort_by=sort_by,
        sort_order=sort_order
    )
    
    return PaginatedResponse(
        items=[TaskResponse.model_validate(task) for task in tasks],
        total=total,
        page=skip // limit + 1,
        per_page=limit,
        pages=(total + limit - 1) // limit
    )


@router.get("/types")
async def list_task_types(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Lista tipos únicos de tarefas.
    
    Args:
        current_user: Usuário autenticado
        db: Sessão do banco de dados
        
    Returns:
        List[str]: Lista de tipos de tarefas
    """
    task_service = TaskService(db)
    
    # Usuários normais só veem tipos de suas tarefas
    user_filter = None if current_user.is_superuser else current_user.id
    
    types = await task_service.get_task_types(user_filter)
    return {"task_types": types}


@router.get("/stats")
async def get_tasks_stats(
    user_id: Optional[int] = Query(None, description="Filtrar por usuário (apenas superusers)"),
    days: int = Query(30, ge=1, le=365, description="Período em dias"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Retorna estatísticas das tarefas.
    
    Args:
        user_id: Filtro por usuário
        days: Período em dias
        current_user: Usuário autenticado
        db: Sessão do banco de dados
        
    Returns:
        dict: Estatísticas das tarefas
    """
    task_service = TaskService(db)
    
    # Usuários normais só veem suas próprias estatísticas
    if not current_user.is_superuser:
        user_id = current_user.id
    
    stats = await task_service.get_stats(user_id, days)
    return stats


@router.get("/active")
async def get_active_tasks(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Retorna tarefas ativas do usuário.
    
    Args:
        current_user: Usuário autenticado
        db: Sessão do banco de dados
        
    Returns:
        List[TaskResponse]: Lista de tarefas ativas
    """
    task_service = TaskService(db)
    
    # Usuários normais só veem suas próprias tarefas
    user_filter = None if current_user.is_superuser else current_user.id
    
    active_tasks = await task_service.get_active_tasks(user_filter)
    return {
        "active_tasks": [TaskResponse.model_validate(task) for task in active_tasks],
        "count": len(active_tasks)
    }


@router.post("/", response_model=TaskResponse)
async def create_task(
    task_create: TaskCreate,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Cria nova tarefa assíncrona.
    
    Args:
        task_create: Dados da tarefa para criação
        background_tasks: Tarefas em background
        current_user: Usuário autenticado
        db: Sessão do banco de dados
        
    Returns:
        TaskResponse: Dados da tarefa criada
        
    Raises:
        HTTPException: Se dados inválidos
    """
    task_service = TaskService(db)
    
    # Valida tipo de tarefa
    valid_types = [
        "rom_verification",
        "rom_extraction",
        "metadata_fetch",
        "file_scan",
        "database_backup",
        "cleanup",
        "import_dat",
        "batch_operation"
    ]
    
    if task_create.task_type not in valid_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Tipo de tarefa inválido. Opções: {', '.join(valid_types)}"
        )
    
    # Cria tarefa
    task_data = task_create.dict()
    task_data["user_id"] = current_user.id
    task_data["status"] = "pending"
    
    task = await task_service.create(task_data)
    
    # Agenda execução em background
    background_tasks.add_task(
        execute_task_background,
        task.id,
        task.task_type,
        task.parameters or {}
    )
    
    return TaskResponse.model_validate(task)


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Retorna dados detalhados de uma tarefa específica.
    
    Args:
        task_id: ID da tarefa
        current_user: Usuário autenticado
        db: Sessão do banco de dados
        
    Returns:
        TaskResponse: Dados detalhados da tarefa
        
    Raises:
        HTTPException: Se tarefa não encontrada ou sem permissão
    """
    task_service = TaskService(db)
    task = await task_service.get_detailed(task_id)
    
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tarefa não encontrada"
        )
    
    # Verifica permissão (apenas o criador ou superuser)
    if task.user_id != current_user.id and not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Sem permissão para acessar esta tarefa"
        )
    
    return TaskResponse.model_validate(task)


@router.get("/{task_id}/progress", response_model=TaskProgressUpdate)
async def get_task_progress(
    task_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Retorna progresso de uma tarefa específica.
    
    Args:
        task_id: ID da tarefa
        current_user: Usuário autenticado
        db: Sessão do banco de dados
        
    Returns:
        TaskProgressUpdate: Progresso da tarefa
        
    Raises:
        HTTPException: Se tarefa não encontrada ou sem permissão
    """
    task_service = TaskService(db)
    task = await task_service.get_by_id(task_id)
    
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tarefa não encontrada"
        )
    
    # Verifica permissão (apenas o criador ou superuser)
    if task.user_id != current_user.id and not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Sem permissão para acessar esta tarefa"
        )
    
    progress = await task_service.get_progress(task_id)
    return TaskProgressUpdate(**progress)


@router.get("/{task_id}/result", response_model=TaskResultResponse)
async def get_task_result(
    task_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Retorna resultado de uma tarefa específica.
    
    Args:
        task_id: ID da tarefa
        current_user: Usuário autenticado
        db: Sessão do banco de dados
        
    Returns:
        TaskResultResponse: Resultado da tarefa
        
    Raises:
        HTTPException: Se tarefa não encontrada, sem permissão ou não concluída
    """
    task_service = TaskService(db)
    task = await task_service.get_by_id(task_id)
    
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tarefa não encontrada"
        )
    
    # Verifica permissão (apenas o criador ou superuser)
    if task.user_id != current_user.id and not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Sem permissão para acessar esta tarefa"
        )
    
    # Verifica se tarefa foi concluída
    if task.status not in ["completed", "failed"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tarefa ainda não foi concluída"
        )
    
    result = await task_service.get_result(task_id)
    return TaskResultResponse(**result)


@router.put("/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: int,
    task_update: TaskUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Atualiza dados de uma tarefa específica.
    
    Args:
        task_id: ID da tarefa
        task_update: Dados para atualização
        current_user: Usuário autenticado
        db: Sessão do banco de dados
        
    Returns:
        TaskResponse: Dados atualizados da tarefa
        
    Raises:
        HTTPException: Se tarefa não encontrada, sem permissão ou em execução
    """
    task_service = TaskService(db)
    
    # Verifica se tarefa existe
    task = await task_service.get_by_id(task_id)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tarefa não encontrada"
        )
    
    # Verifica permissão (apenas o criador ou superuser)
    if task.user_id != current_user.id and not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Sem permissão para editar esta tarefa"
        )
    
    # Verifica se tarefa pode ser editada
    if task.status in ["running", "completed"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Não é possível editar tarefa em execução ou concluída"
        )
    
    # Atualiza tarefa
    update_data = task_update.dict(exclude_unset=True)
    updated_task = await task_service.update(task_id, update_data)
    return TaskResponse.model_validate(updated_task)


@router.post("/{task_id}/cancel")
async def cancel_task(
    task_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Cancela uma tarefa específica.
    
    Args:
        task_id: ID da tarefa
        current_user: Usuário autenticado
        db: Sessão do banco de dados
        
    Returns:
        dict: Mensagem de confirmação
        
    Raises:
        HTTPException: Se tarefa não encontrada, sem permissão ou não cancelável
    """
    task_service = TaskService(db)
    
    # Verifica se tarefa existe
    task = await task_service.get_by_id(task_id)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tarefa não encontrada"
        )
    
    # Verifica permissão (apenas o criador ou superuser)
    if task.user_id != current_user.id and not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Sem permissão para cancelar esta tarefa"
        )
    
    # Verifica se tarefa pode ser cancelada
    if task.status in ["completed", "failed", "cancelled"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tarefa não pode ser cancelada"
        )
    
    # Cancela tarefa
    await task_service.cancel(task_id)
    
    return {"message": "Tarefa cancelada com sucesso"}


@router.post("/{task_id}/retry")
async def retry_task(
    task_id: int,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Reexecuta uma tarefa falhada.
    
    Args:
        task_id: ID da tarefa
        background_tasks: Tarefas em background
        current_user: Usuário autenticado
        db: Sessão do banco de dados
        
    Returns:
        dict: Mensagem de confirmação
        
    Raises:
        HTTPException: Se tarefa não encontrada, sem permissão ou não falhada
    """
    task_service = TaskService(db)
    
    # Verifica se tarefa existe
    task = await task_service.get_by_id(task_id)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tarefa não encontrada"
        )
    
    # Verifica permissão (apenas o criador ou superuser)
    if task.user_id != current_user.id and not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Sem permissão para reexecutar esta tarefa"
        )
    
    # Verifica se tarefa pode ser reexecutada
    if task.status != "failed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Apenas tarefas falhadas podem ser reexecutadas"
        )
    
    # Reseta status da tarefa
    await task_service.reset_for_retry(task_id)
    
    # Agenda nova execução
    background_tasks.add_task(
        execute_task_background,
        task_id,
        task.task_type,
        task.parameters or {}
    )
    
    return {"message": "Tarefa reagendada para execução"}


@router.delete("/{task_id}")
async def delete_task(
    task_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Deleta uma tarefa específica.
    
    Args:
        task_id: ID da tarefa
        current_user: Usuário autenticado
        db: Sessão do banco de dados
        
    Returns:
        dict: Mensagem de confirmação
        
    Raises:
        HTTPException: Se tarefa não encontrada, sem permissão ou em execução
    """
    task_service = TaskService(db)
    
    # Verifica se tarefa existe
    task = await task_service.get_by_id(task_id)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tarefa não encontrada"
        )
    
    # Verifica permissão (apenas o criador ou superuser)
    if task.user_id != current_user.id and not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Sem permissão para deletar esta tarefa"
        )
    
    # Verifica se tarefa pode ser deletada
    if task.status == "running":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Não é possível deletar tarefa em execução"
        )
    
    # Deleta tarefa
    await task_service.delete(task_id)
    
    return {"message": "Tarefa deletada com sucesso"}


# Endpoints de agendamento

@router.get("/scheduled/")
async def list_scheduled_tasks(
    current_user: User = Depends(get_current_active_superuser),
    db: AsyncSession = Depends(get_db)
):
    """Lista tarefas agendadas (apenas superusers).
    
    Args:
        current_user: Usuário autenticado (deve ser superuser)
        db: Sessão do banco de dados
        
    Returns:
        List[dict]: Lista de tarefas agendadas
    """
    scheduler_service = SchedulerService(db)
    scheduled_tasks = await scheduler_service.list_scheduled()
    return [task.__dict__ for task in scheduled_tasks]


@router.post("/schedule")
async def schedule_task(
    schedule_data: dict,
    current_user: User = Depends(get_current_active_superuser),
    db: AsyncSession = Depends(get_db)
):
    """Agenda nova tarefa recorrente (apenas superusers).
    
    Args:
        schedule_data: Dados do agendamento
        current_user: Usuário autenticado (deve ser superuser)
        db: Sessão do banco de dados
        
    Returns:
        dict: Dados do agendamento criado
        
    Raises:
        HTTPException: Se dados inválidos
    """
    scheduler_service = SchedulerService(db)
    
    # Valida dados do agendamento
    if not schedule_data.cron_expression and not schedule_data.interval_seconds:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Expressão cron ou intervalo em segundos é obrigatório"
        )
    
    # Cria agendamento
    schedule_dict = schedule_data.dict()
    schedule_dict["created_by"] = current_user.id
    
    scheduled_task = await scheduler_service.create_schedule(schedule_dict)
    return scheduled_task.__dict__


@router.delete("/schedule/{schedule_id}")
async def delete_scheduled_task(
    schedule_id: int,
    current_user: User = Depends(get_current_active_superuser),
    db: AsyncSession = Depends(get_db)
):
    """Remove agendamento de tarefa (apenas superusers).
    
    Args:
        schedule_id: ID do agendamento
        current_user: Usuário autenticado (deve ser superuser)
        db: Sessão do banco de dados
        
    Returns:
        dict: Mensagem de confirmação
        
    Raises:
        HTTPException: Se agendamento não encontrado
    """
    scheduler_service = SchedulerService(db)
    
    # Verifica se agendamento existe
    schedule = await scheduler_service.get_by_id(schedule_id)
    if not schedule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agendamento não encontrado"
        )
    
    # Remove agendamento
    await scheduler_service.delete_schedule(schedule_id)
    
    return {"message": "Agendamento removido com sucesso"}


# Endpoints de limpeza

@router.post("/cleanup")
async def cleanup_old_tasks(
    days: int = Query(30, ge=1, le=365, description="Dias para manter tarefas"),
    dry_run: bool = Query(True, description="Apenas simular limpeza"),
    current_user: User = Depends(get_current_active_superuser),
    db: AsyncSession = Depends(get_db)
):
    """Remove tarefas antigas (apenas superusers).
    
    Args:
        days: Dias para manter tarefas
        dry_run: Apenas simular limpeza
        current_user: Usuário autenticado (deve ser superuser)
        db: Sessão do banco de dados
        
    Returns:
        dict: Resultado da limpeza
    """
    task_service = TaskService(db)
    
    # Calcula data limite
    cutoff_date = datetime.utcnow() - timedelta(days=days)
    
    # Executa limpeza
    result = await task_service.cleanup_old_tasks(cutoff_date, dry_run)
    
    return {
        "message": "Limpeza concluída" if not dry_run else "Simulação de limpeza concluída",
        "cutoff_date": cutoff_date.isoformat(),
        "tasks_to_delete": result["count"],
        "dry_run": dry_run
    }


# Função auxiliar para execução de tarefas em background

async def execute_task_background(task_id: int, task_type: str, parameters: dict):
    """Executa tarefa em background.
    
    Args:
        task_id: ID da tarefa
        task_type: Tipo da tarefa
        parameters: Parâmetros da tarefa
    """
    try:
        # Implementar execução baseada no tipo
        if task_type == "rom_verification":
            # Implementar verificação de ROM
            pass
        elif task_type == "rom_extraction":
            # Implementar extração de ROM
            pass
        elif task_type == "metadata_fetch":
            # Implementar busca de metadados
            pass
        elif task_type == "file_scan":
            # Implementar escaneamento de arquivos
            pass
        elif task_type == "database_backup":
            # Implementar backup do banco
            pass
        elif task_type == "cleanup":
            # Implementar limpeza
            pass
        elif task_type == "import_dat":
            # Implementar importação DAT
            pass
        elif task_type == "batch_operation":
            # Implementar operação em lote
            pass
        else:
            raise ValueError(f"Tipo de tarefa não suportado: {task_type}")
            
    except Exception as e:
        # Log do erro e marca tarefa como falhada
        pass