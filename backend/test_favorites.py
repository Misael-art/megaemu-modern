import pytest
import asyncio
from app.core.database import AsyncSessionLocal
from app.services.user import UserService
from app.services.game import GameService
from app.models.user import User
from app.models.game import Game

@pytest.mark.asyncio
async def test_add_remove_favorite():
    async with AsyncSessionLocal() as db:
        user_service = UserService(db)
        game_service = GameService(db)
        
        # Criar ou obter usuário de teste
        user = await user_service.get_by_email_or_username(db, identifier="test_user")
        if not user:
            user = await user_service.create(db, {
                "username": "test_user",
                "email": "test@example.com",
                "hashed_password": "hashed_test_pass",
                "role": "user",
                "status": "active"
            })
        
        # Criar ou obter jogo de teste
        game = await game_service.get_by_name(db, name="Test Game")
        if not game:
            game = await game_service.create(db, {
                "name": "Test Game",
                "system_id": "some_system_id",
                "description": "Test description"
            })
        
        # Adicionar favorito
        await game_service.add_favorite(db, user_id=user.id, game_id=game.id)
        favorites = await game_service.get_favorites(db, user_id=user.id)
        assert any(f.id == game.id for f in favorites)
        
        # Remover favorito
        await game_service.remove_favorite(db, user_id=user.id, game_id=game.id)
        favorites = await game_service.get_favorites(db, user_id=user.id)
        assert not any(f.id == game.id for f in favorites)