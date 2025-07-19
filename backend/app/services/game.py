"""Serviços para gerenciamento de jogos.

Este módulo implementa a lógica de negócio para operações relacionadas
a jogos, gêneros, screenshots e metadados de jogos.
"""

from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy import and_, func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.sql import Select

from app.models.game import Game, GameGenre, GameScreenshot, GameMetadata, game_genre_association
from app.models.rom import ROM
from app.models.system import System
from app.schemas.game import (
    GameCreate,
    GameUpdate,
    GameGenreCreate,
    GameGenreUpdate,
    GameScreenshotCreate,
    GameScreenshotUpdate,
    GameMetadataCreate,
    GameMetadataUpdate,
    GameFilterParams,
    GameSearchRequest,
    GamePlayUpdate,
)
from app.services.base import BaseService


class GameService(BaseService[Game, GameCreate, GameUpdate]):
    """Serviço para operações com jogos."""
    
    def __init__(self):
        super().__init__(Game)
    
    async def get_by_id(
        self,
        db: AsyncSession,
        game_id: UUID,
        *,
        load_relationships: bool = False
    ) -> Optional[Game]:
        """Busca jogo por ID.
        
        Args:
            db: Sessão do banco de dados
            game_id: ID do jogo
            load_relationships: Se deve carregar relacionamentos
            
        Returns:
            Jogo encontrado ou None
        """
        return await self.get(db, game_id, load_relationships=load_relationships)
    
    async def create_game(
        self,
        db: AsyncSession,
        *,
        game_in: GameCreate
    ) -> Game:
        """Cria um novo jogo.
        
        Args:
            db: Sessão do banco de dados
            game_in: Dados do jogo
            
        Returns:
            Jogo criado
            
        Raises:
            HTTPException: Se jogo já existe
        """
        # Verifica se jogo já existe
        existing_game = await self.get_by_name_and_system(
            db,
            name=game_in.name,
            system_id=game_in.system_id
        )
        if existing_game:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Jogo já existe para este sistema"
            )
        
        # Cria o jogo
        game_data = game_in.dict(exclude={"genre_ids"})
        game = Game(**game_data)
        
        # Adiciona gêneros se especificados
        if game_in.genre_ids:
            genres = await self._get_genres_by_ids(db, game_in.genre_ids)
            game.genres = genres
        
        db.add(game)
        await db.commit()
        await db.refresh(game)
        
        return game
    
    async def get_by_name_and_system(
        self,
        db: AsyncSession,
        *,
        name: str,
        system_id: UUID
    ) -> Optional[Game]:
        """Busca jogo por nome e sistema.
        
        Args:
            db: Sessão do banco de dados
            name: Nome do jogo
            system_id: ID do sistema
            
        Returns:
            Jogo encontrado ou None
        """
        query = select(Game).where(
            and_(
                Game.name == name,
                Game.system_id == system_id
            )
        )
        
        result = await db.execute(query)
        return result.scalar_one_or_none()
    
    async def get_with_details(
        self,
        db: AsyncSession,
        *,
        game_id: UUID
    ) -> Optional[Game]:
        """Busca jogo com todos os detalhes.
        
        Args:
            db: Sessão do banco de dados
            game_id: ID do jogo
            
        Returns:
            Jogo com detalhes ou None
        """
        query = (
            select(Game)
            .options(
                selectinload(Game.system),
                selectinload(Game.genres),
                selectinload(Game.screenshots),
                selectinload(Game.metadata),
                selectinload(Game.roms)
            )
            .where(Game.id == game_id)
        )
        
        result = await db.execute(query)
        return result.scalar_one_or_none()
    
    async def search_games(
        self,
        db: AsyncSession,
        *,
        search_request: GameSearchRequest
    ) -> Dict[str, Any]:
        """Busca jogos com filtros e paginação.
        
        Args:
            db: Sessão do banco de dados
            search_request: Parâmetros de busca
            
        Returns:
            Resultado da busca com jogos e metadados
        """
        query = select(Game).options(
            selectinload(Game.system),
            selectinload(Game.genres)
        )
        
        # Aplica filtros
        query = self._apply_filters(query, search_request.filters)
        
        # Busca por texto
        if search_request.search:
            query = self._apply_text_search(query, search_request.search)
        
        # Conta total
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await db.execute(count_query)
        total = total_result.scalar()
        
        # Aplica ordenação
        query = self._apply_sorting(query, search_request.sort_by, search_request.sort_order)
        
        # Aplica paginação
        offset = (search_request.page - 1) * search_request.page_size
        query = query.offset(offset).limit(search_request.page_size)
        
        # Executa query
        result = await db.execute(query)
        games = result.scalars().all()
        
        return {
            "items": games,
            "total": total,
            "page": search_request.page,
            "page_size": search_request.page_size,
            "total_pages": (total + search_request.page_size - 1) // search_request.page_size
        }
    
    async def get_games_by_system(
        self,
        db: AsyncSession,
        *,
        system_id: UUID,
        limit: Optional[int] = None
    ) -> List[Game]:
        """Busca jogos por sistema.
        
        Args:
            db: Sessão do banco de dados
            system_id: ID do sistema
            limit: Limite de resultados
            
        Returns:
            Lista de jogos
        """
        query = (
            select(Game)
            .where(Game.system_id == system_id)
            .order_by(Game.name)
        )
        
        if limit:
            query = query.limit(limit)
        
        result = await db.execute(query)
        return result.scalars().all()
    
    async def get_games_by_genre(
        self,
        db: AsyncSession,
        *,
        genre_id: UUID,
        limit: Optional[int] = None
    ) -> List[Game]:
        """Busca jogos por gênero.
        
        Args:
            db: Sessão do banco de dados
            genre_id: ID do gênero
            limit: Limite de resultados
            
        Returns:
            Lista de jogos
        """
        query = (
            select(Game)
            .join(game_genre_association)
            .where(game_genre_association.c.genre_id == genre_id)
            .order_by(Game.name)
        )
        
        if limit:
            query = query.limit(limit)
        
        result = await db.execute(query)
        return result.scalars().all()
    
    async def get_favorite_games(
        self,
        db: AsyncSession,
        *,
        user_id: UUID,
        limit: Optional[int] = None
    ) -> List[Game]:
        """Busca jogos favoritos do usuário.
        
        Args:
            db: Sessão do banco de dados
            user_id: ID do usuário
            limit: Limite de resultados
            
        Returns:
            Lista de jogos favoritos
        """
        # Verifica se usuário existe
        user_exists = await db.scalar(select(func.count()).select_from(User).where(User.id == user_id))
        if not user_exists:
            logger.warning(f"Tentativa de buscar favoritos para usuário inexistente: {user_id}")
            return []

        # Query para jogos favoritos
        query = (
            select(Game)
            .join(user_favorite_games, user_favorite_games.c.game_id == Game.id)
            .where(user_favorite_games.c.user_id == user_id)
            .order_by(user_favorite_games.c.added_at.desc())
        )
        
        if limit:
            query = query.limit(limit)
        
        result = await db.execute(query)
        favorites = result.scalars().all()
        
        logger.info(f"Buscados {len(favorites)} jogos favoritos para usuário {user_id}")
        return favorites
    
    async def update_play_stats(
        self,
        db: AsyncSession,
        *,
        game_id: UUID,
        play_update: GamePlayUpdate
    ) -> Game:
        """Atualiza estatísticas de jogo.
        
        Args:
            db: Sessão do banco de dados
            game_id: ID do jogo
            play_update: Dados de atualização
            
        Returns:
            Jogo atualizado
            
        Raises:
            HTTPException: Se jogo não encontrado
        """
        game = await self.get(db, game_id)
        if not game:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Jogo não encontrado"
            )
        
        # Atualiza estatísticas
        if play_update.play_count is not None:
            game.play_count = play_update.play_count
        
        if play_update.play_time is not None:
            game.play_time = play_update.play_time
        
        if play_update.last_played is not None:
            game.last_played = play_update.last_played
        
        if play_update.is_favorite is not None:
            game.is_favorite = play_update.is_favorite
        
        if play_update.is_completed is not None:
            game.is_completed = play_update.is_completed
        
        await db.commit()
        await db.refresh(game)
        
        return game
    
    async def _get_genres_by_ids(
        self,
        db: AsyncSession,
        genre_ids: List[UUID]
    ) -> List[GameGenre]:
        """Busca gêneros por IDs.
        
        Args:
            db: Sessão do banco de dados
            genre_ids: Lista de IDs dos gêneros
            
        Returns:
            Lista de gêneros
        """
        query = select(GameGenre).where(GameGenre.id.in_(genre_ids))
        result = await db.execute(query)
        return result.scalars().all()
    
    def _apply_filters(self, query: Select, filters: GameFilterParams) -> Select:
        """Aplica filtros à query.
        
        Args:
            query: Query base
            filters: Filtros
            
        Returns:
            Query com filtros
        """
        conditions = []
        
        if filters.system_id:
            conditions.append(Game.system_id == filters.system_id)
        
        if filters.genre_id:
            query = query.join(game_genre_association).where(
                game_genre_association.c.genre_id == filters.genre_id
            )
        
        if filters.developer:
            conditions.append(Game.developer.ilike(f"%{filters.developer}%"))
        
        if filters.publisher:
            conditions.append(Game.publisher.ilike(f"%{filters.publisher}%"))
        
        if filters.region:
            conditions.append(Game.region == filters.region)
        
        if filters.language:
            conditions.append(Game.language == filters.language)
        
        if filters.rating_min:
            conditions.append(Game.rating >= filters.rating_min)
        
        if filters.rating_max:
            conditions.append(Game.rating <= filters.rating_max)
        
        if filters.release_year_min:
            conditions.append(Game.release_year >= filters.release_year_min)
        
        if filters.release_year_max:
            conditions.append(Game.release_year <= filters.release_year_max)
        
        if filters.score_min:
            conditions.append(Game.score >= filters.score_min)
        
        if filters.score_max:
            conditions.append(Game.score <= filters.score_max)
        
        if filters.players_min:
            conditions.append(Game.players >= filters.players_min)
        
        if filters.players_max:
            conditions.append(Game.players <= filters.players_max)
        
        if filters.is_favorite is not None:
            conditions.append(Game.is_favorite == filters.is_favorite)
        
        if filters.is_completed is not None:
            conditions.append(Game.is_completed == filters.is_completed)
        
        if filters.has_rom is not None:
            if filters.has_rom:
                query = query.join(ROM)
            else:
                query = query.outerjoin(ROM).where(ROM.id.is_(None))
        
        if filters.rom_verified is not None:
            query = query.join(ROM)
            if filters.rom_verified:
                conditions.append(ROM.is_verified == True)
            else:
                conditions.append(ROM.is_verified == False)
        
        if conditions:
            query = query.where(and_(*conditions))
        
        return query
    
    def _apply_text_search(self, query: Select, search: str) -> Select:
        """Aplica busca por texto.
        
        Args:
            query: Query base
            search: Texto de busca
            
        Returns:
            Query com busca por texto
        """
        search_conditions = [
            Game.name.ilike(f"%{search}%"),
            Game.description.ilike(f"%{search}%"),
            Game.developer.ilike(f"%{search}%"),
            Game.publisher.ilike(f"%{search}%")
        ]
        
        return query.where(or_(*search_conditions))
    
    def _apply_sorting(self, query: Select, sort_by: str, sort_order: str) -> Select:
        """Aplica ordenação à query.
        
        Args:
            query: Query base
            sort_by: Campo de ordenação
            sort_order: Ordem (asc/desc)
            
        Returns:
            Query com ordenação
        """
        order_field = getattr(Game, sort_by, Game.name)
        
        if sort_order == "desc":
            order_field = order_field.desc()
        
        return query.order_by(order_field)
    
    def _add_relationship_loading(self, query: Select) -> Select:
        """Adiciona carregamento de relacionamentos.
        
        Args:
            query: Query base
            
        Returns:
            Query com relacionamentos
        """
        return query.options(
            selectinload(Game.system),
            selectinload(Game.genres),
            selectinload(Game.screenshots),
            selectinload(Game.metadata),
            selectinload(Game.roms)
        )


class GameGenreService(BaseService[GameGenre, GameGenreCreate, GameGenreUpdate]):
    """Serviço para operações com gêneros de jogos."""
    
    def __init__(self):
        super().__init__(GameGenre)
    
    async def create_genre(
        self,
        db: AsyncSession,
        *,
        genre_in: GameGenreCreate
    ) -> GameGenre:
        """Cria um novo gênero.
        
        Args:
            db: Sessão do banco de dados
            genre_in: Dados do gênero
            
        Returns:
            Gênero criado
            
        Raises:
            HTTPException: Se gênero já existe
        """
        # Verifica se gênero já existe
        existing_genre = await self.get_by_name(db, name=genre_in.name)
        if existing_genre:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Gênero já existe"
            )
        
        return await self.create(db, obj_in=genre_in)
    
    async def get_by_name(
        self,
        db: AsyncSession,
        *,
        name: str
    ) -> Optional[GameGenre]:
        """Busca gênero por nome.
        
        Args:
            db: Sessão do banco de dados
            name: Nome do gênero
            
        Returns:
            Gênero encontrado ou None
        """
        return await self.get_by_field(db, "name", name)
    
    async def get_genres_with_game_count(
        self,
        db: AsyncSession
    ) -> List[GameGenre]:
        """Busca gêneros com contagem de jogos.
        
        Args:
            db: Sessão do banco de dados
            
        Returns:
            Lista de gêneros com contagem
        """
        query = (
            select(
                GameGenre,
                func.count(game_genre_association.c.game_id).label("game_count")
            )
            .outerjoin(game_genre_association)
            .group_by(GameGenre.id)
            .order_by(GameGenre.name)
        )
        
        result = await db.execute(query)
        genres_with_count = []
        
        for genre, count in result:
            genre.game_count = count
            genres_with_count.append(genre)
        
        return genres_with_count
    
    def _add_relationship_loading(self, query: Select) -> Select:
        """Adiciona carregamento de relacionamentos.
        
        Args:
            query: Query base
            
        Returns:
            Query com relacionamentos
        """
        return query.options(selectinload(GameGenre.games))


class GameScreenshotService(BaseService[GameScreenshot, GameScreenshotCreate, GameScreenshotUpdate]):
    """Serviço para operações com screenshots de jogos."""
    
    def __init__(self):
        super().__init__(GameScreenshot)
    
    async def create_screenshot(
        self,
        db: AsyncSession,
        *,
        screenshot_in: GameScreenshotCreate
    ) -> GameScreenshot:
        """Cria um novo screenshot.
        
        Args:
            db: Sessão do banco de dados
            screenshot_in: Dados do screenshot
            
        Returns:
            Screenshot criado
        """
        return await self.create(db, obj_in=screenshot_in)
    
    async def get_by_game(
        self,
        db: AsyncSession,
        *,
        game_id: UUID
    ) -> List[GameScreenshot]:
        """Busca screenshots por jogo.
        
        Args:
            db: Sessão do banco de dados
            game_id: ID do jogo
            
        Returns:
            Lista de screenshots
        """
        query = (
            select(GameScreenshot)
            .where(GameScreenshot.game_id == game_id)
            .order_by(GameScreenshot.order_index, GameScreenshot.created_at)
        )
        
        result = await db.execute(query)
        return result.scalars().all()
    
    async def get_primary_screenshot(
        self,
        db: AsyncSession,
        *,
        game_id: UUID
    ) -> Optional[GameScreenshot]:
        """Busca screenshot principal do jogo.
        
        Args:
            db: Sessão do banco de dados
            game_id: ID do jogo
            
        Returns:
            Screenshot principal ou None
        """
        query = (
            select(GameScreenshot)
            .where(
                and_(
                    GameScreenshot.game_id == game_id,
                    GameScreenshot.is_primary == True
                )
            )
        )
        
        result = await db.execute(query)
        return result.scalar_one_or_none()
    
    async def set_primary_screenshot(
        self,
        db: AsyncSession,
        *,
        screenshot_id: UUID
    ) -> GameScreenshot:
        """Define screenshot como principal.
        
        Args:
            db: Sessão do banco de dados
            screenshot_id: ID do screenshot
            
        Returns:
            Screenshot atualizado
            
        Raises:
            HTTPException: Se screenshot não encontrado
        """
        screenshot = await self.get(db, screenshot_id)
        if not screenshot:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Screenshot não encontrado"
            )
        
        # Remove principal de outros screenshots do mesmo jogo
        query = (
            select(GameScreenshot)
            .where(
                and_(
                    GameScreenshot.game_id == screenshot.game_id,
                    GameScreenshot.is_primary == True
                )
            )
        )
        result = await db.execute(query)
        current_primaries = result.scalars().all()
        
        for primary_screenshot in current_primaries:
            primary_screenshot.is_primary = False
        
        # Define novo principal
        screenshot.is_primary = True
        
        await db.commit()
        await db.refresh(screenshot)
        
        return screenshot
    
    def _add_relationship_loading(self, query: Select) -> Select:
        """Adiciona carregamento de relacionamentos.
        
        Args:
            query: Query base
            
        Returns:
            Query com relacionamentos
        """
        return query.options(selectinload(GameScreenshot.game))


class GameMetadataService(BaseService[GameMetadata, GameMetadataCreate, GameMetadataUpdate]):
    """Serviço para operações com metadados de jogos."""
    
    def __init__(self):
        super().__init__(GameMetadata)
    
    async def create_metadata(
        self,
        db: AsyncSession,
        *,
        metadata_in: GameMetadataCreate
    ) -> GameMetadata:
        """Cria novos metadados.
        
        Args:
            db: Sessão do banco de dados
            metadata_in: Dados dos metadados
            
        Returns:
            Metadados criados
            
        Raises:
            HTTPException: Se metadados já existem para o jogo
        """
        # Verifica se metadados já existem
        existing_metadata = await self.get_by_game(db, game_id=metadata_in.game_id)
        if existing_metadata:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Metadados já existem para este jogo"
            )
        
        return await self.create(db, obj_in=metadata_in)
    
    async def get_by_game(
        self,
        db: AsyncSession,
        *,
        game_id: UUID
    ) -> Optional[GameMetadata]:
        """Busca metadados por jogo.
        
        Args:
            db: Sessão do banco de dados
            game_id: ID do jogo
            
        Returns:
            Metadados encontrados ou None
        """
        return await self.get_by_field(db, "game_id", game_id)
    
    async def update_metadata(
        self,
        db: AsyncSession,
        *,
        game_id: UUID,
        metadata_in: GameMetadataUpdate
    ) -> GameMetadata:
        """Atualiza metadados do jogo.
        
        Args:
            db: Sessão do banco de dados
            game_id: ID do jogo
            metadata_in: Dados dos metadados
            
        Returns:
            Metadados atualizados
            
        Raises:
            HTTPException: Se metadados não encontrados
        """
        metadata = await self.get_by_game(db, game_id=game_id)
        if not metadata:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Metadados não encontrados"
            )
        
        return await self.update(db, db_obj=metadata, obj_in=metadata_in)
    
    def _add_relationship_loading(self, query: Select) -> Select:
        """Adiciona carregamento de relacionamentos.
        
        Args:
            query: Query base
            
        Returns:
            Query com relacionamentos
        """
        return query.options(selectinload(GameMetadata.game))