"""Configuração do banco de dados PostgreSQL com SQLAlchemy async.

Implementa pool de conexões otimizado, sessões assíncronas e utilitários
para operações de banco de dados de alta performance.
"""

import time
from typing import AsyncGenerator, Optional

from loguru import logger
from prometheus_client import Histogram, Gauge
from sqlalchemy import MetaData, event
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool, QueuePool

from app.core.config import settings


class Base(DeclarativeBase):
    """Classe base para todos os modelos SQLAlchemy.
    
    Define convenções de nomenclatura para tabelas e constraints.
    """
    
    metadata = MetaData(
        naming_convention={
            "ix": "ix_%(column_0_label)s",
            "uq": "uq_%(table_name)s_%(column_0_name)s",
            "ck": "ck_%(table_name)s_%(constraint_name)s",
            "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
            "pk": "pk_%(table_name)s",
        }
    )


# Engine assíncrono com configuração adaptável para SQLite e PostgreSQL
if str(settings.DATABASE_URL).startswith("sqlite"):
    # Configuração para SQLite com aiosqlite
    database_url = str(settings.DATABASE_URL).replace("sqlite:///", "sqlite+aiosqlite:///")
    engine = create_async_engine(
        database_url,
        echo=settings.DEBUG,
        poolclass=NullPool,  # SQLite não precisa de pool
        connect_args={"check_same_thread": False},
    )
else:
    # Configuração para PostgreSQL
    engine = create_async_engine(
        str(settings.DATABASE_URL),
        echo=settings.DEBUG,
        echo_pool=settings.DEBUG,
        pool_size=settings.DB_POOL_SIZE,
        max_overflow=settings.DB_MAX_OVERFLOW,
        pool_timeout=settings.DB_POOL_TIMEOUT,
        pool_recycle=settings.DB_POOL_RECYCLE,
        pool_pre_ping=True,
        connect_args={
            "server_settings": {
                "application_name": settings.PROJECT_NAME,
                "jit": "off",
            },
            "command_timeout": 60,
        },
    )

# Session factory assíncrona
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=True,
    autocommit=False,
)


# Event listeners para logging e monitoramento
@event.listens_for(engine.sync_engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    """Configura parâmetros de conexão específicos do PostgreSQL."""
    if settings.DEBUG:
        logger.debug("Nova conexão estabelecida com PostgreSQL")


@event.listens_for(engine.sync_engine, "checkout")
def receive_checkout(dbapi_connection, connection_record, connection_proxy):
    """Log quando uma conexão é retirada do pool."""
    if settings.DEBUG:
        logger.debug("Conexão retirada do pool")


@event.listens_for(engine.sync_engine, "checkin")
def receive_checkin(dbapi_connection, connection_record):
    """Log quando uma conexão é retornada ao pool."""
    if settings.DEBUG:
        logger.debug("Conexão retornada ao pool")


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency para obter sessão de banco de dados.
    
    Gerencia automaticamente o ciclo de vida da sessão:
    - Cria nova sessão
    - Faz yield da sessão para uso
    - Fecha sessão automaticamente
    - Faz rollback em caso de erro
    
    Yields:
        AsyncSession: Sessão de banco de dados configurada
    
    Example:
        ```python
        @app.get("/games/")
        async def get_games(db: AsyncSession = Depends(get_db)):
            result = await db.execute(select(Game))
            return result.scalars().all()
        ```
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception as e:
            await session.rollback()
            logger.error(f"Erro na sessão de banco de dados: {str(e)}")
            raise
        finally:
            await session.close()


class DatabaseManager:
    """Gerenciador de operações de banco de dados.
    
    Fornece métodos utilitários para operações comuns de banco de dados
    com tratamento de erros e logging integrados.
    """
    
    def __init__(self):
        self.engine = engine
        self.session_factory = AsyncSessionLocal
    
    async def health_check(self) -> bool:
        """Verifica se o banco de dados está acessível.
        
        Returns:
            bool: True se o banco estiver acessível, False caso contrário
        """
        try:
            from sqlalchemy import text
            async with self.engine.begin() as conn:
                await conn.execute(text("SELECT 1"))
            return True
        except Exception as e:
            logger.error(f"Health check do banco falhou: {e}")
            return False
    
    async def get_pool_status(self) -> dict:
        """Retorna informações sobre o pool de conexões.
        
        Returns:
            dict: Estatísticas do pool de conexões
        """
        pool = self.engine.pool
        return {
            "size": pool.size(),
            "checked_in": pool.checkedin(),
            "checked_out": pool.checkedout(),
            "overflow": pool.overflow(),
        }
    
    async def execute_raw_sql(self, sql: str, params: Optional[dict] = None) -> any:
        """Executa SQL bruto de forma segura.
        
        Args:
            sql: Query SQL para executar
            params: Parâmetros para a query
            
        Returns:
            Resultado da execução da query
        """
        async with self.session_factory() as session:
            try:
                result = await session.execute(sql, params or {})
                await session.commit()
                return result
            except Exception as e:
                await session.rollback()
                logger.error(f"Erro ao executar SQL: {e}")
                raise
    
    async def backup_database(self, backup_path: str) -> bool:
        """Cria backup do banco de dados.
        
        Args:
            backup_path: Caminho para salvar o backup
            
        Returns:
            bool: True se o backup foi criado com sucesso
        """
        try:
            # Implementar backup usando pg_dump
            import subprocess
            import os
            
            cmd = [
                "pg_dump",
                "-h", settings.POSTGRES_SERVER,
                "-p", str(settings.POSTGRES_PORT),
                "-U", settings.POSTGRES_USER,
                "-d", settings.POSTGRES_DB,
                "-f", backup_path,
                "--verbose",
                "--no-password",
            ]
            
            env = os.environ.copy()
            env["PGPASSWORD"] = settings.POSTGRES_PASSWORD
            
            process = subprocess.run(
                cmd,
                env=env,
                capture_output=True,
                text=True,
                timeout=3600,  # 1 hora timeout
            )
            
            if process.returncode == 0:
                logger.info(f"Backup criado com sucesso: {backup_path}")
                return True
            else:
                logger.error(f"Erro no backup: {process.stderr}")
                return False
                
        except Exception as e:
            logger.error(f"Erro ao criar backup: {e}")
            return False


# Instância global do gerenciador
db_manager = DatabaseManager()


# Utilitários para transações
class TransactionManager:
    """Context manager para transações de banco de dados.
    
    Simplifica o gerenciamento de transações com commit/rollback automático.
    """
    
    def __init__(self, session: AsyncSession):
        self.session = session
        self._transaction = None
    
    async def __aenter__(self):
        self._transaction = await self.session.begin()
        return self.session
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            await self._transaction.rollback()
            logger.error(f"Transação revertida devido a erro: {exc_val}")
        else:
            await self._transaction.commit()
            logger.debug("Transação commitada com sucesso")


async def with_transaction(session: AsyncSession):
    """Context manager para transações.
    
    Example:
        ```python
        async with with_transaction(session) as tx_session:
            # Operações de banco de dados
            await tx_session.add(new_game)
            # Commit automático se não houver erro
        ```
    """
    return TransactionManager(session)


# Métricas Prometheus
QUERY_DURATION = Histogram('database_query_duration_seconds', 'Duração das queries do banco de dados', ['operation'])
POOL_SIZE = Gauge('database_pool_size', 'Tamanho atual do pool de conexões')
POOL_CHECKED_IN = Gauge('database_pool_checked_in', 'Conexões checked in no pool')
POOL_CHECKED_OUT = Gauge('database_pool_checked_out', 'Conexões checked out no pool')
POOL_OVERFLOW = Gauge('database_pool_overflow', 'Overflow do pool de conexões')

@event.listens_for(engine.sync_engine, 'before_execute')
def before_execute(conn, clauseelement, multiparams, params):
    conn.info['query_start_time'] = time.time()
    return clauseelement, multiparams, params

@event.listens_for(engine.sync_engine, 'after_execute')
def after_execute(conn, clauseelement, multiparams, params, result):
    duration = time.time() - conn.info.get('query_start_time', 0)
    operation = str(clauseelement.__class__.__name__)
    QUERY_DURATION.labels(operation).observe(duration)
    return result


async def update_pool_metrics(self):
    status = await self.get_pool_status()
    POOL_SIZE.set(status['size'])
    POOL_CHECKED_IN.set(status['checked_in'])
    POOL_CHECKED_OUT.set(status['checked_out'])
    POOL_OVERFLOW.set(status['overflow'])