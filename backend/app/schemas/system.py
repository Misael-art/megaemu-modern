"""Schemas para sistemas de videogame.

Define estruturas de dados para validação e serialização
de operações relacionadas a sistemas, emuladores e metadados.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import Field, field_validator

from app.schemas.base import BaseEntitySchema, BaseSchema, FilterParams, PaginationParams, SortParams


class SystemBase(BaseSchema):
    """Schema base para sistemas."""
    
    name: str = Field(
        min_length=1,
        max_length=255,
        description="Nome do sistema",
        examples=["Nintendo Entertainment System", "Sega Genesis"]
    )
    
    short_name: str = Field(
        min_length=1,
        max_length=50,
        description="Nome abreviado do sistema",
        examples=["NES", "Genesis"]
    )
    
    description: Optional[str] = Field(
        default=None,
        max_length=2000,
        description="Descrição detalhada do sistema"
    )
    
    manufacturer: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Fabricante do sistema",
        examples=["Nintendo", "Sega", "Sony"]
    )
    
    release_year: Optional[int] = Field(
        default=None,
        ge=1970,
        le=2030,
        description="Ano de lançamento",
        examples=[1985, 1991, 1995]
    )
    
    generation: Optional[int] = Field(
        default=None,
        ge=1,
        le=10,
        description="Geração do console (1-10)",
        examples=[3, 4, 5]
    )
    
    cpu: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Processador do sistema",
        examples=["MOS 6502", "Motorola 68000"]
    )
    
    memory: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Memória do sistema",
        examples=["2KB RAM", "64KB RAM"]
    )
    
    storage: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Armazenamento do sistema",
        examples=["Cartridge", "CD-ROM", "DVD"]
    )
    
    resolution: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Resolução de vídeo",
        examples=["256x240", "320x224", "640x480"]
    )
    
    supported_extensions: List[str] = Field(
        default_factory=list,
        description="Extensões de arquivo suportadas",
        examples=[["nes", "unf"], ["md", "gen", "smd"]]
    )
    
    bios_required: bool = Field(
        default=False,
        description="Se o sistema requer BIOS"
    )
    
    bios_files: List[str] = Field(
        default_factory=list,
        description="Arquivos de BIOS necessários",
        examples=[["bios.bin"], ["scph1001.bin", "scph5501.bin"]]
    )
    
    @field_validator('supported_extensions')
    @classmethod
    def validate_extensions(cls, v: List[str]) -> List[str]:
        """Valida e normaliza extensões de arquivo."""
        if not v:
            return v
        
        # Remove pontos e converte para minúsculas
        normalized = [ext.lower().lstrip('.') for ext in v]
        
        # Remove duplicatas mantendo ordem
        seen = set()
        result = []
        for ext in normalized:
            if ext not in seen:
                seen.add(ext)
                result.append(ext)
        
        return result
    
    @field_validator('bios_files')
    @classmethod
    def validate_bios_files(cls, v: List[str]) -> List[str]:
        """Valida arquivos de BIOS."""
        if not v:
            return v
        
        # Remove duplicatas mantendo ordem
        seen = set()
        result = []
        for bios in v:
            if bios and bios not in seen:
                seen.add(bios)
                result.append(bios)
        
        return result


class SystemCreate(SystemBase):
    """Schema para criação de sistema."""
    
    default_emulator: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Emulador padrão para o sistema",
        examples=["RetroArch", "FCEUX", "Gens"]
    )
    
    rom_path: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Caminho padrão para ROMs do sistema"
    )
    
    save_path: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Caminho para saves do sistema"
    )
    
    screenshot_path: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Caminho para screenshots do sistema"
    )
    
    active: bool = Field(
        default=True,
        description="Se o sistema está ativo"
    )


class SystemUpdate(BaseSchema):
    """Schema para atualização de sistema."""
    
    name: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=255,
        description="Nome do sistema"
    )
    
    short_name: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=50,
        description="Nome abreviado do sistema"
    )
    
    description: Optional[str] = Field(
        default=None,
        max_length=2000,
        description="Descrição detalhada do sistema"
    )
    
    manufacturer: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Fabricante do sistema"
    )
    
    release_year: Optional[int] = Field(
        default=None,
        ge=1970,
        le=2030,
        description="Ano de lançamento"
    )
    
    generation: Optional[int] = Field(
        default=None,
        ge=1,
        le=10,
        description="Geração do console"
    )
    
    cpu: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Processador do sistema"
    )
    
    memory: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Memória do sistema"
    )
    
    storage: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Armazenamento do sistema"
    )
    
    resolution: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Resolução de vídeo"
    )
    
    default_emulator: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Emulador padrão"
    )
    
    supported_extensions: Optional[List[str]] = Field(
        default=None,
        description="Extensões de arquivo suportadas"
    )
    
    bios_required: Optional[bool] = Field(
        default=None,
        description="Se o sistema requer BIOS"
    )
    
    bios_files: Optional[List[str]] = Field(
        default=None,
        description="Arquivos de BIOS necessários"
    )
    
    rom_path: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Caminho padrão para ROMs"
    )
    
    save_path: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Caminho para saves"
    )
    
    screenshot_path: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Caminho para screenshots"
    )
    
    active: Optional[bool] = Field(
        default=None,
        description="Se o sistema está ativo"
    )
    
    @field_validator('supported_extensions')
    @classmethod
    def validate_extensions(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        """Valida e normaliza extensões de arquivo."""
        if v is None:
            return v
        
        # Remove pontos e converte para minúsculas
        normalized = [ext.lower().lstrip('.') for ext in v]
        
        # Remove duplicatas mantendo ordem
        seen = set()
        result = []
        for ext in normalized:
            if ext not in seen:
                seen.add(ext)
                result.append(ext)
        
        return result


class SystemResponse(SystemBase, BaseEntitySchema):
    """Schema para resposta de sistema."""
    
    default_emulator: Optional[str] = Field(
        default=None,
        description="Emulador padrão para o sistema"
    )
    
    rom_path: Optional[str] = Field(
        default=None,
        description="Caminho padrão para ROMs do sistema"
    )
    
    save_path: Optional[str] = Field(
        default=None,
        description="Caminho para saves do sistema"
    )
    
    screenshot_path: Optional[str] = Field(
        default=None,
        description="Caminho para screenshots do sistema"
    )
    
    active: bool = Field(
        description="Se o sistema está ativo"
    )
    
    # Estatísticas calculadas
    games_count: int = Field(
        default=0,
        ge=0,
        description="Número de jogos cadastrados"
    )
    
    roms_count: int = Field(
        default=0,
        ge=0,
        description="Número de ROMs cadastradas"
    )
    
    verified_roms_count: int = Field(
        default=0,
        ge=0,
        description="Número de ROMs verificadas"
    )
    
    total_size_mb: float = Field(
        default=0.0,
        ge=0,
        description="Tamanho total das ROMs em MB"
    )
    
    # Relacionamentos
    emulators: List["SystemEmulatorResponse"] = Field(
        default_factory=list,
        description="Emuladores configurados para o sistema"
    )
    
    metadata: List["SystemMetadataResponse"] = Field(
        default_factory=list,
        description="Metadados adicionais do sistema"
    )


class SystemWithGamesResponse(SystemResponse):
    """Schema para resposta de sistema com jogos associados."""
    
    games: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Lista de jogos associados ao sistema"
    )


class SystemEmulatorBase(BaseSchema):
    """Schema base para emuladores de sistema."""
    
    name: str = Field(
        min_length=1,
        max_length=255,
        description="Nome do emulador",
        examples=["RetroArch", "FCEUX", "Gens"]
    )
    
    version: Optional[str] = Field(
        default=None,
        max_length=50,
        description="Versão do emulador",
        examples=["1.9.0", "2.6.4"]
    )
    
    executable_path: str = Field(
        min_length=1,
        max_length=500,
        description="Caminho para o executável do emulador"
    )
    
    command_line: Optional[str] = Field(
        default=None,
        max_length=1000,
        description="Argumentos de linha de comando",
        examples=["-L {core} {rom}", "{rom}"]
    )
    
    core_name: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Nome do core (para RetroArch)",
        examples=["fceumm", "genesis_plus_gx"]
    )
    
    compatibility_rating: Optional[int] = Field(
        default=None,
        ge=1,
        le=5,
        description="Avaliação de compatibilidade (1-5)"
    )
    
    notes: Optional[str] = Field(
        default=None,
        max_length=1000,
        description="Notas sobre o emulador"
    )
    
    active: bool = Field(
        default=True,
        description="Se o emulador está ativo"
    )


class SystemEmulatorCreate(SystemEmulatorBase):
    """Schema para criação de emulador de sistema."""
    
    system_id: UUID = Field(
        description="ID do sistema ao qual o emulador pertence"
    )


class SystemEmulatorUpdate(BaseSchema):
    """Schema para atualização de emulador de sistema."""
    
    name: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=255,
        description="Nome do emulador"
    )
    
    version: Optional[str] = Field(
        default=None,
        max_length=50,
        description="Versão do emulador"
    )
    
    executable_path: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=500,
        description="Caminho para o executável"
    )
    
    command_line: Optional[str] = Field(
        default=None,
        max_length=1000,
        description="Argumentos de linha de comando"
    )
    
    core_name: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Nome do core"
    )
    
    compatibility_rating: Optional[int] = Field(
        default=None,
        ge=1,
        le=5,
        description="Avaliação de compatibilidade"
    )
    
    notes: Optional[str] = Field(
        default=None,
        max_length=1000,
        description="Notas sobre o emulador"
    )
    
    active: Optional[bool] = Field(
        default=None,
        description="Se o emulador está ativo"
    )


class SystemEmulatorResponse(SystemEmulatorBase, BaseEntitySchema):
    """Schema para resposta de emulador de sistema."""
    
    system_id: UUID = Field(
        description="ID do sistema ao qual o emulador pertence"
    )


class SystemMetadataBase(BaseSchema):
    """Schema base para metadados de sistema."""
    
    type: str = Field(
        min_length=1,
        max_length=50,
        description="Tipo do metadado",
        examples=["image", "link", "statistic", "config"]
    )
    
    key: str = Field(
        min_length=1,
        max_length=255,
        description="Chave do metadado",
        examples=["logo_url", "wikipedia_link", "total_games"]
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


class SystemMetadataCreate(SystemMetadataBase):
    """Schema para criação de metadado de sistema."""
    
    system_id: UUID = Field(
        description="ID do sistema ao qual o metadado pertence"
    )


class SystemMetadataUpdate(BaseSchema):
    """Schema para atualização de metadado de sistema."""
    
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


class SystemMetadataResponse(SystemMetadataBase, BaseEntitySchema):
    """Schema para resposta de metadado de sistema."""
    
    system_id: UUID = Field(
        description="ID do sistema ao qual o metadado pertence"
    )


class SystemFilterParams(FilterParams):
    """Parâmetros de filtro específicos para sistemas."""
    
    manufacturer: Optional[str] = Field(
        default=None,
        description="Filtrar por fabricante",
        examples=["Nintendo", "Sega"]
    )
    
    generation: Optional[int] = Field(
        default=None,
        ge=1,
        le=10,
        description="Filtrar por geração"
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
    
    bios_required: Optional[bool] = Field(
        default=None,
        description="Filtrar sistemas que requerem BIOS"
    )
    
    has_games: Optional[bool] = Field(
        default=None,
        description="Filtrar sistemas que têm jogos cadastrados"
    )


class SystemSearchRequest(BaseSchema):
    """Request para busca de sistemas."""
    
    pagination: PaginationParams = Field(
        default_factory=PaginationParams,
        description="Parâmetros de paginação"
    )
    
    sorting: SortParams = Field(
        default_factory=SortParams,
        description="Parâmetros de ordenação"
    )
    
    filters: SystemFilterParams = Field(
        default_factory=SystemFilterParams,
        description="Filtros de busca"
    )


class SystemStatsResponse(BaseSchema):
    """Schema para estatísticas de um sistema."""
    
    system_id: UUID = Field(
        description="ID do sistema"
    )
    
    total_games: int = Field(
        ge=0,
        description="Total de jogos"
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
        description="Tamanho total em MB"
    )
    
    completion_percentage: float = Field(
        ge=0,
        le=100,
        description="Porcentagem de completude da coleção"
    )
    
    most_common_region: Optional[str] = Field(
        default=None,
        description="Região mais comum das ROMs"
    )
    
    most_common_language: Optional[str] = Field(
        default=None,
        description="Idioma mais comum das ROMs"
    )
    
    last_rom_added: Optional[datetime] = Field(
        default=None,
        description="Data da última ROM adicionada"
    )


class SystemList(BaseSchema):
    """Schema para listagem de sistemas."""
    
    id: UUID = Field(
        description="ID do sistema"
    )
    
    name: str = Field(
        description="Nome do sistema"
    )
    
    short_name: str = Field(
        description="Nome abreviado do sistema"
    )
    
    manufacturer: Optional[str] = Field(
        default=None,
        description="Fabricante do sistema"
    )
    
    release_year: Optional[int] = Field(
        default=None,
        description="Ano de lançamento"
    )
    
    generation: Optional[int] = Field(
        default=None,
        description="Geração do console"
    )
    
    games_count: int = Field(
        default=0,
        ge=0,
        description="Número de jogos cadastrados"
    )
    
    roms_count: int = Field(
        default=0,
        ge=0,
        description="Número de ROMs cadastradas"
    )
    
    active: bool = Field(
        description="Se o sistema está ativo"
    )
    
    # Relacionamentos
    emulators: List["SystemEmulatorResponse"] = Field(
        default_factory=list,
        description="Emuladores configurados para o sistema"
    )
    
    metadata: List["SystemMetadataResponse"] = Field(
        default_factory=list,
        description="Metadados adicionais do sistema"
    )


class EmulatorConfig(SystemEmulatorResponse):
    """Schema para configuração de emulador."""
    pass

class EmulatorConfigUpdate(SystemEmulatorUpdate):
    """Schema para atualização de configuração de emulador."""
    pass

SystemResponse.model_rebuild()
SystemList.model_rebuild()
SystemWithGamesResponse.model_rebuild()