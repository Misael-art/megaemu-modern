"""Utilitários para validação de dados.

Este módulo contém funções para validação de dados,
formatos, tipos e regras de negócio.
"""

import re
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union, Tuple
from email_validator import validate_email, EmailNotValidError


def validate_email_address(email: str) -> Tuple[bool, Optional[str]]:
    """Valida endereço de email.
    
    Args:
        email: Endereço de email para validar
        
    Returns:
        Tupla (é_válido, mensagem_erro)
    """
    try:
        # Normaliza e valida email
        valid = validate_email(email)
        return True, None
    except EmailNotValidError as e:
        return False, str(e)


def validate_password_strength(password: str) -> Tuple[bool, List[str]]:
    """Valida força da senha.
    
    Args:
        password: Senha para validar
        
    Returns:
        Tupla (é_válida, lista_de_erros)
    """
    errors = []
    
    # Comprimento mínimo
    if len(password) < 8:
        errors.append("Senha deve ter pelo menos 8 caracteres")
    
    # Comprimento máximo
    if len(password) > 128:
        errors.append("Senha deve ter no máximo 128 caracteres")
    
    # Pelo menos uma letra minúscula
    if not re.search(r'[a-z]', password):
        errors.append("Senha deve conter pelo menos uma letra minúscula")
    
    # Pelo menos uma letra maiúscula
    if not re.search(r'[A-Z]', password):
        errors.append("Senha deve conter pelo menos uma letra maiúscula")
    
    # Pelo menos um dígito
    if not re.search(r'\d', password):
        errors.append("Senha deve conter pelo menos um número")
    
    # Pelo menos um caractere especial
    if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        errors.append("Senha deve conter pelo menos um caractere especial")
    
    # Não deve conter espaços
    if ' ' in password:
        errors.append("Senha não deve conter espaços")
    
    return len(errors) == 0, errors


def validate_username(username: str) -> Tuple[bool, Optional[str]]:
    """Valida nome de usuário.
    
    Args:
        username: Nome de usuário para validar
        
    Returns:
        Tupla (é_válido, mensagem_erro)
    """
    # Comprimento
    if len(username) < 3:
        return False, "Nome de usuário deve ter pelo menos 3 caracteres"
    
    if len(username) > 50:
        return False, "Nome de usuário deve ter no máximo 50 caracteres"
    
    # Apenas letras, números, underscore e hífen
    if not re.match(r'^[a-zA-Z0-9_-]+$', username):
        return False, "Nome de usuário deve conter apenas letras, números, _ e -"
    
    # Não pode começar ou terminar com underscore ou hífen
    if username.startswith(('_', '-')) or username.endswith(('_', '-')):
        return False, "Nome de usuário não pode começar ou terminar com _ ou -"
    
    # Não pode ter underscore ou hífen consecutivos
    if '__' in username or '--' in username or '_-' in username or '-_' in username:
        return False, "Nome de usuário não pode ter _ ou - consecutivos"
    
    return True, None


def validate_file_path(file_path: Union[str, Path]) -> Tuple[bool, Optional[str]]:
    """Valida caminho de arquivo.
    
    Args:
        file_path: Caminho para validar
        
    Returns:
        Tupla (é_válido, mensagem_erro)
    """
    try:
        path = Path(file_path)
        
        # Deve ser caminho absoluto
        if not path.is_absolute():
            return False, "Caminho deve ser absoluto"
        
        # Verifica caracteres inválidos no Windows
        invalid_chars = '<>:"|?*'
        if any(char in str(path) for char in invalid_chars):
            return False, f"Caminho contém caracteres inválidos: {invalid_chars}"
        
        # Verifica se o diretório pai existe
        if not path.parent.exists():
            return False, "Diretório pai não existe"
        
        return True, None
        
    except (OSError, ValueError) as e:
        return False, f"Caminho inválido: {e}"


def validate_directory_path(dir_path: Union[str, Path]) -> Tuple[bool, Optional[str]]:
    """Valida caminho de diretório.
    
    Args:
        dir_path: Caminho para validar
        
    Returns:
        Tupla (é_válido, mensagem_erro)
    """
    try:
        path = Path(dir_path)
        
        # Deve ser caminho absoluto
        if not path.is_absolute():
            return False, "Caminho deve ser absoluto"
        
        # Verifica caracteres inválidos
        invalid_chars = '<>:"|?*'
        if any(char in str(path) for char in invalid_chars):
            return False, f"Caminho contém caracteres inválidos: {invalid_chars}"
        
        # Deve existir e ser diretório
        if path.exists() and not path.is_dir():
            return False, "Caminho existe mas não é um diretório"
        
        return True, None
        
    except (OSError, ValueError) as e:
        return False, f"Caminho inválido: {e}"


def validate_file_extension(filename: str, allowed_extensions: List[str]) -> Tuple[bool, Optional[str]]:
    """Valida extensão de arquivo.
    
    Args:
        filename: Nome do arquivo
        allowed_extensions: Lista de extensões permitidas (com ponto)
        
    Returns:
        Tupla (é_válida, mensagem_erro)
    """
    if not filename:
        return False, "Nome do arquivo não pode estar vazio"
    
    extension = Path(filename).suffix.lower()
    
    if not extension:
        return False, "Arquivo deve ter uma extensão"
    
    if extension not in [ext.lower() for ext in allowed_extensions]:
        return False, f"Extensão {extension} não permitida. Permitidas: {', '.join(allowed_extensions)}"
    
    return True, None


def validate_file_size(file_path: Union[str, Path], max_size_mb: float) -> Tuple[bool, Optional[str]]:
    """Valida tamanho de arquivo.
    
    Args:
        file_path: Caminho do arquivo
        max_size_mb: Tamanho máximo em MB
        
    Returns:
        Tupla (é_válido, mensagem_erro)
    """
    try:
        path = Path(file_path)
        
        if not path.exists():
            return False, "Arquivo não existe"
        
        if not path.is_file():
            return False, "Caminho não é um arquivo"
        
        size_bytes = path.stat().st_size
        size_mb = size_bytes / (1024 * 1024)
        
        if size_mb > max_size_mb:
            return False, f"Arquivo muito grande: {size_mb:.2f}MB (máximo: {max_size_mb}MB)"
        
        return True, None
        
    except OSError as e:
        return False, f"Erro ao verificar arquivo: {e}"


def validate_hash_format(hash_value: str, hash_type: str) -> Tuple[bool, Optional[str]]:
    """Valida formato de hash.
    
    Args:
        hash_value: Valor do hash
        hash_type: Tipo do hash (md5, sha1, sha256, crc32)
        
    Returns:
        Tupla (é_válido, mensagem_erro)
    """
    if not hash_value:
        return False, "Hash não pode estar vazio"
    
    # Remove espaços e converte para minúsculo
    hash_value = hash_value.strip().lower()
    
    # Define comprimentos esperados
    expected_lengths = {
        'md5': 32,
        'sha1': 40,
        'sha256': 64,
        'crc32': 8
    }
    
    hash_type = hash_type.lower()
    
    if hash_type not in expected_lengths:
        return False, f"Tipo de hash não suportado: {hash_type}"
    
    expected_length = expected_lengths[hash_type]
    
    if len(hash_value) != expected_length:
        return False, f"Hash {hash_type} deve ter {expected_length} caracteres"
    
    # Verifica se contém apenas caracteres hexadecimais
    if not re.match(r'^[a-f0-9]+$', hash_value):
        return False, "Hash deve conter apenas caracteres hexadecimais"
    
    return True, None


def validate_url(url: str) -> Tuple[bool, Optional[str]]:
    """Valida URL.
    
    Args:
        url: URL para validar
        
    Returns:
        Tupla (é_válida, mensagem_erro)
    """
    if not url:
        return False, "URL não pode estar vazia"
    
    # Padrão básico para URL
    url_pattern = re.compile(
        r'^https?://'  # http:// ou https://
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+'  # domínio
        r'(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|'  # host
        r'localhost|'  # localhost
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # IP
        r'(?::\d+)?'  # porta opcional
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)
    
    if not url_pattern.match(url):
        return False, "Formato de URL inválido"
    
    return True, None


def validate_date_range(start_date: datetime, end_date: datetime) -> Tuple[bool, Optional[str]]:
    """Valida intervalo de datas.
    
    Args:
        start_date: Data de início
        end_date: Data de fim
        
    Returns:
        Tupla (é_válido, mensagem_erro)
    """
    if start_date >= end_date:
        return False, "Data de início deve ser anterior à data de fim"
    
    # Verifica se as datas não são muito antigas ou futuras
    min_date = datetime(1970, 1, 1)
    max_date = datetime(2100, 12, 31)
    
    if start_date < min_date or end_date < min_date:
        return False, "Datas não podem ser anteriores a 1970"
    
    if start_date > max_date or end_date > max_date:
        return False, "Datas não podem ser posteriores a 2100"
    
    return True, None


def validate_pagination_params(page: int, size: int, max_size: int = 100) -> Tuple[bool, Optional[str]]:
    """Valida parâmetros de paginação.
    
    Args:
        page: Número da página
        size: Tamanho da página
        max_size: Tamanho máximo permitido
        
    Returns:
        Tupla (é_válido, mensagem_erro)
    """
    if page < 1:
        return False, "Número da página deve ser maior que 0"
    
    if size < 1:
        return False, "Tamanho da página deve ser maior que 0"
    
    if size > max_size:
        return False, f"Tamanho da página não pode exceder {max_size}"
    
    return True, None


def validate_sort_params(sort_by: str, allowed_fields: List[str]) -> Tuple[bool, Optional[str]]:
    """Valida parâmetros de ordenação.
    
    Args:
        sort_by: Campo para ordenação
        allowed_fields: Campos permitidos
        
    Returns:
        Tupla (é_válido, mensagem_erro)
    """
    if not sort_by:
        return False, "Campo de ordenação não pode estar vazio"
    
    # Remove prefixo de direção (-)
    field = sort_by.lstrip('-')
    
    if field not in allowed_fields:
        return False, f"Campo '{field}' não permitido para ordenação. Permitidos: {', '.join(allowed_fields)}"
    
    return True, None


def validate_search_query(query: str, min_length: int = 2, max_length: int = 100) -> Tuple[bool, Optional[str]]:
    """Valida consulta de busca.
    
    Args:
        query: Consulta de busca
        min_length: Comprimento mínimo
        max_length: Comprimento máximo
        
    Returns:
        Tupla (é_válida, mensagem_erro)
    """
    if not query or not query.strip():
        return False, "Consulta de busca não pode estar vazia"
    
    query = query.strip()
    
    if len(query) < min_length:
        return False, f"Consulta deve ter pelo menos {min_length} caracteres"
    
    if len(query) > max_length:
        return False, f"Consulta deve ter no máximo {max_length} caracteres"
    
    # Verifica caracteres perigosos para SQL injection
    dangerous_chars = [';', '--', '/*', '*/', 'xp_', 'sp_']
    query_lower = query.lower()
    
    for char in dangerous_chars:
        if char in query_lower:
            return False, "Consulta contém caracteres não permitidos"
    
    return True, None


def validate_json_data(data: Any, required_fields: List[str]) -> Tuple[bool, List[str]]:
    """Valida dados JSON.
    
    Args:
        data: Dados para validar
        required_fields: Campos obrigatórios
        
    Returns:
        Tupla (é_válido, lista_de_erros)
    """
    errors = []
    
    if not isinstance(data, dict):
        errors.append("Dados devem ser um objeto JSON")
        return False, errors
    
    # Verifica campos obrigatórios
    for field in required_fields:
        if field not in data:
            errors.append(f"Campo obrigatório ausente: {field}")
        elif data[field] is None or data[field] == "":
            errors.append(f"Campo obrigatório vazio: {field}")
    
    return len(errors) == 0, errors


def validate_numeric_range(
    value: Union[int, float],
    min_value: Optional[Union[int, float]] = None,
    max_value: Optional[Union[int, float]] = None
) -> Tuple[bool, Optional[str]]:
    """Valida valor numérico dentro de um intervalo.
    
    Args:
        value: Valor para validar
        min_value: Valor mínimo (opcional)
        max_value: Valor máximo (opcional)
        
    Returns:
        Tupla (é_válido, mensagem_erro)
    """
    if not isinstance(value, (int, float)):
        return False, "Valor deve ser numérico"
    
    if min_value is not None and value < min_value:
        return False, f"Valor deve ser maior ou igual a {min_value}"
    
    if max_value is not None and value > max_value:
        return False, f"Valor deve ser menor ou igual a {max_value}"
    
    return True, None


def sanitize_filename(filename: str) -> str:
    """Sanitiza nome de arquivo removendo caracteres inválidos.
    
    Args:
        filename: Nome do arquivo
        
    Returns:
        Nome sanitizado
    """
    # Remove caracteres inválidos
    invalid_chars = '<>:"|?*'
    for char in invalid_chars:
        filename = filename.replace(char, '_')
    
    # Remove espaços extras e caracteres de controle
    filename = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', filename)
    filename = re.sub(r'\s+', ' ', filename).strip()
    
    # Limita comprimento
    if len(filename) > 255:
        name, ext = os.path.splitext(filename)
        max_name_length = 255 - len(ext)
        filename = name[:max_name_length] + ext
    
    return filename


def sanitize_string(text: str, max_length: Optional[int] = None) -> str:
    """Sanitiza string removendo caracteres perigosos.
    
    Args:
        text: Texto para sanitizar
        max_length: Comprimento máximo (opcional)
        
    Returns:
        Texto sanitizado
    """
    if not text:
        return ""
    
    # Remove caracteres de controle
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]', '', text)
    
    # Normaliza espaços
    text = re.sub(r'\s+', ' ', text).strip()
    
    # Limita comprimento
    if max_length and len(text) > max_length:
        text = text[:max_length].strip()
    
    return text


def is_safe_path(path: Union[str, Path], base_path: Union[str, Path]) -> bool:
    """Verifica se caminho está dentro do diretório base (previne path traversal).
    
    Args:
        path: Caminho para verificar
        base_path: Diretório base
        
    Returns:
        True se caminho é seguro
    """
    try:
        path = Path(path).resolve()
        base_path = Path(base_path).resolve()
        
        # Verifica se o caminho está dentro do diretório base
        return str(path).startswith(str(base_path))
        
    except (OSError, ValueError):
        return False

def sanitize_path(path: str) -> str:
    """Sanitiza um caminho removendo caracteres inválidos e normalizando-o.
    
    Args:
        path: O caminho para sanitizar
    
    Returns:
        Caminho sanitizado
    """
    import os
    import re
    # Normaliza o caminho
    path = os.path.normpath(path)
    # Remove caracteres inválidos
    invalid_chars = '<>:"|?*'
    for char in invalid_chars:
        path = path.replace(char, '_')
    # Remove caracteres de controle
    path = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', path)
    # Sanitiza cada parte do caminho usando sanitize_filename
    parts = path.split(os.sep)
    sanitized_parts = [sanitize_filename(part) for part in parts if part]
    return os.sep.join(sanitized_parts)