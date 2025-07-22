"""Configurações da aplicação MegaEmu Modern.

Este módulo centraliza todas as configurações do sistema,
incluindo banco de dados, autenticação, logging e paths.
"""

import os
from datetime import timedelta
from pathlib import Path
from typing import List, Optional
from pydantic_settings import BaseSettings
from pydantic import field_validator
from functools import lru_cache


class Settings(BaseSettings):
    """Configurações da aplicação."""
    
    # Informações básicas da aplicação
    APP_NAME: str = "MegaEmu Modern"
    APP_VERSION: str = "1.0.0"
    APP_DESCRIPTION: str = "Sistema moderno de catalogação de ROMs"
    DEBUG: bool = False
    
    # Configurações do servidor
    HOST: str = "localhost"
    PORT: int = 8000
    RELOAD: bool = False
    
    # Configurações de segurança
    SECRET_KEY: str = "your-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # Configurações de CORS
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]
    CORS_ALLOW_CREDENTIALS: bool = True
    CORS_ALLOW_METHODS: List[str] = ["*"]
    CORS_ALLOW_HEADERS: List[str] = ["*"]
    
    # Configurações do banco de dados
    DATABASE_URL: str = "sqlite:///./megaemu.db"
    DATABASE_ECHO: bool = False
    DATABASE_POOL_SIZE: int = 5
    DATABASE_MAX_OVERFLOW: int = 10
    
    # Configurações de Redis (para cache e sessões)
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_CACHE_TTL: int = 3600  # 1 hora
    
    # Configurações de paths
    BASE_DIR: Path = Path(__file__).parent.parent
    DATA_DIR: Path = BASE_DIR / "data"
    LOGS_DIR: Path = BASE_DIR / "logs"
    TEMP_DIR: Path = BASE_DIR / "temp"
    UPLOADS_DIR: Path = BASE_DIR / "uploads"
    BACKUPS_DIR: Path = BASE_DIR / "backups"
    
    # Configurações de ROMs
    ROM_EXTENSIONS: List[str] = [
        ".zip", ".rar", ".7z", ".gz", ".tar",
        ".nes", ".smc", ".sfc", ".md", ".gen",
        ".gb", ".gbc", ".gba", ".n64", ".z64",
        ".iso", ".cue", ".bin", ".img", ".nrg"
    ]
    
    ROM_MAX_SIZE_MB: int = 4096  # 4GB
    ROM_SCAN_RECURSIVE: bool = True
    ROM_AUTO_EXTRACT: bool = True
    ROM_AUTO_VERIFY: bool = True
    
    # Configurações de importação
    IMPORT_BATCH_SIZE: int = 100
    IMPORT_MAX_CONCURRENT: int = 4
    IMPORT_TIMEOUT_SECONDS: int = 300
    
    # Configurações de verificação
    VERIFICATION_ALGORITHMS: List[str] = ["md5", "sha1", "crc32"]
    VERIFICATION_BATCH_SIZE: int = 50
    VERIFICATION_TIMEOUT_SECONDS: int = 600
    
    # Configurações de logging
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    LOG_MAX_SIZE_MB: int = 10
    LOG_BACKUP_COUNT: int = 5
    LOG_TO_FILE: bool = True
    LOG_TO_CONSOLE: bool = True
    
    # Configurações de tarefas assíncronas
    TASK_QUEUE_SIZE: int = 1000
    TASK_WORKER_COUNT: int = 4
    TASK_RETRY_ATTEMPTS: int = 3
    TASK_RETRY_DELAY_SECONDS: int = 60
    TASK_CLEANUP_HOURS: int = 24
    
    # Configurações de retry para banco de dados
    DATABASE_RETRY_ATTEMPTS: int = 3
    DATABASE_RETRY_DELAY_SECONDS: int = 5
    
    # Configurações de cache
    CACHE_ENABLED: bool = True
    CACHE_DEFAULT_TTL: int = 3600
    CACHE_MAX_SIZE: int = 1000
    
    # Configurações de API
    API_V1_PREFIX: str = "/api/v1"
    API_RATE_LIMIT: str = "100/minute"
    API_MAX_PAGE_SIZE: int = 100
    API_DEFAULT_PAGE_SIZE: int = 20
    
    # Configurações de upload
    UPLOAD_MAX_SIZE_MB: int = 100
    UPLOAD_ALLOWED_EXTENSIONS: List[str] = [
        ".jpg", ".jpeg", ".png", ".gif", ".webp",
        ".xml", ".dat", ".txt", ".json"
    ]
    
    # Configurações de backup
    BACKUP_ENABLED: bool = True
    BACKUP_SCHEDULE: str = "0 2 * * *"  # Diário às 2h
    BACKUP_RETENTION_DAYS: int = 30
    BACKUP_COMPRESS: bool = True
    CLOUD_BACKUP_ENABLED: bool = False
    AWS_S3_BUCKET: Optional[str] = None
    AWS_S3_REGION: Optional[str] = None
    AWS_ACCESS_KEY_ID: Optional[str] = None
    AWS_SECRET_ACCESS_KEY: Optional[str] = None
    
    # Configurações de monitoramento
    MONITORING_ENABLED: bool = True
    METRICS_ENABLED: bool = True
    HEALTH_CHECK_INTERVAL: int = 60
    
    # Configurações de email (para notificações)
    EMAIL_ENABLED: bool = False
    SMTP_HOST: str = "localhost"
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_USE_TLS: bool = True
    EMAIL_FROM: str = "noreply@megaemu.local"
    
    # Configurações de integração externa
    EXTERNAL_API_TIMEOUT: int = 30
    EXTERNAL_API_RETRIES: int = 3
    EXTERNAL_API_RATE_LIMIT: str = "10/minute"
    
    # Configurações de desenvolvimento
    DEV_MODE: bool = False
    DEV_RELOAD: bool = False
    DEV_DEBUG_SQL: bool = False
    
    @field_validator('SECRET_KEY')
    def validate_secret_key(cls, v):
        """Valida chave secreta."""
        if len(v) < 32:
            raise ValueError('SECRET_KEY deve ter pelo menos 32 caracteres')
        return v
        
    @field_validator('DATABASE_URL')
    def validate_database_url(cls, v):
        """Valida URL do banco de dados."""
        if not v:
            raise ValueError('DATABASE_URL é obrigatória')
        return v
        
    @field_validator('CORS_ORIGINS')
    def validate_cors_origins(cls, v):
        """Valida origens CORS."""
        if not isinstance(v, list):
            raise ValueError('CORS_ORIGINS deve ser uma lista')
        return v
        
    @field_validator('ROM_EXTENSIONS')
    def validate_rom_extensions(cls, v):
        """Valida extensões de ROM."""
        if not isinstance(v, list):
            raise ValueError('ROM_EXTENSIONS deve ser uma lista')
        
        # Garante que todas as extensões começam com ponto
        validated = []
        for ext in v:
            if not ext.startswith('.'):
                ext = '.' + ext
            validated.append(ext.lower())
        
        return validated
        
    @field_validator('LOG_LEVEL')
    def validate_log_level(cls, v):
        """Valida nível de log."""
        valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        if v.upper() not in valid_levels:
            raise ValueError(f'LOG_LEVEL deve ser um de: {valid_levels}')
        return v.upper()
    
    def create_directories(self):
        """Cria diretórios necessários."""
        directories = [
            self.DATA_DIR,
            self.LOGS_DIR,
            self.TEMP_DIR,
            self.UPLOADS_DIR,
            self.BACKUPS_DIR
        ]
        
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
    
    def get_database_url(self) -> str:
        """Retorna URL do banco de dados."""
        return self.DATABASE_URL
    
    def get_redis_url(self) -> str:
        """Retorna URL do Redis."""
        return self.REDIS_URL
    
    def is_production(self) -> bool:
        """Verifica se está em produção."""
        return not self.DEBUG and not self.DEV_MODE
    
    def is_development(self) -> bool:
        """Verifica se está em desenvolvimento."""
        return self.DEBUG or self.DEV_MODE
    
    def get_jwt_settings(self) -> dict:
        """Retorna configurações JWT."""
        return {
            "secret_key": self.SECRET_KEY,
            "algorithm": self.ALGORITHM,
            "access_token_expire_minutes": self.ACCESS_TOKEN_EXPIRE_MINUTES,
            "refresh_token_expire_days": self.REFRESH_TOKEN_EXPIRE_DAYS
        }
    
    def get_cors_settings(self) -> dict:
        """Retorna configurações CORS."""
        return {
            "allow_origins": self.CORS_ORIGINS,
            "allow_credentials": self.CORS_ALLOW_CREDENTIALS,
            "allow_methods": self.CORS_ALLOW_METHODS,
            "allow_headers": self.CORS_ALLOW_HEADERS
        }
    
    def get_upload_settings(self) -> dict:
        """Retorna configurações de upload."""
        return {
            "max_size_mb": self.UPLOAD_MAX_SIZE_MB,
            "allowed_extensions": self.UPLOAD_ALLOWED_EXTENSIONS,
            "upload_dir": self.UPLOADS_DIR
        }
    
    def get_rom_settings(self) -> dict:
        """Retorna configurações de ROM."""
        return {
            "extensions": self.ROM_EXTENSIONS,
            "max_size_mb": self.ROM_MAX_SIZE_MB,
            "scan_recursive": self.ROM_SCAN_RECURSIVE,
            "auto_extract": self.ROM_AUTO_EXTRACT,
            "auto_verify": self.ROM_AUTO_VERIFY
        }
    
    def get_task_settings(self) -> dict:
        """Retorna configurações de tarefas."""
        return {
            "queue_size": self.TASK_QUEUE_SIZE,
            "worker_count": self.TASK_WORKER_COUNT,
            "retry_attempts": self.TASK_RETRY_ATTEMPTS,
            "retry_delay_seconds": self.TASK_RETRY_DELAY_SECONDS,
            "cleanup_hours": self.TASK_CLEANUP_HOURS
        }
    
    class Config:
        """Configuração do Pydantic."""
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


class DevelopmentSettings(Settings):
    """Configurações para desenvolvimento."""
    
    DEBUG: bool = True
    DEV_MODE: bool = True
    DEV_RELOAD: bool = True
    DEV_DEBUG_SQL: bool = True
    
    LOG_LEVEL: str = "DEBUG"
    LOG_TO_CONSOLE: bool = True
    
    DATABASE_ECHO: bool = True
    
    # Configurações mais permissivas para desenvolvimento
    CORS_ORIGINS: List[str] = ["*"]
    API_RATE_LIMIT: str = "1000/minute"


class ProductionSettings(Settings):
    """Configurações para produção."""
    
    DEBUG: bool = False
    DEV_MODE: bool = False
    
    LOG_LEVEL: str = "INFO"
    LOG_TO_FILE: bool = True
    
    # Configurações mais restritivas para produção
    API_RATE_LIMIT: str = "60/minute"
    
    BACKUP_ENABLED: bool = True
    MONITORING_ENABLED: bool = True
    METRICS_ENABLED: bool = True


class TestSettings(Settings):
    """Configurações para testes."""
    
    DEBUG: bool = True
    
    # Banco de dados em memória para testes
    DATABASE_URL: str = "sqlite:///:memory:"
    DATABASE_ECHO: bool = False
    
    # Desabilita funcionalidades externas
    CACHE_ENABLED: bool = False
    EMAIL_ENABLED: bool = False
    BACKUP_ENABLED: bool = False
    MONITORING_ENABLED: bool = False
    
    # Configurações de teste
    TASK_WORKER_COUNT: int = 1
    IMPORT_BATCH_SIZE: int = 10
    VERIFICATION_BATCH_SIZE: int = 10


@lru_cache()
def get_settings() -> Settings:
    """Retorna instância das configurações baseada no ambiente."""
    environment = os.getenv("ENVIRONMENT", "development").lower()
    
    if environment == "production":
        return ProductionSettings()
    elif environment == "test":
        return TestSettings()
    else:
        return DevelopmentSettings()


# Instância global das configurações
settings = get_settings()

# Cria diretórios necessários
settings.create_directories()