"""Endpoints de autenticação e autorização.

Fornece endpoints para:
- Login e logout
- Registro de usuários
- Refresh de tokens
- Verificação de tokens
- Reset de senha
"""

from datetime import timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.security import (
    create_access_token,
    create_refresh_token,
    verify_password,
    get_password_hash,
    decode_token
)
from app.models.user import User
from app.schemas.auth import (
    Token,
    TokenData,
    UserLogin,
    UserRegister,
    PasswordReset,
    PasswordResetRequest
)
from app.schemas.user import UserResponse, UserCreate
from app.services.user import UserService
from app.utils.email import send_email
from app.utils.validation_utils import validate_email_address, validate_password_strength

router = APIRouter()


@router.post("/login", response_model=Token)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db)
):
    """Autentica usuário e retorna tokens de acesso.
    
    Args:
        form_data: Dados do formulário OAuth2 (username/email e password)
        db: Sessão do banco de dados
        
    Returns:
        Token: Access token e refresh token
        
    Raises:
        HTTPException: Se credenciais inválidas
    """
    try:
        print(f"[DEBUG] Tentativa de login para usuário: {form_data.username}")
        
        user_service = UserService(db)
        print(f"[DEBUG] UserService criado com sucesso")
        
        # Busca usuário por email ou username
        print(f"[DEBUG] Buscando usuário por email ou username: {form_data.username}")
        user = await user_service.get_by_email_or_username(db, identifier=form_data.username)
        print(f"[DEBUG] Usuário encontrado: {user is not None}")
        
        if not user:
            print(f"[DEBUG] Usuário não encontrado")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Email/usuário ou senha incorretos",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        print(f"[DEBUG] Verificando senha")
        if not verify_password(form_data.password, user.hashed_password):
            print(f"[DEBUG] Senha incorreta")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Email/usuário ou senha incorretos",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        print(f"[DEBUG] Verificando se usuário está ativo")
        if not user.is_active:
            print(f"[DEBUG] Usuário inativo")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Usuário inativo"
            )
        
        print(f"[DEBUG] Atualizando último login")
        # Atualiza último login
        user.update_last_login()
        await db.commit()
        await db.refresh(user)
        
        print(f"[DEBUG] Criando tokens")
        # Cria tokens
        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": str(user.id)}, expires_delta=access_token_expires
        )
        
        refresh_token = create_refresh_token(data={"sub": str(user.id)})
        
        print(f"[DEBUG] Login realizado com sucesso para usuário: {user.username}")
        return Token(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        )
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        print(f"[ERROR] Erro inesperado durante login: {str(e)}")
        print(f"[ERROR] Tipo do erro: {type(e).__name__}")
        import traceback
        print(f"[ERROR] Traceback completo: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro interno do servidor"
        )


@router.post("/register", response_model=UserResponse)
async def register(
    user_data: UserRegister,
    db: AsyncSession = Depends(get_db)
):
    """Registra novo usuário.
    
    Args:
        user_data: Dados do usuário para registro
        db: Sessão do banco de dados
        
    Returns:
        UserResponse: Dados do usuário criado
        
    Raises:
        HTTPException: Se dados inválidos ou usuário já existe
    """
    user_service = UserService(db)
    
    # Validações
    if not validate_email_address(user_data.email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email inválido"
        )
    
    password_validation = validate_password_strength(user_data.password)
    if not password_validation["valid"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Senha inválida: {', '.join(password_validation['errors'])}"
        )
    
    # Verifica se usuário já existe
    existing_user = await user_service.get_by_email(db, email=user_data.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email já cadastrado"
        )
    
    existing_username = await user_service.get_by_username(db, username=user_data.username)
    if existing_username:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nome de usuário já existe"
        )
    
    # Cria usuário usando o schema correto
    user_create_data = UserCreate(
        email=user_data.email,
        username=user_data.username,
        full_name=user_data.full_name,
        password=user_data.password,
        password_confirm=user_data.confirm_password
    )
    
    user = await user_service.create_user(db, user_in=user_create_data)
    
    # Envia email de boas-vindas (opcional)
    if settings.EMAILS_ENABLED:
        try:
            subject = "Bem-vindo ao MegaEmu"
            body = f"Olá {user.full_name or user.username},\n\nBem-vindo ao MegaEmu! Sua conta foi criada com sucesso."
            html_body = f"""<html><body><h1>Bem-vindo ao MegaEmu</h1><p>Olá {user.full_name or user.username},</p><p>Sua conta foi criada com sucesso.</p><p>Atenciosamente,<br>Equipe MegaEmu</p></body></html>"""
            await send_email(to_email=user.email, subject=subject, body=body, html_body=html_body)
        except Exception as e:
            print(f"Erro ao enviar email de boas-vindas: {e}")
    
    return UserResponse.model_validate(user)


@router.post("/refresh", response_model=Token)
async def refresh_token(
    refresh_token: str,
    db: AsyncSession = Depends(get_db)
):
    """Renova access token usando refresh token.
    
    Args:
        refresh_token: Refresh token válido
        db: Sessão do banco de dados
        
    Returns:
        Token: Novo access token e refresh token
        
    Raises:
        HTTPException: Se refresh token inválido
    """
    try:
        payload = decode_token(refresh_token)
        user_id = payload.get("sub")
        
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token inválido"
            )
        
        user_service = UserService(db)
        user = await user_service.get_by_id(int(user_id))
        
        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Usuário não encontrado ou inativo"
            )
        
        # Cria novos tokens
        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": str(user.id)}, expires_delta=access_token_expires
        )
        
        new_refresh_token = create_refresh_token(data={"sub": str(user.id)})
        
        return Token(
            access_token=access_token,
            refresh_token=new_refresh_token,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido"
        )


@router.post("/verify-token")
async def verify_token(
    token: str,
    db: AsyncSession = Depends(get_db)
):
    """Verifica se um token é válido.
    
    Args:
        token: Token para verificação
        db: Sessão do banco de dados
        
    Returns:
        dict: Status da verificação e dados do usuário
        
    Raises:
        HTTPException: Se token inválido
    """
    try:
        payload = decode_token(token)
        user_id = payload.get("sub")
        
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token inválido"
            )
        
        user_service = UserService(db)
        user = await user_service.get_by_id(int(user_id))
        
        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Usuário não encontrado ou inativo"
            )
        
        return {
            "valid": True,
            "user_id": user.id,
            "username": user.username,
            "email": user.email,
            "is_superuser": user.is_superuser
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido"
        )


@router.post("/password-reset-request")
async def password_reset_request(
    request_data: PasswordResetRequest,
    db: AsyncSession = Depends(get_db)
):
    """Solicita reset de senha.
    
    Args:
        request_data: Email para reset de senha
        db: Sessão do banco de dados
        
    Returns:
        dict: Mensagem de confirmação
    """
    user_service = UserService(db)
    user = await user_service.get_by_email(request_data.email)
    
    if not user:
        # Por segurança, sempre retorna sucesso mesmo se email não existe
        return {"message": "Se o email existir, você receberá instruções para reset"}
    
    # Gera token de reset
    reset_token = create_access_token(
        data={"sub": str(user.id), "type": "password_reset"},
        expires_delta=timedelta(hours=1)  # Token expira em 1 hora
    )
    
    # Envia email com link de reset
    if settings.EMAILS_ENABLED:
        try:
            email_service = EmailService()
            reset_url = f"{settings.FRONTEND_URL}/reset-password?token={reset_token}"
            await email_service.send_password_reset_email(
                user.email, user.full_name, reset_url
            )
        except Exception as e:
            print(f"Erro ao enviar email de reset: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Erro ao enviar email de reset"
            )
    
    return {"message": "Se o email existir, você receberá instruções para reset"}


@router.post("/password-reset")
async def password_reset(
    reset_data: PasswordReset,
    db: AsyncSession = Depends(get_db)
):
    """Executa reset de senha.
    
    Args:
        reset_data: Token e nova senha
        db: Sessão do banco de dados
        
    Returns:
        dict: Mensagem de confirmação
        
    Raises:
        HTTPException: Se token inválido ou senha inválida
    """
    try:
        payload = decode_token(reset_data.token)
        user_id = payload.get("sub")
        token_type = payload.get("type")
        
        if user_id is None or token_type != "password_reset":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Token de reset inválido"
            )
        
        # Valida nova senha
        password_validation = validate_password_strength(reset_data.new_password)
        if not password_validation["valid"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Senha inválida: {', '.join(password_validation['errors'])}"
            )
        
        user_service = UserService(db)
        user = await user_service.get_by_id(int(user_id))
        
        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Usuário não encontrado ou inativo"
            )
        
        # Atualiza senha
        await user_service.update_password(user.id, reset_data.new_password)
        
        return {"message": "Senha alterada com sucesso"}
        
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token de reset inválido"
        )


@router.post("/logout")
async def logout():
    """Logout do usuário.
    
    Nota: Como usamos JWT stateless, o logout é feito no frontend
    removendo o token. Este endpoint existe para compatibilidade
    e pode ser usado para invalidar tokens em implementações futuras.
    
    Returns:
        dict: Mensagem de confirmação
    """
    return {"message": "Logout realizado com sucesso"}