"""Modelos para jogos e informações relacionadas.

Define entidades para jogos, gêneros, metadados e screenshots,
com relacionamentos otimizados e índices para busca eficiente.
"""

from datetime import datetime
from enum import Enum
from typing import List, Optional

from sqlalchemy import (
    Enum as SQLEnum,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Table,
    Text,
    UniqueConstraint,
    Index,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import BaseModel, MetadataMixin, SlugMixin


class GameStatus(str, Enum):
    """Status de verificação e disponibilidade do jogo."""
    UNKNOWN = "unknown"
    AVAILABLE = "available"
    MISSING = "missing"
    VERIFIED = "verified"
    UNVERIFIED = "unverified"
    CORRUPTED = "corrupted"
    DUPLICATE = "duplicate"
    FAVORITE = "favorite"
    COMPLETED = "completed"
    IN_PROGRESS = "in_progress"
    WISHLIST = "wishlist"


class GameGenre(BaseModel):
    """Modelo para gêneros de jogos.
    
    Representa categorias como Action, RPG, Sports, etc.
    """
    
    __tablename__ = "game_genres"
    
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        unique=True,
        index=True,
        doc="Nome do gênero (ex: Action, RPG)"
    )
    
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        doc="Descrição do gênero"
    )
    
    color: Mapped[Optional[str]] = mapped_column(
        String(7),  # Hex color code
        nullable=True,
        doc="Cor para exibição na interface (#RRGGBB)"
    )
    
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        doc="Se o gênero está ativo"
    )
    
    sort_order: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        index=True,
        doc="Ordem de exibição"
    )
    
    # Relacionamentos
    games: Mapped[List["Game"]] = relationship(
        "Game",
        secondary="game_genre_associations",
        back_populates="genres",
        lazy="dynamic"
    )
    
    def __repr__(self) -> str:
        return f"<GameGenre(name='{self.name}')>"
    
    @property
    def game_count(self) -> int:
        """Retorna o número de jogos do gênero."""
        return self.games.count()


# Tabela de associação many-to-many entre Game e GameGenre
game_genre_association = Base.metadata.tables.get('game_genre_associations') or \
    Table(
        'game_genre_associations',
        Base.metadata,
        Column('game_id', UUID(as_uuid=True), ForeignKey('games.id', ondelete='CASCADE'), primary_key=True),
        Column('genre_id', UUID(as_uuid=True), ForeignKey('game_genres.id', ondelete='CASCADE'), primary_key=True),
        Column('created_at', DateTime(timezone=True), server_default='now()'),
    )

# Tabela de associação many-to-many entre User e Game para favoritos
user_favorite_association = Base.metadata.tables.get('user_favorite_games') or \
    Table(
        'user_favorite_games',
        Base.metadata,
        Column('user_id', UUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), primary_key=True),
        Column('game_id', UUID(as_uuid=True), ForeignKey('games.id', ondelete='CASCADE'), primary_key=True),
        Column('added_at', DateTime(timezone=True), server_default='now()'),
        Column('notes', Text, nullable=True),
        Index('ix_user_favorites_user', 'user_id'),
        Index('ix_user_favorites_game', 'game_id'),
    )


class Game(BaseModel, SlugMixin, MetadataMixin):
    # ... campos existentes ...
    
    # Relacionamento com usuários que favoritaram
    favorited_by: Mapped[List["User"]] = relationship(
        "User",
        secondary="user_favorite_games",
        back_populates="favorite_games",
        lazy="dynamic"
    )
    """Modelo principal para jogos.
    
    Representa um jogo específico com todas suas informações,
    incluindo dados de múltiplas fontes e busca full-text.
    """
    
    __tablename__ = "games"
    
    # Relacionamento com sistema
    system_id: Mapped[UUID] = mapped_column(
        ForeignKey("systems.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    # Informações básicas
    name: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        index=True,
        doc="Nome do jogo"
    )
    
    original_name: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        doc="Nome original (para jogos traduzidos)"
    )
    
    alternative_names: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="[]",
        doc="Nomes alternativos do jogo"
    )
    
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        doc="Descrição do jogo"
    )
    
    # Informações de publicação
    developer: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        index=True,
        doc="Desenvolvedor do jogo"
    )
    
    publisher: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        index=True,
        doc="Publicador do jogo"
    )
    
    release_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
        doc="Data de lançamento"
    )
    
    release_year: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        index=True,
        doc="Ano de lançamento"
    )
    
    region: Mapped[Optional[str]] = mapped_column(
        String(10),
        nullable=True,
        index=True,
        doc="Região de lançamento (US, EU, JP, etc.)"
    )
    
    language: Mapped[Optional[str]] = mapped_column(
        String(10),
        nullable=True,
        doc="Idioma principal do jogo"
    )
    
    # Classificações e avaliações
    esrb_rating: Mapped[Optional[str]] = mapped_column(
        String(10),
        nullable=True,
        doc="Classificação ESRB (E, T, M, etc.)"
    )
    
    user_rating: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        doc="Avaliação dos usuários (0-10)"
    )
    
    critic_rating: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        doc="Avaliação da crítica (0-10)"
    )
    
    popularity_score: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        index=True,
        doc="Score de popularidade para ordenação"
    )
    
    # Informações técnicas
    players_min: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        doc="Número mínimo de jogadores"
    )
    
    players_max: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        doc="Número máximo de jogadores"
    )
    
    coop_support: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        doc="Suporte a modo cooperativo"
    )
    
    online_support: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        doc="Suporte a modo online"
    )
    
    # Dados de verificação
    crc32: Mapped[Optional[str]] = mapped_column(
        String(8),
        nullable=True,
        index=True,
        doc="CRC32 do arquivo ROM"
    )
    
    md5: Mapped[Optional[str]] = mapped_column(
        String(32),
        nullable=True,
        index=True,
        doc="Hash MD5 do arquivo ROM"
    )
    
    sha1: Mapped[Optional[str]] = mapped_column(
        String(40),
        nullable=True,
        index=True,
        doc="Hash SHA1 do arquivo ROM"
    )
    
    file_size: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        doc="Tamanho do arquivo em bytes"
    )
    
    # Status e configurações
    is_favorite: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
        doc="Se o jogo está marcado como favorito"
    )
    
    is_completed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        doc="Se o jogo foi completado"
    )
    
    play_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        doc="Número de vezes que foi jogado"
    )
    
    last_played: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="Última vez que foi jogado"
    )
    
    # Dados de importação
    import_source: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        doc="Fonte da importação (DAT, XML, manual, etc.)"
    )
    
    external_ids: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="{}",
        doc="IDs externos (IGDB, MobyGames, etc.)"
    )
    
    # Busca full-text
    search_vector: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        doc="Vetor de busca full-text"
    )
    
    # Relacionamentos
    system: Mapped["System"] = relationship(
        "System",
        back_populates="games"
    )
    
    genres: Mapped[List[GameGenre]] = relationship(
        "GameGenre",
        secondary="game_genre_associations",
        back_populates="games"
    )
    
    roms: Mapped[List["ROM"]] = relationship(
        "ROM",
        back_populates="game",
        cascade="all, delete-orphan"
    )
    
    screenshots: Mapped[List["GameScreenshot"]] = relationship(
        "GameScreenshot",
        back_populates="game",
        cascade="all, delete-orphan"
    )
    
    game_metadata: Mapped[List["GameMetadata"]] = relationship(
        "GameMetadata",
        back_populates="game",
        cascade="all, delete-orphan"
    )
    
    # Índices compostos e de busca
    __table_args__ = (
        UniqueConstraint('system_id', 'name', 'region', name='uq_game_system_name_region'),
        Index('ix_game_search_vector', 'search_vector', postgresql_using='gin'),
        Index('ix_game_release_year_rating', 'release_year', 'user_rating'),
        Index('ix_game_system_popularity', 'system_id', 'popularity_score'),
        Index('ix_game_hashes', 'crc32', 'md5', 'sha1'),
    )
    
    def __repr__(self) -> str:
        return f"<Game(name='{self.name}', system='{self.system.short_name if self.system else 'Unknown'}')>"
    
    @property
    def display_name(self) -> str:
        """Nome para exibição com região se necessário."""
        if self.region and self.region.upper() not in ['US', 'USA']:
            return f"{self.name} ({self.region.upper()})"
        return self.name
    
    @property
    def players_text(self) -> str:
        """Texto formatado do número de jogadores."""
        if self.players_min and self.players_max:
            if self.players_min == self.players_max:
                return f"{self.players_min} player{'s' if self.players_min > 1 else ''}"
            else:
                return f"{self.players_min}-{self.players_max} players"
        elif self.players_max:
            return f"Up to {self.players_max} players"
        return "Unknown"
    
    def add_genre(self, genre: GameGenre) -> None:
        """Adiciona um gênero ao jogo.
        
        Args:
            genre: Gênero a ser adicionado
        """
        if genre not in self.genres:
            self.genres.append(genre)
    
    def remove_genre(self, genre: GameGenre) -> bool:
        """Remove um gênero do jogo.
        
        Args:
            genre: Gênero a ser removido
            
        Returns:
            True se removido, False se não encontrado
        """
        try:
            self.genres.remove(genre)
            return True
        except ValueError:
            return False
    
    def set_external_id(self, source: str, external_id: str) -> None:
        """Define um ID externo.
        
        Args:
            source: Fonte do ID (igdb, mobygames, etc.)
            external_id: ID na fonte externa
        """
        if not self.external_ids:
            self.external_ids = {}
        self.external_ids[source] = external_id
    
    def get_external_id(self, source: str) -> Optional[str]:
        """Obtém um ID externo.
        
        Args:
            source: Fonte do ID
            
        Returns:
            ID externo ou None se não encontrado
        """
        return self.external_ids.get(source) if self.external_ids else None
    
    def increment_play_count(self) -> None:
        """Incrementa o contador de jogadas e atualiza última jogada."""
        self.play_count += 1
        self.last_played = datetime.utcnow()


class GameScreenshot(BaseModel):
    """Modelo para screenshots de jogos.
    
    Armazena imagens relacionadas aos jogos como capturas de tela,
    artwork, logos, etc.
    """
    
    __tablename__ = "game_screenshots"
    
    # Relacionamento com jogo
    game_id: Mapped[UUID] = mapped_column(
        ForeignKey("games.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    # Informações da imagem
    image_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        doc="Tipo da imagem (screenshot, artwork, logo, etc.)"
    )
    
    file_path: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        doc="Caminho para o arquivo de imagem"
    )
    
    file_url: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        doc="URL da imagem (se hospedada externamente)"
    )
    
    title: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        doc="Título ou descrição da imagem"
    )
    
    # Metadados da imagem
    width: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        doc="Largura da imagem em pixels"
    )
    
    height: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        doc="Altura da imagem em pixels"
    )
    
    file_size: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        doc="Tamanho do arquivo em bytes"
    )
    
    mime_type: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        doc="Tipo MIME da imagem"
    )
    
    # Configurações
    is_primary: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        doc="Se é a imagem principal do jogo"
    )
    
    sort_order: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        doc="Ordem de exibição"
    )
    
    # Relacionamentos
    game: Mapped[Game] = relationship(
        "Game",
        back_populates="screenshots"
    )
    
    # Índices
    __table_args__ = (
        Index('ix_screenshot_game_type', 'game_id', 'image_type'),
        Index('ix_screenshot_primary', 'game_id', 'is_primary'),
    )
    
    def __repr__(self) -> str:
        return f"<GameScreenshot(game='{self.game.name if self.game else 'Unknown'}', type='{self.image_type}')>"


class GameMetadata(BaseModel):
    """Modelo para metadados adicionais de jogos.
    
    Armazena informações extras que não se encaixam nos campos principais,
    como dados de fontes externas, estatísticas, etc.
    """
    
    __tablename__ = "game_metadata"
    
    # Relacionamento com jogo
    game_id: Mapped[UUID] = mapped_column(
        ForeignKey("games.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    # Tipo e dados do metadado
    metadata_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        doc="Tipo do metadado (review, stat, link, etc.)"
    )
    
    key: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        doc="Chave do metadado"
    )
    
    value: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        doc="Valor do metadado"
    )
    
    json_value: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        doc="Valor em formato JSON para dados complexos"
    )
    
    # Fonte e configurações
    source: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        doc="Fonte do metadado (igdb, mobygames, etc.)"
    )
    
    is_public: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        doc="Se o metadado é público"
    )
    
    sort_order: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        doc="Ordem de exibição"
    )
    
    # Relacionamentos
    game: Mapped[Game] = relationship(
        "Game",
        back_populates="game_metadata"
    )
    
    # Índices
    __table_args__ = (
        UniqueConstraint('game_id', 'metadata_type', 'key', name='uq_game_metadata'),
        Index('ix_game_metadata_source', 'source', 'metadata_type'),
    )
    
    def __repr__(self) -> str:
        return f"<GameMetadata(type='{self.metadata_type}', key='{self.key}')>"