"""Validadores customizados para schemas Pydantic.

Centraliza validações comuns que podem ser reutilizadas
em diferentes schemas da aplicação.
"""

import re
from typing import Any
from pathlib import Path

from pydantic import field_validator


class CommonValidators:
    """Classe com validadores comuns reutilizáveis."""
    
    @staticmethod
    def validate_password_strength(password: str) -> str:
        """Valida força da senha com critérios rigorosos."""
        if len(password) < 8:
            raise ValueError('Senha deve ter pelo menos 8 caracteres')
        
        if len(password) > 128:
            raise ValueError('Senha não pode ter mais de 128 caracteres')
        
        has_upper = any(c.isupper() for c in password)
        has_lower = any(c.islower() for c in password)
        has_digit = any(c.isdigit() for c in password)
        has_special = any(c in '!@#$%^&*()_+-=[]{}|;:,.<>?/~`' for c in password)
        
        if not (has_upper and has_lower and has_digit):
            raise ValueError('Senha deve conter maiúsculas, minúsculas e números')
        
        if not has_special:
            raise ValueError('Senha deve conter pelo menos um caractere especial')
        
        # Verificar padrões comuns fracos
        weak_patterns = [
            r'(.)\1{2,}',  # 3+ caracteres repetidos
            r'123456',     # sequência numérica
            r'abcdef',     # sequência alfabética
            r'qwerty',     # padrão de teclado
            r'password',   # palavra comum
        ]
        
        for pattern in weak_patterns:
            if re.search(pattern, password.lower()):
                raise ValueError('Senha contém padrões fracos ou comuns')
        
        return password
    
    @staticmethod
    def validate_username(username: str) -> str:
        """Valida formato do nome de usuário."""
        if not re.match(r'^[a-zA-Z0-9_-]+$', username):
            raise ValueError('Nome de usuário deve conter apenas letras, números, underscore e hífen')
        
        if username.startswith(('_', '-')) or username.endswith(('_', '-')):
            raise ValueError('Nome de usuário não pode começar ou terminar com underscore ou hífen')
        
        # Verificar palavras reservadas
        reserved_words = [
            'admin', 'administrator', 'root', 'system', 'user',
            'api', 'www', 'mail', 'email', 'support', 'help',
            'null', 'undefined', 'test', 'demo'
        ]
        
        if username.lower() in reserved_words:
            raise ValueError('Nome de usuário não pode ser uma palavra reservada')
        
        return username
    
    @staticmethod
    def validate_email_format(email: str) -> str:
        """Valida formato rigoroso de email."""
        # Padrão mais rigoroso para email
        pattern = r'^[a-zA-Z0-9]([a-zA-Z0-9._-]*[a-zA-Z0-9])?@[a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?\.[a-zA-Z]{2,}$'
        
        if not re.match(pattern, email):
            raise ValueError('Formato de email inválido')
        
        # Verificar domínios temporários conhecidos
        temp_domains = [
            '10minutemail.com', 'tempmail.org', 'guerrillamail.com',
            'mailinator.com', 'throwaway.email'
        ]
        
        domain = email.split('@')[1].lower()
        if domain in temp_domains:
            raise ValueError('Emails temporários não são permitidos')
        
        return email
    
    @staticmethod
    def validate_file_path(file_path: str) -> str:
        """Valida caminho de arquivo."""
        try:
            path = Path(file_path)
            
            # Verificar se é caminho absoluto
            if not path.is_absolute():
                raise ValueError('Caminho deve ser absoluto')
            
            # Verificar caracteres perigosos
            dangerous_chars = ['..', '<', '>', '|', '&', ';']
            if any(char in str(path) for char in dangerous_chars):
                raise ValueError('Caminho contém caracteres perigosos')
            
            # Verificar comprimento
            if len(str(path)) > 500:
                raise ValueError('Caminho muito longo (máximo 500 caracteres)')
            
            return str(path)
            
        except Exception as e:
            raise ValueError(f'Caminho inválido: {e}')
    
    @staticmethod
    def validate_filename(filename: str) -> str:
        """Valida nome de arquivo."""
        # Caracteres não permitidos no Windows e Unix
        invalid_chars = r'[\\/:*?"<>|]'
        
        if re.search(invalid_chars, filename):
            raise ValueError('Nome do arquivo contém caracteres inválidos')
        
        # Nomes reservados no Windows
        reserved_names = [
            'CON', 'PRN', 'AUX', 'NUL',
            'COM1', 'COM2', 'COM3', 'COM4', 'COM5', 'COM6', 'COM7', 'COM8', 'COM9',
            'LPT1', 'LPT2', 'LPT3', 'LPT4', 'LPT5', 'LPT6', 'LPT7', 'LPT8', 'LPT9'
        ]
        
        name_without_ext = filename.split('.')[0].upper()
        if name_without_ext in reserved_names:
            raise ValueError('Nome do arquivo é reservado pelo sistema')
        
        # Verificar comprimento
        if len(filename) > 255:
            raise ValueError('Nome do arquivo muito longo (máximo 255 caracteres)')
        
        return filename
    
    @staticmethod
    def validate_hash(hash_value: str, hash_type: str) -> str:
        """Valida formato de hash."""
        hash_patterns = {
            'md5': r'^[0-9A-Fa-f]{32}$',
            'sha1': r'^[0-9A-Fa-f]{40}$',
            'sha256': r'^[0-9A-Fa-f]{64}$',
            'crc32': r'^[0-9A-Fa-f]{8}$'
        }
        
        pattern = hash_patterns.get(hash_type.lower())
        if not pattern:
            raise ValueError(f'Tipo de hash não suportado: {hash_type}')
        
        if not re.match(pattern, hash_value):
            raise ValueError(f'Formato de hash {hash_type.upper()} inválido')
        
        return hash_value.upper()
    
    @staticmethod
    def validate_file_size(size: int, max_size_gb: int = 10) -> int:
        """Valida tamanho de arquivo."""
        if size < 0:
            raise ValueError('Tamanho do arquivo não pode ser negativo')
        
        max_bytes = max_size_gb * 1024 * 1024 * 1024
        if size > max_bytes:
            raise ValueError(f'Tamanho do arquivo excede o limite de {max_size_gb}GB')
        
        return size
    
    @staticmethod
    def validate_region_code(region: str) -> str:
        """Valida código de região."""
        valid_regions = [
            'USA', 'EUR', 'JPN', 'BRA', 'KOR', 'CHN', 'AUS', 'CAN',
            'FRA', 'GER', 'ITA', 'SPA', 'UK', 'RUS', 'MEX', 'ARG'
        ]
        
        if region.upper() not in valid_regions:
            raise ValueError(f'Código de região inválido: {region}')
        
        return region.upper()