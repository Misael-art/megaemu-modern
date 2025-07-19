"""Serviços para gerenciamento de usuários.

Este módulo implementa a lógica de negócio para operações relacionadas
a usuários, incluindo autenticação, autorização e gerenciamento de preferências.
"""

import secrets
from datetime import datetime, timedelta
from typing import Optional, Union

from fastapi import HTTPException, status
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.models.user import User, UserPreferences, UserRole, UserStatus
from app.schemas.user import (
    UserCreate,
    UserUpdate,
    UserPreferencesUpdate,
    PasswordChange,
    PasswordReset,
    PasswordResetConfirm,
)
from app.services.base import BaseService
from app.utils.email import send_email
from app.core.security import (
    create_access_token,
    create_refresh_token,
    verify_password,
    get_password_hash,
)

# Configuração para hash de senhas
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class UserService(BaseService[User, UserCreate, UserUpdate]):
    """Serviço para operações com usuários."""
    
    def __init__(self, db: AsyncSession):
        super().__init__(User)
        self.db = db
    
    async def create_user(
        self,
        db: AsyncSession,
        *,
        user_in: UserCreate
    ) -> User:
        """Cria um novo usuário.
        
        Args:
            db: Sessão do banco de dados
            user_in: Dados do usuário
            
        Returns:
            Usuário criado
            
        Raises:
            HTTPException: Se usuário já existe
        """
        # Verifica se usuário já existe
        existing_user = await self.get_by_email(db, email=user_in.email)
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email já está em uso"
            )
        
        existing_username = await self.get_by_username(db, username=user_in.username)
        if existing_username:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Nome de usuário já está em uso"
            )
        
        # Hash da senha
        hashed_password = get_password_hash(user_in.password)
        
        # Cria usuário
        user_data = user_in.model_dump(exclude={'password'})
        user_data['hashed_password'] = hashed_password
        user_data['status'] = UserStatus.ACTIVE
        user_data['role'] = UserRole.USER
        
        # Gera token de verificação de email
        if settings.EMAIL_VERIFICATION_ENABLED:
            user_data['email_verification_token'] = secrets.token_urlsafe(32)
            user_data['email_verification_expires'] = datetime.utcnow() + timedelta(
                hours=settings.EMAIL_VERIFICATION_EXPIRE_HOURS
            )
        else:
            user_data['email_verified'] = True
        
        # Cria o usuário passando os dados como kwargs
        user = await self.create(db, obj_in={}, **user_data)
        
        # Cria preferências padrão
        await self._create_default_preferences(db, user_id=user.id)
        
        # Envia email de verificação se habilitado
        if settings.EMAIL_VERIFICATION_ENABLED and user.email_verification_token:
            await self._send_verification_email(user)
        
        return user
    
    async def get_by_email(
        self,
        db: AsyncSession,
        *,
        email: str
    ) -> Optional[User]:
        """Busca usuário por email.
        
        Args:
            db: Sessão do banco de dados
            email: Email do usuário
            
        Returns:
            Usuário encontrado ou None
        """
        return await self.get_by_field(db, "email", email.lower())
    
    async def get_by_username(
        self,
        db: AsyncSession,
        *,
        username: str
    ) -> Optional[User]:
        """Busca usuário por nome de usuário.
        
        Args:
            db: Sessão do banco de dados
            username: Nome de usuário
            
        Returns:
            Usuário encontrado ou None
        """
        return await self.get_by_field(db, "username", username.lower())
    
    async def get_by_email_or_username(
        self,
        db: AsyncSession,
        *,
        identifier: str
    ) -> Optional[User]:
        """Busca usuário por email ou nome de usuário.
        
        Args:
            db: Sessão do banco de dados
            identifier: Email ou nome de usuário
            
        Returns:
            Usuário encontrado ou None
        """
        # Tenta buscar por email primeiro
        user = await self.get_by_email(db, email=identifier)
        if user:
            return user
        
        # Se não encontrou por email, tenta por username
        return await self.get_by_username(db, username=identifier)
    
    async def get_by_id(
        self,
        db: AsyncSession,
        user_id: Union[str, int],
        *,
        load_relationships: bool = False
    ) -> Optional[User]:
        """Busca usuário por ID.
        
        Args:
            db: Sessão do banco de dados
            user_id: ID do usuário
            load_relationships: Se deve carregar relacionamentos
            
        Returns:
            Usuário encontrado ou None
        """
        if load_relationships:
            query = select(User).where(User.id == user_id).options(
                selectinload(User.preferences)
            )
            result = await db.execute(query)
            return result.scalar_one_or_none()
        else:
            return await self.get(db, user_id)
    
    async def authenticate(
        self,
        db: AsyncSession,
        *,
        email: str,
        password: str
    ) -> Optional[User]:
        """Autentica usuário.
        
        Args:
            db: Sessão do banco de dados
            email: Email do usuário
            password: Senha do usuário
            
        Returns:
            Usuário autenticado ou None
        """
        user = await self.get_by_email(db, email=email)
        if not user:
            return None
        
        if not verify_password(password, user.hashed_password):
            return None
        
        # Atualiza informações de login
        await self._update_login_info(db, user)
        
        return user
    
    async def update_password(
        self,
        db: AsyncSession,
        *,
        user: User,
        password_change: PasswordChange
    ) -> User:
        """Atualiza senha do usuário.
        
        Args:
            db: Sessão do banco de dados
            user: Usuário
            password_change: Dados da mudança de senha
            
        Returns:
            Usuário atualizado
            
        Raises:
            HTTPException: Se senha atual incorreta
        """
        # Verifica senha atual
        if not verify_password(password_change.current_password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Senha atual incorreta"
            )
        
        # Atualiza senha
        hashed_password = get_password_hash(password_change.new_password)
        update_data = {
            'hashed_password': hashed_password,
            'password_changed_at': datetime.utcnow()
        }
        
        return await self.update(db, db_obj=user, obj_in=update_data)
    
    async def request_password_reset(
        self,
        db: AsyncSession,
        *,
        password_reset: PasswordReset
    ) -> bool:
        """Solicita reset de senha.
        
        Args:
            db: Sessão do banco de dados
            password_reset: Dados do reset
            
        Returns:
            True se email enviado
        """
        user = await self.get_by_email(db, email=password_reset.email)
        if not user:
            # Por segurança, sempre retorna True
            return True
        
        # Gera token de reset
        reset_token = secrets.token_urlsafe(32)
        reset_expires = datetime.utcnow() + timedelta(
            hours=settings.PASSWORD_RESET_EXPIRE_HOURS
        )
        
        # Atualiza usuário
        update_data = {
            'password_reset_token': reset_token,
            'password_reset_expires': reset_expires
        }
        await self.update(db, db_obj=user, obj_in=update_data)
        
        # Envia email
        await self._send_password_reset_email(user, reset_token)
        
        return True
    
    async def reset_password(
        self,
        db: AsyncSession,
        *,
        password_reset_confirm: PasswordResetConfirm
    ) -> User:
        """Confirma reset de senha.
        
        Args:
            db: Sessão do banco de dados
            password_reset_confirm: Dados da confirmação
            
        Returns:
            Usuário atualizado
            
        Raises:
            HTTPException: Se token inválido ou expirado
        """
        # Busca usuário pelo token
        query = select(User).where(
            User.password_reset_token == password_reset_confirm.token
        )
        result = await db.execute(query)
        user = result.scalar_one_or_none()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Token de reset inválido"
            )
        
        # Verifica expiração
        if not user.password_reset_expires or user.password_reset_expires < datetime.utcnow():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Token de reset expirado"
            )
        
        # Atualiza senha
        hashed_password = get_password_hash(password_reset_confirm.new_password)
        update_data = {
            'hashed_password': hashed_password,
            'password_changed_at': datetime.utcnow(),
            'password_reset_token': None,
            'password_reset_expires': None
        }
        
        return await self.update(db, db_obj=user, obj_in=update_data)
    
    async def verify_email(
        self,
        db: AsyncSession,
        *,
        token: str
    ) -> User:
        """Verifica email do usuário.
        
        Args:
            db: Sessão do banco de dados
            token: Token de verificação
            
        Returns:
            Usuário verificado
            
        Raises:
            HTTPException: Se token inválido ou expirado
        """
        # Busca usuário pelo token
        query = select(User).where(
            User.email_verification_token == token
        )
        result = await db.execute(query)
        user = result.scalar_one_or_none()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Token de verificação inválido"
            )
        
        # Verifica expiração
        if not user.email_verification_expires or user.email_verification_expires < datetime.utcnow():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Token de verificação expirado"
            )
        
        # Marca email como verificado
        update_data = {
            'email_verified': True,
            'email_verification_token': None,
            'email_verification_expires': None
        }
        
        return await self.update(db, db_obj=user, obj_in=update_data)
    
    async def deactivate_user(
        self,
        db: AsyncSession,
        *,
        user_id: Union[str, int]
    ) -> User:
        """Desativa usuário.
        
        Args:
            db: Sessão do banco de dados
            user_id: ID do usuário
            
        Returns:
            Usuário desativado
            
        Raises:
            HTTPException: Se usuário não encontrado
        """
        user = await self.get(db, user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Usuário não encontrado"
            )
        
        update_data = {'status': UserStatus.INACTIVE}
        return await self.update(db, db_obj=user, obj_in=update_data)
    
    async def _create_default_preferences(
        self,
        db: AsyncSession,
        *,
        user_id: str
    ) -> UserPreferences:
        """Cria preferências padrão para o usuário.
        
        Args:
            db: Sessão do banco de dados
            user_id: ID do usuário
            
        Returns:
            Preferências criadas
        """
        preferences_data = {
            'user_id': user_id,
            'theme': 'light',
            'sidebar_collapsed': False,
            'items_per_page': 25,
            'default_game_view': 'grid',
            'show_screenshots': True,
            'autoplay_videos': False,
            'search_include_description': True,
            'search_fuzzy_matching': True,
            'notifications_enabled': True,
            'email_notifications': True,
            'auto_verify_roms': True,
            'auto_download_metadata': True,
            'auto_download_screenshots': False
        }
        
        preferences = UserPreferences(**preferences_data)
        db.add(preferences)
        await db.commit()
        await db.refresh(preferences)
        
        return preferences
    
    async def _update_login_info(
        self,
        db: AsyncSession,
        user: User
    ) -> None:
        """Atualiza informações de login do usuário.
        
        Args:
            db: Sessão do banco de dados
            user: Usuário
        """
        update_data = {
            'last_login': datetime.utcnow(),
            'login_count': user.login_count + 1
        }
        await self.update(db, db_obj=user, obj_in=update_data)
    
    async def _send_verification_email(
        self,
        user: User
    ) -> None:
        """Envia email de verificação.
        
        Args:
            user: Usuário
        """
        verification_url = f"{settings.FRONTEND_URL}/verify-email?token={user.email_verification_token}"
        
        await send_email(
            to_email=user.email,
            subject="Verificação de Email - MegaEmu",
            template="email_verification.html",
            context={
                'user_name': user.full_name or user.username,
                'verification_url': verification_url,
                'expire_hours': settings.EMAIL_VERIFICATION_EXPIRE_HOURS
            }
        )
    
    async def _send_password_reset_email(
        self,
        user: User,
        reset_token: str
    ) -> None:
        """Envia email de reset de senha.
        
        Args:
            user: Usuário
            reset_token: Token de reset
        """
        reset_url = f"{settings.FRONTEND_URL}/reset-password?token={reset_token}"
        
        await send_email(
            to_email=user.email,
            subject="Reset de Senha - MegaEmu",
            template="password_reset.html",
            context={
                'user_name': user.full_name or user.username,
                'reset_url': reset_url,
                'expire_hours': settings.PASSWORD_RESET_EXPIRE_HOURS
            }
        )


class AuthService:
    """Serviço para autenticação e autorização."""
    
    def __init__(self, user_service: UserService):
        self.user_service = user_service
    
    async def login(
        self,
        db: AsyncSession,
        *,
        email: str,
        password: str
    ) -> dict:
        """Realiza login do usuário.
        
        Args:
            db: Sessão do banco de dados
            email: Email do usuário
            password: Senha do usuário
            
        Returns:
            Tokens de acesso e refresh
            
        Raises:
            HTTPException: Se credenciais inválidas
        """
        user = await self.user_service.authenticate(
            db, email=email, password=password
        )
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Email ou senha incorretos"
            )
        
        if user.status != UserStatus.ACTIVE:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Conta desativada"
            )
        
        # Gera tokens
        access_token = create_access_token(subject=str(user.id))
        refresh_token = create_refresh_token(subject=str(user.id))
        
        return {
            'access_token': access_token,
            'refresh_token': refresh_token,
            'token_type': 'bearer',
            'user': user
        }
    
    async def refresh_token(
        self,
        db: AsyncSession,
        *,
        refresh_token: str
    ) -> dict:
        """Renova token de acesso.
        
        Args:
            db: Sessão do banco de dados
            refresh_token: Token de refresh
            
        Returns:
            Novo token de acesso
            
        Raises:
            HTTPException: Se token inválido
        """
        # Implementar validação do refresh token
        # e geração de novo access token
        pass


class UserPreferencesService(BaseService[UserPreferences, dict, UserPreferencesUpdate]):
    """Serviço para preferências do usuário."""
    
    def __init__(self):
        super().__init__(UserPreferences)
    
    async def get_by_user_id(
        self,
        db: AsyncSession,
        *,
        user_id: str
    ) -> Optional[UserPreferences]:
        """Busca preferências por ID do usuário.
        
        Args:
            db: Sessão do banco de dados
            user_id: ID do usuário
            
        Returns:
            Preferências do usuário ou None
        """
        return await self.get_by_field(db, "user_id", user_id)
    
    async def update_preferences(
        self,
        db: AsyncSession,
        *,
        user_id: str,
        preferences_in: UserPreferencesUpdate
    ) -> UserPreferences:
        """Atualiza preferências do usuário.
        
        Args:
            db: Sessão do banco de dados
            user_id: ID do usuário
            preferences_in: Dados das preferências
            
        Returns:
            Preferências atualizadas
            
        Raises:
            HTTPException: Se preferências não encontradas
        """
        preferences = await self.get_by_user_id(db, user_id=user_id)
        if not preferences:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Preferências não encontradas"
            )
        
        return await self.update(db, db_obj=preferences, obj_in=preferences_in)
    
    async def add_custom_path(
        self,
        db: AsyncSession,
        *,
        user_id: str,
        path_type: str,
        path: str
    ) -> UserPreferences:
        """Adiciona caminho customizado.
        
        Args:
            db: Sessão do banco de dados
            user_id: ID do usuário
            path_type: Tipo do caminho (roms, emulators, etc.)
            path: Caminho
            
        Returns:
            Preferências atualizadas
        """
        preferences = await self.get_by_user_id(db, user_id=user_id)
        if not preferences:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Preferências não encontradas"
            )
        
        # Adiciona caminho
        preferences.add_custom_path(path_type, path)
        await db.commit()
        await db.refresh(preferences)
        
        return preferences
    
    async def remove_custom_path(
        self,
        db: AsyncSession,
        *,
        user_id: str,
        path_type: str,
        path: str
    ) -> UserPreferences:
        """Remove caminho customizado.
        
        Args:
            db: Sessão do banco de dados
            user_id: ID do usuário
            path_type: Tipo do caminho
            path: Caminho
            
        Returns:
            Preferências atualizadas
        """
        preferences = await self.get_by_user_id(db, user_id=user_id)
        if not preferences:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Preferências não encontradas"
            )
        
        # Remove caminho
        preferences.remove_custom_path(path_type, path)
        await db.commit()
        await db.refresh(preferences)
        
        return preferences
    
    async def save_filter(
        self,
        db: AsyncSession,
        *,
        user_id: str,
        filter_name: str,
        filter_data: dict
    ) -> UserPreferences:
        """Salva filtro personalizado.
        
        Args:
            db: Sessão do banco de dados
            user_id: ID do usuário
            filter_name: Nome do filtro
            filter_data: Dados do filtro
            
        Returns:
            Preferências atualizadas
        """
        preferences = await self.get_by_user_id(db, user_id=user_id)
        if not preferences:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Preferências não encontradas"
            )
        
        # Salva filtro
        preferences.save_filter(filter_name, filter_data)
        await db.commit()
        await db.refresh(preferences)
        
        return preferences
    
    async def remove_filter(
        self,
        db: AsyncSession,
        *,
        user_id: str,
        filter_name: str
    ) -> UserPreferences:
        """Remove filtro personalizado.
        
        Args:
            db: Sessão do banco de dados
            user_id: ID do usuário
            filter_name: Nome do filtro
            
        Returns:
            Preferências atualizadas
        """
        preferences = await self.get_by_user_id(db, user_id=user_id)
        if not preferences:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Preferências não encontradas"
            )
        
        # Remove filtro
        preferences.remove_filter(filter_name)
        await db.commit()
        await db.refresh(preferences)
        
        return preferences