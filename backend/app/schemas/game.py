"""Schemas para jogos e metadados relacionados.

Define estruturas de dados para validação e serialização
de operações relacionadas a jogos, gêneros, screenshots e metadados.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import Field, field_validator, HttpUrl

from app.schemas.base import BaseEntitySchema, BaseSchema, FilterParams, PaginationParams, SortParams
from app.schemas.rom import ROMResponse


class GameGenreBase(BaseSchema):
    """Schema base para gêneros de jogos."""
    
    name: str = Field(
        min_length=1,
        max_length=100,
        description="Nome do gênero",
        examples=["Action", "RPG", "Platform", "Puzzle"]
    )
    
    description: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Descrição do gênero"
    )
    
    color: Optional[str] = Field(
        default=None,
        pattern="^#[0-9A-Fa-f]{6}$",
        description="Cor hexadecimal para o gênero",
        examples=["#FF5733", "#33FF57"]
    )
    
    active: bool = Field(
        default=True,
        description="Se o gênero está ativo"
    )


class GameGenreCreate(GameGenreBase):
    """Schema para criação de gênero de jogo."""
    pass


class GameGenreUpdate(BaseSchema):
    """Schema para atualização de gênero de jogo."""
    
    name: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=100,
        description="Nome do gênero"
    )
    
    description: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Descrição do gênero"
    )
    
    color: Optional[str] = Field(
        default=None,
        pattern="^#[0-9A-Fa-f]{6}$",
        description="Cor hexadecimal para o gênero"
    )
    
    active: Optional[bool] = Field(
        default=None,
        description="Se o gênero está ativo"
    )


class GameGenreResponse(GameGenreBase, BaseEntitySchema):
    """Schema para resposta de gênero de jogo."""
    
    games_count: int = Field(
        default=0,
        ge=0,
        description="Número de jogos neste gênero"
    )


class GameBase(BaseSchema):
    """Schema base para jogos."""
    
    name: str = Field(
        min_length=1,
        max_length=255,
        description="Nome do jogo",
        examples=["Super Mario Bros.", "The Legend of Zelda"]
    )
    
    description: Optional[str] = Field(
        default=None,
        max_length=5000,
        description="Descrição do jogo"
    )
    
    developer: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Desenvolvedor do jogo",
        examples=["Nintendo", "Capcom", "Konami"]
    )
    
    publisher: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Publicador do jogo",
        examples=["Nintendo", "Sega", "Sony"]
    )
    
    release_date: Optional[datetime] = Field(
        default=None,
        description="Data de lançamento"
    )
    
    release_year: Optional[int] = Field(
        default=None,
        ge=1970,
        le=2030,
        description="Ano de lançamento",
        examples=[1985, 1991, 1998]
    )
    
    region: Optional[str] = Field(
        default=None,
        max_length=10,
        description="Região do jogo",
        examples=["USA", "EUR", "JPN", "BRA"]
    )
    
    language: Optional[str] = Field(
        default=None,
        max_length=10,
        description="Idioma do jogo",
        examples=["en", "pt", "ja", "es"]
    )
    
    rating: Optional[str] = Field(
        default=None,
        max_length=10,
        description="Classificação etária",
        examples=["E", "T", "M", "L", "10+"]
    )
    
    score: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=10.0,
        description="Pontuação do jogo (0-10)"
    )
    
    players_min: Optional[int] = Field(
        default=None,
        ge=1,
        le=8,
        description="Número mínimo de jogadores"
    )
    
    players_max: Optional[int] = Field(
        default=None,
        ge=1,
        le=8,
        description="Número máximo de jogadores"
    )
    
    @field_validator('players_max')
    @classmethod
    def validate_players_max(cls, v: Optional[int], info) -> Optional[int]:
        """Valida que players_max >= players_min."""
        if v is not None and 'players_min' in info.data:
            players_min = info.data['players_min']
            if players_min is not None and v < players_min:
                raise ValueError('Número máximo de jogadores deve ser >= mínimo')
        return v


class GameCreate(GameBase):
    """Schema para criação de jogo."""
    
    system_id: UUID = Field(
        description="ID do sistema ao qual o jogo pertence"
    )
    
    genre_ids: List[UUID] = Field(
        default_factory=list,
        description="IDs dos gêneros do jogo"
    )
    
    # Hashes para verificação
    crc32: Optional[str] = Field(
        default=None,
        pattern="^[0-9A-Fa-f]{8}$",
        description="Hash CRC32 da ROM",
        examples=["12345678"]
    )
    
    md5: Optional[str] = Field(
        default=None,
        pattern="^[0-9A-Fa-f]{32}$",
        description="Hash MD5 da ROM",
        examples=["d41d8cd98f00b204e9800998ecf8427e"]
    )
    
    sha1: Optional[str] = Field(
        default=None,
        pattern="^[0-9A-Fa-f]{40}$",
        description="Hash SHA1 da ROM",
        examples=["da39a3ee5e6b4b0d3255bfef95601890afd80709"]
    )
    
    # IDs externos
    igdb_id: Optional[int] = Field(
        default=None,
        description="ID no IGDB"
    )
    
    mobygames_id: Optional[int] = Field(
        default=None,
        description="ID no MobyGames"
    )
    
    # Status
    enabled: bool = Field(
        default=True,
        description="Se o jogo está habilitado"
    )
    
    favorite: bool = Field(
        default=False,
        description="Se o jogo é favorito"
    )
    
    completed: bool = Field(
        default=False,
        description="Se o jogo foi completado"
    )


class GameUpdate(BaseSchema):
    """Schema para atualização de jogo."""
    
    name: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=255,
        description="Nome do jogo"
    )
    
    description: Optional[str] = Field(
        default=None,
        max_length=5000,
        description="Descrição do jogo"
    )
    
    developer: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Desenvolvedor do jogo"
    )
    
    publisher: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Publicador do jogo"
    )
    
    release_date: Optional[datetime] = Field(
        default=None,
        description="Data de lançamento"
    )
    
    release_year: Optional[int] = Field(
        default=None,
        ge=1970,
        le=2030,
        description="Ano de lançamento"
    )
    
    region: Optional[str] = Field(
        default=None,
        max_length=10,
        description="Região do jogo"
    )
    
    language: Optional[str] = Field(
        default=None,
        max_length=10,
        description="Idioma do jogo"
    )
    
    rating: Optional[str] = Field(
        default=None,
        max_length=10,
        description="Classificação etária"
    )
    
    score: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=10.0,
        description="Pontuação do jogo"
    )
    
    players_min: Optional[int] = Field(
        default=None,
        ge=1,
        le=8,
        description="Número mínimo de jogadores"
    )
    
    players_max: Optional[int] = Field(
        default=None,
        ge=1,
        le=8,
        description="Número máximo de jogadores"
    )
    
    genre_ids: Optional[List[UUID]] = Field(
        default=None,
        description="IDs dos gêneros do jogo"
    )
    
    igdb_id: Optional[int] = Field(
        default=None,
        description="ID no IGDB"
    )
    
    mobygames_id: Optional[int] = Field(
        default=None,
        description="ID no MobyGames"
    )
    
    enabled: Optional[bool] = Field(
        default=None,
        description="Se o jogo está habilitado"
    )
    
    favorite: Optional[bool] = Field(
        default=None,
        description="Se o jogo é favorito"
    )
    
    completed: Optional[bool] = Field(
        default=None,
        description="Se o jogo foi completado"
    )


class GameResponse(GameBase, BaseEntitySchema):
    """Schema para resposta de jogo."""
    
    system_id: UUID = Field(
        description="ID do sistema ao qual o jogo pertence"
    )
    
    system_name: Optional[str] = Field(
        default=None,
        description="Nome do sistema"
    )
    
    # Hashes
    crc32: Optional[str] = Field(
        default=None,
        description="Hash CRC32 da ROM"
    )
    
    md5: Optional[str] = Field(
        default=None,
        description="Hash MD5 da ROM"
    )
    
    sha1: Optional[str] = Field(
        default=None,
        description="Hash SHA1 da ROM"
    )
    
    # IDs externos
    igdb_id: Optional[int] = Field(
        default=None,
        description="ID no IGDB"
    )
    
    mobygames_id: Optional[int] = Field(
        default=None,
        description="ID no MobyGames"
    )
    
    # Status
    enabled: bool = Field(
        description="Se o jogo está habilitado"
    )
    
    favorite: bool = Field(
        description="Se o jogo é favorito"
    )
    
    completed: bool = Field(
        description="Se o jogo foi completado"
    )
    
    # Estatísticas
    play_count: int = Field(
        default=0,
        ge=0,
        description="Número de vezes jogado"
    )
    
    play_time_minutes: int = Field(
        default=0,
        ge=0,
        description="Tempo total jogado em minutos"
    )
    
    last_played: Optional[datetime] = Field(
        default=None,
        description="Data da última vez jogado"
    )
    
    # Relacionamentos
    genres: List[GameGenreResponse] = Field(
        default_factory=list,
        description="Gêneros do jogo"
    )
    
    screenshots: List["GameScreenshotResponse"] = Field(
        default_factory=list,
        description="Screenshots do jogo"
    )
    
    roms: List[ROMResponse] = Field(
        default_factory=list,
        description="ROMs do jogo"
    )
    
    metadata: List["GameMetadataResponse"] = Field(
        default_factory=list,
        description="Metadados adicionais"
    )


class GameScreenshotBase(BaseSchema):
    """Schema base para screenshots de jogos."""
    
    type: str = Field(
        max_length=50,
        description="Tipo da imagem",
        examples=["screenshot", "title", "gameplay", "box_art"]
    )
    
    file_path: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Caminho local do arquivo"
    )
    
    url: Optional[HttpUrl] = Field(
        default=None,
        description="URL da imagem"
    )
    
    width: Optional[int] = Field(
        default=None,
        ge=1,
        description="Largura da imagem em pixels"
    )
    
    height: Optional[int] = Field(
        default=None,
        ge=1,
        description="Altura da imagem em pixels"
    )
    
    file_size: Optional[int] = Field(
        default=None,
        ge=0,
        description="Tamanho do arquivo em bytes"
    )
    
    mime_type: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Tipo MIME da imagem",
        examples=["image/png", "image/jpeg"]
    )
    
    is_primary: bool = Field(
        default=False,
        description="Se é a imagem principal"
    )


class GameScreenshotCreate(GameScreenshotBase):
    """Schema para criação de screenshot de jogo."""
    
    game_id: UUID = Field(
        description="ID do jogo ao qual a screenshot pertence"
    )


class GameScreenshotUpdate(BaseSchema):
    """Schema para atualização de screenshot de jogo."""
    
    type: Optional[str] = Field(
        default=None,
        max_length=50,
        description="Tipo da imagem"
    )
    
    file_path: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Caminho local do arquivo"
    )
    
    url: Optional[HttpUrl] = Field(
        default=None,
        description="URL da imagem"
    )
    
    is_primary: Optional[bool] = Field(
        default=None,
        description="Se é a imagem principal"
    )


class GameScreenshotResponse(GameScreenshotBase, BaseEntitySchema):
    """Schema para resposta de screenshot de jogo."""
    
    game_id: UUID = Field(
        description="ID do jogo ao qual a screenshot pertence"
    )


class GameMetadataBase(BaseSchema):
    """Schema base para metadados de jogos."""
    
    type: str = Field(
        min_length=1,
        max_length=50,
        description="Tipo do metadado",
        examples=["link", "video", "review", "trivia"]
    )
    
    key: str = Field(
        min_length=1,
        max_length=255,
        description="Chave do metadado",
        examples=["wikipedia_url", "youtube_trailer", "ign_review"]
    )
    
    value: Optional[str] = Field(
        default=None,
        max_length=2000,
        description="Valor textual do metadado"
    )
    
    json_value: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Valor JSON complexo do metadado"
    )
    
    description: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Descrição do metadado"
    )


class GameMetadataCreate(GameMetadataBase):
    """Schema para criação de metadado de jogo."""
    
    game_id: UUID = Field(
        description="ID do jogo ao qual o metadado pertence"
    )


class GameMetadataUpdate(BaseSchema):
    """Schema para atualização de metadado de jogo."""
    
    value: Optional[str] = Field(
        default=None,
        max_length=2000,
        description="Valor textual do metadado"
    )
    
    json_value: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Valor JSON complexo do metadado"
    )
    
    description: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Descrição do metadado"
    )


class GameMetadataResponse(BaseSchema):
    id: UUID = Field(description="ID dos metadados")
    key: str = Field(description="Chave dos metadados")
    value: str = Field(description="Valor dos metadados")
    source: Optional[str] = Field(default=None, description="Fonte dos metadados")
    
    value: Optional[str] = Field(
        default=None,
        max_length=2000,
        description="Valor textual do metadado"
    )
    
    json_value: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Valor JSON complexo do metadado"
    )
    
    description: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Descrição do metadado"
    )


class GameMetadataResponse(GameMetadataBase, BaseEntitySchema):
    """Schema para resposta de metadado de jogo."""
    
    game_id: UUID = Field(
        description="ID do jogo ao qual o metadado pertence"
    )


class GameFilterParams(FilterParams):
    """Parâmetros de filtro específicos para jogos."""
    
    system_id: Optional[UUID] = Field(
        default=None,
        description="Filtrar por sistema"
    )
    
    genre_ids: Optional[List[UUID]] = Field(
        default=None,
        description="Filtrar por gêneros"
    )
    
    developer: Optional[str] = Field(
        default=None,
        description="Filtrar por desenvolvedor"
    )
    
    publisher: Optional[str] = Field(
        default=None,
        description="Filtrar por publicador"
    )
    
    region: Optional[str] = Field(
        default=None,
        description="Filtrar por região"
    )
    
    language: Optional[str] = Field(
        default=None,
        description="Filtrar por idioma"
    )
    
    rating: Optional[str] = Field(
        default=None,
        description="Filtrar por classificação"
    )
    
    release_year_min: Optional[int] = Field(
        default=None,
        ge=1970,
        le=2030,
        description="Ano mínimo de lançamento"
    )
    
    release_year_max: Optional[int] = Field(
        default=None,
        ge=1970,
        le=2030,
        description="Ano máximo de lançamento"
    )
    
    score_min: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=10.0,
        description="Pontuação mínima"
    )
    
    score_max: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=10.0,
        description="Pontuação máxima"
    )
    
    players_min: Optional[int] = Field(
        default=None,
        ge=1,
        le=8,
        description="Número mínimo de jogadores"
    )
    
    players_max: Optional[int] = Field(
        default=None,
        ge=1,
        le=8,
        description="Número máximo de jogadores"
    )
    
    favorite_only: Optional[bool] = Field(
        default=None,
        description="Apenas jogos favoritos"
    )
    
    completed_only: Optional[bool] = Field(
        default=None,
        description="Apenas jogos completados"
    )
    
    has_roms: Optional[bool] = Field(
        default=None,
        description="Apenas jogos com ROMs"
    )
    
    verified_roms_only: Optional[bool] = Field(
        default=None,
        description="Apenas jogos com ROMs verificadas"
    )


class GameSearch(BaseSchema):
    """Schema para busca de jogos."""
    
    query: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=255,
        description="Termo de busca"
    )
    
    genres: Optional[List[UUID]] = Field(
        default=None,
        description="IDs de gêneros para filtro"
    )
    
    min_score: Optional[float] = Field(
        default=None,
        ge=0,
        le=10,
        description="Pontuação mínima"
    )
    
    max_score: Optional[float] = Field(
        default=None,
        ge=0,
        le=10,
        description="Pontuação máxima"
    )
    
    release_year_min: Optional[int] = Field(
        default=None,
        ge=1900,
        description="Ano de lançamento mínimo"
    )
    
    release_year_max: Optional[int] = Field(
        default=None,
        le=2100,
        description="Ano de lançamento máximo"
    )
    
    developer: Optional[str] = Field(
        default=None,
        description="Desenvolvedor"
    )
    
    publisher: Optional[str] = Field(
        default=None,
        description="Publicador"
    )
    
    region: Optional[str] = Field(
        default=None,
        description="Região"
    )
    
    language: Optional[str] = Field(
        default=None,
        description="Idioma"
    )
    
    favorite_only: Optional[bool] = Field(
        default=None,
        description="Apenas favoritos"
    )
    
    completed_only: Optional[bool] = Field(
        default=None,
        description="Apenas completados"
    )

GameSearch.model_rebuild()


class GameSearchRequest(BaseSchema):
    """Request para busca de jogos."""
    
    pagination: PaginationParams = Field(
        default_factory=PaginationParams,
        description="Parâmetros de paginação"
    )
    
    sorting: SortParams = Field(
        default_factory=SortParams,
        description="Parâmetros de ordenação"
    )
    
    filters: GameFilterParams = Field(
        default_factory=GameFilterParams,
        description="Filtros de busca"
    )
    
    full_text_search: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=255,
        description="Busca textual completa"
    )


class GameSearchResponse(BaseSchema):
    """Response para busca de jogos com destaque de termos."""
    
    game: GameResponse = Field(
        description="Dados do jogo"
    )
    
    relevance_score: Optional[float] = Field(
        default=None,
        description="Pontuação de relevância da busca"
    )
    
    highlighted_fields: Optional[Dict[str, str]] = Field(
        default=None,
        description="Campos com termos destacados"
    )


class GameStatsResponse(BaseSchema):
    """Schema para estatísticas de um jogo."""
    
    game_id: UUID = Field(
        description="ID do jogo"
    )
    
    total_roms: int = Field(
        ge=0,
        description="Total de ROMs"
    )
    
    verified_roms: int = Field(
        ge=0,
        description="ROMs verificadas"
    )
    
    total_size_mb: float = Field(
        ge=0,
        description="Tamanho total das ROMs em MB"
    )
    
    play_count: int = Field(
        ge=0,
        description="Número de vezes jogado"
    )
    
    play_time_minutes: int = Field(
        ge=0,
        description="Tempo total jogado em minutos"
    )
    
    last_played: Optional[datetime] = Field(
        default=None,
        description="Data da última vez jogado"
    )
    
    screenshots_count: int = Field(
        ge=0,
        description="Número de screenshots"
    )
    
    metadata_count: int = Field(
        ge=0,
        description="Número de metadados"
    )


class GamePlayUpdate(BaseSchema):
    """Schema para atualização de estatísticas de jogo."""
    
    play_time_minutes: Optional[int] = Field(
        default=None,
        ge=0,
        description="Tempo jogado nesta sessão em minutos"
    )
    
    completed: Optional[bool] = Field(
        default=None,
        description="Se o jogo foi completado"
    )
    
    favorite: Optional[bool] = Field(
        default=None,
        description="Se o jogo é favorito"
    )


class GameList(BaseSchema):
    """Schema para listagem de jogos."""
    
    id: UUID = Field(
        description="ID do jogo"
    )
    
    name: str = Field(
        description="Nome do jogo"
    )
    
    system_id: UUID = Field(
        description="ID do sistema ao qual o jogo pertence"
    )
    
    release_year: Optional[int] = Field(
        default=None,
        description="Ano de lançamento"
    )
    
    developer: Optional[str] = Field(
        default=None,
        description="Desenvolvedor do jogo"
    )
    
    publisher: Optional[str] = Field(
        default=None,
        description="Publicador do jogo"
    )
    
    region: Optional[str] = Field(
        default=None,
        description="Região do jogo"
    )
    
    language: Optional[str] = Field(
        default=None,
        description="Idioma do jogo"
    )
    
    score: Optional[float] = Field(
        default=None,
        description="Pontuação do jogo (0-10)"
    )
    
    favorite: bool = Field(
        default=False,
        description="Se o jogo é favorito"
    )
    
    completed: bool = Field(
        default=False,
        description="Se o jogo foi completado"
    )
    
    genres: List[GameGenreResponse] = Field(
        default_factory=list,
        description="Gêneros do jogo"
    )


class GameDetail(GameResponse):
    """Schema para detalhes completos de um jogo."""
    
    description: Optional[str] = Field(
        default=None,
        description="Descrição detalhada do jogo"
    )
    
    screenshots: List[str] = Field(
        default_factory=list,
        description="URLs de screenshots do jogo"
    )
    
    videos: List[str] = Field(
        default_factory=list,
        description="URLs de vídeos do jogo"
    )
    
    related_games: List[GameList] = Field(
        default_factory=list,
        description="Jogos relacionados"
    )
    
    metadata: Optional[GameMetadataResponse] = Field(
        default=None,
        description="Metadados adicionais do jogo"
    )
    
    roms: List[ROMResponse] = Field(
        default_factory=list,
        description="ROMs associadas ao jogo"
    )
    
    achievements: List["AchievementResponse"] = Field(
        default_factory=list,
        description="Conquistas do jogo"
    )


class AchievementResponse(BaseSchema):
    id: UUID = Field(description="ID da conquista")
    name: str = Field(description="Nome da conquista")
    description: Optional[str] = Field(default=None, description="Descrição da conquista")
    points: Optional[int] = Field(default=None, ge=0, description="Pontos da conquista")
    unlocked: bool = Field(default=False, description="Se a conquista foi desbloqueada")
    unlocked_at: Optional[datetime] = Field(default=None, description="Data de desbloqueio")

GameDetail.model_rebuild()