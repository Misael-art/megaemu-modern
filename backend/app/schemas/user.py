"""Schemas para usuários e autenticação.

Define estruturas de dados para validação e serialização
de operações relacionadas a usuários, preferências e autenticação.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import EmailStr, Field, field_validator, model_validator

from app.models.user import UserRole, UserStatus
from app.schemas.base import BaseEntitySchema, BaseSchema
from app.schemas.validators import CommonValidators


class UserBase(BaseSchema):
    """Schema base para usuários."""
    
    username: str = Field(
        min_length=3,
        max_length=50,
        pattern="^[a-zA-Z0-9_-]+$",
        description="Nome de usuário único (apenas letras, números, _ e -)",
        examples=["user123", "john_doe"]
    )
    
    email: EmailStr = Field(
        description="Email válido do usuário",
        examples=["user@example.com"]
    )
    
    full_name: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=255,
        description="Nome completo do usuário",
        examples=["João Silva"]
    )
    
    bio: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Biografia do usuário",
        examples=["Desenvolvedor apaixonado por jogos retro"]
    )
    
    timezone: Optional[str] = Field(
        default="UTC",
        max_length=50,
        description="Fuso horário do usuário",
        examples=["America/Sao_Paulo", "UTC"]
    )
    
    language: Optional[str] = Field(
        default="en",
        pattern="^[a-z]{2}(-[A-Z]{2})?$",
        description="Idioma preferido (formato ISO 639-1)",
        examples=["pt-BR", "en", "es"]
    )


class UserCreate(UserBase):
    """Schema para criação de usuário."""
    
    password: str = Field(
        min_length=8,
        max_length=128,
        description="Senha do usuário (mínimo 8 caracteres)",
        examples=["mySecurePassword123"]
    )
    
    password_confirm: str = Field(
        min_length=8,
        max_length=128,
        description="Confirmação da senha",
        examples=["mySecurePassword123"]
    )
    
    role: Optional[UserRole] = Field(
        default=UserRole.USER,
        description="Role do usuário no sistema"
    )
    
    @field_validator('password')
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        """Valida a força da senha."""
        if len(v) < 8:
            raise ValueError('Senha deve ter pelo menos 8 caracteres')
        
        has_upper = any(c.isupper() for c in v)
        has_lower = any(c.islower() for c in v)
        has_digit = any(c.isdigit() for c in v)
        has_special = any(c in '!@#$%^&*()_+-=[]{}|;:,.<>?/~`' for c in v)
        
        if not (has_upper and has_lower and has_digit):
            raise ValueError(
                'Senha deve conter pelo menos uma letra maiúscula, '
                'uma minúscula e um número'
            )
        
        if not has_special:
            raise ValueError('Senha deve conter pelo menos um caractere especial')
        
        return v
    
    @model_validator(mode='after')
    def validate_passwords_match(self):
        """Valida se as senhas coincidem."""
        if self.password != self.password_confirm:
            raise ValueError('Senhas não coincidem')
        return self


class UserUpdate(BaseSchema):
    """Schema para atualização de usuário."""
    
    full_name: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=255,
        description="Nome completo do usuário"
    )
    
    bio: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Biografia do usuário"
    )
    
    avatar_url: Optional[str] = Field(
        default=None,
        max_length=500,
        description="URL do avatar do usuário"
    )
    
    timezone: Optional[str] = Field(
        default=None,
        max_length=50,
        description="Fuso horário do usuário"
    )
    
    language: Optional[str] = Field(
        default=None,
        pattern="^[a-z]{2}(-[A-Z]{2})?$",
        description="Idioma preferido"
    )
    
    role: Optional[UserRole] = Field(
        default=None,
        description="Role do usuário (apenas admins)"
    )
    
    status: Optional[UserStatus] = Field(
        default=None,
        description="Status do usuário (apenas admins)"
    )


class UserUpdateMe(BaseSchema):
    """Schema for user self-updates."""
    
    full_name: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=255,
        description="Nome completo do usuário"
    )
    
    bio: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Biografia do usuário"
    )
    
    avatar_url: Optional[str] = Field(
        default=None,
        max_length=500,
        description="URL do avatar do usuário"
    )
    
    timezone: Optional[str] = Field(
        default=None,
        max_length=50,
        description="Fuso horário do usuário"
    )
    
    language: Optional[str] = Field(
        default=None,
        pattern="^[a-z]{2}(-[A-Z]{2})?$",
        description="Idioma preferido"
    )
    
    role: Optional[UserRole] = Field(
        default=None,
        description="Role do usuário (apenas admins)"
    )
    
    status: Optional[UserStatus] = Field(
        default=None,
        description="Status do usuário (apenas admins)"
    )


class UserResponse(UserBase, BaseEntitySchema):
    """Schema para resposta de usuário."""
    
    role: UserRole = Field(
        description="Role do usuário no sistema"
    )
    
    status: UserStatus = Field(
        description="Status atual do usuário"
    )
    
    avatar_url: Optional[str] = Field(
        default=None,
        description="URL do avatar do usuário"
    )
    
    last_login: Optional[datetime] = Field(
        default=None,
        description="Data do último login"
    )
    
    login_count: int = Field(
        ge=0,
        description="Número total de logins"
    )
    
    email_verified: bool = Field(
        description="Se o email foi verificado"
    )
    
    email_verified_at: Optional[datetime] = Field(
        default=None,
        description="Data da verificação do email"
    )
    
    two_factor_enabled: bool = Field(
        description="Se a autenticação 2FA está habilitada"
    )
    
    password_changed_at: Optional[datetime] = Field(
        default=None,
        description="Data da última alteração de senha"
    )
    
    @property
    def display_name(self) -> str:
        """Nome para exibição."""
        return self.full_name or self.username
    
    @property
    def is_active(self) -> bool:
        """Se o usuário está ativo."""
        return self.status == UserStatus.ACTIVE


class UserLogin(BaseSchema):
    """Schema para login de usuário."""
    
    username: str = Field(
        min_length=1,
        max_length=255,
        description="Nome de usuário ou email",
        examples=["user123", "user@example.com"]
    )
    
    password: str = Field(
        min_length=1,
        max_length=128,
        description="Senha do usuário"
    )
    
    remember_me: bool = Field(
        default=False,
        description="Manter login ativo por mais tempo"
    )
    
    two_factor_code: Optional[str] = Field(
        default=None,
        pattern="^[0-9]{6}$",
        description="Código de autenticação 2FA (6 dígitos)",
        examples=["123456"]
    )


class TokenResponse(BaseSchema):
    """Schema para resposta de token de autenticação."""
    
    access_token: str = Field(
        description="Token de acesso JWT"
    )
    
    token_type: str = Field(
        default="bearer",
        description="Tipo do token"
    )
    
    expires_in: int = Field(
        description="Tempo de expiração em segundos",
        examples=[3600]
    )
    
    refresh_token: Optional[str] = Field(
        default=None,
        description="Token de renovação"
    )
    
    user: UserResponse = Field(
        description="Dados do usuário autenticado"
    )


class PasswordChange(BaseSchema):
    """Schema para alteração de senha."""
    
    current_password: str = Field(
        min_length=1,
        max_length=128,
        description="Senha atual"
    )
    
    new_password: str = Field(
        min_length=8,
        max_length=128,
        description="Nova senha"
    )
    
    new_password_confirm: str = Field(
        min_length=8,
        max_length=128,
        description="Confirmação da nova senha"
    )
    
    @field_validator('new_password')
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        """Valida a força da nova senha."""
        if len(v) < 8:
            raise ValueError('Senha deve ter pelo menos 8 caracteres')
        
        has_upper = any(c.isupper() for c in v)
        has_lower = any(c.islower() for c in v)
        has_digit = any(c.isdigit() for c in v)
        
        if not (has_upper and has_lower and has_digit):
            raise ValueError(
                'Senha deve conter pelo menos uma letra maiúscula, '
                'uma minúscula e um número'
            )
        
        return v
    
    @model_validator(mode='after')
    def validate_passwords_match(self):
        """Valida se as novas senhas coincidem."""
        if self.new_password != self.new_password_confirm:
            raise ValueError('Novas senhas não coincidem')
        return self


class PasswordReset(BaseSchema):
    """Schema para reset de senha."""
    
    email: EmailStr = Field(
        description="Email do usuário para reset"
    )


class PasswordResetConfirm(BaseSchema):
    """Schema para confirmação de reset de senha."""
    
    token: str = Field(
        min_length=1,
        description="Token de reset recebido por email"
    )
    
    new_password: str = Field(
        min_length=8,
        max_length=128,
        description="Nova senha"
    )
    
    new_password_confirm: str = Field(
        min_length=8,
        max_length=128,
        description="Confirmação da nova senha"
    )
    
    @field_validator('new_password')
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        """Valida a força da nova senha."""
        if len(v) < 8:
            raise ValueError('Senha deve ter pelo menos 8 caracteres')
        
        has_upper = any(c.isupper() for c in v)
        has_lower = any(c.islower() for c in v)
        has_digit = any(c.isdigit() for c in v)
        
        if not (has_upper and has_lower and has_digit):
            raise ValueError(
                'Senha deve conter pelo menos uma letra maiúscula, '
                'uma minúscula e um número'
            )
        
        return v
    
    @model_validator(mode='after')
    def validate_passwords_match(self):
        """Valida se as senhas coincidem."""
        if self.new_password != self.new_password_confirm:
            raise ValueError('Senhas não coincidem')
        return self


class EmailVerification(BaseSchema):
    """Schema para verificação de email."""
    
    token: str = Field(
        min_length=1,
        description="Token de verificação recebido por email"
    )


class UserPreferencesBase(BaseSchema):
    """Schema base para preferências do usuário."""
    
    theme: str = Field(
        default="light",
        pattern="^(light|dark|auto)$",
        description="Tema da interface",
        examples=["light", "dark", "auto"]
    )
    
    sidebar_collapsed: bool = Field(
        default=False,
        description="Se a sidebar está colapsada"
    )
    
    items_per_page: int = Field(
        default=25,
        ge=10,
        le=100,
        description="Itens por página nas listagens"
    )
    
    default_system_view: str = Field(
        default="grid",
        pattern="^(grid|list|table)$",
        description="Visualização padrão dos sistemas",
        examples=["grid", "list", "table"]
    )
    
    show_screenshots: bool = Field(
        default=True,
        description="Se deve mostrar screenshots"
    )
    
    auto_play_videos: bool = Field(
        default=False,
        description="Se deve reproduzir vídeos automaticamente"
    )
    
    search_include_descriptions: bool = Field(
        default=True,
        description="Se deve incluir descrições na busca"
    )
    
    search_fuzzy_matching: bool = Field(
        default=True,
        description="Se deve usar busca fuzzy"
    )
    
    email_notifications: bool = Field(
        default=True,
        description="Se deve receber notificações por email"
    )
    
    task_notifications: bool = Field(
        default=True,
        description="Se deve receber notificações de tarefas"
    )
    
    auto_verify_roms: bool = Field(
        default=True,
        description="Se deve verificar ROMs automaticamente"
    )
    
    auto_download_metadata: bool = Field(
        default=True,
        description="Se deve baixar metadados automaticamente"
    )
    
    auto_download_screenshots: bool = Field(
        default=False,
        description="Se deve baixar screenshots automaticamente"
    )


class UserPreferencesUpdate(UserPreferencesBase):
    """Schema para atualização de preferências."""
    
    custom_rom_paths: Optional[Dict[str, str]] = Field(
        default=None,
        description="Caminhos personalizados para ROMs por sistema"
    )
    
    custom_emulator_paths: Optional[Dict[str, str]] = Field(
        default=None,
        description="Caminhos personalizados para emuladores"
    )
    
    saved_filters: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Filtros salvos pelo usuário"
    )
    
    advanced_settings: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Configurações avançadas personalizadas"
    )


class UserPreferencesResponse(UserPreferencesBase, BaseEntitySchema):
    """Schema para resposta de preferências."""
    


class UserStatsResponse(BaseSchema):
    """Schema para estatísticas do usuário."""
    
    total_games: int = Field(
        ge=0,
        description="Total de jogos na coleção"
    )
    
    total_roms: int = Field(
        ge=0,
        description="Total de ROMs na coleção"
    )
    
    verified_roms: int = Field(
        ge=0,
        description="ROMs verificadas"
    )
    
    favorite_games: int = Field(
        ge=0,
        description="Jogos marcados como favoritos"
    )
    
    completed_games: int = Field(
        ge=0,
        description="Jogos marcados como completos"
    )
    
    systems_count: int = Field(
        ge=0,
        description="Número de sistemas diferentes"
    )
    
    total_playtime: int = Field(
        ge=0,
        description="Tempo total de jogo em minutos"
    )
    
    last_played: Optional[datetime] = Field(
        default=None,
        description="Data do último jogo jogado"
    )
    
    collection_size_mb: float = Field(
        ge=0,
        description="Tamanho da coleção em MB"
    )
    
    most_played_system: Optional[str] = Field(
        default=None,
        description="Sistema mais jogado"
    )
    



class UserList(BaseSchema):
    """Schema para listagem de usuários."""
    
    id: UUID = Field(
        description="ID único do usuário",
        examples=["123e4567-e89b-12d3-a456-426614174000"]
    )
    
    username: str = Field(
        description="Nome de usuário",
        examples=["user123"]
    )
    
    email: EmailStr = Field(
        description="Email do usuário",
        examples=["user@example.com"]
    )
    
    full_name: Optional[str] = Field(
        default=None,
        description="Nome completo",
        examples=["João Silva"]
    )
    
    role: UserRole = Field(
        description="Role do usuário"
    )
    
    status: UserStatus = Field(
        description="Status do usuário"
    )
    
    created_at: datetime = Field(
        description="Data de criação"
    )
    
    last_login: Optional[datetime] = Field(
        default=None,
        description="Data do último login"
    )
    


