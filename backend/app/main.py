"""MegaEmu Modern - FastAPI Main Application

Sistema moderno para catalogação e organização de ROMs de videogames retro.
Arquitetura baseada em FastAPI com SQLAlchemy async, Celery e PostgreSQL.
"""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.openapi.docs import get_swagger_ui_html, get_redoc_html
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from loguru import logger
from prometheus_client import make_asgi_app

from app.api.v1.api import api_router
from app.core.config import settings
from app.core.database import engine
from app.core.exceptions import (
    DatabaseError,
    MegaEmuException,
    ValidationError,
)
from app.core.logging import setup_logging
from app.core.middleware import (
    LoggingMiddleware,
    RateLimitMiddleware,
    SecurityHeadersMiddleware,
)
from app.core.container import container
from app.services.user import UserService
from app.services.factories import create_rom_service, create_import_service
from app.services.task import TaskService
from app.core.plugin_manager import plugin_manager
from alembic import command
from alembic.config import Config


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Gerencia o ciclo de vida da aplicação.
    
    Configura logging, conecta ao banco de dados e inicializa serviços
    durante o startup. Limpa recursos durante o shutdown.
    """
    # Startup
    logger.info("🚀 Iniciando MegaEmu Modern Backend")
    setup_logging()
    
    # Executar migrações Alembic de forma assíncrona
    try:
        from alembic.env import run_async_migrations
        await run_async_migrations()
        logger.info("✅ Migrações de banco de dados aplicadas com sucesso")
    except Exception as e:
        logger.error(f"❌ Erro ao aplicar migrações: {e}")
        # Não falhar se as migrações falharem em desenvolvimento
        logger.warning("Continuando sem migrações para desenvolvimento")
    
    # Migrações e DI comentados temporariamente para desenvolvimento
    logger.info("⚠️ Migrações e DI desabilitados para desenvolvimento")
    
    # Configurar container DI (comentado)
    # container.register_singleton(UserService, UserService)
    # container.register(ROMService, factory=create_rom_service, lifetime='singleton')
    # container.register(ImportService, factory=lambda: create_import_service(container.get(ROMService), container.get(TaskService)), lifetime='transient')
    
    # Inicializar gerenciador de plugins
    plugin_manager  # Força carregamento
    logger.info(f"✅ {len(plugin_manager.list_plugins())} plugins carregados")
    
    # Verificar conexão com banco de dados
    try:
        from sqlalchemy import text
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
        logger.info("✅ Conexão com PostgreSQL estabelecida")
    except Exception as e:
        logger.error(f"❌ Erro ao conectar com PostgreSQL: {e}")
        raise
    
    # Verificar conexão com Redis (comentado para desenvolvimento)
    # try:
    #     from app.core.redis import init_redis, redis_manager
    #     await init_redis()
    #     await redis_manager.ping()
    #     logger.info("✅ Conexão com Redis estabelecida")
    # except Exception as e:
    #     logger.error(f"❌ Erro ao conectar com Redis: {e}")
    #     raise
    
    logger.info("🎮 MegaEmu Modern Backend iniciado com sucesso!")
    
    yield
    
    # Shutdown
    logger.info("🛑 Finalizando MegaEmu Modern Backend")
    
    # Fechar conexão com Redis (comentado para desenvolvimento)
    # try:
    #     from app.core.redis import close_redis
    #     await close_redis()
    # except Exception as e:
    #     logger.error(f"Erro ao fechar Redis: {e}")
    
    await engine.dispose()
    logger.info("👋 MegaEmu Modern Backend finalizado")


def create_application() -> FastAPI:
    """Factory para criar a aplicação FastAPI.
    
    Configura middlewares, rotas, handlers de exceção e documentação.
    
    Returns:
        FastAPI: Instância configurada da aplicação
    """
    app = FastAPI(
        title=settings.PROJECT_NAME,
        description="Sistema moderno para catalogação de ROMs de videogames retro",
        version=settings.VERSION,
        openapi_url=f"{settings.API_V1_STR}/openapi.json",
        docs_url=None,
        redoc_url=None,
        lifespan=lifespan,
    )
    
    # Middlewares de segurança
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(LoggingMiddleware)
    
    # CORS
    if settings.BACKEND_CORS_ORIGINS:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=[str(origin) for origin in settings.BACKEND_CORS_ORIGINS],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    
    # Compressão
    app.add_middleware(GZipMiddleware, minimum_size=1000)
    
    # Rotas da API
    app.include_router(api_router, prefix=settings.API_V1_STR)
    
    # Arquivos estáticos
    app.mount("/static", StaticFiles(directory="app/static"), name="static")
    
    # Métricas Prometheus
    if settings.ENABLE_METRICS:
        metrics_app = make_asgi_app()
        app.mount("/metrics", metrics_app)
    
    # Rota raiz - Interface Web
    @app.get("/")
    async def read_index():
        """Serve a página principal da interface web."""
        return FileResponse('app/static/index.html')
    
    # Health check
    @app.get("/health")
    async def health_check():
        """Endpoint de health check para monitoramento."""
        return {
            "status": "healthy",
            "service": settings.PROJECT_NAME,
            "version": settings.VERSION,
        }
    
    # Exception handlers
    @app.exception_handler(MegaEmuException)
    async def megaemu_exception_handler(request: Request, exc: MegaEmuException):
        """Handler para exceções customizadas do MegaEmu."""
        logger.error(f"MegaEmu Exception: {exc.message} - {exc.details}")
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": exc.error_code,
                "message": exc.message,
                "details": exc.details,
            },
        )
    
    @app.exception_handler(ValidationError)
    async def validation_exception_handler(request: Request, exc: ValidationError):
        """Handler para erros de validação."""
        logger.warning(f"Validation Error: {exc.message}")
        return JSONResponse(
            status_code=422,
            content={
                "error": "validation_error",
                "message": exc.message,
                "details": exc.details,
            },
        )
    
    @app.exception_handler(DatabaseError)
    async def database_exception_handler(request: Request, exc: DatabaseError):
        """Handler para erros de banco de dados."""
        logger.error(f"Database Error: {exc.message} - {exc.details}")
        return JSONResponse(
            status_code=500,
            content={
                "error": "database_error",
                "message": "Erro interno do banco de dados",
                "details": None if not settings.DEBUG else exc.details,
            },
        )
    
    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        """Handler geral para exceções não tratadas."""
        import traceback
        error_details = traceback.format_exc()
        logger.error(f"Unhandled Exception in {request.method} {request.url}: {str(exc)}")
        logger.error(f"Full traceback: {error_details}")
        return JSONResponse(
            status_code=500,
            content={
                "error": "internal_server_error",
                "message": "Erro interno do servidor",
                "details": error_details if settings.DEBUG else None,
            },
        )
    
    # Custom Swagger UI with local assets
    @app.get(f"{settings.API_V1_STR}/docs", include_in_schema=False)
    async def custom_swagger_ui_html():
        return get_swagger_ui_html(
            openapi_url=app.openapi_url,
            title=app.title + " - Swagger UI",
            swagger_js_url="/static/swagger/swagger-ui-bundle.js",
            swagger_css_url="/static/swagger/swagger-ui.css",
        )

    # Custom Redoc with local assets
    @app.get(f"{settings.API_V1_STR}/redoc", include_in_schema=False)
    async def custom_redoc_html():
        return get_redoc_html(
            openapi_url=app.openapi_url,
            title=app.title + " - ReDoc",
            redoc_js_url="/static/swagger/redoc.standalone.js",
        )

    return app


# Criar instância da aplicação
app = create_application()


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
        log_level="info",
    )