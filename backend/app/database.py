"""Configuração do banco de dados.

Este módulo configura a conexão com o banco de dados SQLAlchemy,
gerencia sessões e fornece utilitários para operações de banco.
"""

import logging
from contextlib import contextmanager
from typing import Generator, Optional

from sqlalchemy import (
    create_engine,
    event,
    MetaData,
    inspect
)
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import (
    sessionmaker,
    Session,
    declarative_base
)
from sqlalchemy.pool import StaticPool

from app.core.config import settings

# Configuração do logger
logger = logging.getLogger(__name__)

# Metadados para convenções de nomenclatura
convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s"
}

metadata = MetaData(naming_convention=convention)

# Base declarativa para modelos
Base = declarative_base(metadata=metadata)

# Engine do SQLAlchemy
engine: Optional[Engine] = None

# Factory de sessões
SessionLocal: Optional[sessionmaker] = None


def create_database_engine() -> Engine:
    """Cria e configura o engine do banco de dados."""
    global engine
    
    if engine is not None:
        return engine
    
    # Configurações do engine baseadas no tipo de banco
    engine_kwargs = {
        "echo": settings.DEBUG,
        "future": True,
    }
    
    # Configurações específicas para SQLite
    if settings.DATABASE_URL.startswith("sqlite"):
        engine_kwargs.update({
            "poolclass": StaticPool,
            "connect_args": {
                "check_same_thread": False,
                "timeout": 20
            }
        })
    else:
        # Configurações para outros bancos (PostgreSQL, MySQL, etc.)
        engine_kwargs.update({
            "pool_size": settings.DATABASE_POOL_SIZE,
            "max_overflow": settings.DATABASE_MAX_OVERFLOW,
            "pool_pre_ping": True,
            "pool_recycle": 3600
        })
    
    try:
        engine = create_engine(settings.DATABASE_URL, **engine_kwargs)
        
        # Configura eventos do SQLAlchemy
        configure_engine_events(engine)
        
        logger.info(f"Engine do banco de dados criado: {settings.DATABASE_URL}")
        return engine
        
    except Exception as e:
        logger.error(f"Erro ao criar engine do banco: {e}")
        raise


def configure_engine_events(engine: Engine) -> None:
    """Configura eventos do engine."""
    
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        """Configura pragmas do SQLite."""
        if settings.DATABASE_URL.startswith("sqlite"):
            cursor = dbapi_connection.cursor()
            # Habilita chaves estrangeiras
            cursor.execute("PRAGMA foreign_keys=ON")
            # Configura modo WAL para melhor concorrência
            cursor.execute("PRAGMA journal_mode=WAL")
            # Configura sincronização
            cursor.execute("PRAGMA synchronous=NORMAL")
            # Configura timeout
            cursor.execute("PRAGMA busy_timeout=30000")
            cursor.close()
    
    @event.listens_for(engine, "before_cursor_execute")
    def receive_before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        """Log de queries em modo debug."""
        if settings.DEBUG:
            logger.debug(f"SQL: {statement}")
            if parameters:
                logger.debug(f"Parâmetros: {parameters}")


def create_session_factory() -> sessionmaker:
    """Cria factory de sessões."""
    global SessionLocal
    
    if SessionLocal is not None:
        return SessionLocal
    
    if engine is None:
        create_database_engine()
    
    SessionLocal = sessionmaker(
        bind=engine,
        autocommit=False,
        autoflush=False,
        expire_on_commit=False
    )
    
    logger.info("Factory de sessões criada")
    return SessionLocal


def get_db() -> Generator[Session, None, None]:
    """Dependency para obter sessão do banco de dados.
    
    Usado como dependency no FastAPI para injeção de dependência.
    """
    if SessionLocal is None:
        create_session_factory()
    
    db = SessionLocal()
    try:
        yield db
    except SQLAlchemyError as e:
        logger.error(f"Erro na sessão do banco: {e}")
        db.rollback()
        raise
    finally:
        db.close()


@contextmanager
def get_db_session() -> Generator[Session, None, None]:
    """Context manager para sessões do banco de dados.
    
    Usado para operações manuais fora do FastAPI.
    """
    if SessionLocal is None:
        create_session_factory()
    
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except SQLAlchemyError as e:
        logger.error(f"Erro na sessão do banco: {e}")
        db.rollback()
        raise
    except Exception as e:
        logger.error(f"Erro inesperado na sessão: {e}")
        db.rollback()
        raise
    finally:
        db.close()


def create_tables() -> None:
    """Cria todas as tabelas do banco de dados."""
    try:
        if engine is None:
            create_database_engine()
        
        # Importa todos os modelos para garantir que estão registrados
        from app.models import (
            User, System, Game, ROM, Task,
            UserPreferences, SystemEmulator, SystemMetadata,
            GameGenre, GameScreenshot, GameMetadata,
            ROMFile, ROMVerification, TaskResult
        )
        
        Base.metadata.create_all(bind=engine)
        logger.info("Tabelas do banco de dados criadas")
        
    except Exception as e:
        logger.error(f"Erro ao criar tabelas: {e}")
        raise


def drop_tables() -> None:
    """Remove todas as tabelas do banco de dados."""
    try:
        if engine is None:
            create_database_engine()
        
        Base.metadata.drop_all(bind=engine)
        logger.info("Tabelas do banco de dados removidas")
        
    except Exception as e:
        logger.error(f"Erro ao remover tabelas: {e}")
        raise


def reset_database() -> None:
    """Reseta o banco de dados (remove e recria tabelas)."""
    logger.warning("Resetando banco de dados...")
    drop_tables()
    create_tables()
    logger.info("Banco de dados resetado")


def check_database_connection() -> bool:
    """Verifica se a conexão com o banco está funcionando."""
    try:
        if engine is None:
            create_database_engine()
        
        with engine.connect() as conn:
            conn.execute("SELECT 1")
        
        logger.info("Conexão com banco de dados OK")
        return True
        
    except Exception as e:
        logger.error(f"Erro na conexão com banco: {e}")
        return False


def get_database_info() -> dict:
    """Retorna informações sobre o banco de dados."""
    try:
        if engine is None:
            create_database_engine()
        
        inspector = inspect(engine)
        
        info = {
            "url": str(engine.url).replace(engine.url.password or "", "***"),
            "driver": engine.dialect.name,
            "tables": inspector.get_table_names(),
            "pool_size": getattr(engine.pool, 'size', None),
            "pool_checked_out": getattr(engine.pool, 'checkedout', None),
            "pool_overflow": getattr(engine.pool, 'overflow', None),
        }
        
        return info
        
    except Exception as e:
        logger.error(f"Erro ao obter informações do banco: {e}")
        return {"error": str(e)}


def backup_database(backup_path: str) -> bool:
    """Cria backup do banco de dados."""
    try:
        if not settings.DATABASE_URL.startswith("sqlite"):
            logger.warning("Backup automático só suportado para SQLite")
            return False
        
        import shutil
        from pathlib import Path
        
        # Extrai caminho do arquivo SQLite
        db_path = settings.DATABASE_URL.replace("sqlite:///", "")
        
        if not Path(db_path).exists():
            logger.error(f"Arquivo do banco não encontrado: {db_path}")
            return False
        
        # Cria backup
        shutil.copy2(db_path, backup_path)
        logger.info(f"Backup criado: {backup_path}")
        return True
        
    except Exception as e:
        logger.error(f"Erro ao criar backup: {e}")
        return False


def restore_database(backup_path: str) -> bool:
    """Restaura banco de dados a partir de backup."""
    global engine, SessionLocal
    try:
        if not settings.DATABASE_URL.startswith("sqlite"):
            logger.warning("Restore automático só suportado para SQLite")
            return False
        
        import shutil
        from pathlib import Path
        
        if not Path(backup_path).exists():
            logger.error(f"Arquivo de backup não encontrado: {backup_path}")
            return False
        
        # Fecha conexões existentes
        if engine:
            engine.dispose()
        
        # Extrai caminho do arquivo SQLite
        db_path = settings.DATABASE_URL.replace("sqlite:///", "")
        
        # Restaura backup
        shutil.copy2(backup_path, db_path)
        
        # Recria engine
        engine = None
        SessionLocal = None
        create_database_engine()
        create_session_factory()
        
        logger.info(f"Banco restaurado de: {backup_path}")
        return True
        
    except Exception as e:
        logger.error(f"Erro ao restaurar backup: {e}")
        return False


def get_table_stats() -> dict:
    """Retorna estatísticas das tabelas."""
    try:
        with get_db_session() as db:
            from app.models import User, System, Game, ROM, Task
            
            stats = {
                "users": db.query(User).count(),
                "systems": db.query(System).count(),
                "games": db.query(Game).count(),
                "roms": db.query(ROM).count(),
                "tasks": db.query(Task).count(),
            }
            
            return stats
            
    except Exception as e:
        logger.error(f"Erro ao obter estatísticas: {e}")
        return {"error": str(e)}


def optimize_database() -> bool:
    """Otimiza o banco de dados."""
    try:
        if settings.DATABASE_URL.startswith("sqlite"):
            with get_db_session() as db:
                # Executa VACUUM para SQLite
                db.execute("VACUUM")
                db.execute("ANALYZE")
                logger.info("Banco SQLite otimizado")
                return True
        else:
            logger.info("Otimização automática não implementada para este banco")
            return False
            
    except Exception as e:
        logger.error(f"Erro ao otimizar banco: {e}")
        return False


# Inicialização automática em desenvolvimento
if settings.DEBUG:
    try:
        create_database_engine()
        create_session_factory()
        
        # Verifica se precisa criar tabelas
        if engine and not inspect(engine).get_table_names():
            logger.info("Criando tabelas iniciais...")
            create_tables()
            
    except Exception as e:
        logger.warning(f"Erro na inicialização automática: {e}")