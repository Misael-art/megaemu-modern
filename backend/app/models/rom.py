"""Modelos para ROMs e arquivos relacionados.

Define entidades para arquivos ROM, verificações de integridade
e metadados de arquivos com suporte a múltiplos formatos.
"""

from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import List, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum as SQLEnum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Index,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import BaseModel, MetadataMixin


class ROMStatus(str, Enum):
    """Status de verificação do ROM."""
    UNKNOWN = "unknown"
    VERIFIED = "verified"
    GOOD = "good"
    BAD = "bad"
    MISSING = "missing"
    DUPLICATE = "duplicate"
    RENAMED = "renamed"
    OVERDUMP = "overdump"
    UNDERDUMP = "underdump"
    CORRUPT = "corrupt"
    HACKED = "hacked"
    TRANSLATED = "translated"
    HOMEBREW = "homebrew"
    PROTOTYPE = "prototype"
    BETA = "beta"
    DEMO = "demo"
    SAMPLE = "sample"


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
    MANUAL = "manual"
    AUTOMATIC = "automatic"
    DAT_FILE = "dat_file"
    HASH_CHECK = "hash_check"
    FILE_SIZE = "file_size"
    HEADER_CHECK = "header_check"
    FULL_SCAN = "full_scan"


class VerificationSource(str, Enum):
    """Fontes de verificação de ROM."""
    NO_INTRO = "no_intro"
    GOODTOOLS = "goodtools"
    TOSEC = "tosec"
    REDUMP = "redump"
    MAME = "mame"
    USER_MANUAL = "user_manual"
    SYSTEM_AUTO = "system_auto"
    EXTERNAL_DB = "external_db"
    CUSTOM_DAT = "custom_dat"


class ROM(BaseModel, MetadataMixin):
    """Modelo principal para arquivos ROM.
    
    Representa um arquivo ROM específico com informações de verificação,
    localização e metadados técnicos.
    """
    
    __tablename__ = "roms"
    
    # Relacionamento com jogo
    game_id: Mapped[UUID] = mapped_column(
        ForeignKey("games.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    # Informações do arquivo
    filename: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        index=True,
        doc="Nome do arquivo ROM"
    )
    
    file_path: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        doc="Caminho completo para o arquivo"
    )
    
    file_extension: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True,
        doc="Extensão do arquivo (.nes, .smc, etc.)"
    )
    
    file_size: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        index=True,
        doc="Tamanho do arquivo em bytes"
    )
    
    # Hashes de verificação
    crc32: Mapped[Optional[str]] = mapped_column(
        String(8),
        nullable=True,
        index=True,
        doc="Hash CRC32 do arquivo"
    )
    
    md5: Mapped[Optional[str]] = mapped_column(
        String(32),
        nullable=True,
        index=True,
        doc="Hash MD5 do arquivo"
    )
    
    sha1: Mapped[Optional[str]] = mapped_column(
        String(40),
        nullable=True,
        index=True,
        doc="Hash SHA1 do arquivo"
    )
    
    sha256: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
        index=True,
        doc="Hash SHA256 do arquivo"
    )
    
    # Status e verificação
    status: Mapped[ROMStatus] = mapped_column(
        SQLEnum(ROMStatus),
        nullable=False,
        default=ROMStatus.UNKNOWN,
        index=True,
        doc="Status de verificação do ROM"
    )
    
    is_verified: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
        doc="Se o ROM foi verificado contra DAT"
    )
    
    verification_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="Data da última verificação"
    )
    
    # Informações de compressão
    is_compressed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        doc="Se o arquivo está comprimido"
    )
    
    compression_type: Mapped[Optional[CompressionType]] = mapped_column(
        SQLEnum(CompressionType),
        nullable=True,
        doc="Tipo de compressão usado"
    )
    
    compressed_size: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        doc="Tamanho do arquivo comprimido"
    )
    
    uncompressed_size: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        doc="Tamanho do arquivo descomprimido"
    )
    
    # Informações de região e versão
    region: Mapped[Optional[str]] = mapped_column(
        String(10),
        nullable=True,
        index=True,
        doc="Região do ROM (US, EU, JP, etc.)"
    )
    
    version: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        doc="Versão do ROM (Rev A, v1.1, etc.)"
    )
    
    revision: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        doc="Revisão do ROM"
    )
    
    # Flags e características
    is_good: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        doc="Se é considerado um bom dump"
    )
    
    is_prototype: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        doc="Se é um protótipo"
    )
    
    is_beta: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        doc="Se é uma versão beta"
    )
    
    is_demo: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        doc="Se é uma demo"
    )
    
    is_homebrew: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        doc="Se é um homebrew"
    )
    
    is_hack: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        doc="Se é um hack/modificação"
    )
    
    is_translation: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        doc="Se é uma tradução"
    )
    
    # Informações de acesso
    last_accessed: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="Última vez que foi acessado"
    )
    
    access_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        doc="Número de vezes que foi acessado"
    )
    
    # Dados de importação
    import_source: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        doc="Fonte da importação (scan, manual, etc.)"
    )
    
    dat_name: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        doc="Nome do DAT de origem"
    )
    
    # Relacionamentos
    game: Mapped["Game"] = relationship(
        "Game",
        back_populates="roms"
    )
    
    rom_files: Mapped[List["ROMFile"]] = relationship(
        "ROMFile",
        back_populates="rom",
        cascade="all, delete-orphan"
    )
    
    verifications: Mapped[List["ROMVerification"]] = relationship(
        "ROMVerification",
        back_populates="rom",
        cascade="all, delete-orphan"
    )
    
    # Índices compostos
    __table_args__ = (
        UniqueConstraint('game_id', 'filename', name='uq_rom_game_filename'),
        Index('ix_rom_hashes', 'crc32', 'md5', 'sha1'),
        Index('ix_rom_status_verified', 'status', 'is_verified'),
        Index('ix_rom_file_info', 'file_extension', 'file_size'),
        Index('ix_rom_flags', 'is_good', 'is_prototype', 'is_beta'),
    )
    
    def __repr__(self) -> str:
        return f"<ROM(filename='{self.filename}', status='{self.status.value}')>"
    
    @property
    def file_path_obj(self) -> Path:
        """Retorna o caminho como objeto Path."""
        return Path(self.file_path)
    
    @property
    def exists(self) -> bool:
        """Verifica se o arquivo existe no sistema de arquivos."""
        return self.file_path_obj.exists()
    
    @property
    def display_name(self) -> str:
        """Nome para exibição com informações de região/versão."""
        name = self.filename
        if self.region:
            name += f" ({self.region})"
        if self.version:
            name += f" [{self.version}]"
        return name
    
    @property
    def compression_ratio(self) -> Optional[float]:
        """Calcula a taxa de compressão."""
        if self.compressed_size and self.uncompressed_size:
            return (1 - self.compressed_size / self.uncompressed_size) * 100
        return None
    
    def update_access_info(self) -> None:
        """Atualiza informações de acesso."""
        self.last_accessed = datetime.utcnow()
        self.access_count += 1
    
    def calculate_hashes(self) -> dict[str, str]:
        """Calcula hashes do arquivo.
        
        Returns:
            Dicionário com os hashes calculados
        """
        import hashlib
        
        if not self.exists:
            raise FileNotFoundError(f"Arquivo não encontrado: {self.file_path}")
        
        hashes = {}
        
        with open(self.file_path, 'rb') as f:
            content = f.read()
            
            # CRC32
            import zlib
            hashes['crc32'] = format(zlib.crc32(content) & 0xffffffff, '08x')
            
            # MD5
            hashes['md5'] = hashlib.md5(content).hexdigest()
            
            # SHA1
            hashes['sha1'] = hashlib.sha1(content).hexdigest()
            
            # SHA256
            hashes['sha256'] = hashlib.sha256(content).hexdigest()
        
        return hashes
    
    def update_hashes(self) -> None:
        """Atualiza os hashes do arquivo."""
        hashes = self.calculate_hashes()
        self.crc32 = hashes['crc32']
        self.md5 = hashes['md5']
        self.sha1 = hashes['sha1']
        self.sha256 = hashes['sha256']


class ROMFile(BaseModel):
    """Modelo para arquivos dentro de ROMs comprimidos.
    
    Representa arquivos individuais dentro de arquivos comprimidos
    como ZIP, RAR, etc.
    """
    
    __tablename__ = "rom_files"
    
    # Relacionamento com ROM
    rom_id: Mapped[UUID] = mapped_column(
        ForeignKey("roms.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    # Informações do arquivo
    filename: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        doc="Nome do arquivo dentro do comprimido"
    )
    
    file_path: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        doc="Caminho do arquivo dentro do comprimido"
    )
    
    file_size: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        doc="Tamanho do arquivo em bytes"
    )
    
    # Hashes
    crc32: Mapped[Optional[str]] = mapped_column(
        String(8),
        nullable=True,
        index=True,
        doc="Hash CRC32 do arquivo"
    )
    
    md5: Mapped[Optional[str]] = mapped_column(
        String(32),
        nullable=True,
        index=True,
        doc="Hash MD5 do arquivo"
    )
    
    sha1: Mapped[Optional[str]] = mapped_column(
        String(40),
        nullable=True,
        index=True,
        doc="Hash SHA1 do arquivo"
    )
    
    # Informações de compressão
    compressed_size: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        doc="Tamanho comprimido do arquivo"
    )
    
    compression_method: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        doc="Método de compressão usado"
    )
    
    # Status
    is_main_file: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        doc="Se é o arquivo principal do ROM"
    )
    
    # Relacionamentos
    rom: Mapped[ROM] = relationship(
        "ROM",
        back_populates="rom_files"
    )
    
    # Índices
    __table_args__ = (
        UniqueConstraint('rom_id', 'file_path', name='uq_rom_file_path'),
        Index('ix_rom_file_hashes', 'crc32', 'md5', 'sha1'),
    )
    
    def __repr__(self) -> str:
        return f"<ROMFile(filename='{self.filename}', size={self.file_size})>"


class ROMVerification(BaseModel):
    """Modelo para histórico de verificações de ROM.
    
    Mantém um log de todas as verificações realizadas em um ROM,
    incluindo resultados e fontes de verificação.
    """
    
    __tablename__ = "rom_verifications"
    
    # Relacionamento com ROM
    rom_id: Mapped[UUID] = mapped_column(
        ForeignKey("roms.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    # Informações da verificação
    verification_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        doc="Tipo de verificação (dat, manual, auto)"
    )
    
    verification_source: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        doc="Fonte da verificação (nome do DAT, etc.)"
    )
    
    # Resultados
    status_before: Mapped[ROMStatus] = mapped_column(
        SQLEnum(ROMStatus),
        nullable=False,
        doc="Status antes da verificação"
    )
    
    status_after: Mapped[ROMStatus] = mapped_column(
        SQLEnum(ROMStatus),
        nullable=False,
        doc="Status após a verificação"
    )
    
    # Hashes verificados
    expected_crc32: Mapped[Optional[str]] = mapped_column(
        String(8),
        nullable=True,
        doc="CRC32 esperado"
    )
    
    actual_crc32: Mapped[Optional[str]] = mapped_column(
        String(8),
        nullable=True,
        doc="CRC32 encontrado"
    )
    
    expected_md5: Mapped[Optional[str]] = mapped_column(
        String(32),
        nullable=True,
        doc="MD5 esperado"
    )
    
    actual_md5: Mapped[Optional[str]] = mapped_column(
        String(32),
        nullable=True,
        doc="MD5 encontrado"
    )
    
    expected_sha1: Mapped[Optional[str]] = mapped_column(
        String(40),
        nullable=True,
        doc="SHA1 esperado"
    )
    
    actual_sha1: Mapped[Optional[str]] = mapped_column(
        String(40),
        nullable=True,
        doc="SHA1 encontrado"
    )
    
    # Detalhes da verificação
    verification_details: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        doc="Detalhes adicionais da verificação"
    )
    
    error_message: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        doc="Mensagem de erro se a verificação falhou"
    )
    
    # Timing
    verification_duration: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        doc="Duração da verificação em segundos"
    )
    
    # Relacionamentos
    rom: Mapped[ROM] = relationship(
        "ROM",
        back_populates="verifications"
    )
    
    # Índices
    __table_args__ = (
        Index('ix_verification_type_date', 'verification_type', 'created_at'),
        Index('ix_verification_status', 'status_before', 'status_after'),
    )
    
    def __repr__(self) -> str:
        return f"<ROMVerification(type='{self.verification_type}', status='{self.status_after.value}')>"
    
    @property
    def is_successful(self) -> bool:
        """Verifica se a verificação foi bem-sucedida."""
        return self.status_after in [ROMStatus.VERIFIED, ROMStatus.GOOD]
    
    @property
    def hash_matches(self) -> dict[str, bool]:
        """Verifica quais hashes coincidem."""
        matches = {}
        
        if self.expected_crc32 and self.actual_crc32:
            matches['crc32'] = self.expected_crc32.lower() == self.actual_crc32.lower()
        
        if self.expected_md5 and self.actual_md5:
            matches['md5'] = self.expected_md5.lower() == self.actual_md5.lower()
        
        if self.expected_sha1 and self.actual_sha1:
            matches['sha1'] = self.expected_sha1.lower() == self.actual_sha1.lower()
        
        return matches
    
    @property
    def all_hashes_match(self) -> bool:
        """Verifica se todos os hashes disponíveis coincidem."""
        matches = self.hash_matches
        return len(matches) > 0 and all(matches.values())