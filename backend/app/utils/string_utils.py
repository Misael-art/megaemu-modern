"""Utilitários para manipulação de strings.

Este módulo contém funções para formatação, normalização,
comparação e transformação de strings.
"""

import re
import unicodedata
from typing import List, Optional, Dict, Any
from difflib import SequenceMatcher


def normalize_string(text: str) -> str:
    """Normaliza string removendo acentos e caracteres especiais.
    
    Args:
        text: Texto para normalizar
        
    Returns:
        Texto normalizado
    """
    if not text:
        return ""
    
    # Remove acentos
    text = unicodedata.normalize('NFD', text)
    text = ''.join(char for char in text if unicodedata.category(char) != 'Mn')
    
    # Converte para minúsculo
    text = text.lower()
    
    # Remove caracteres especiais, mantém apenas letras, números e espaços
    text = re.sub(r'[^a-z0-9\s]', '', text)
    
    # Normaliza espaços
    text = re.sub(r'\s+', ' ', text).strip()
    
    return text


def slugify(text: str, separator: str = '-') -> str:
    """Converte texto em slug URL-friendly.
    
    Args:
        text: Texto para converter
        separator: Separador para espaços
        
    Returns:
        Slug gerado
    """
    if not text:
        return ""
    
    # Normaliza texto
    slug = normalize_string(text)
    
    # Substitui espaços pelo separador
    slug = re.sub(r'\s+', separator, slug)
    
    # Remove separadores duplicados
    slug = re.sub(f'{re.escape(separator)}+', separator, slug)
    
    # Remove separadores do início e fim
    slug = slug.strip(separator)
    
    return slug


def clean_filename(filename: str) -> str:
    """Limpa nome de arquivo removendo caracteres inválidos.
    
    Args:
        filename: Nome do arquivo
        
    Returns:
        Nome limpo
    """
    if not filename:
        return ""
    
    # Remove caracteres inválidos para nomes de arquivo
    invalid_chars = r'[<>:"/\\|?*]'
    filename = re.sub(invalid_chars, '_', filename)
    
    # Remove caracteres de controle
    filename = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', filename)
    
    # Normaliza espaços
    filename = re.sub(r'\s+', ' ', filename).strip()
    
    # Remove pontos do início e fim
    filename = filename.strip('.')
    
    return filename


def truncate_string(text: str, max_length: int, suffix: str = '...') -> str:
    """Trunca string mantendo comprimento máximo.
    
    Args:
        text: Texto para truncar
        max_length: Comprimento máximo
        suffix: Sufixo para indicar truncamento
        
    Returns:
        Texto truncado
    """
    if not text or len(text) <= max_length:
        return text
    
    if len(suffix) >= max_length:
        return text[:max_length]
    
    return text[:max_length - len(suffix)] + suffix


def extract_numbers(text: str) -> List[int]:
    """Extrai números de uma string.
    
    Args:
        text: Texto para extrair números
        
    Returns:
        Lista de números encontrados
    """
    if not text:
        return []
    
    numbers = re.findall(r'\d+', text)
    return [int(num) for num in numbers]


def extract_version(text: str) -> Optional[str]:
    """Extrai versão de uma string.
    
    Args:
        text: Texto para extrair versão
        
    Returns:
        Versão encontrada ou None
    """
    if not text:
        return None
    
    # Padrões comuns de versão
    patterns = [
        r'v?(\d+\.\d+\.\d+)',  # v1.2.3 ou 1.2.3
        r'v?(\d+\.\d+)',       # v1.2 ou 1.2
        r'v?(\d+)',            # v1 ou 1
        r'(\d+\.\d+\.\d+)',   # 1.2.3
        r'(\d+\.\d+)',        # 1.2
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1)
    
    return None


def similarity_ratio(text1: str, text2: str) -> float:
    """Calcula similaridade entre duas strings.
    
    Args:
        text1: Primeira string
        text2: Segunda string
        
    Returns:
        Ratio de similaridade (0.0 a 1.0)
    """
    if not text1 and not text2:
        return 1.0
    
    if not text1 or not text2:
        return 0.0
    
    # Normaliza strings para comparação
    norm1 = normalize_string(text1)
    norm2 = normalize_string(text2)
    
    return SequenceMatcher(None, norm1, norm2).ratio()


def fuzzy_match(text: str, candidates: List[str], threshold: float = 0.6) -> List[tuple]:
    """Busca fuzzy em lista de candidatos.
    
    Args:
        text: Texto para buscar
        candidates: Lista de candidatos
        threshold: Threshold mínimo de similaridade
        
    Returns:
        Lista de tuplas (candidato, score) ordenada por score
    """
    if not text or not candidates:
        return []
    
    matches = []
    
    for candidate in candidates:
        score = similarity_ratio(text, candidate)
        if score >= threshold:
            matches.append((candidate, score))
    
    # Ordena por score decrescente
    matches.sort(key=lambda x: x[1], reverse=True)
    
    return matches


def camel_to_snake(text: str) -> str:
    """Converte camelCase para snake_case.
    
    Args:
        text: Texto em camelCase
        
    Returns:
        Texto em snake_case
    """
    if not text:
        return ""
    
    # Adiciona underscore antes de letras maiúsculas
    text = re.sub(r'([a-z0-9])([A-Z])', r'\1_\2', text)
    
    return text.lower()


def snake_to_camel(text: str, capitalize_first: bool = False) -> str:
    """Converte snake_case para camelCase.
    
    Args:
        text: Texto em snake_case
        capitalize_first: Se deve capitalizar primeira letra
        
    Returns:
        Texto em camelCase
    """
    if not text:
        return ""
    
    components = text.split('_')
    
    if capitalize_first:
        return ''.join(word.capitalize() for word in components)
    else:
        return components[0] + ''.join(word.capitalize() for word in components[1:])


def title_case(text: str) -> str:
    """Converte texto para Title Case.
    
    Args:
        text: Texto para converter
        
    Returns:
        Texto em Title Case
    """
    if not text:
        return ""
    
    # Palavras que não devem ser capitalizadas (exceto no início)
    minor_words = {
        'a', 'an', 'and', 'as', 'at', 'but', 'by', 'for',
        'if', 'in', 'nor', 'of', 'on', 'or', 'so', 'the',
        'to', 'up', 'yet', 'da', 'de', 'do', 'e', 'em',
        'na', 'no', 'o', 'ou', 'para', 'por', 'um', 'uma'
    }
    
    words = text.lower().split()
    result = []
    
    for i, word in enumerate(words):
        if i == 0 or word not in minor_words:
            result.append(word.capitalize())
        else:
            result.append(word)
    
    return ' '.join(result)


def extract_parentheses_content(text: str) -> List[str]:
    """Extrai conteúdo entre parênteses.
    
    Args:
        text: Texto para extrair
        
    Returns:
        Lista de conteúdos encontrados
    """
    if not text:
        return []
    
    return re.findall(r'\(([^)]+)\)', text)


def extract_brackets_content(text: str) -> List[str]:
    """Extrai conteúdo entre colchetes.
    
    Args:
        text: Texto para extrair
        
    Returns:
        Lista de conteúdos encontrados
    """
    if not text:
        return []
    
    return re.findall(r'\[([^\]]+)\]', text)


def remove_extra_whitespace(text: str) -> str:
    """Remove espaços extras de uma string.
    
    Args:
        text: Texto para limpar
        
    Returns:
        Texto sem espaços extras
    """
    if not text:
        return ""
    
    # Remove espaços no início e fim
    text = text.strip()
    
    # Substitui múltiplos espaços por um único
    text = re.sub(r'\s+', ' ', text)
    
    return text


def format_file_size(size_bytes: int) -> str:
    """Formata tamanho de arquivo em formato legível.
    
    Args:
        size_bytes: Tamanho em bytes
        
    Returns:
        Tamanho formatado
    """
    if size_bytes == 0:
        return "0 B"
    
    units = ['B', 'KB', 'MB', 'GB', 'TB', 'PB']
    unit_index = 0
    size = float(size_bytes)
    
    while size >= 1024 and unit_index < len(units) - 1:
        size /= 1024
        unit_index += 1
    
    if unit_index == 0:
        return f"{int(size)} {units[unit_index]}"
    else:
        return f"{size:.2f} {units[unit_index]}"


def format_duration(seconds: int) -> str:
    """Formata duração em formato legível.
    
    Args:
        seconds: Duração em segundos
        
    Returns:
        Duração formatada
    """
    if seconds < 60:
        return f"{seconds}s"
    
    minutes = seconds // 60
    remaining_seconds = seconds % 60
    
    if minutes < 60:
        if remaining_seconds > 0:
            return f"{minutes}m {remaining_seconds}s"
        else:
            return f"{minutes}m"
    
    hours = minutes // 60
    remaining_minutes = minutes % 60
    
    if hours < 24:
        if remaining_minutes > 0:
            return f"{hours}h {remaining_minutes}m"
        else:
            return f"{hours}h"
    
    days = hours // 24
    remaining_hours = hours % 24
    
    if remaining_hours > 0:
        return f"{days}d {remaining_hours}h"
    else:
        return f"{days}d"


def parse_boolean(value: str) -> bool:
    """Converte string para boolean.
    
    Args:
        value: Valor para converter
        
    Returns:
        Valor boolean
    """
    if not isinstance(value, str):
        return bool(value)
    
    value = value.lower().strip()
    
    true_values = {'true', '1', 'yes', 'on', 'sim', 'verdadeiro'}
    false_values = {'false', '0', 'no', 'off', 'não', 'nao', 'falso'}
    
    if value in true_values:
        return True
    elif value in false_values:
        return False
    else:
        raise ValueError(f"Não é possível converter '{value}' para boolean")


def mask_sensitive_data(text: str, mask_char: str = '*', visible_chars: int = 4) -> str:
    """Mascara dados sensíveis mostrando apenas alguns caracteres.
    
    Args:
        text: Texto para mascarar
        mask_char: Caractere para mascarar
        visible_chars: Número de caracteres visíveis no final
        
    Returns:
        Texto mascarado
    """
    if not text or len(text) <= visible_chars:
        return mask_char * len(text) if text else ""
    
    masked_length = len(text) - visible_chars
    return mask_char * masked_length + text[-visible_chars:]


def generate_initials(name: str, max_initials: int = 2) -> str:
    """Gera iniciais de um nome.
    
    Args:
        name: Nome completo
        max_initials: Número máximo de iniciais
        
    Returns:
        Iniciais geradas
    """
    if not name:
        return ""
    
    words = name.strip().split()
    initials = []
    
    for word in words[:max_initials]:
        if word and word[0].isalpha():
            initials.append(word[0].upper())
    
    return ''.join(initials)


def highlight_search_terms(text: str, search_terms: List[str], highlight_tag: str = 'mark') -> str:
    """Destaca termos de busca no texto.
    
    Args:
        text: Texto original
        search_terms: Termos para destacar
        highlight_tag: Tag HTML para destaque
        
    Returns:
        Texto com termos destacados
    """
    if not text or not search_terms:
        return text
    
    result = text
    
    for term in search_terms:
        if term:
            # Escapa caracteres especiais do regex
            escaped_term = re.escape(term)
            pattern = f'({escaped_term})'
            replacement = f'<{highlight_tag}>\\1</{highlight_tag}>'
            result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
    
    return result


def extract_domain_from_url(url: str) -> Optional[str]:
    """Extrai domínio de uma URL.
    
    Args:
        url: URL para extrair domínio
        
    Returns:
        Domínio extraído ou None
    """
    if not url:
        return None
    
    # Remove protocolo
    url = re.sub(r'^https?://', '', url)
    
    # Remove caminho e parâmetros
    url = url.split('/')[0]
    url = url.split('?')[0]
    url = url.split('#')[0]
    
    # Remove porta
    url = url.split(':')[0]
    
    return url if url else None


def pluralize(word: str, count: int, plural_form: Optional[str] = None) -> str:
    """Pluraliza palavra baseado na contagem.
    
    Args:
        word: Palavra singular
        count: Contagem
        plural_form: Forma plural personalizada
        
    Returns:
        Palavra no singular ou plural
    """
    if count == 1:
        return word
    
    if plural_form:
        return plural_form
    
    # Regras básicas de pluralização em português
    if word.endswith(('s', 'x', 'z')):
        return word  # Invariável
    elif word.endswith('ão'):
        return word[:-2] + 'ões'  # Simplificado
    elif word.endswith('al'):
        return word[:-2] + 'ais'
    elif word.endswith('el'):
        return word[:-2] + 'éis'
    elif word.endswith('il'):
        return word[:-2] + 'is'
    elif word.endswith('ol'):
        return word[:-2] + 'óis'
    elif word.endswith('ul'):
        return word[:-2] + 'uis'
    else:
        return word + 's'  # Regra geral


def format_list(items: List[str], conjunction: str = 'e') -> str:
    """Formata lista de itens em string legível.
    
    Args:
        items: Lista de itens
        conjunction: Conjunção para último item
        
    Returns:
        String formatada
    """
    if not items:
        return ""
    
    if len(items) == 1:
        return items[0]
    
    if len(items) == 2:
        return f"{items[0]} {conjunction} {items[1]}"
    
    return f"{', '.join(items[:-1])} {conjunction} {items[-1]}"