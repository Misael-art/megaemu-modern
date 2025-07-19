"""Utilitários criptográficos.

Este módulo contém funções para operações criptográficas,
hashing, tokens e validação de integridade.
"""

import hashlib
import hmac
import secrets
import base64
import zlib
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Union
from pathlib import Path
import jwt
from passlib.context import CryptContext
from passlib.hash import bcrypt


# Configuração do contexto de senha
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """Gera hash da senha usando bcrypt.
    
    Args:
        password: Senha em texto plano
        
    Returns:
        Hash da senha
    """
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifica se senha corresponde ao hash.
    
    Args:
        plain_password: Senha em texto plano
        hashed_password: Hash da senha
        
    Returns:
        True se senha é válida
    """
    return pwd_context.verify(plain_password, hashed_password)


def generate_salt(length: int = 32) -> str:
    """Gera salt aleatório.
    
    Args:
        length: Comprimento do salt em bytes
        
    Returns:
        Salt em base64
    """
    return base64.b64encode(secrets.token_bytes(length)).decode('utf-8')


def generate_token(length: int = 32) -> str:
    """Gera token aleatório seguro.
    
    Args:
        length: Comprimento do token em bytes
        
    Returns:
        Token em hexadecimal
    """
    return secrets.token_hex(length)


def generate_api_key(prefix: str = "mk", length: int = 32) -> str:
    """Gera chave de API.
    
    Args:
        prefix: Prefixo da chave
        length: Comprimento da parte aleatória
        
    Returns:
        Chave de API
    """
    random_part = secrets.token_hex(length)
    return f"{prefix}_{random_part}"


def create_jwt_token(
    data: Dict[str, Any],
    secret_key: str,
    expires_delta: Optional[timedelta] = None,
    algorithm: str = "HS256"
) -> str:
    """Cria token JWT.
    
    Args:
        data: Dados para incluir no token
        secret_key: Chave secreta
        expires_delta: Tempo de expiração
        algorithm: Algoritmo de assinatura
        
    Returns:
        Token JWT
    """
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(hours=24)
    
    to_encode.update({"exp": expire})
    
    return jwt.encode(to_encode, secret_key, algorithm=algorithm)


def decode_jwt_token(
    token: str,
    secret_key: str,
    algorithm: str = "HS256"
) -> Optional[Dict[str, Any]]:
    """Decodifica token JWT.
    
    Args:
        token: Token JWT
        secret_key: Chave secreta
        algorithm: Algoritmo de verificação
        
    Returns:
        Dados decodificados ou None se inválido
    """
    try:
        payload = jwt.decode(token, secret_key, algorithms=[algorithm])
        return payload
    except jwt.PyJWTError:
        return None


def calculate_file_hash(
    file_path: Union[str, Path],
    algorithm: str = "sha256",
    chunk_size: int = 8192
) -> str:
    """Calcula hash de arquivo.
    
    Args:
        file_path: Caminho do arquivo
        algorithm: Algoritmo de hash
        chunk_size: Tamanho do chunk
        
    Returns:
        Hash em hexadecimal
        
    Raises:
        FileNotFoundError: Se arquivo não existe
        ValueError: Se algoritmo não suportado
    """
    file_path = Path(file_path)
    
    if not file_path.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {file_path}")
    
    # Seleciona algoritmo
    if algorithm.lower() == "md5":
        hasher = hashlib.md5()
    elif algorithm.lower() == "sha1":
        hasher = hashlib.sha1()
    elif algorithm.lower() == "sha256":
        hasher = hashlib.sha256()
    elif algorithm.lower() == "sha512":
        hasher = hashlib.sha512()
    elif algorithm.lower() == "crc32":
        return calculate_crc32(file_path, chunk_size)
    else:
        raise ValueError(f"Algoritmo não suportado: {algorithm}")
    
    # Calcula hash em chunks
    with open(file_path, 'rb') as f:
        while chunk := f.read(chunk_size):
            hasher.update(chunk)
    
    return hasher.hexdigest()


def calculate_crc32(file_path: Union[str, Path], chunk_size: int = 8192) -> str:
    """Calcula CRC32 de arquivo.
    
    Args:
        file_path: Caminho do arquivo
        chunk_size: Tamanho do chunk
        
    Returns:
        CRC32 em hexadecimal
    """
    file_path = Path(file_path)
    crc = 0
    
    with open(file_path, 'rb') as f:
        while chunk := f.read(chunk_size):
            crc = zlib.crc32(chunk, crc)
    
    return format(crc & 0xffffffff, '08x')


def calculate_string_hash(text: str, algorithm: str = "sha256") -> str:
    """Calcula hash de string.
    
    Args:
        text: Texto para hash
        algorithm: Algoritmo de hash
        
    Returns:
        Hash em hexadecimal
        
    Raises:
        ValueError: Se algoritmo não suportado
    """
    if algorithm.lower() == "md5":
        hasher = hashlib.md5()
    elif algorithm.lower() == "sha1":
        hasher = hashlib.sha1()
    elif algorithm.lower() == "sha256":
        hasher = hashlib.sha256()
    elif algorithm.lower() == "sha512":
        hasher = hashlib.sha512()
    else:
        raise ValueError(f"Algoritmo não suportado: {algorithm}")
    
    hasher.update(text.encode('utf-8'))
    return hasher.hexdigest()


def create_hmac_signature(
    message: str,
    secret_key: str,
    algorithm: str = "sha256"
) -> str:
    """Cria assinatura HMAC.
    
    Args:
        message: Mensagem para assinar
        secret_key: Chave secreta
        algorithm: Algoritmo de hash
        
    Returns:
        Assinatura HMAC em hexadecimal
    """
    if algorithm.lower() == "sha256":
        hash_func = hashlib.sha256
    elif algorithm.lower() == "sha1":
        hash_func = hashlib.sha1
    elif algorithm.lower() == "sha512":
        hash_func = hashlib.sha512
    else:
        raise ValueError(f"Algoritmo não suportado: {algorithm}")
    
    signature = hmac.new(
        secret_key.encode('utf-8'),
        message.encode('utf-8'),
        hash_func
    )
    
    return signature.hexdigest()


def verify_hmac_signature(
    message: str,
    signature: str,
    secret_key: str,
    algorithm: str = "sha256"
) -> bool:
    """Verifica assinatura HMAC.
    
    Args:
        message: Mensagem original
        signature: Assinatura para verificar
        secret_key: Chave secreta
        algorithm: Algoritmo de hash
        
    Returns:
        True se assinatura é válida
    """
    expected_signature = create_hmac_signature(message, secret_key, algorithm)
    return hmac.compare_digest(signature, expected_signature)


def encode_base64(data: Union[str, bytes]) -> str:
    """Codifica dados em base64.
    
    Args:
        data: Dados para codificar
        
    Returns:
        Dados codificados em base64
    """
    if isinstance(data, str):
        data = data.encode('utf-8')
    
    return base64.b64encode(data).decode('utf-8')


def decode_base64(encoded_data: str) -> bytes:
    """Decodifica dados de base64.
    
    Args:
        encoded_data: Dados codificados
        
    Returns:
        Dados decodificados
        
    Raises:
        ValueError: Se dados inválidos
    """
    try:
        return base64.b64decode(encoded_data)
    except Exception as e:
        raise ValueError(f"Erro ao decodificar base64: {e}")


def generate_checksum(data: Union[str, bytes], algorithm: str = "sha256") -> str:
    """Gera checksum de dados.
    
    Args:
        data: Dados para checksum
        algorithm: Algoritmo de hash
        
    Returns:
        Checksum em hexadecimal
    """
    if isinstance(data, str):
        data = data.encode('utf-8')
    
    if algorithm.lower() == "md5":
        hasher = hashlib.md5()
    elif algorithm.lower() == "sha1":
        hasher = hashlib.sha1()
    elif algorithm.lower() == "sha256":
        hasher = hashlib.sha256()
    elif algorithm.lower() == "sha512":
        hasher = hashlib.sha512()
    else:
        raise ValueError(f"Algoritmo não suportado: {algorithm}")
    
    hasher.update(data)
    return hasher.hexdigest()


def verify_checksum(
    data: Union[str, bytes],
    expected_checksum: str,
    algorithm: str = "sha256"
) -> bool:
    """Verifica checksum de dados.
    
    Args:
        data: Dados para verificar
        expected_checksum: Checksum esperado
        algorithm: Algoritmo de hash
        
    Returns:
        True se checksum é válido
    """
    actual_checksum = generate_checksum(data, algorithm)
    return hmac.compare_digest(actual_checksum.lower(), expected_checksum.lower())


def create_session_token(user_id: str, expires_hours: int = 24) -> Dict[str, Any]:
    """Cria token de sessão.
    
    Args:
        user_id: ID do usuário
        expires_hours: Horas até expiração
        
    Returns:
        Dicionário com token e informações
    """
    token = generate_token(32)
    expires_at = datetime.utcnow() + timedelta(hours=expires_hours)
    
    return {
        "token": token,
        "user_id": user_id,
        "expires_at": expires_at,
        "created_at": datetime.utcnow()
    }


def hash_api_key(api_key: str) -> str:
    """Gera hash de chave de API para armazenamento.
    
    Args:
        api_key: Chave de API
        
    Returns:
        Hash da chave
    """
    return calculate_string_hash(api_key, "sha256")


def generate_csrf_token() -> str:
    """Gera token CSRF.
    
    Returns:
        Token CSRF
    """
    return generate_token(16)


def constant_time_compare(a: str, b: str) -> bool:
    """Compara strings em tempo constante.
    
    Args:
        a: Primeira string
        b: Segunda string
        
    Returns:
        True se strings são iguais
    """
    return hmac.compare_digest(a, b)


def derive_key(
    password: str,
    salt: str,
    iterations: int = 100000,
    key_length: int = 32
) -> str:
    """Deriva chave usando PBKDF2.
    
    Args:
        password: Senha base
        salt: Salt
        iterations: Número de iterações
        key_length: Comprimento da chave
        
    Returns:
        Chave derivada em hexadecimal
    """
    key = hashlib.pbkdf2_hmac(
        'sha256',
        password.encode('utf-8'),
        salt.encode('utf-8'),
        iterations,
        key_length
    )
    
    return key.hex()


def encrypt_simple(data: str, key: str) -> str:
    """Criptografia simples usando XOR (apenas para dados não sensíveis).
    
    Args:
        data: Dados para criptografar
        key: Chave de criptografia
        
    Returns:
        Dados criptografados em base64
    """
    # Gera chave derivada
    derived_key = derive_key(key, "megaemu_salt", 1000, len(data))
    key_bytes = bytes.fromhex(derived_key)
    
    # XOR dos dados
    encrypted = bytes(a ^ b for a, b in zip(data.encode('utf-8'), key_bytes))
    
    return encode_base64(encrypted)


def decrypt_simple(encrypted_data: str, key: str) -> str:
    """Descriptografia simples usando XOR.
    
    Args:
        encrypted_data: Dados criptografados em base64
        key: Chave de descriptografia
        
    Returns:
        Dados descriptografados
        
    Raises:
        ValueError: Se erro na descriptografia
    """
    try:
        # Decodifica base64
        encrypted_bytes = decode_base64(encrypted_data)
        
        # Gera chave derivada
        derived_key = derive_key(key, "megaemu_salt", 1000, len(encrypted_bytes))
        key_bytes = bytes.fromhex(derived_key)
        
        # XOR dos dados
        decrypted = bytes(a ^ b for a, b in zip(encrypted_bytes, key_bytes))
        
        return decrypted.decode('utf-8')
        
    except Exception as e:
        raise ValueError(f"Erro na descriptografia: {e}")


def generate_fingerprint(data: Dict[str, Any]) -> str:
    """Gera fingerprint de dados.
    
    Args:
        data: Dados para fingerprint
        
    Returns:
        Fingerprint em hexadecimal
    """
    # Serializa dados de forma determinística
    import json
    serialized = json.dumps(data, sort_keys=True, separators=(',', ':'))
    
    return calculate_string_hash(serialized, "sha256")


def validate_hash_format(hash_value: str, algorithm: str) -> bool:
    """Valida formato de hash.
    
    Args:
        hash_value: Valor do hash
        algorithm: Algoritmo esperado
        
    Returns:
        True se formato é válido
    """
    if not hash_value:
        return False
    
    # Remove espaços e converte para minúsculo
    hash_value = hash_value.strip().lower()
    
    # Define comprimentos esperados
    expected_lengths = {
        'md5': 32,
        'sha1': 40,
        'sha256': 64,
        'sha512': 128,
        'crc32': 8
    }
    
    algorithm = algorithm.lower()
    
    if algorithm not in expected_lengths:
        return False
    
    expected_length = expected_lengths[algorithm]
    
    if len(hash_value) != expected_length:
        return False
    
    # Verifica se contém apenas caracteres hexadecimais
    import re
    return bool(re.match(r'^[a-f0-9]+$', hash_value))


def secure_random_string(length: int, alphabet: Optional[str] = None) -> str:
    """Gera string aleatória segura.
    
    Args:
        length: Comprimento da string
        alphabet: Alfabeto personalizado
        
    Returns:
        String aleatória
    """
    if alphabet is None:
        alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    
    return ''.join(secrets.choice(alphabet) for _ in range(length))