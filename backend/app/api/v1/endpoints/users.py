"""Endpoints de gerenciamento de usuários.

Fornece endpoints para:
- CRUD de usuários
- Perfil do usuário atual
- Atualização de dados pessoais
- Gerenciamento de permissões
- Listagem e busca de usuários
"""

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import (
    get_current_user,
    get_current_active_superuser,
    get_current_active_user
)
from app.models.user import User
from app.schemas.user import (
    UserResponse,
    UserCreate,
    UserUpdate,
    UserUpdateMe,
    UserList,
    UserStatsResponse
)
from app.schemas.base import PaginatedResponse
from app.services.user import UserService
from app.utils.validation_utils import (
    validate_email_address,
    validate_password_strength,
    validate_pagination_params
)

router = APIRouter()


@router.get("/me", response_model=UserResponse)
async def get_current_user_profile(
    current_user: User = Depends(get_current_active_user)
):
    """Retorna perfil do usuário atual.
    
    Args:
        current_user: Usuário autenticado
        
    Returns:
        UserResponse: Dados do usuário atual
    """
    return UserResponse.model_validate(current_user)


@router.put("/me", response_model=UserResponse)
async def update_current_user_profile(
    user_update: UserUpdateMe,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Atualiza perfil do usuário atual.
    
    Args:
        user_update: Dados para atualização
        current_user: Usuário autenticado
        db: Sessão do banco de dados
        
    Returns:
        UserResponse: Dados atualizados do usuário
        
    Raises:
        HTTPException: Se dados inválidos
    """
    user_service = UserService(db)
    
    # Validações
    update_data = user_update.dict(exclude_unset=True)
    
    if "email" in update_data:
        if not validate_email_address(update_data["email"]):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email inválido"
            )
        
        # Verifica se email já existe (exceto o próprio usuário)
        existing_user = await user_service.get_by_email(update_data["email"])
        if existing_user and existing_user.id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email já está em uso"
            )
    
    if "username" in update_data:
        # Verifica se username já existe (exceto o próprio usuário)
        existing_user = await user_service.get_by_username(update_data["username"])
        if existing_user and existing_user.id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Nome de usuário já está em uso"
            )
    
    if "password" in update_data:
        password_validation = validate_password_strength(update_data["password"])
        if not password_validation["valid"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Senha inválida: {', '.join(password_validation['errors'])}"
            )
        
        # Hash da nova senha
        from app.core.security import get_password_hash
        update_data["hashed_password"] = get_password_hash(update_data["password"])
        del update_data["password"]
    
    # Atualiza usuário
    updated_user = await user_service.update(current_user.id, update_data)
    return UserResponse.model_validate(updated_user)


@router.delete("/me")
async def delete_current_user_account(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Deleta conta do usuário atual.
    
    Args:
        current_user: Usuário autenticado
        db: Sessão do banco de dados
        
    Returns:
        dict: Mensagem de confirmação
    """
    user_service = UserService(db)
    
    # Soft delete - marca como inativo
    await user_service.update(current_user.id, {"is_active": False})
    
    return {"message": "Conta deletada com sucesso"}


@router.get("/stats", response_model=UserStatsResponse)
async def get_current_user_stats(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Retorna estatísticas do usuário atual.
    
    Args:
        current_user: Usuário autenticado
        db: Sessão do banco de dados
        
    Returns:
        UserStats: Estatísticas do usuário
    """
    user_service = UserService(db)
    stats = await user_service.get_user_stats(current_user.id)
    return UserStatsResponse(**stats)


# Endpoints administrativos (requerem superuser)

@router.get("/", response_model=PaginatedResponse[UserList])
async def list_users(
    skip: int = Query(0, ge=0, description="Número de registros para pular"),
    limit: int = Query(50, ge=1, le=100, description="Número máximo de registros"),
    search: Optional[str] = Query(None, description="Busca por nome, email ou username"),
    is_active: Optional[bool] = Query(None, description="Filtrar por status ativo"),
    is_superuser: Optional[bool] = Query(None, description="Filtrar por superusuários"),
    current_user: User = Depends(get_current_active_superuser),
    db: AsyncSession = Depends(get_db)
):
    """Lista usuários (apenas superusers).
    
    Args:
        skip: Número de registros para pular
        limit: Limite de registros por página
        search: Termo de busca
        is_active: Filtro por status ativo
        is_superuser: Filtro por superusuários
        current_user: Usuário autenticado (deve ser superuser)
        db: Sessão do banco de dados
        
    Returns:
        PaginatedResponse[UserList]: Lista paginada de usuários
    """
    # Valida parâmetros de paginação
    validate_pagination_params(skip, limit)
    
    user_service = UserService(db)
    
    # Filtros
    filters = {}
    if is_active is not None:
        filters["is_active"] = is_active
    if is_superuser is not None:
        filters["is_superuser"] = is_superuser
    
    # Busca usuários
    users, total = await user_service.list_users(
        skip=skip,
        limit=limit,
        search=search,
        filters=filters
    )
    
    return PaginatedResponse(
        items=[UserList.model_validate(user) for user in users],
        total=total,
        page=skip // limit + 1,
        per_page=limit,
        pages=(total + limit - 1) // limit
    )


@router.post("/", response_model=UserResponse)
async def create_user(
    user_create: UserCreate,
    current_user: User = Depends(get_current_active_superuser),
    db: AsyncSession = Depends(get_db)
):
    """Cria novo usuário (apenas superusers).
    
    Args:
        user_create: Dados do usuário para criação
        current_user: Usuário autenticado (deve ser superuser)
        db: Sessão do banco de dados
        
    Returns:
        UserResponse: Dados do usuário criado
        
    Raises:
        HTTPException: Se dados inválidos ou usuário já existe
    """
    user_service = UserService(db)
    
    # Validações
    if not validate_email_address(user_create.email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email inválido"
        )
    
    if user_create.password:
        password_validation = validate_password_strength(user_create.password)
        if not password_validation["valid"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Senha inválida: {', '.join(password_validation['errors'])}"
            )
    
    # Verifica se usuário já existe
    existing_user = await user_service.get_by_email(user_create.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email já cadastrado"
        )
    
    existing_username = await user_service.get_by_username(user_create.username)
    if existing_username:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nome de usuário já existe"
        )
    
    # Cria usuário
    from app.core.security import get_password_hash
    
    user_data = user_create.dict()
    if user_data.get("password"):
        user_data["hashed_password"] = get_password_hash(user_data["password"])
        del user_data["password"]
    
    user = await user_service.create(user_data)
    return UserResponse.model_validate(user)


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: int,
    current_user: User = Depends(get_current_active_superuser),
    db: AsyncSession = Depends(get_db)
):
    """Retorna dados de um usuário específico (apenas superusers).
    
    Args:
        user_id: ID do usuário
        current_user: Usuário autenticado (deve ser superuser)
        db: Sessão do banco de dados
        
    Returns:
        UserResponse: Dados do usuário
        
    Raises:
        HTTPException: Se usuário não encontrado
    """
    user_service = UserService(db)
    user = await user_service.get_by_id(user_id)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuário não encontrado"
        )
    
    return UserResponse.from_orm(user)


@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    user_update: UserUpdate,
    current_user: User = Depends(get_current_active_superuser),
    db: AsyncSession = Depends(get_db)
):
    """Atualiza dados de um usuário específico (apenas superusers).
    
    Args:
        user_id: ID do usuário
        user_update: Dados para atualização
        current_user: Usuário autenticado (deve ser superuser)
        db: Sessão do banco de dados
        
    Returns:
        UserResponse: Dados atualizados do usuário
        
    Raises:
        HTTPException: Se usuário não encontrado ou dados inválidos
    """
    user_service = UserService(db)
    
    # Verifica se usuário existe
    user = await user_service.get_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuário não encontrado"
        )
    
    # Validações
    update_data = user_update.dict(exclude_unset=True)
    
    if "email" in update_data:
        if not validate_email_address(update_data["email"]):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email inválido"
            )
        
        # Verifica se email já existe (exceto o próprio usuário)
        existing_user = await user_service.get_by_email(update_data["email"])
        if existing_user and existing_user.id != user_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email já está em uso"
            )
    
    if "username" in update_data:
        # Verifica se username já existe (exceto o próprio usuário)
        existing_user = await user_service.get_by_username(update_data["username"])
        if existing_user and existing_user.id != user_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Nome de usuário já está em uso"
            )
    
    if "password" in update_data:
        password_validation = validate_password_strength(update_data["password"])
        if not password_validation["valid"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Senha inválida: {', '.join(password_validation['errors'])}"
            )
        
        # Hash da nova senha
        from app.core.security import get_password_hash
        update_data["hashed_password"] = get_password_hash(update_data["password"])
        del update_data["password"]
    
    # Atualiza usuário
    updated_user = await user_service.update(user_id, update_data)
    return UserResponse.model_validate(updated_user)


@router.delete("/{user_id}")
async def delete_user(
    user_id: int,
    current_user: User = Depends(get_current_active_superuser),
    db: AsyncSession = Depends(get_db)
):
    """Deleta um usuário específico (apenas superusers).
    
    Args:
        user_id: ID do usuário
        current_user: Usuário autenticado (deve ser superuser)
        db: Sessão do banco de dados
        
    Returns:
        dict: Mensagem de confirmação
        
    Raises:
        HTTPException: Se usuário não encontrado ou tentativa de auto-deleção
    """
    user_service = UserService(db)
    
    # Verifica se usuário existe
    user = await user_service.get_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuário não encontrado"
        )
    
    # Impede auto-deleção
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Não é possível deletar sua própria conta"
        )
    
    # Soft delete - marca como inativo
    await user_service.update(user_id, {"is_active": False})
    
    return {"message": "Usuário deletado com sucesso"}


@router.post("/{user_id}/activate")
async def activate_user(
    user_id: int,
    current_user: User = Depends(get_current_active_superuser),
    db: AsyncSession = Depends(get_db)
):
    """Ativa um usuário específico (apenas superusers).
    
    Args:
        user_id: ID do usuário
        current_user: Usuário autenticado (deve ser superuser)
        db: Sessão do banco de dados
        
    Returns:
        dict: Mensagem de confirmação
        
    Raises:
        HTTPException: Se usuário não encontrado
    """
    user_service = UserService(db)
    
    # Verifica se usuário existe
    user = await user_service.get_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuário não encontrado"
        )
    
    # Ativa usuário
    await user_service.update(user_id, {"is_active": True})
    
    return {"message": "Usuário ativado com sucesso"}


@router.post("/{user_id}/deactivate")
async def deactivate_user(
    user_id: int,
    current_user: User = Depends(get_current_active_superuser),
    db: AsyncSession = Depends(get_db)
):
    """Desativa um usuário específico (apenas superusers).
    
    Args:
        user_id: ID do usuário
        current_user: Usuário autenticado (deve ser superuser)
        db: Sessão do banco de dados
        
    Returns:
        dict: Mensagem de confirmação
        
    Raises:
        HTTPException: Se usuário não encontrado ou tentativa de auto-desativação
    """
    user_service = UserService(db)
    
    # Verifica se usuário existe
    user = await user_service.get_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuário não encontrado"
        )
    
    # Impede auto-desativação
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Não é possível desativar sua própria conta"
        )
    
    # Desativa usuário
    await user_service.update(user_id, {"is_active": False})
    
    return {"message": "Usuário desativado com sucesso"}