"""Módulo de dependências de autenticação.

Contém funções de dependência para autenticação de usuários no FastAPI.
"""

import uuid
from typing import AsyncGenerator, List

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_token
from app.core.database import get_db
from app.models.user import User, UserRole
from app.services.user import UserService

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/auth/login")

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
) -> User:
    """Obtém o usuário atual a partir do token JWT.
    
    Args:
        token: Token JWT do esquema OAuth2
        db: Sessão do banco de dados
        
    Returns:
        Usuário autenticado
        
    Raises:
        HTTPException: Se token inválido ou usuário não encontrado
    """
    payload = decode_token(token)
    user_id_str = payload.get("sub")
    if not user_id_str:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    try:
        user_id = uuid.UUID(user_id_str)
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido - ID de usuário malformado",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user_service = UserService(db)
    user = await user_service.get_by_id(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuário não encontrado",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user

async def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """Obtém o usuário atual ativo.
    
    Args:
        current_user: Usuário atual da dependência
        
    Returns:
        Usuário ativo
        
    Raises:
        HTTPException: Se usuário inativo
    """
    if not current_user.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Usuário inativo")
    return current_user

async def get_current_active_admin(
    current_user: User = Depends(get_current_user)
) -> User:
    """Obtém o administrador atual ativo.
    
    Args:
        current_user: Usuário atual da dependência
        
    Returns:
        Administrador ativo
        
    Raises:
        HTTPException: Se não for administrador
    """
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="Privilégios insuficientes"
        )
    return current_user

# Nova dependência para RBAC baseada em roles
def get_user_with_role(roles: List[UserRole]):
    def dependency(current_user: User = Depends(get_current_active_user)) -> User:
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permissões insuficientes para esta role"
            )
        return current_user
    return dependency

async def get_current_active_superuser(
    current_user: User = Depends(get_current_user)
) -> User:
    """Obtém o superusuário atual ativo.
    
    Args:
        current_user: Usuário atual da dependência
        
    Returns:
        Superusuário ativo
        
    Raises:
        HTTPException: Se não for superusuário
    """
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="Privilégios insuficientes"
        )
    return current_user