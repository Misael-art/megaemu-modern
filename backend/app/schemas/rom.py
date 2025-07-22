"""Schemas para ROMs e arquivos relacionados.

Define estruturas de dados para validação e serialização
de operações relacionadas a ROMs, arquivos e verificações.
"""

import re
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import Field, field_validator, computed_field, model_validator

from app.schemas.base import BaseEntitySchema, BaseSchema, FilterParams, PaginationParams, SortParams


class ROMStatus(str, Enum):
    """Status de uma ROM."""
    PENDING = "pending"
    VERIFIED = "verified"
    INVALID = "invalid"
    MISSING = "missing"
    CORRUPTED = "corrupted"
    DUPLICATE = "duplicate"
    UNKNOWN = "unknown"


class CompressionType(str, Enum):
    """Tipos de compressão suportados."""
    NONE = "none"
    ZIP = "zip"
    RAR = "rar"
    SEVEN_ZIP = "7z"
    GZ = "gz"
    TAR = "tar"
    TAR_GZ = "tar.gz"
    TAR_BZ2 = "tar.bz2"
    XZ = "xz"


class VerificationType(str, Enum):
    """Tipos de verificação de ROM."""
    HASH = "hash"
    DAT = "dat"
    MANUAL = "manual"
    AUTO = "auto"
    IMPORT = "import"


class VerificationSource(str, Enum):
    """Fontes de verificação."""
    NO_INTRO = "no_intro"
    REDUMP = "redump"
    TOSEC = "tosec"
    GOODTOOLS = "goodtools"
    MAME = "mame"
    MANUAL = "manual"
    UNKNOWN = "unknown"


class ROMBase(BaseSchema):
    """Schema base para ROMs."""
    
    filename: str = Field(
        min_length=1,
        max_length=255,
        description="Nome do arquivo da ROM",
        examples=["game.zip", "rom.bin", "cartridge.smc"]
    )
    
    file_path: str = Field(
        min_length=1,
        max_length=500,
        description="Caminho completo para o arquivo"
    )
    
    file_size: int = Field(
        ge=0,
        description="Tamanho do arquivo em bytes"
    )
    
    file_extension: Optional[str] = Field(
        default=None,
        max_length=10,
        description="Extensão do arquivo",
        examples=[".zip", ".bin", ".smc", ".nes"]
    )
    
    # Hashes para verificação
    crc32: Optional[str] = Field(
        default=None,
        pattern="^[0-9A-Fa-f]{8}$",
        description="Hash CRC32",
        examples=["12345678"]
    )
    
    md5: Optional[str] = Field(
        default=None,
        pattern="^[0-9A-Fa-f]{32}$",
        description="Hash MD5",
        examples=["d41d8cd98f00b204e9800998ecf8427e"]
    )
    
    sha1: Optional[str] = Field(
        default=None,
        pattern="^[0-9A-Fa-f]{40}$",
        description="Hash SHA1",
        examples=["da39a3ee5e6b4b0d3255bfef95601890afd80709"]
    )
    
    sha256: Optional[str] = Field(
        default=None,
        pattern="^[0-9A-Fa-f]{64}$",
        description="Hash SHA256"
    )
    
    # Status e metadados
    status: ROMStatus = Field(
        default=ROMStatus.PENDING,
        description="Status da ROM"
    )
    
    # Informações de compressão
    compression_type: CompressionType = Field(
        default=CompressionType.NONE,
        description="Tipo de compressão"
    )
    
    compressed_size: Optional[int] = Field(
        default=None,
        ge=0,
        description="Tamanho comprimido em bytes"
    )
    
    uncompressed_size: Optional[int] = Field(
        default=None,
        ge=0,
        description="Tamanho descomprimido em bytes"
    )
    
    # Informações regionais e de versão
    region: Optional[str] = Field(
        default=None,
        max_length=10,
        description="Região da ROM",
        examples=["USA", "EUR", "JPN", "BRA"]
    )
    
    version: Optional[str] = Field(
        default=None,
        max_length=50,
        description="Versão da ROM",
        examples=["1.0", "Rev A", "Beta"]
    )
    
    revision: Optional[str] = Field(
        default=None,
        max_length=50,
        description="Revisão da ROM"
    )
    
    # Estatísticas de acesso
    access_count: int = Field(
        default=0,
        ge=0,
        description="Número de vezes acessada"
    )
    
    last_accessed: Optional[datetime] = Field(
        default=None,
        description="Data do último acesso"
    )
    
    # Fonte da importação
    import_source: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Fonte da importação",
        examples=["manual", "dat_import", "auto_scan"]
    )
    
    @field_validator('file_path')
    @classmethod
    def validate_file_path(cls, v: str) -> str:
        """Valida o caminho do arquivo."""
        try:
            path = Path(v)
            if not path.is_absolute():
                raise ValueError('Caminho deve ser absoluto')
            return str(path)
        except Exception as e:
            raise ValueError(f'Caminho inválido: {e}')
    
    @computed_field
    @property
    def compression_ratio(self) -> Optional[float]:
        """Calcula a taxa de compressão."""
        if self.compressed_size and self.uncompressed_size and self.uncompressed_size > 0:
            return round((1 - self.compressed_size / self.uncompressed_size) * 100, 2)
        return None


class ROMCreate(ROMBase):
    """Schema para criação de ROM."""
    
    game_id: Optional[UUID] = Field(
        default=None,
        description="ID do jogo associado (opcional)"
    )
    
    system_id: UUID = Field(
        description="ID do sistema ao qual a ROM pertence"
    )
    
    # Flags de controle
    auto_verify: bool = Field(
        default=True,
        description="Se deve verificar automaticamente"
    )
    
    auto_extract: bool = Field(
        default=False,
        description="Se deve extrair automaticamente arquivos comprimidos"
    )

    @model_validator(mode='after')
    def check_required_hashes(self) -> 'ROMCreate':
        if not (self.crc32 or self.md5 or self.sha1 or self.sha256):
            raise ValueError('Pelo menos um hash deve ser fornecido para verificação')
        return self

    @field_validator('file_size')
    @classmethod
    def validate_size(cls, v: int) -> int:
        if v > 10 * 1024 * 1024 * 1024:  # 10GB max
            raise ValueError('Tamanho do arquivo excede o limite de 10GB')
        return v

    @field_validator('filename')
    @classmethod
    def validate_filename(cls, v: str) -> str:
        invalid_chars = r'[\/:*?"<>|]'
        if re.search(invalid_chars, v):
            raise ValueError('Nome do arquivo contém caracteres inválidos')
        return v


class ROMUpdate(BaseSchema):
    """Schema para atualização de ROM."""
    
    filename: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=255,
        description="Nome do arquivo da ROM"
    )
    
    file_path: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=500,
        description="Caminho completo para o arquivo"
    )
    
    game_id: Optional[UUID] = Field(
        default=None,
        description="ID do jogo associado"
    )
    
    status: Optional[ROMStatus] = Field(
        default=None,
        description="Status da ROM"
    )
    
    region: Optional[str] = Field(
        default=None,
        max_length=10,
        description="Região da ROM"
    )
    
    version: Optional[str] = Field(
        default=None,
        max_length=50,
        description="Versão da ROM"
    )
    
    revision: Optional[str] = Field(
        default=None,
        max_length=50,
        description="Revisão da ROM"
    )


class ROMResponse(ROMBase, BaseEntitySchema):
    """Schema para resposta de ROM."""
    
    game_id: Optional[UUID] = Field(
        default=None,
        description="ID do jogo associado"
    )
    
    game_name: Optional[str] = Field(
        default=None,
        description="Nome do jogo associado"
    )
    
    system_id: UUID = Field(
        description="ID do sistema ao qual a ROM pertence"
    )
    
    system_name: Optional[str] = Field(
        default=None,
        description="Nome do sistema"
    )
    
    # Informações calculadas
    exists: bool = Field(
        description="Se o arquivo existe no disco"
    )
    
    display_name: str = Field(
        description="Nome de exibição formatado"
    )
    
    # Relacionamentos
    files: List["ROMFileResponse"] = Field(
        default_factory=list,
        description="Arquivos dentro da ROM (se comprimida)"
    )
    
    verifications: List["ROMVerificationResponse"] = Field(
        default_factory=list,
        description="Histórico de verificações"
    )
    
    @computed_field
    @property
    def file_size_mb(self) -> float:
        """Tamanho do arquivo em MB."""
        return round(self.file_size / (1024 * 1024), 2)
    
    @computed_field
    @property
    def is_compressed(self) -> bool:
        """Se a ROM está comprimida."""
        return self.compression_type != CompressionType.NONE


class ROMFileBase(BaseSchema):
    """Schema base para arquivos dentro de ROMs comprimidas."""
    
    filename: str = Field(
        min_length=1,
        max_length=255,
        description="Nome do arquivo"
    )
    
    path_in_archive: str = Field(
        min_length=1,
        max_length=500,
        description="Caminho dentro do arquivo comprimido"
    )
    
    file_size: int = Field(
        ge=0,
        description="Tamanho do arquivo em bytes"
    )
    
    # Hashes
    crc32: Optional[str] = Field(
        default=None,
        pattern="^[0-9A-Fa-f]{8}$",
        description="Hash CRC32"
    )
    
    md5: Optional[str] = Field(
        default=None,
        pattern="^[0-9A-Fa-f]{32}$",
        description="Hash MD5"
    )
    
    sha1: Optional[str] = Field(
        default=None,
        pattern="^[0-9A-Fa-f]{40}$",
        description="Hash SHA1"
    )
    
    # Informações de compressão
    compressed_size: Optional[int] = Field(
        default=None,
        ge=0,
        description="Tamanho comprimido em bytes"
    )
    
    compression_method: Optional[str] = Field(
        default=None,
        max_length=50,
        description="Método de compressão usado"
    )
    
    # Flags
    is_main_file: bool = Field(
        default=False,
        description="Se é o arquivo principal da ROM"
    )


class ROMFileCreate(ROMFileBase):
    """Schema para criação de arquivo de ROM."""
    
    rom_id: UUID = Field(
        description="ID da ROM à qual o arquivo pertence"
    )


class ROMFileUpdate(BaseSchema):
    """Schema para atualização de arquivo de ROM."""
    
    is_main_file: Optional[bool] = Field(
        default=None,
        description="Se é o arquivo principal da ROM"
    )


class ROMFileResponse(ROMFileBase, BaseEntitySchema):
    """Schema para resposta de arquivo de ROM."""
    
    rom_id: UUID = Field(
        description="ID da ROM à qual o arquivo pertence"
    )
    
    @computed_field
    @property
    def file_size_mb(self) -> float:
        """Tamanho do arquivo em MB."""
        return round(self.file_size / (1024 * 1024), 2)
    
    @computed_field
    @property
    def compression_ratio(self) -> Optional[float]:
        """Taxa de compressão do arquivo."""
        if self.compressed_size and self.file_size > 0:
            return round((1 - self.compressed_size / self.file_size) * 100, 2)
        return None


class ROMVerificationBase(BaseSchema):
    """Schema base para verificações de ROM."""
    
    verification_type: VerificationType = Field(
        description="Tipo de verificação"
    )
    
    verification_source: VerificationSource = Field(
        description="Fonte da verificação"
    )
    
    status_before: ROMStatus = Field(
        description="Status antes da verificação"
    )
    
    status_after: ROMStatus = Field(
        description="Status após a verificação"
    )
    
    expected_crc32: Optional[str] = Field(
        default=None,
        pattern="^[0-9A-Fa-f]{8}$",
        description="CRC32 esperado"
    )
    
    actual_crc32: Optional[str] = Field(
        default=None,
        pattern="^[0-9A-Fa-f]{8}$",
        description="CRC32 atual"
    )
    
    expected_md5: Optional[str] = Field(
        default=None,
        pattern="^[0-9A-Fa-f]{32}$",
        description="MD5 esperado"
    )
    
    actual_md5: Optional[str] = Field(
        default=None,
        pattern="^[0-9A-Fa-f]{32}$",
        description="MD5 atual"
    )
    
    expected_sha1: Optional[str] = Field(
        default=None,
        pattern="^[0-9A-Fa-f]{40}$",
        description="SHA1 esperado"
    )
    
    actual_sha1: Optional[str] = Field(
        default=None,
        pattern="^[0-9A-Fa-f]{40}$",
        description="SHA1 atual"
    )
    
    details: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Detalhes adicionais da verificação"
    )
    
    error_message: Optional[str] = Field(
        default=None,
        max_length=1000,
        description="Mensagem de erro (se houver)"
    )
    
    verification_duration_ms: Optional[int] = Field(
        default=None,
        ge=0,
        description="Duração da verificação em milissegundos"
    )


class ROMVerificationCreate(ROMVerificationBase):
    """Schema para criação de verificação de ROM."""
    
    rom_id: UUID = Field(
        description="ID da ROM verificada"
    )


class ROMVerificationResponse(ROMVerificationBase, BaseEntitySchema):
    """Schema para resposta de verificação de ROM."""
    
    rom_id: UUID = Field(
        description="ID da ROM verificada"
    )
    
    @computed_field
    @property
    def is_successful(self) -> bool:
        """Se a verificação foi bem-sucedida."""
        return self.status_after in [ROMStatus.VERIFIED]
    
    @computed_field
    @property
    def hash_matches(self) -> Dict[str, bool]:
        """Quais hashes coincidem."""
        matches = {}
        
        if self.expected_crc32 and self.actual_crc32:
            matches['crc32'] = self.expected_crc32.lower() == self.actual_crc32.lower()
        
        if self.expected_md5 and self.actual_md5:
            matches['md5'] = self.expected_md5.lower() == self.actual_md5.lower()
        
        if self.expected_sha1 and self.actual_sha1:
            matches['sha1'] = self.expected_sha1.lower() == self.actual_sha1.lower()
        
        return matches


class ROMFilterParams(FilterParams):
    """Parâmetros de filtro específicos para ROMs."""
    
    system_id: Optional[UUID] = Field(
        default=None,
        description="Filtrar por sistema"
    )
    
    game_id: Optional[UUID] = Field(
        default=None,
        description="Filtrar por jogo"
    )
    
    status: Optional[List[ROMStatus]] = Field(
        default=None,
        description="Filtrar por status"
    )
    
    compression_type: Optional[List[CompressionType]] = Field(
        default=None,
        description="Filtrar por tipo de compressão"
    )
    
    region: Optional[str] = Field(
        default=None,
        description="Filtrar por região"
    )
    
    file_extension: Optional[List[str]] = Field(
        default=None,
        description="Filtrar por extensão"
    )
    
    file_size_min: Optional[int] = Field(
        default=None,
        ge=0,
        description="Tamanho mínimo em bytes"
    )
    
    file_size_max: Optional[int] = Field(
        default=None,
        ge=0,
        description="Tamanho máximo em bytes"
    )
    
    has_game: Optional[bool] = Field(
        default=None,
        description="Apenas ROMs com jogo associado"
    )
    
    verified_only: Optional[bool] = Field(
        default=None,
        description="Apenas ROMs verificadas"
    )
    
    missing_only: Optional[bool] = Field(
        default=None,
        description="Apenas ROMs ausentes"
    )
    
    duplicates_only: Optional[bool] = Field(
        default=None,
        description="Apenas ROMs duplicadas"
    )


class ROMSearchRequest(BaseSchema):
    """Request para busca de ROMs."""
    
    pagination: PaginationParams = Field(
        default_factory=PaginationParams,
        description="Parâmetros de paginação"
    )
    
    sorting: SortParams = Field(
        default_factory=SortParams,
        description="Parâmetros de ordenação"
    )
    
    filters: ROMFilterParams = Field(
        default_factory=ROMFilterParams,
        description="Filtros de busca"
    )
    
    filename_search: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=255,
        description="Busca por nome de arquivo"
    )


class ROMStats(BaseSchema):
    """Schema para estatísticas de ROMs."""
    
    total: int = Field(ge=0, description="Total de ROMs")
    verified: int = Field(ge=0, description="ROMs verificadas")
    invalid: int = Field(ge=0, description="ROMs inválidas")
    by_system: Dict[str, int] = Field(default_factory=dict)

ROMStats.model_rebuild()
    
class ROMStatsResponse(BaseSchema):
    """Schema para resposta de estatísticas de ROMs."""

    total_roms: int = Field(
        ge=0,
        description="Total de ROMs"
    )
    
    verified_roms: int = Field(
        ge=0,
        description="ROMs verificadas"
    )
    
    invalid_roms: int = Field(
        ge=0,
        description="ROMs inválidas"
    )
    
    missing_roms: int = Field(
        ge=0,
        description="ROMs ausentes"
    )
    
    duplicate_roms: int = Field(
        ge=0,
        description="ROMs duplicadas"
    )
    
    total_size_mb: float = Field(
        ge=0,
        description="Tamanho total em MB"
    )
    
    compressed_size_mb: float = Field(
        ge=0,
        description="Tamanho comprimido total em MB"
    )
    
    average_compression_ratio: Optional[float] = Field(
        default=None,
        description="Taxa média de compressão"
    )
    
    by_system: Dict[str, int] = Field(
        default_factory=dict,
        description="ROMs por sistema"
    )
    
    by_status: Dict[ROMStatus, int] = Field(
        default_factory=dict,
        description="ROMs por status"
    )
    
    by_compression: Dict[CompressionType, int] = Field(
        default_factory=dict,
        description="ROMs por tipo de compressão"
    )


class ROMHashUpdate(BaseSchema):
    """Schema para atualização de hashes de ROM."""
    
    crc32: Optional[str] = Field(
        default=None,
        pattern="^[0-9A-Fa-f]{8}$",
        description="Hash CRC32"
    )
    
    md5: Optional[str] = Field(
        default=None,
        pattern="^[0-9A-Fa-f]{32}$",
        description="Hash MD5"
    )
    
    sha1: Optional[str] = Field(
        default=None,
        pattern="^[0-9A-Fa-f]{40}$",
        description="Hash SHA1"
    )
    
    sha256: Optional[str] = Field(
        default=None,
        pattern="^[0-9A-Fa-f]{64}$",
        description="Hash SHA256"
    )


class ROMVerifyRequest(BaseSchema):
    """Request para verificação de ROM."""
    
    verification_type: VerificationType = Field(
        default=VerificationType.AUTO,
        description="Tipo de verificação"
    )
    
    verification_source: VerificationSource = Field(
        default=VerificationSource.UNKNOWN,
        description="Fonte da verificação"
    )
    
    expected_hashes: Optional[ROMHashUpdate] = Field(
        default=None,
        description="Hashes esperados para comparação"
    )
    
    force_recalculate: bool = Field(
        default=False,
        description="Forçar recálculo dos hashes"
    )


class ROMBatchOperation(BaseSchema):
    """Schema para operações em lote de ROMs."""
    
    operation_type: str = Field(description="Tipo de operação")
    rom_ids: List[UUID] = Field(min_length=1, description="IDs das ROMs")
    parameters: Optional[Dict[str, Any]] = Field(default=None, description="Parâmetros da operação")
    dry_run: bool = Field(default=False, description="Execução de teste")
    force: bool = Field(default=False, description="Forçar operação")

ROMBatchOperation.model_rebuild()
    
class ROMStatsResponse(BaseSchema):
    """Schema para resposta de estatísticas de ROMs."""

    total_roms: int = Field(
        ge=0,
        description="Total de ROMs"
    )
    
    verified_roms: int = Field(
        ge=0,
        description="ROMs verificadas"
    )
    
    invalid_roms: int = Field(
        ge=0,
        description="ROMs inválidas"
    )
    
    missing_roms: int = Field(
        ge=0,
        description="ROMs ausentes"
    )
    
    duplicate_roms: int = Field(
        ge=0,
        description="ROMs duplicadas"
    )
    
    total_size_mb: float = Field(
        ge=0,
        description="Tamanho total em MB"
    )
    
    compressed_size_mb: float = Field(
        ge=0,
        description="Tamanho comprimido total em MB"
    )
    
    average_compression_ratio: Optional[float] = Field(
        default=None,
        description="Taxa média de compressão"
    )
    
    by_system: Dict[str, int] = Field(
        default_factory=dict,
        description="ROMs por sistema"
    )
    
    by_status: Dict[ROMStatus, int] = Field(
        default_factory=dict,
        description="ROMs por status"
    )
    
    by_compression: Dict[CompressionType, int] = Field(
        default_factory=dict,
        description="ROMs por tipo de compressão"
    )


class ROMHashUpdate(BaseSchema):
    """Schema para atualização de hashes de ROM."""
    
    crc32: Optional[str] = Field(
        default=None,
        pattern="^[0-9A-Fa-f]{8}$",
        description="Hash CRC32"
    )
    
    md5: Optional[str] = Field(
        default=None,
        pattern="^[0-9A-Fa-f]{32}$",
        description="Hash MD5"
    )
    
    sha1: Optional[str] = Field(
        default=None,
        pattern="^[0-9A-Fa-f]{40}$",
        description="Hash SHA1"
    )
    
    sha256: Optional[str] = Field(
        default=None,
        pattern="^[0-9A-Fa-f]{64}$",
        description="Hash SHA256"
    )


class ROMVerifyRequest(BaseSchema):
    """Request para verificação de ROM."""
    
    verification_type: VerificationType = Field(
        default=VerificationType.AUTO,
        description="Tipo de verificação"
    )
    
    verification_source: VerificationSource = Field(
        default=VerificationSource.UNKNOWN,
        description="Fonte da verificação"
    )
    
    expected_hashes: Optional[ROMHashUpdate] = Field(
        default=None,
        description="Hashes esperados para comparação"
    )
    
    force_recalculate: bool = Field(
        default=False,
        description="Forçar recálculo dos hashes"
    )


class ROMBulkOperation(BaseSchema):
    """Schema para operações em lote com ROMs."""
    
    rom_ids: List[UUID] = Field(
        min_length=1,
        description="IDs das ROMs para operação"
    )
    
    operation: str = Field(
        description="Tipo de operação",
        examples=["verify", "delete", "move", "update_status"]
    )
    
    parameters: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Parâmetros específicos da operação"
    )


class ROMImportRequest(BaseSchema):
    """Request para importação de ROMs."""
    
    source_path: str = Field(
        description="Caminho de origem para importação"
    )
    
    system_id: UUID = Field(
        description="ID do sistema"
    )
    
    recursive: bool = Field(
        default=True,
        description="Busca recursiva em subdiretórios"
    )
    
    auto_verify: bool = Field(
        default=True,
        description="Verificar automaticamente após importação"
    )
    
    auto_extract: bool = Field(
        default=False,
        description="Extrair arquivos comprimidos automaticamente"
    )
    
    overwrite_existing: bool = Field(
        default=False,
        description="Sobrescrever ROMs existentes"
    )
    
    file_extensions: Optional[List[str]] = Field(
        default=None,
        description="Extensões de arquivo para importar"
    )
    
    @field_validator('source_path')
    @classmethod
    def validate_source_path(cls, v: str) -> str:
        """Valida o caminho de origem."""
        try:
            path = Path(v)
            if not path.exists():
                raise ValueError('Caminho não existe')
            return str(path.absolute())
        except Exception as e:
            raise ValueError(f'Caminho inválido: {e}')


class ROMList(BaseSchema):
    """Schema para listagem de ROMs."""
    
    id: UUID
    filename: str
    file_path: Optional[str] = None
    file_size: Optional[int] = None
    checksum: Optional[str] = None
    region: Optional[str] = None
    language: Optional[str] = None
    version: Optional[str] = None
    verified: bool = False
    game_id: Optional[UUID] = None
    system_id: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime

class ROMDetail(ROMResponse):
    """Schema detalhado para ROM."""
    
    # Campos adicionais para detalhes
    description: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    rating: Optional[float] = None

ROMResponse.model_rebuild()

class ROMVerification(BaseSchema):
    """Schema para verificação de ROM."""
    
    id: UUID = Field(description="ID da verificação")
    rom_id: UUID = Field(description="ID da ROM")
    verification_type: VerificationType = Field(description="Tipo de verificação")
    verification_source: VerificationSource = Field(description="Fonte da verificação")
    status: ROMStatus = Field(description="Status da verificação")
    verified_at: datetime = Field(description="Data da verificação")
    verified_by: Optional[str] = Field(default=None, description="Verificado por")
    notes: Optional[str] = Field(default=None, description="Notas da verificação")

ROMVerification.model_rebuild()

class ROMUploadResponse(BaseSchema):
    """Schema para resposta de upload de ROM."""
    
    success: bool = Field(description="Sucesso do upload")
    rom_id: Optional[UUID] = Field(default=None, description="ID da ROM criada")
    filename: str = Field(description="Nome do arquivo")
    file_size: int = Field(ge=0, description="Tamanho do arquivo em bytes")
    message: str = Field(description="Mensagem de status")
    warnings: Optional[List[str]] = Field(default=None, description="Avisos durante o upload")
    errors: Optional[List[str]] = Field(default=None, description="Erros durante o upload")

ROMUploadResponse.model_rebuild()