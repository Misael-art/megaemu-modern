"""Módulo de segurança e autenticação.

Contém funções para autenticação JWT, hashing de senhas
e outras operações de segurança.
"""

from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Union

import jwt
from fastapi import HTTPException, status
from passlib.context import CryptContext

from app.core.config import settings


# Configuração do contexto de senha
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Algoritmo JWT
ALGORITHM = "HS256"


def create_access_token(
    data: Dict[str, Any], 
    expires_delta: Optional[timedelta] = None
) -> str:
    """Cria token de acesso JWT.
    
    Args:
        data: Dados para incluir no token
        expires_delta: Tempo de expiração personalizado
        
    Returns:
        Token JWT codificado
    """
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )
    
    to_encode.update({"exp": expire})
    
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token(data: Dict[str, Any]) -> str:
    """Cria token de refresh JWT.
    
    Args:
        data: Dados para incluir no token
        
    Returns:
        Token JWT de refresh
    """
    to_encode = data.copy()
    
    # Refresh token expira em 30 dias
    expire = datetime.utcnow() + timedelta(days=30)
    to_encode.update({"exp": expire, "type": "refresh"})
    
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> Dict[str, Any]:
    """Decodifica e valida token JWT.
    
    Args:
        token: Token JWT para decodificar
        
    Returns:
        Payload decodificado
        
    Raises:
        HTTPException: Se token inválido ou expirado
    """
    try:
        payload = jwt.decode(
            token, 
            settings.SECRET_KEY, 
            algorithms=[ALGORITHM]
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expirado",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido",
            headers={"WWW-Authenticate": "Bearer"},
        )


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifica se senha corresponde ao hash.
    
    Args:
        plain_password: Senha em texto plano
        hashed_password: Hash da senha armazenado
        
    Returns:
        True se senha é válida
    """
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Gera hash da senha usando bcrypt.
    
    Args:
        password: Senha em texto plano
        
    Returns:
        Hash da senha
    """
    return pwd_context.hash(password)


def create_password_reset_token(email: str) -> str:
    """Cria token para reset de senha.
    
    Args:
        email: Email do usuário
        
    Returns:
        Token de reset
    """
    delta = timedelta(hours=1)  # Token expira em 1 hora
    now = datetime.utcnow()
    expires = now + delta
    
    exp = expires.timestamp()
    encoded_jwt = jwt.encode(
        {"exp": exp, "nbf": now, "sub": email, "type": "password_reset"},
        settings.SECRET_KEY,
        algorithm=ALGORITHM,
    )
    return encoded_jwt


def verify_password_reset_token(token: str) -> Optional[str]:
    """Verifica token de reset de senha.
    
    Args:
        token: Token de reset
        
    Returns:
        Email do usuário se token válido, None caso contrário
    """
    try:
        decoded_token = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[ALGORITHM]
        )
        if decoded_token.get("type") != "password_reset":
            return None
        return decoded_token.get("sub")
    except jwt.JWTError:
        return None


def create_email_verification_token(email: str) -> str:
    """Cria token para verificação de email.
    
    Args:
        email: Email do usuário
        
    Returns:
        Token de verificação
    """
    delta = timedelta(hours=24)  # Token expira em 24 horas
    now = datetime.utcnow()
    expires = now + delta
    
    exp = expires.timestamp()
    encoded_jwt = jwt.encode(
        {"exp": exp, "nbf": now, "sub": email, "type": "email_verification"},
        settings.SECRET_KEY,
        algorithm=ALGORITHM,
    )
    return encoded_jwt


def verify_email_verification_token(token: str) -> Optional[str]:
    """Verifica token de verificação de email.
    
    Args:
        token: Token de verificação
        
    Returns:
        Email do usuário se token válido, None caso contrário
    """
    try:
        decoded_token = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[ALGORITHM]
        )
        if decoded_token.get("type") != "email_verification":
            return None
        return decoded_token.get("sub")
    except jwt.JWTError:
        return None