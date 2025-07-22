"""Configurações centralizadas do MegaEmu Modern.

Utiliza Pydantic Settings para validação e carregamento de variáveis de ambiente.
Todas as configurações são tipadas e validadas automaticamente.
"""

import secrets
from typing import Any, Dict, List, Optional, Union

from pydantic import AnyHttpUrl, EmailStr, HttpUrl, PostgresDsn
from pydantic_settings import BaseSettings
from pydantic import model_validator, field_validator, ConfigDict


class Settings(BaseSettings):
    """Configurações principais da aplicação.
    
    Carrega configurações de variáveis de ambiente com validação automática.
    Suporta arquivos .env para desenvolvimento local.
    """
    
    # Informações do projeto
    PROJECT_NAME: str = "MegaEmu Modern"
    VERSION: str = "1.0.0"
    DESCRIPTION: str = "Sistema moderno para catalogação de ROMs de videogames retro"
    
    # API
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str = secrets.token_urlsafe(32)
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 8  # 8 dias
    
    # Debug e desenvolvimento
    DEBUG: bool = True
    TESTING: bool = False    
    # CORS
    BACKEND_CORS_ORIGINS: List[AnyHttpUrl] = [
        "http://localhost:3000",  # React dev server
        "http://localhost:5173",  # Vite dev server
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ]
    
    @field_validator('BACKEND_CORS_ORIGINS', mode='before')
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> Union[List[str], str]:
        if isinstance(v, str) and not v.startswith('['):
            return [i.strip() for i in v.split(',')]
        elif isinstance(v, (list, str)):
            return v
        raise ValueError(v)
    
    # Banco de dados PostgreSQL
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_USER: str = "megaemu"
    POSTGRES_PASSWORD: str = "megaemu123"
    POSTGRES_DB: str = "megaemu_modern"
    POSTGRES_PORT: int = 5432
    
    DATABASE_URL: Optional[str] = None
    
    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def assemble_db_connection(cls, v: Optional[str], info) -> Any:
        """Constrói URL de conexão do banco de dados."""
        if isinstance(v, str):
            return v
        # Se não há DATABASE_URL definida, usa SQLite para desenvolvimento
        return "sqlite+aiosqlite:///./megaemu_modern.db"    
    # Pool de conexões do banco
    DB_POOL_SIZE: int = 20
    DB_MAX_OVERFLOW: int = 30
    DB_POOL_TIMEOUT: int = 30
    DB_POOL_RECYCLE: int = 3600
    
    # Database timeouts
    DATABASE_STATEMENT_TIMEOUT: int = 30  # segundos
    
    # Redis
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: Optional[str] = None
    REDIS_DB: int = 0
    REDIS_URL: Optional[str] = None
    
    @model_validator(mode='after')
    def assemble_connections(self) -> 'Settings':
        """Monta URLs de conexão para Redis e outros serviços."""
        if not self.REDIS_URL:
            if self.REDIS_PASSWORD:
                self.REDIS_URL = f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
            else:
                self.REDIS_URL = f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
        return self
    
    # Cache
    CACHE_TTL: int = 300  # 5 minutos
    CACHE_MAX_SIZE: int = 1000
    
    # Celery (para tarefas assíncronas)
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/1"
    
    # Web Scraping
    SCRAPING_DELAY: float = 1.0
    SCRAPING_TIMEOUT: int = 30
    SCRAPING_RETRIES: int = 3
    SCRAPING_USER_AGENT: str = "MegaEmu-Modern/1.0.0"
    
    # Playwright
    PLAYWRIGHT_HEADLESS: bool = True
    PLAYWRIGHT_TIMEOUT: int = 30000    
    # Rate Limiting
    ENABLE_RATE_LIMITING: bool = True
    RATE_LIMIT_REQUESTS: int = 100
    RATE_LIMIT_WINDOW: int = 3600  # 1 hora
    
    # Upload de arquivos
    MAX_UPLOAD_SIZE: int = 50 * 1024 * 1024  # 50MB
    ALLOWED_EXTENSIONS: List[str] = [
        ".zip", ".rar", ".7z", ".tar", ".gz",
        ".jpg", ".jpeg", ".png", ".gif", ".webp",
        ".pdf", ".txt", ".md"
    ]
    
    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    LOG_FILE: str = "logs/megaemu.log"
    LOG_MAX_SIZE: int = 10 * 1024 * 1024  # 10MB
    LOG_BACKUP_COUNT: int = 5
    
    # Métricas e monitoramento
    ENABLE_METRICS: bool = True
    METRICS_PORT: int = 8001
    
    # Segurança
    ALGORITHM: str = "HS256"
    PASSWORD_MIN_LENGTH: int = 8
    PASSWORD_REQUIRE_UPPERCASE: bool = True
    PASSWORD_REQUIRE_LOWERCASE: bool = True
    PASSWORD_REQUIRE_NUMBERS: bool = True
    PASSWORD_REQUIRE_SPECIAL: bool = True
    
    # Email
    SMTP_TLS: bool = True
    SMTP_PORT: Optional[int] = None
    SMTP_HOST: Optional[str] = None
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    EMAILS_FROM_EMAIL: Optional[EmailStr] = None
    EMAILS_FROM_NAME: Optional[str] = None    
    @field_validator('EMAILS_FROM_NAME', mode='before')
    @classmethod
    def get_project_name(cls, v: Optional[str], info) -> str:
        if not v:
            return info.data.get('PROJECT_NAME', 'MegaEmu Modern')
        return v
    
    # Diretórios de dados
    DATA_DIR: str = "data"
    ROMS_DIR: str = "data/roms"
    COVERS_DIR: str = "data/covers"
    SCREENSHOTS_DIR: str = "data/screenshots"
    MANUALS_DIR: str = "data/manuals"
    SAVES_DIR: str = "data/saves"
    TEMP_DIR: str = "data/temp"
    
    # Configurações específicas do MegaEmu
    SUPPORTED_SYSTEMS: List[str] = [
        "nes", "snes", "gb", "gbc", "gba", "n64",
        "genesis", "sms", "gg", "psx", "ps2",
        "arcade", "mame", "fba"
    ]
    
    ROM_EXTENSIONS: Dict[str, List[str]] = {
        "nes": [".nes", ".unf"],
        "snes": [".smc", ".sfc", ".fig"],
        "gb": [".gb"],
        "gbc": [".gbc"],
        "gba": [".gba"],
        "n64": [".n64", ".v64", ".z64"],
        "genesis": [".md", ".gen", ".smd"],
        "sms": [".sms"],
        "gg": [".gg"],
        "psx": [".bin", ".cue", ".iso", ".img"],
        "ps2": [".iso"],
        "arcade": [".zip"],
        "mame": [".zip"],
        "fba": [".zip"]
    }    
    # Integração com APIs externas
    IGDB_CLIENT_ID: Optional[str] = None
    IGDB_CLIENT_SECRET: Optional[str] = None
    THEGAMESDB_API_KEY: Optional[str] = None
    MOBYGAMES_API_KEY: Optional[str] = None
    
    # Backup automático
    BACKUP_ENABLED: bool = True
    BACKUP_INTERVAL_HOURS: int = 24
    BACKUP_RETENTION_DAYS: int = 30
    BACKUP_LOCATION: str = "backups"
    
    model_config = ConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="forbid"
    )


from functools import lru_cache
import os

@lru_cache()
def get_settings() -> Settings:
    """Retorna instância das configurações baseada no ambiente."""
    return Settings()

# Instância global das configurações
settings = Settings()


# Configurações derivadas para facilitar o uso
class DerivedSettings:
    """Configurações derivadas das principais."""
    
    @staticmethod
    def get_database_url() -> str:
        """Retorna URL do banco de dados como string."""
        return str(settings.DATABASE_URL)
    
    @staticmethod
    def get_redis_url() -> str:
        """Retorna URL do Redis como string."""
        return str(settings.REDIS_URL)
    
    @staticmethod
    def is_development() -> bool:
        """Verifica se está em modo de desenvolvimento."""
        return settings.DEBUG
    
    @staticmethod
    def is_testing() -> bool:
        """Verifica se está em modo de teste."""
        return settings.TESTING


derived_settings = DerivedSettings()