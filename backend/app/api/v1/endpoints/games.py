"""Endpoints de gerenciamento de jogos.

Fornece endpoints para:
- CRUD de jogos
- Listagem e busca de jogos
- Metadados e informações detalhadas
- Relacionamentos com ROMs
- Estatísticas e análises
- Importação de dados externos
"""

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_active_user, get_current_active_superuser
from app.models.user import User
from app.schemas.game import (
    GameResponse,
    GameCreate,
    GameUpdate,
    GameList,
    GameDetail,
    GameStatsResponse,
    GameSearch,
    GameMetadataResponse,
    GameMetadataUpdate
)
from app.schemas.base import PaginatedResponse
from app.services.game import GameService
from app.services.processing import MetadataService
from app.utils.validation_utils import (
    validate_pagination_params,
    validate_sort_params,
    validate_search_query
)

router = APIRouter()


@router.get("/", response_model=PaginatedResponse[GameList])
async def list_games(
    skip: int = Query(0, ge=0, description="Número de registros para pular"),
    limit: int = Query(50, ge=1, le=100, description="Número máximo de registros"),
    search: Optional[str] = Query(None, description="Busca por título, desenvolvedor ou publisher"),
    system_id: Optional[int] = Query(None, description="Filtrar por sistema"),
    genre: Optional[str] = Query(None, description="Filtrar por gênero"),
    year: Optional[int] = Query(None, ge=1970, le=2030, description="Filtrar por ano de lançamento"),
    developer: Optional[str] = Query(None, description="Filtrar por desenvolvedor"),
    publisher: Optional[str] = Query(None, description="Filtrar por publisher"),
    region: Optional[str] = Query(None, description="Filtrar por região"),
    has_rom: Optional[bool] = Query(None, description="Filtrar jogos com/sem ROM"),
    sort_by: str = Query("title", description="Campo para ordenação"),
    sort_order: str = Query("asc", regex="^(asc|desc)$", description="Ordem da classificação"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Lista jogos com filtros e paginação.
    
    Args:
        skip: Número de registros para pular
        limit: Limite de registros por página
        search: Termo de busca
        system_id: Filtro por sistema
        genre: Filtro por gênero
        year: Filtro por ano
        developer: Filtro por desenvolvedor
        publisher: Filtro por publisher
        region: Filtro por região
        has_rom: Filtro por presença de ROM
        sort_by: Campo para ordenação
        sort_order: Ordem da classificação
        current_user: Usuário autenticado
        db: Sessão do banco de dados
        
    Returns:
        PaginatedResponse[GameList]: Lista paginada de jogos
    """
    # Valida parâmetros
    validate_pagination_params(skip, limit)
    validate_sort_params(sort_by, ["title", "release_date", "developer", "publisher", "created_at"])
    
    if search:
        validate_search_query(search)
    
    game_service = GameService(db)
    
    # Busca jogos usando método simples
    from sqlalchemy import select, func, desc, asc
    from sqlalchemy.orm import selectinload
    
    # Query base
    query = select(Game).options(
        selectinload(Game.system),
        selectinload(Game.genres)
    )
    
    # Aplica filtros
    if system_id:
        query = query.where(Game.system_id == system_id)
    if search:
        query = query.where(Game.name.ilike(f"%{search}%"))
    
    # Conta total
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar()
    
    # Aplica ordenação
    if sort_by == "name":
        if sort_order == "desc":
            query = query.order_by(desc(Game.name))
        else:
            query = query.order_by(asc(Game.name))
    else:
        query = query.order_by(Game.created_at.desc())
    
    # Aplica paginação
    query = query.offset(skip).limit(limit)
    
    # Executa query
    result = await db.execute(query)
    games = result.scalars().all()
    
    # Calcula informações de paginação
    pages = (total + limit - 1) // limit
    current_page = skip // limit + 1
    
    return PaginatedResponse(
        items=[GameList.model_validate(game) for game in games],
        total=total,
        page=current_page,
        per_page=limit,
        pages=pages
    )


@router.get("/search", response_model=List[GameSearch])
async def search_games(
    q: str = Query(..., min_length=2, description="Termo de busca"),
    limit: int = Query(20, ge=1, le=50, description="Limite de resultados"),
    system_id: Optional[int] = Query(None, description="Filtrar por sistema"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Busca rápida de jogos para autocomplete.
    
    Args:
        q: Termo de busca
        limit: Limite de resultados
        system_id: Filtro por sistema
        current_user: Usuário autenticado
        db: Sessão do banco de dados
        
    Returns:
        List[GameSearch]: Lista de jogos encontrados
    """
    validate_search_query(q)
    
    game_service = GameService(db)
    games = await game_service.search_games(q, limit, system_id)
    
    return [GameSearch.model_validate(game) for game in games]


@router.get("/genres")
async def list_genres(
    system_id: Optional[int] = Query(None, description="Filtrar por sistema"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Lista gêneros únicos de jogos.
    
    Args:
        system_id: Filtro por sistema
        current_user: Usuário autenticado
        db: Sessão do banco de dados
        
    Returns:
        List[str]: Lista de gêneros
    """
    game_service = GameService(db)
    genres = await game_service.get_genres(system_id)
    return {"genres": genres}


@router.get("/developers")
async def list_developers(
    system_id: Optional[int] = Query(None, description="Filtrar por sistema"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Lista desenvolvedores únicos de jogos.
    
    Args:
        system_id: Filtro por sistema
        current_user: Usuário autenticado
        db: Sessão do banco de dados
        
    Returns:
        List[str]: Lista de desenvolvedores
    """
    game_service = GameService(db)
    developers = await game_service.get_developers(system_id)
    return {"developers": developers}


@router.get("/publishers")
async def list_publishers(
    system_id: Optional[int] = Query(None, description="Filtrar por sistema"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Lista publishers únicos de jogos.
    
    Args:
        system_id: Filtro por sistema
        current_user: Usuário autenticado
        db: Sessão do banco de dados
        
    Returns:
        List[str]: Lista de publishers
    """
    game_service = GameService(db)
    publishers = await game_service.get_publishers(system_id)
    return {"publishers": publishers}


@router.get("/stats")
async def get_games_stats(
    system_id: Optional[int] = Query(None, description="Filtrar por sistema"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Retorna estatísticas gerais dos jogos.
    
    Args:
        system_id: Filtro por sistema
        current_user: Usuário autenticado
        db: Sessão do banco de dados
        
    Returns:
        dict: Estatísticas dos jogos
    """
    game_service = GameService(db)
    stats = await game_service.get_general_stats(system_id)
    return stats


@router.post("/", response_model=GameResponse)
async def create_game(
    game_create: GameCreate,
    current_user: User = Depends(get_current_active_superuser),
    db: AsyncSession = Depends(get_db)
):
    """Cria novo jogo (apenas superusers).
    
    Args:
        game_create: Dados do jogo para criação
        current_user: Usuário autenticado (deve ser superuser)
        db: Sessão do banco de dados
        
    Returns:
        GameResponse: Dados do jogo criado
        
    Raises:
        HTTPException: Se dados inválidos
    """
    game_service = GameService(db)
    
    # Verifica se sistema existe
    from app.services.system import SystemService
    system_service = SystemService(db)
    system = await system_service.get_by_id(game_create.system_id)
    if not system:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Sistema não encontrado"
        )
    
    # Cria jogo
    game_data = game_create.dict()
    game_data["created_by"] = current_user.id
    
    game = await game_service.create(game_data)
    return GameResponse.model_validate(game)


@router.get("/{game_id}", response_model=GameDetail)
async def get_game(
    game_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Retorna dados detalhados de um jogo específico.
    
    Args:
        game_id: ID do jogo
        current_user: Usuário autenticado
        db: Sessão do banco de dados
        
    Returns:
        GameDetail: Dados detalhados do jogo
        
    Raises:
        HTTPException: Se jogo não encontrado
    """
    game_service = GameService(db)
    game = await game_service.get_detailed(game_id)
    
    if not game:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Jogo não encontrado"
        )
    
    return GameDetail.model_validate(game)


@router.get("/{game_id}/stats", response_model=GameStatsResponse)
async def get_game_stats(
    game_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Retorna estatísticas de um jogo específico.
    
    Args:
        game_id: ID do jogo
        current_user: Usuário autenticado
        db: Sessão do banco de dados
        
    Returns:
        GameStats: Estatísticas do jogo
        
    Raises:
        HTTPException: Se jogo não encontrado
    """
    game_service = GameService(db)
    
    # Verifica se jogo existe
    game = await game_service.get_by_id(game_id)
    if not game:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Jogo não encontrado"
        )
    
    stats = await game_service.get_game_stats(game_id)
    return GameStatsResponse(**stats)


@router.put("/{game_id}", response_model=GameResponse)
async def update_game(
    game_id: int,
    game_update: GameUpdate,
    current_user: User = Depends(get_current_active_superuser),
    db: AsyncSession = Depends(get_db)
):
    """Atualiza dados de um jogo específico (apenas superusers).
    
    Args:
        game_id: ID do jogo
        game_update: Dados para atualização
        current_user: Usuário autenticado (deve ser superuser)
        db: Sessão do banco de dados
        
    Returns:
        GameResponse: Dados atualizados do jogo
        
    Raises:
        HTTPException: Se jogo não encontrado ou dados inválidos
    """
    game_service = GameService(db)
    
    # Verifica se jogo existe
    game = await game_service.get_by_id(game_id)
    if not game:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Jogo não encontrado"
        )
    
    # Validações
    update_data = game_update.dict(exclude_unset=True)
    
    if "system_id" in update_data:
        # Verifica se sistema existe
        from app.services.system import SystemService
        system_service = SystemService(db)
        system = await system_service.get_by_id(update_data["system_id"])
        if not system:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Sistema não encontrado"
            )
    
    # Atualiza jogo
    update_data["updated_by"] = current_user.id
    updated_game = await game_service.update(game_id, update_data)
    return GameResponse.model_validate(updated_game)


@router.delete("/{game_id}")
async def delete_game(
    game_id: int,
    current_user: User = Depends(get_current_active_superuser),
    db: AsyncSession = Depends(get_db)
):
    """Deleta um jogo específico (apenas superusers).
    
    Args:
        game_id: ID do jogo
        current_user: Usuário autenticado (deve ser superuser)
        db: Sessão do banco de dados
        
    Returns:
        dict: Mensagem de confirmação
        
    Raises:
        HTTPException: Se jogo não encontrado ou possui ROMs associadas
    """
    game_service = GameService(db)
    
    # Verifica se jogo existe
    game = await game_service.get_by_id(game_id)
    if not game:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Jogo não encontrado"
        )
    
    # Verifica se possui ROMs associadas
    roms_count = await game_service.count_roms(game_id)
    if roms_count > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Não é possível deletar jogo com {roms_count} ROMs associadas"
        )
    
    # Deleta jogo
    await game_service.delete(game_id)
    
    return {"message": "Jogo deletado com sucesso"}


# Endpoints de metadados

@router.get("/{game_id}/metadata", response_model=GameMetadataResponse)
async def get_game_metadata(
    game_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Retorna metadados de um jogo específico.
    
    Args:
        game_id: ID do jogo
        current_user: Usuário autenticado
        db: Sessão do banco de dados
        
    Returns:
        GameMetadata: Metadados do jogo
        
    Raises:
        HTTPException: Se jogo não encontrado
    """
    game_service = GameService(db)
    
    # Verifica se jogo existe
    game = await game_service.get_by_id(game_id)
    if not game:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Jogo não encontrado"
        )
    
    metadata = await game_service.get_metadata(game_id)
    return GameMetadataResponse.model_validate(metadata) if metadata else GameMetadataResponse(game_id=game_id)


@router.put("/{game_id}/metadata", response_model=GameMetadataResponse)
async def update_game_metadata(
    game_id: int,
    metadata_update: GameMetadataUpdate,
    current_user: User = Depends(get_current_active_superuser),
    db: AsyncSession = Depends(get_db)
):
    """Atualiza metadados de um jogo específico (apenas superusers).
    
    Args:
        game_id: ID do jogo
        metadata_update: Dados dos metadados para atualização
        current_user: Usuário autenticado (deve ser superuser)
        db: Sessão do banco de dados
        
    Returns:
        GameMetadata: Metadados atualizados do jogo
        
    Raises:
        HTTPException: Se jogo não encontrado
    """
    game_service = GameService(db)
    
    # Verifica se jogo existe
    game = await game_service.get_by_id(game_id)
    if not game:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Jogo não encontrado"
        )
    
    # Atualiza ou cria metadados
    metadata_data = metadata_update.dict(exclude_unset=True)
    metadata_data["game_id"] = game_id
    metadata_data["updated_by"] = current_user.id
    
    metadata = await game_service.update_metadata(game_id, metadata_data)
    return GameMetadataResponse.model_validate(metadata)


@router.post("/{game_id}/fetch-metadata")
async def fetch_external_metadata(
    game_id: int,
    source: str = Query("igdb", description="Fonte dos metadados (igdb, mobygames)"),
    current_user: User = Depends(get_current_active_superuser),
    db: AsyncSession = Depends(get_db)
):
    """Busca metadados externos para um jogo (apenas superusers).
    
    Args:
        game_id: ID do jogo
        source: Fonte dos metadados
        current_user: Usuário autenticado (deve ser superuser)
        db: Sessão do banco de dados
        
    Returns:
        dict: Status da operação
        
    Raises:
        HTTPException: Se jogo não encontrado ou fonte inválida
    """
    game_service = GameService(db)
    
    # Verifica se jogo existe
    game = await game_service.get_by_id(game_id)
    if not game:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Jogo não encontrado"
        )
    
    # Valida fonte
    valid_sources = ["igdb", "mobygames"]
    if source not in valid_sources:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Fonte inválida. Opções: {', '.join(valid_sources)}"
        )
    
    # Busca metadados externos
    metadata_service = MetadataService(db)
    
    try:
        result = await metadata_service.fetch_external_metadata(game_id, source)
        return {
            "message": "Metadados buscados com sucesso",
            "source": source,
            "found": result.get("found", False),
            "updated_fields": result.get("updated_fields", [])
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao buscar metadados: {str(e)}"
        )


@router.post("/import-dat")
async def import_dat_file(
    file: UploadFile = File(...),
    system_id: int = Query(..., description="ID do sistema para importação"),
    overwrite: bool = Query(False, description="Sobrescrever jogos existentes"),
    current_user: User = Depends(get_current_active_superuser),
    db: AsyncSession = Depends(get_db)
):
    """Importa jogos de arquivo DAT (apenas superusers).
    
    Args:
        file: Arquivo DAT para importação
        system_id: ID do sistema
        overwrite: Se deve sobrescrever jogos existentes
        current_user: Usuário autenticado (deve ser superuser)
        db: Sessão do banco de dados
        
    Returns:
        dict: Resultado da importação
        
    Raises:
        HTTPException: Se arquivo inválido ou sistema não encontrado
    """
    # Verifica se sistema existe
    from app.services.system import SystemService
    system_service = SystemService(db)
    system = await system_service.get_by_id(system_id)
    if not system:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Sistema não encontrado"
        )
    
    # Valida arquivo
    if not file.filename.lower().endswith(('.dat', '.xml')):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Arquivo deve ser .dat ou .xml"
        )
    
    try:
        # Lê conteúdo do arquivo
        content = await file.read()
        
        # Importa dados
        from app.services.processing import ImportService
        import_service = ImportService(db)
        
        result = await import_service.import_dat_file(
            content=content,
            system_id=system_id,
            overwrite=overwrite,
            user_id=current_user.id
        )
        
        return {
            "message": "Importação concluída",
            "imported": result.get("imported", 0),
            "updated": result.get("updated", 0),
            "skipped": result.get("skipped", 0),
            "errors": result.get("errors", [])
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro na importação: {str(e)}"
        )