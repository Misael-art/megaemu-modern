"""Modelos para usuários e autenticação.

Define entidades para usuários, preferências e configurações
com suporte a autenticação e autorização.
"""

from datetime import datetime
from enum import Enum
from typing import List, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    Index,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import BaseModel, MetadataMixin


class UserRole(str, Enum):
    """Roles de usuário no sistema."""
    ADMIN = "admin"
    USER = "user"
    GUEST = "guest"
    MODERATOR = "moderator"


class UserStatus(str, Enum):
    """Status do usuário."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    PENDING = "pending"
    BANNED = "banned"


class User(BaseModel, MetadataMixin):
    """Modelo principal para usuários do sistema.
    
    Representa um usuário com informações de autenticação,
    perfil e configurações personalizadas.
    """
    
    __tablename__ = "users"
    
    # Informações básicas
    username: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        unique=True,
        index=True,
        doc="Nome de usuário único"
    )
    
    email: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique=True,
        index=True,
        doc="Email do usuário"
    )
    
    full_name: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        doc="Nome completo do usuário"
    )
    
    # Autenticação
    hashed_password: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        doc="Senha hasheada"
    )
    
    password_changed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="Data da última alteração de senha"
    )
    
    # Status e role
    role: Mapped[UserRole] = mapped_column(
        SQLEnum(UserRole),
        nullable=False,
        default=UserRole.USER,
        index=True,
        doc="Role do usuário no sistema"
    )
    
    status: Mapped[UserStatus] = mapped_column(
        SQLEnum(UserStatus),
        nullable=False,
        default=UserStatus.ACTIVE,
        index=True,
        doc="Status atual do usuário"
    )
    
    # Informações de acesso
    last_login: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
        doc="Data do último login"
    )
    
    login_count: Mapped[int] = mapped_column(
        nullable=False,
        default=0,
        doc="Número total de logins"
    )
    
    # Verificação de email
    email_verified: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        doc="Se o email foi verificado"
    )
    
    email_verified_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="Data da verificação do email"
    )
    
    # Tokens de recuperação
    reset_token: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        unique=True,
        doc="Token para recuperação de senha"
    )
    
    reset_token_expires: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="Expiração do token de recuperação"
    )
    
    verification_token: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        unique=True,
        doc="Token para verificação de email"
    )
    
    # Configurações de segurança
    two_factor_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        doc="Se a autenticação 2FA está habilitada"
    )
    
    two_factor_secret: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        doc="Chave secreta para 2FA"
    )
    
    # Informações de perfil
    avatar_url: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        doc="URL do avatar do usuário"
    )
    
    bio: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        doc="Biografia do usuário"
    )
    
    timezone: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        default="UTC",
        doc="Fuso horário do usuário"
    )
    
    language: Mapped[Optional[str]] = mapped_column(
        String(10),
        nullable=True,
        default="en",
        doc="Idioma preferido"
    )
    
    # Relacionamentos
    preferences: Mapped[Optional["UserPreferences"]] = relationship(
        "UserPreferences",
        back_populates="user",
    )
    
    favorite_games: Mapped[List["Game"]] = relationship(
        "Game",
        secondary="user_favorite_games",
        back_populates="favorited_by",
        lazy="dynamic",
        uselist=False,
        cascade="all, delete-orphan"
    )
    
    tasks: Mapped[List["Task"]] = relationship(
        "Task",
        back_populates="user",
        lazy="dynamic"
    )
    
    # Índices
    __table_args__ = (
        UniqueConstraint('username', name='uq_user_username'),
        UniqueConstraint('email', name='uq_user_email'),
        Index('ix_user_status_role', 'status', 'role'),
        Index('ix_user_last_login', 'last_login'),
    )
    
    def __repr__(self) -> str:
        return f"<User(username='{self.username}', email='{self.email}')>"
    
    @property
    def is_active(self) -> bool:
        """Verifica se o usuário está ativo."""
        return self.status == UserStatus.ACTIVE
    
    @property
    def is_admin(self) -> bool:
        """Verifica se o usuário é administrador."""
        return self.role == UserRole.ADMIN
    
    @property
    def is_moderator(self) -> bool:
        """Verifica se o usuário é moderador ou admin."""
        return self.role in [UserRole.ADMIN, UserRole.MODERATOR]
    
    @property
    def display_name(self) -> str:
        """Retorna o nome para exibição."""
        return self.full_name or self.username
    
    def update_last_login(self) -> None:
        """Atualiza informações do último login."""
        self.last_login = datetime.utcnow()
        self.login_count += 1
    
    def verify_email(self) -> None:
        """Marca o email como verificado."""
        self.email_verified = True
        self.email_verified_at = datetime.utcnow()
        self.verification_token = None
    
    def set_password_changed(self) -> None:
        """Marca que a senha foi alterada."""
        self.password_changed_at = datetime.utcnow()
        self.reset_token = None
        self.reset_token_expires = None
    
    def can_access_admin(self) -> bool:
        """Verifica se pode acessar área administrativa."""
        return self.is_active and self.is_admin
    
    def can_moderate(self) -> bool:
        """Verifica se pode moderar conteúdo."""
        return self.is_active and self.is_moderator


class UserPreferences(BaseModel):
    """Modelo para preferências do usuário.
    
    Armazena configurações personalizadas e preferências
    de interface e funcionalidades.
    """
    
    __tablename__ = "user_preferences"
    
    # Relacionamento com usuário (one-to-one)
    user_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True
    )
    
    # Preferências de interface
    theme: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="light",
        doc="Tema da interface (light, dark, auto)"
    )
    
    sidebar_collapsed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        doc="Se a sidebar está colapsada"
    )
    
    items_per_page: Mapped[int] = mapped_column(
        nullable=False,
        default=25,
        doc="Itens por página nas listagens"
    )
    
    # Preferências de jogos
    default_system_view: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="grid",
        doc="Visualização padrão (grid, list, table)"
    )
    
    show_screenshots: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        doc="Se deve mostrar screenshots"
    )
    
    auto_play_videos: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        doc="Se deve reproduzir vídeos automaticamente"
    )
    
    # Preferências de busca
    search_include_descriptions: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        doc="Se deve incluir descrições na busca"
    )
    
    search_fuzzy_matching: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        doc="Se deve usar busca fuzzy"
    )
    
    # Preferências de notificações
    email_notifications: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        doc="Se deve receber notificações por email"
    )
    
    task_notifications: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        doc="Se deve receber notificações de tarefas"
    )
    
    # Preferências de importação
    auto_verify_roms: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        doc="Se deve verificar ROMs automaticamente"
    )
    
    auto_download_metadata: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        doc="Se deve baixar metadados automaticamente"
    )
    
    auto_download_screenshots: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        doc="Se deve baixar screenshots automaticamente"
    )
    
    # Caminhos personalizados
    custom_rom_paths: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="{}",
        doc="Caminhos personalizados para ROMs por sistema"
    )

    custom_emulator_paths: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="{}",
        doc="Caminhos personalizados para emuladores"
    )

    # Filtros salvos
    saved_filters: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="{}",
        doc="Filtros salvos pelo usuário"
    )

    # Configurações avançadas
    advanced_settings: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="{}",
        doc="Configurações avançadas personalizadas"
    )
    
    # Relacionamentos
    user: Mapped[User] = relationship(
        "User",
        back_populates="preferences"
    )
    
    def __repr__(self) -> str:
        return f"<UserPreferences(user='{self.user.username if self.user else 'Unknown'}')>"
    
    def set_custom_rom_path(self, system_id: str, path: str) -> None:
        """Define um caminho personalizado para ROMs de um sistema.
        
        Args:
            system_id: ID do sistema
            path: Caminho personalizado
        """
        if not self.custom_rom_paths:
            self.custom_rom_paths = {}
        self.custom_rom_paths[system_id] = path
    
    def get_custom_rom_path(self, system_id: str) -> Optional[str]:
        """Obtém o caminho personalizado para ROMs de um sistema.
        
        Args:
            system_id: ID do sistema
            
        Returns:
            Caminho personalizado ou None
        """
        return self.custom_rom_paths.get(system_id) if self.custom_rom_paths else None
    
    def set_custom_emulator_path(self, emulator_name: str, path: str) -> None:
        """Define um caminho personalizado para um emulador.
        
        Args:
            emulator_name: Nome do emulador
            path: Caminho personalizado
        """
        if not self.custom_emulator_paths:
            self.custom_emulator_paths = {}
        self.custom_emulator_paths[emulator_name] = path
    
    def get_custom_emulator_path(self, emulator_name: str) -> Optional[str]:
        """Obtém o caminho personalizado para um emulador.
        
        Args:
            emulator_name: Nome do emulador
            
        Returns:
            Caminho personalizado ou None
        """
        return self.custom_emulator_paths.get(emulator_name) if self.custom_emulator_paths else None
    
    def save_filter(self, name: str, filter_data: dict) -> None:
        """Salva um filtro personalizado.
        
        Args:
            name: Nome do filtro
            filter_data: Dados do filtro
        """
        if not self.saved_filters:
            self.saved_filters = {}
        self.saved_filters[name] = filter_data
    
    def get_saved_filter(self, name: str) -> Optional[dict]:
        """Obtém um filtro salvo.
        
        Args:
            name: Nome do filtro
            
        Returns:
            Dados do filtro ou None
        """
        return self.saved_filters.get(name) if self.saved_filters else None
    
    def remove_saved_filter(self, name: str) -> bool:
        """Remove um filtro salvo.
        
        Args:
            name: Nome do filtro
            
        Returns:
            True se removido, False se não encontrado
        """
        if not self.saved_filters:
            return False
        return self.saved_filters.pop(name, None) is not None