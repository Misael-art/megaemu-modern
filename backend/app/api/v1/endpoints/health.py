"""Endpoints de health check e monitoramento.

Fornece endpoints para verificar o status da aplicação,
conexões com banco de dados e outros serviços.
"""

import time
from typing import Dict, Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db, db_manager
from app.core.config import settings
from app.schemas.base import HealthCheckResponse

router = APIRouter()


@router.get("/", response_model=HealthCheckResponse)
async def health_check():
    """Health check básico da aplicação.
    
    Retorna status geral da aplicação sem verificações profundas.
    Usado por load balancers e monitoramento básico.
    """
    return HealthCheck(
        status="healthy",
        timestamp=time.time(),
        service=settings.PROJECT_NAME,
        version=settings.VERSION
    )


@router.get("/detailed", response_model=Dict[str, Any])
async def detailed_health_check(db: AsyncSession = Depends(get_db)):
    """Health check detalhado com verificação de dependências.
    
    Verifica:
    - Conexão com banco de dados
    - Pool de conexões
    - Status do Redis (se configurado)
    - Espaço em disco
    - Memória disponível
    """
    checks = {
        "timestamp": time.time(),
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "status": "healthy",
        "checks": {}
    }
    
    # Verifica banco de dados
    try:
        db_healthy = await db_manager.health_check()
        checks["checks"]["database"] = {
            "status": "healthy" if db_healthy else "unhealthy",
            "details": await db_manager.get_pool_status() if db_healthy else None
        }
    except Exception as e:
        checks["checks"]["database"] = {
            "status": "unhealthy",
            "error": str(e)
        }
        checks["status"] = "unhealthy"
    
    # Verifica Redis (se configurado)
    try:
        from app.core.redis import redis_manager
        await redis_manager.ping()
        checks["checks"]["redis"] = {"status": "healthy"}
    except Exception as e:
        checks["checks"]["redis"] = {
            "status": "unhealthy",
            "error": str(e)
        }
        if not settings.TESTING:  # Redis é opcional em testes
            checks["status"] = "unhealthy"
    
    # Verifica espaço em disco
    try:
        import shutil
        disk_usage = shutil.disk_usage(".")
        free_gb = disk_usage.free / (1024**3)
        
        checks["checks"]["disk_space"] = {
            "status": "healthy" if free_gb > 1.0 else "warning",
            "free_gb": round(free_gb, 2),
            "total_gb": round(disk_usage.total / (1024**3), 2)
        }
        
        if free_gb < 0.5:  # Menos de 500MB
            checks["status"] = "unhealthy"
            
    except Exception as e:
        checks["checks"]["disk_space"] = {
            "status": "unknown",
            "error": str(e)
        }
    
    # Verifica memória
    try:
        import psutil
        memory = psutil.virtual_memory()
        
        checks["checks"]["memory"] = {
            "status": "healthy" if memory.percent < 90 else "warning",
            "used_percent": memory.percent,
            "available_gb": round(memory.available / (1024**3), 2)
        }
        
        if memory.percent > 95:
            checks["status"] = "unhealthy"
            
    except ImportError:
        checks["checks"]["memory"] = {
            "status": "unknown",
            "error": "psutil não disponível"
        }
    except Exception as e:
        checks["checks"]["memory"] = {
            "status": "unknown",
            "error": str(e)
        }
    
    # Se alguma verificação falhou, retorna status 503
    if checks["status"] == "unhealthy":
        raise HTTPException(status_code=503, detail=checks)
    
    return checks


@router.get("/info", response_model=HealthCheckResponse)
async def system_info():
    """Informações do sistema e configuração.
    
    Retorna informações sobre:
    - Versão da aplicação
    - Configurações principais
    - Estatísticas do banco
    - Informações do ambiente
    """
    try:
        # Estatísticas do banco
        pool_stats = await db_manager.get_pool_status()
        
        # Informações do sistema
        import platform
        import sys
        
        return SystemInfo(
            application={
                "name": settings.PROJECT_NAME,
                "version": settings.VERSION,
                "description": settings.DESCRIPTION,
                "debug": settings.DEBUG,
                "testing": settings.TESTING
            },
            system={
                "platform": platform.platform(),
                "python_version": sys.version,
                "architecture": platform.architecture()[0]
            },
            database={
                "url": str(settings.DATABASE_URL).split("@")[-1],  # Remove credenciais
                "pool_size": settings.DB_POOL_SIZE,
                "pool_stats": pool_stats
            },
            configuration={
                "api_prefix": settings.API_V1_STR,
                "cors_origins": [str(origin) for origin in settings.BACKEND_CORS_ORIGINS],
                "cache_ttl": settings.CACHE_TTL,
                "rate_limit": f"{settings.RATE_LIMIT_REQUESTS}/{settings.RATE_LIMIT_WINDOW}s"
            }
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao obter informações do sistema: {str(e)}"
        )


@router.get("/metrics")
async def metrics():
    """Métricas básicas da aplicação.
    
    Retorna métricas em formato compatível com Prometheus
    ou formato JSON simples.
    """
    try:
        # Estatísticas do banco
        pool_stats = await db_manager.get_pool_status()
        
        # Aqui você pode adicionar mais métricas:
        # - Número de requests por endpoint
        # - Tempo de resposta médio
        # - Número de usuários ativos
        # - Tamanho do cache
        # - etc.
        
        metrics = {
            "database_pool_size": pool_stats.get("size", 0),
            "database_pool_checked_out": pool_stats.get("checked_out", 0),
            "database_pool_overflow": pool_stats.get("overflow", 0),
            "uptime_seconds": time.time() - getattr(metrics, "_start_time", time.time()),
        }
        
        return metrics
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao obter métricas: {str(e)}"
        )


# Armazena tempo de início para cálculo de uptime
if not hasattr(metrics, "_start_time"):
    metrics._start_time = time.time()