"""Mixins base para modelos SQLAlchemy.

Fornece funcionalidades comuns como timestamps automáticos,
UUIDs e métodos utilitários para todos os modelos.
"""

import uuid
from datetime import datetime
from typing import Any, Dict

from sqlalchemy import DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class UUIDMixin:
    """Mixin para adicionar campo UUID como chave primária.
    
    Gera automaticamente UUIDs únicos para cada registro.
    """
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
        doc="Identificador único do registro"
    )


class TimestampMixin:
    """Mixin para adicionar campos de timestamp automáticos.
    
    Adiciona created_at e updated_at com valores automáticos.
    """
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
        doc="Data e hora de criação do registro"
    )
    
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        index=True,
        doc="Data e hora da última atualização"
    )


class SoftDeleteMixin:
    """Mixin para soft delete (exclusão lógica).
    
    Permite marcar registros como deletados sem removê-los fisicamente.
    """
    
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
        doc="Data e hora da exclusão lógica"
    )
    
    @property
    def is_deleted(self) -> bool:
        """Verifica se o registro foi deletado logicamente."""
        return self.deleted_at is not None
    
    def soft_delete(self) -> None:
        """Marca o registro como deletado."""
        self.deleted_at = datetime.utcnow()
    
    def restore(self) -> None:
        """Restaura um registro deletado logicamente."""
        self.deleted_at = None


class MetadataMixin:
    """Mixin para campos de metadados adicionais.
    
    Permite armazenar informações extras em formato JSON.
    """
    
    metadata_: Mapped[Dict[str, Any] | None] = mapped_column(
        "metadata",  # Nome da coluna no banco
        JSON,
        nullable=True,
        doc="Metadados adicionais em formato JSON"
    )
    
    def set_metadata(self, key: str, value: Any) -> None:
        """Define um valor nos metadados.
        
        Args:
            key: Chave do metadado
            value: Valor a ser armazenado
        """
        if self.metadata_ is None:
            self.metadata_ = {}
        self.metadata_[key] = value
    
    def get_metadata(self, key: str, default: Any = None) -> Any:
        """Obtém um valor dos metadados.
        
        Args:
            key: Chave do metadado
            default: Valor padrão se a chave não existir
            
        Returns:
            Valor do metadado ou valor padrão
        """
        if self.metadata_ is None:
            return default
        return self.metadata_.get(key, default)
    
    def remove_metadata(self, key: str) -> bool:
        """Remove um metadado.
        
        Args:
            key: Chave do metadado a remover
            
        Returns:
            True se o metadado foi removido, False se não existia
        """
        if self.metadata_ is None:
            return False
        return self.metadata_.pop(key, None) is not None


class AuditMixin:
    """Mixin para auditoria de alterações.
    
    Rastreia quem criou e modificou os registros.
    """
    
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
        doc="ID do usuário que criou o registro"
    )
    
    updated_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
        doc="ID do usuário que fez a última atualização"
    )


class VersionMixin:
    """Mixin para controle de versão otimista.
    
    Previne conflitos de concorrência usando versioning.
    """
    
    version: Mapped[int] = mapped_column(
        default=1,
        nullable=False,
        doc="Versão do registro para controle de concorrência"
    )


class SlugMixin:
    """Mixin para campos slug (URLs amigáveis).
    
    Adiciona campo slug único para URLs SEO-friendly.
    """
    
    slug: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
        doc="Slug único para URLs amigáveis"
    )
    
    @classmethod
    def generate_slug(cls, text: str) -> str:
        """Gera um slug a partir de um texto.
        
        Args:
            text: Texto para gerar o slug
            
        Returns:
            Slug gerado
        """
        import re
        import unicodedata
        
        # Normaliza unicode e remove acentos
        text = unicodedata.normalize('NFKD', text)
        text = text.encode('ascii', 'ignore').decode('ascii')
        
        # Converte para minúsculas e substitui espaços/caracteres especiais
        text = re.sub(r'[^\w\s-]', '', text.lower())
        text = re.sub(r'[-\s]+', '-', text)
        
        return text.strip('-')


class BaseModel(Base, UUIDMixin, TimestampMixin):
    """Modelo base com funcionalidades essenciais.
    
    Combina UUID e timestamps para uso geral.
    Todos os modelos principais devem herdar desta classe.
    """
    
    __abstract__ = True
    
    def to_dict(self, exclude: set[str] | None = None) -> Dict[str, Any]:
        """Converte o modelo para dicionário.
        
        Args:
            exclude: Campos a excluir da conversão
            
        Returns:
            Dicionário com os dados do modelo
        """
        exclude = exclude or set()
        result = {}
        
        for column in self.__table__.columns:
            if column.name not in exclude:
                value = getattr(self, column.name)
                # Converte tipos especiais para serialização
                if isinstance(value, datetime):
                    value = value.isoformat()
                elif isinstance(value, uuid.UUID):
                    value = str(value)
                result[column.name] = value
        
        return result
    
    def update_from_dict(self, data: Dict[str, Any], exclude: set[str] | None = None) -> None:
        """Atualiza o modelo a partir de um dicionário.
        
        Args:
            data: Dados para atualizar
            exclude: Campos a excluir da atualização
        """
        exclude = exclude or {'id', 'created_at', 'updated_at'}
        
        for key, value in data.items():
            if key not in exclude and hasattr(self, key):
                setattr(self, key, value)
    
    def __repr__(self) -> str:
        """Representação string do modelo."""
        return f"<{self.__class__.__name__}(id={self.id})>"