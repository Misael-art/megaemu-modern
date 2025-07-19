"""Router principal da API v1.

Agrega todos os endpoints da API v1 em um router principal
que é incluído na aplicação FastAPI principal.
"""

from fastapi import APIRouter

from app.api.v1.endpoints import (
    auth,
    users,
    systems,
    games,
    roms,
    tasks,
    health
)

# Router principal da API v1
api_router = APIRouter()

# Inclui routers de cada módulo
api_router.include_router(
    health.router,
    prefix="/health",
    tags=["health"]
)

api_router.include_router(
    auth.router,
    prefix="/auth",
    tags=["authentication"]
)

api_router.include_router(
    users.router,
    prefix="/users",
    tags=["users"]
)

api_router.include_router(
    systems.router,
    prefix="/systems",
    tags=["systems"]
)

api_router.include_router(
    games.router,
    prefix="/games",
    tags=["games"]
)

api_router.include_router(
    roms.router,
    prefix="/roms",
    tags=["roms"]
)

api_router.include_router(
    tasks.router,
    prefix="/tasks",
    tags=["tasks"]
)