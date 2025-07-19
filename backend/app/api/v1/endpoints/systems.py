"""Endpoints de gerenciamento de sistemas de videogame.

Fornece endpoints para:
- CRUD de sistemas (consoles, handhelds, etc.)
- Listagem e busca de sistemas
- Estatísticas por sistema
- Configurações de emulação
- Metadados e informações técnicas
"""

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_active_user, get_current_active_superuser
from app.models.user import User
from app.schemas.system import (
    SystemResponse,
    SystemCreate,
    SystemUpdate,
    SystemList,
    SystemStatsResponse,
    SystemWithGamesResponse,
    EmulatorConfig,
    EmulatorConfigUpdate
)
from app.schemas.base import PaginatedResponse
from app.services.system import SystemService
from app.utils.validation_utils import validate_pagination_params, validate_sort_params

router = APIRouter()


@router.get("/", response_model=PaginatedResponse[SystemList])
async def list_systems(
    skip: int = Query(0, ge=0, description="Número de registros para pular"),
    limit: int = Query(50, ge=1, le=100, description="Número máximo de registros"),
    search: Optional[str] = Query(None, description="Busca por nome ou fabricante"),
    manufacturer: Optional[str] = Query(None, description="Filtrar por fabricante"),
    generation: Optional[int] = Query(None, ge=1, le=10, description="Filtrar por geração"),
    system_type: Optional[str] = Query(None, description="Filtrar por tipo (console, handheld, arcade, computer)"),
    is_active: Optional[bool] = Query(None, description="Filtrar por status ativo"),
    sort_by: str = Query("name", description="Campo para ordenação"),
    sort_order: str = Query("asc", regex="^(asc|desc)$", description="Ordem da classificação"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Lista sistemas de videogame.
    
    Args:
        skip: Número de registros para pular
        limit: Limite de registros por página
        search: Termo de busca
        manufacturer: Filtro por fabricante
        generation: Filtro por geração
        system_type: Filtro por tipo de sistema
        is_active: Filtro por status ativo
        sort_by: Campo para ordenação
        sort_order: Ordem da classificação
        current_user: Usuário autenticado
        db: Sessão do banco de dados
        
    Returns:
        PaginatedResponse[SystemList]: Lista paginada de sistemas
    """
    # Valida parâmetros
    validate_pagination_params(skip, limit)
    validate_sort_params(sort_by, ["name", "manufacturer", "release_date", "generation"])
    
    system_service = SystemService(db)
    
    # Filtros
    filters = {}
    if manufacturer:
        filters["manufacturer"] = manufacturer
    if generation:
        filters["generation"] = generation
    if system_type:
        filters["system_type"] = system_type
    if is_active is not None:
        filters["is_active"] = is_active
    
    # Busca sistemas
    systems, total = await system_service.list_systems(
        skip=skip,
        limit=limit,
        search=search,
        filters=filters,
        sort_by=sort_by,
        sort_order=sort_order
    )
    
    return PaginatedResponse(
        items=[SystemList.model_validate(system) for system in systems],
        total=total,
        page=skip // limit + 1,
        per_page=limit,
        pages=(total + limit - 1) // limit
    )


@router.get("/manufacturers")
async def list_manufacturers(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Lista fabricantes únicos de sistemas.
    
    Args:
        current_user: Usuário autenticado
        db: Sessão do banco de dados
        
    Returns:
        List[str]: Lista de fabricantes
    """
    system_service = SystemService(db)
    manufacturers = await system_service.get_manufacturers()
    return {"manufacturers": manufacturers}


@router.get("/types")
async def list_system_types(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Lista tipos de sistemas disponíveis.
    
    Args:
        current_user: Usuário autenticado
        db: Sessão do banco de dados
        
    Returns:
        List[str]: Lista de tipos de sistemas
    """
    system_service = SystemService(db)
    types = await system_service.get_system_types()
    return {"types": types}


@router.get("/stats")
async def get_systems_stats(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Retorna estatísticas gerais dos sistemas.
    
    Args:
        current_user: Usuário autenticado
        db: Sessão do banco de dados
        
    Returns:
        dict: Estatísticas dos sistemas
    """
    system_service = SystemService(db)
    stats = await system_service.get_general_stats()
    return stats


@router.post("/", response_model=SystemResponse)
async def create_system(
    system_create: SystemCreate,
    current_user: User = Depends(get_current_active_superuser),
    db: AsyncSession = Depends(get_db)
):
    """Cria novo sistema (apenas superusers).
    
    Args:
        system_create: Dados do sistema para criação
        current_user: Usuário autenticado (deve ser superuser)
        db: Sessão do banco de dados
        
    Returns:
        SystemResponse: Dados do sistema criado
        
    Raises:
        HTTPException: Se dados inválidos ou sistema já existe
    """
    system_service = SystemService(db)
    
    # Verifica se sistema já existe
    existing_system = await system_service.get_by_name(system_create.name)
    if existing_system:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Sistema com este nome já existe"
        )
    
    # Cria sistema
    system_data = system_create.dict()
    system_data["created_by"] = current_user.id
    
    system = await system_service.create(system_data)
    return SystemResponse.model_validate(system)


@router.get("/{system_id}", response_model=SystemResponse)
async def get_system(
    system_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Retorna dados de um sistema específico.
    
    Args:
        system_id: ID do sistema
        current_user: Usuário autenticado
        db: Sessão do banco de dados
        
    Returns:
        SystemResponse: Dados do sistema
        
    Raises:
        HTTPException: Se sistema não encontrado
    """
    system_service = SystemService(db)
    system = await system_service.get_by_id(system_id)
    
    if not system:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sistema não encontrado"
        )
    
    return SystemResponse.model_validate(system)


@router.get("/{system_id}/with-games", response_model=SystemWithGamesResponse)
async def get_system_with_games(
    system_id: int,
    limit: int = Query(10, ge=1, le=50, description="Limite de jogos a retornar"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Retorna sistema com lista de jogos.
    
    Args:
        system_id: ID do sistema
        limit: Limite de jogos a retornar
        current_user: Usuário autenticado
        db: Sessão do banco de dados
        
    Returns:
        SystemWithGames: Dados do sistema com jogos
        
    Raises:
        HTTPException: Se sistema não encontrado
    """
    system_service = SystemService(db)
    system_with_games = await system_service.get_with_games(system_id, limit)
    
    if not system_with_games:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sistema não encontrado"
        )
    
    return SystemWithGamesResponse.model_validate(system_with_games)


@router.get("/{system_id}/stats", response_model=SystemStatsResponse)
async def get_system_stats(
    system_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Retorna estatísticas de um sistema específico.
    
    Args:
        system_id: ID do sistema
        current_user: Usuário autenticado
        db: Sessão do banco de dados
        
    Returns:
        SystemStats: Estatísticas do sistema
        
    Raises:
        HTTPException: Se sistema não encontrado
    """
    system_service = SystemService(db)
    
    # Verifica se sistema existe
    system = await system_service.get_by_id(system_id)
    if not system:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sistema não encontrado"
        )
    
    stats = await system_service.get_system_stats(system_id)
    return SystemStatsResponse(**stats)


@router.put("/{system_id}", response_model=SystemResponse)
async def update_system(
    system_id: int,
    system_update: SystemUpdate,
    current_user: User = Depends(get_current_active_superuser),
    db: AsyncSession = Depends(get_db)
):
    """Atualiza dados de um sistema específico (apenas superusers).
    
    Args:
        system_id: ID do sistema
        system_update: Dados para atualização
        current_user: Usuário autenticado (deve ser superuser)
        db: Sessão do banco de dados
        
    Returns:
        SystemResponse: Dados atualizados do sistema
        
    Raises:
        HTTPException: Se sistema não encontrado ou dados inválidos
    """
    system_service = SystemService(db)
    
    # Verifica se sistema existe
    system = await system_service.get_by_id(system_id)
    if not system:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sistema não encontrado"
        )
    
    # Validações
    update_data = system_update.dict(exclude_unset=True)
    
    if "name" in update_data:
        # Verifica se nome já existe (exceto o próprio sistema)
        existing_system = await system_service.get_by_name(update_data["name"])
        if existing_system and existing_system.id != system_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Sistema com este nome já existe"
            )
    
    # Atualiza sistema
    update_data["updated_by"] = current_user.id
    updated_system = await system_service.update(system_id, update_data)
    return SystemResponse.model_validate(updated_system)


@router.delete("/{system_id}")
async def delete_system(
    system_id: int,
    current_user: User = Depends(get_current_active_superuser),
    db: AsyncSession = Depends(get_db)
):
    """Deleta um sistema específico (apenas superusers).
    
    Args:
        system_id: ID do sistema
        current_user: Usuário autenticado (deve ser superuser)
        db: Sessão do banco de dados
        
    Returns:
        dict: Mensagem de confirmação
        
    Raises:
        HTTPException: Se sistema não encontrado ou possui jogos associados
    """
    system_service = SystemService(db)
    
    # Verifica se sistema existe
    system = await system_service.get_by_id(system_id)
    if not system:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sistema não encontrado"
        )
    
    # Verifica se possui jogos associados
    games_count = await system_service.count_games(system_id)
    if games_count > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Não é possível deletar sistema com {games_count} jogos associados"
        )
    
    # Deleta sistema
    await system_service.delete(system_id)
    
    return {"message": "Sistema deletado com sucesso"}


# Endpoints de configuração de emuladores

@router.get("/{system_id}/emulator-config", response_model=EmulatorConfig)
async def get_emulator_config(
    system_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Retorna configuração do emulador para o sistema.
    
    Args:
        system_id: ID do sistema
        current_user: Usuário autenticado
        db: Sessão do banco de dados
        
    Returns:
        EmulatorConfig: Configuração do emulador
        
    Raises:
        HTTPException: Se sistema não encontrado
    """
    system_service = SystemService(db)
    
    # Verifica se sistema existe
    system = await system_service.get_by_id(system_id)
    if not system:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sistema não encontrado"
        )
    
    config = await system_service.get_emulator_config(system_id)
    return EmulatorConfig.model_validate(config) if config else EmulatorConfig(system_id=system_id)


@router.put("/{system_id}/emulator-config", response_model=EmulatorConfig)
async def update_emulator_config(
    system_id: int,
    config_update: EmulatorConfigUpdate,
    current_user: User = Depends(get_current_active_superuser),
    db: AsyncSession = Depends(get_db)
):
    """Atualiza configuração do emulador para o sistema (apenas superusers).
    
    Args:
        system_id: ID do sistema
        config_update: Dados da configuração para atualização
        current_user: Usuário autenticado (deve ser superuser)
        db: Sessão do banco de dados
        
    Returns:
        EmulatorConfig: Configuração atualizada do emulador
        
    Raises:
        HTTPException: Se sistema não encontrado
    """
    system_service = SystemService(db)
    
    # Verifica se sistema existe
    system = await system_service.get_by_id(system_id)
    if not system:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sistema não encontrado"
        )
    
    # Atualiza ou cria configuração
    config_data = config_update.dict(exclude_unset=True)
    config_data["system_id"] = system_id
    config_data["updated_by"] = current_user.id
    
    config = await system_service.update_emulator_config(system_id, config_data)
    return EmulatorConfig.model_validate(config)


@router.post("/{system_id}/activate")
async def activate_system(
    system_id: int,
    current_user: User = Depends(get_current_active_superuser),
    db: AsyncSession = Depends(get_db)
):
    """Ativa um sistema específico (apenas superusers).
    
    Args:
        system_id: ID do sistema
        current_user: Usuário autenticado (deve ser superuser)
        db: Sessão do banco de dados
        
    Returns:
        dict: Mensagem de confirmação
        
    Raises:
        HTTPException: Se sistema não encontrado
    """
    system_service = SystemService(db)
    
    # Verifica se sistema existe
    system = await system_service.get_by_id(system_id)
    if not system:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sistema não encontrado"
        )
    
    # Ativa sistema
    await system_service.update(system_id, {"is_active": True, "updated_by": current_user.id})
    
    return {"message": "Sistema ativado com sucesso"}


@router.post("/{system_id}/deactivate")
async def deactivate_system(
    system_id: int,
    current_user: User = Depends(get_current_active_superuser),
    db: AsyncSession = Depends(get_db)
):
    """Desativa um sistema específico (apenas superusers).
    
    Args:
        system_id: ID do sistema
        current_user: Usuário autenticado (deve ser superuser)
        db: Sessão do banco de dados
        
    Returns:
        dict: Mensagem de confirmação
        
    Raises:
        HTTPException: Se sistema não encontrado
    """
    system_service = SystemService(db)
    
    # Verifica se sistema existe
    system = await system_service.get_by_id(system_id)
    if not system:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sistema não encontrado"
        )
    
    # Desativa sistema
    await system_service.update(system_id, {"is_active": False, "updated_by": current_user.id})
    
    return {"message": "Sistema desativado com sucesso"}