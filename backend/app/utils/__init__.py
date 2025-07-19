"""Módulo de utilitários para o MegaEmu Modern.

Este módulo contém funções utilitárias para manipulação de arquivos,
cálculo de hashes, validação de dados e outras operações auxiliares.
"""

from .file_utils import (
    calculate_file_hash,
    get_file_size,
    get_file_extension,
    is_archive_file,
    extract_archive,
    normalize_path,
    validate_file_path,
    create_directory,
    copy_file,
    move_file,
    delete_file,
    list_directory_files,
    get_file_info,
    compress_file,
    decompress_file
)

from .validation_utils import (
    validate_email,
    validate_password_strength,
    validate_username,
    validate_file_extension,
    validate_file_size,
    validate_hash_format,
    validate_url,
    validate_date_range,
    sanitize_filename,
    sanitize_path
)

from .string_utils import (
    normalize_string,
    clean_filename,
    extract_numbers,
    extract_version,
    similarity_ratio,
    fuzzy_match,
    slugify,
    truncate_string,
    format_file_size,
    format_duration
)

from .crypto_utils import (
    generate_salt,
    hash_password,
    verify_password,
    generate_token,
    decode_jwt_token,
    encrypt_simple,
    decrypt_simple
)

from .email import (
    send_email,
    send_verification_email,
    send_password_reset_email
)

__all__ = [
    # File utilities
    "calculate_file_hash",
    "get_file_size",
    "get_file_extension",
    "is_archive_file",
    "extract_archive",
    "normalize_path",
    "validate_file_path",
    "create_directory",
    "copy_file",
    "move_file",
    "delete_file",
    "list_directory_files",
    "get_file_info",
    "compress_file",
    "decompress_file",
    
    # Validation utilities
    "validate_email",
    "validate_password",
    "validate_username",
    "validate_file_extension",
    "validate_file_size",
    "validate_hash",
    "validate_url",
    "validate_date_range",
    "sanitize_filename",
    "sanitize_path",
    
    # String utilities
    "normalize_string",
    "clean_string",
    "extract_numbers",
    "extract_year",
    "similarity_score",
    "fuzzy_match",
    "generate_slug",
    "truncate_string",
    "format_file_size",
    "format_duration",
    
    # Crypto utilities
    "generate_salt",
    "hash_password",
    "verify_password",
    "generate_token",
    "decode_jwt_token",
    "encrypt_simple",
    "decrypt_simple",
    
    # Email utilities
    "send_email",
    "send_verification_email",
    "send_password_reset_email"
]