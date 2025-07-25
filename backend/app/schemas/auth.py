"""Schemas de autenticação."""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, Field, field_validator, ValidationInfo

from app.schemas.base import BaseSchema
from app.schemas.validators import CommonValidators


class Token(BaseModel):
    """Schema para resposta de token de autenticação."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class TokenData(BaseModel):
    """Schema para dados do token decodificado."""
    user_id: Optional[int] = None
    username: Optional[str] = None
    email: Optional[str] = None
    exp: Optional[datetime] = None


class UserLogin(BaseModel):
    """Schema para login de usuário."""
    email_or_username: str = Field(..., description="Email ou nome de usuário")
    password: str = Field(..., min_length=1, description="Senha do usuário")


class UserRegister(BaseModel):
    """Schema para registro de usuário."""
    email: EmailStr = Field(..., description="Email do usuário", pattern=r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$')
    username: str = Field(..., min_length=3, max_length=50, description="Nome de usuário", pattern="^[a-zA-Z0-9_-]+$")
    full_name: str = Field(..., min_length=2, max_length=100, description="Nome completo", pattern="^[a-zA-ZÀ-ÿ ]+$")
    password: str = Field(..., min_length=8, max_length=128, description="Senha do usuário")
    confirm_password: str = Field(..., description="Confirmação da senha")

    @field_validator('email')
    @classmethod
    def validate_email(cls, v: str) -> str:
        return CommonValidators.validate_email_format(v)

    @field_validator('username')
    @classmethod
    def validate_username(cls, v: str) -> str:
        return CommonValidators.validate_username(v)

    @field_validator('password')
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        return CommonValidators.validate_password_strength(v)

    @field_validator('confirm_password')
    def passwords_match(cls, v, info: ValidationInfo):
        """Valida se as senhas coincidem."""
        if 'password' in info.data and v != info.data['password']:
            raise ValueError('As senhas não coincidem')
        return v


class PasswordResetRequest(BaseModel):
    """Schema para solicitação de reset de senha."""
    email: EmailStr = Field(..., description="Email do usuário")


class PasswordReset(BaseModel):
    """Schema para reset de senha."""
    token: str = Field(..., description="Token de reset de senha")
    new_password: str = Field(..., min_length=8, description="Nova senha")
    confirm_password: str = Field(..., description="Confirmação da nova senha")

    @field_validator('confirm_password')
    def passwords_match(cls, v, info: ValidationInfo):
        """Valida se as senhas coincidem."""
        if 'new_password' in info.data and v != info.data['new_password']:
            raise ValueError('As senhas não coincidem')
        return v


class PasswordChange(BaseModel):
    """Schema para alteração de senha."""
    current_password: str = Field(..., description="Senha atual")
    new_password: str = Field(..., min_length=8, description="Nova senha")
    confirm_password: str = Field(..., description="Confirmação da nova senha")

    @field_validator('confirm_password')
    def passwords_match(cls, v, info: ValidationInfo):
        """Valida se as senhas coincidem."""
        if 'new_password' in info.data and v != info.data['new_password']:
            raise ValueError('As senhas não coincidem')
        return v