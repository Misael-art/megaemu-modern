"""Modelos para sistemas de videogame.

Define entidades relacionadas a consoles, arcades e outros sistemas,
incluindo emuladores e metadados específicos.
"""

from typing import List, Optional

from sqlalchemy import (
    Boolean,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import BaseModel, MetadataMixin, SlugMixin


class System(BaseModel, SlugMixin, MetadataMixin):
    """Modelo para sistemas de videogame (consoles, arcades, etc.).
    
    Representa diferentes plataformas como NES, SNES, Arcade, etc.
    Inclui informações técnicas e de compatibilidade.
    """
    
    __tablename__ = "systems"
    
    # Informações básicas
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique=True,
        index=True,
        doc="Nome do sistema (ex: Nintendo Entertainment System)"
    )
    
    short_name: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        unique=True,
        index=True,
        doc="Nome curto do sistema (ex: NES)"
    )
    
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        doc="Descrição detalhada do sistema"
    )
    
    # Informações técnicas
    manufacturer: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        index=True,
        doc="Fabricante do sistema (ex: Nintendo)"
    )
    
    release_year: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        index=True,
        doc="Ano de lançamento do sistema"
    )
    
    generation: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        index=True,
        doc="Geração do console (1ª, 2ª, 3ª, etc.)"
    )
    
    # Especificações técnicas
    cpu: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        doc="Processador do sistema"
    )
    
    memory: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        doc="Memória RAM do sistema"
    )
    
    storage: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        doc="Tipo de mídia/armazenamento"
    )
    
    resolution: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        doc="Resolução de vídeo suportada"
    )
    
    # Configurações de emulação
    default_emulator: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        doc="Emulador padrão recomendado"
    )
    
    supported_extensions: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="[]",
        doc="Extensões de arquivo suportadas (JSON)"
    )
    
    bios_required: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        doc="Se o sistema requer arquivos BIOS"
    )
    
    bios_files: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="[]",
        doc="Lista de arquivos BIOS necessários (JSON)"
    )
    
    # Status e configurações
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        index=True,
        doc="Se o sistema está ativo no catálogo"
    )
    
    auto_scan_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        doc="Se deve fazer scan automático de ROMs"
    )
    
    sort_order: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        index=True,
        doc="Ordem de exibição na interface"
    )
    
    # Caminhos e configurações
    rom_path: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        doc="Caminho padrão para ROMs do sistema"
    )
    
    bios_path: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        doc="Caminho para arquivos BIOS"
    )
    
    # Relacionamentos
    games: Mapped[List["Game"]] = relationship(
        "Game",
        back_populates="system",
        cascade="all, delete-orphan",
        lazy="dynamic"
    )
    
    emulators: Mapped[List["SystemEmulator"]] = relationship(
        "SystemEmulator",
        back_populates="system",
        cascade="all, delete-orphan"
    )
    
    system_metadata: Mapped[List["SystemMetadata"]] = relationship(
        "SystemMetadata",
        back_populates="system",
        cascade="all, delete-orphan"
    )
    
    # Índices compostos
    __table_args__ = (
        UniqueConstraint('name', name='uq_system_name'),
        UniqueConstraint('short_name', name='uq_system_short_name'),
        UniqueConstraint('slug', name='uq_system_slug'),
    )
    
    def __repr__(self) -> str:
        return f"<System(name='{self.name}', short_name='{self.short_name}')>"
    
    @property
    def game_count(self) -> int:
        """Retorna o número de jogos do sistema."""
        return self.games.count()
    
    def add_supported_extension(self, extension: str) -> None:
        """Adiciona uma extensão suportada.
        
        Args:
            extension: Extensão de arquivo (ex: '.nes')
        """
        if not extension.startswith('.'):
            extension = f'.{extension}'
        
        if extension.lower() not in [ext.lower() for ext in self.supported_extensions]:
            self.supported_extensions.append(extension.lower())
    
    def remove_supported_extension(self, extension: str) -> bool:
        """Remove uma extensão suportada.
        
        Args:
            extension: Extensão a remover
            
        Returns:
            True se removida, False se não encontrada
        """
        if not extension.startswith('.'):
            extension = f'.{extension}'
        
        try:
            self.supported_extensions.remove(extension.lower())
            return True
        except ValueError:
            return False
    
    def supports_extension(self, extension: str) -> bool:
        """Verifica se uma extensão é suportada.
        
        Args:
            extension: Extensão a verificar
            
        Returns:
            True se suportada
        """
        if not extension.startswith('.'):
            extension = f'.{extension}'
        
        return extension.lower() in [ext.lower() for ext in self.supported_extensions]


class SystemEmulator(BaseModel):
    """Modelo para emuladores de sistema.
    
    Representa diferentes emuladores disponíveis para cada sistema,
    com configurações específicas e níveis de compatibilidade.
    """
    
    __tablename__ = "system_emulators"
    
    # Relacionamento com sistema
    system_id: Mapped[UUID] = mapped_column(
        ForeignKey("systems.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    # Informações do emulador
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        doc="Nome do emulador (ex: Nestopia, FCEUX)"
    )
    
    version: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        doc="Versão do emulador"
    )
    
    executable_path: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        doc="Caminho para o executável do emulador"
    )
    
    command_line: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        doc="Template de linha de comando"
    )
    
    # Configurações
    is_default: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        doc="Se é o emulador padrão para o sistema"
    )
    
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        doc="Se o emulador está ativo"
    )
    
    compatibility_rating: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        doc="Rating de compatibilidade (1-10)"
    )
    
    performance_rating: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        doc="Rating de performance (1-10)"
    )
    
    # Configurações avançadas
    config_file: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        doc="Caminho para arquivo de configuração"
    )
    
    additional_parameters: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        doc="Parâmetros adicionais de linha de comando"
    )
    
    supported_features: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="[]",
        doc="Features suportadas pelo emulador"
    )
    
    # Relacionamentos
    system: Mapped["System"] = relationship(
        "System",
        back_populates="emulators"
    )
    
    # Índices
    __table_args__ = (
        UniqueConstraint('system_id', 'name', name='uq_system_emulator'),
    )
    
    def __repr__(self) -> str:
        return f"<SystemEmulator(name='{self.name}', system='{self.system.short_name if self.system else 'Unknown'}')>"


class SystemMetadata(BaseModel):
    """Modelo para metadados adicionais de sistemas.
    
    Armazena informações extras como imagens, links, estatísticas, etc.
    """
    
    __tablename__ = "system_metadata"
    
    # Relacionamento com sistema
    system_id: Mapped[UUID] = mapped_column(
        ForeignKey("systems.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    # Tipo e dados do metadado
    metadata_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        doc="Tipo do metadado (image, link, stat, etc.)"
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
    
    # Configurações
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
    system: Mapped["System"] = relationship(
        "System",
        back_populates="system_metadata"
    )
    
    # Índices
    __table_args__ = (
        UniqueConstraint('system_id', 'metadata_type', 'key', name='uq_system_metadata'),
    )
    
    def __repr__(self) -> str:
        return f"<SystemMetadata(type='{self.metadata_type}', key='{self.key}')>"