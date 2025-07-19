"""Schemas base para validação e serialização.

Define classes base e utilitários comuns utilizados
por todos os schemas Pydantic do sistema.
"""

from datetime import datetime
from typing import Any, Dict, Generic, List, Optional, TypeVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

# Type variable para responses paginadas
T = TypeVar('T')


class BaseSchema(BaseModel):
    """Schema base para todos os schemas Pydantic.
    
    Fornece configuração padrão e métodos utilitários
    para todos os schemas do sistema.
    """
    
    model_config = ConfigDict(
        # Permite validação de atributos extras
        extra="forbid",
        # Usa enum values ao invés de nomes
        use_enum_values=True,
        # Valida assignment de atributos
        validate_assignment=True,
        # Permite serialização de datetime como ISO string
        # Configuração para ORM
        from_attributes=True,
    )


class TimestampSchema(BaseSchema):
    """Schema base para entidades com timestamps.
    
    Inclui campos de criação e atualização automáticos.
    """
    
    created_at: datetime = Field(
        description="Data e hora de criação",
        examples=["2024-01-01T00:00:00Z"]
    )
    
    updated_at: datetime = Field(
        description="Data e hora da última atualização",
        examples=["2024-01-01T12:00:00Z"]
    )


class UUIDSchema(BaseSchema):
    """Schema base para entidades com UUID.
    
    Inclui campo ID como UUID.
    """
    
    id: UUID = Field(
        description="Identificador único da entidade",
        examples=["123e4567-e89b-12d3-a456-426614174000"]
    )


class BaseEntitySchema(UUIDSchema, TimestampSchema):
    """Schema base completo para entidades.
    
    Combina UUID e timestamps para entidades principais.
    """
    pass


class PaginationParams(BaseSchema):
    """Parâmetros para paginação de resultados."""
    
    page: int = Field(
        default=1,
        ge=1,
        description="Número da página (começando em 1)",
        examples=[1]
    )
    
    size: int = Field(
        default=25,
        ge=1,
        le=100,
        description="Número de itens por página (máximo 100)",
        examples=[25]
    )
    
    @property
    def offset(self) -> int:
        """Calcula o offset para a consulta."""
        return (self.page - 1) * self.size


class SortParams(BaseSchema):
    """Parâmetros para ordenação de resultados."""
    
    sort_by: Optional[str] = Field(
        default=None,
        description="Campo para ordenação",
        examples=["name", "created_at"]
    )
    
    sort_order: Optional[str] = Field(
        default="asc",
        pattern="^(asc|desc)$",
        description="Direção da ordenação (asc ou desc)",
        examples=["asc", "desc"]
    )


class FilterParams(BaseSchema):
    """Parâmetros base para filtros."""
    
    search: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=255,
        description="Termo de busca geral",
        examples=["mario", "nintendo"]
    )
    
    active_only: Optional[bool] = Field(
        default=None,
        description="Filtrar apenas itens ativos",
        examples=[True, False]
    )


class PaginatedResponse(BaseSchema, Generic[T]):
    """Response paginada genérica.
    
    Encapsula resultados paginados com metadados
    de paginação e informações da consulta.
    """
    
    items: List[T] = Field(
        description="Lista de itens da página atual"
    )
    
    total: int = Field(
        ge=0,
        description="Total de itens disponíveis",
        examples=[150]
    )
    
    page: int = Field(
        ge=1,
        description="Página atual",
        examples=[1]
    )
    
    size: int = Field(
        ge=1,
        description="Tamanho da página",
        examples=[25]
    )
    
    pages: int = Field(
        ge=0,
        description="Total de páginas",
        examples=[6]
    )
    
    has_next: bool = Field(
        description="Se existe próxima página",
        examples=[True]
    )
    
    has_prev: bool = Field(
        description="Se existe página anterior",
        examples=[False]
    )
    
    @classmethod
    def create(
        cls,
        items: List[T],
        total: int,
        page: int,
        size: int
    ) -> "PaginatedResponse[T]":
        """Cria uma resposta paginada.
        
        Args:
            items: Lista de itens da página
            total: Total de itens
            page: Página atual
            size: Tamanho da página
            
        Returns:
            Resposta paginada configurada
        """
        pages = (total + size - 1) // size if total > 0 else 0
        
        return cls(
            items=items,
            total=total,
            page=page,
            size=size,
            pages=pages,
            has_next=page < pages,
            has_prev=page > 1
        )


class ErrorDetail(BaseSchema):
    """Detalhes de um erro específico."""
    
    field: Optional[str] = Field(
        default=None,
        description="Campo relacionado ao erro",
        examples=["email", "password"]
    )
    
    message: str = Field(
        description="Mensagem de erro",
        examples=["Este campo é obrigatório", "Email inválido"]
    )
    
    code: Optional[str] = Field(
        default=None,
        description="Código do erro",
        examples=["required", "invalid_format"]
    )


class ErrorResponse(BaseSchema):
    """Response padrão para erros da API.
    
    Fornece estrutura consistente para todos os
    tipos de erro retornados pela API.
    """
    
    error: str = Field(
        description="Tipo do erro",
        examples=["validation_error", "not_found", "permission_denied"]
    )
    
    message: str = Field(
        description="Mensagem principal do erro",
        examples=["Dados inválidos", "Recurso não encontrado"]
    )
    
    details: Optional[List[ErrorDetail]] = Field(
        default=None,
        description="Detalhes específicos dos erros"
    )
    
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="Timestamp do erro"
    )
    
    request_id: Optional[str] = Field(
        default=None,
        description="ID da requisição para rastreamento",
        examples=["req_123456789"]
    )


class SuccessResponse(BaseSchema):
    """Response padrão para operações bem-sucedidas."""
    
    success: bool = Field(
        default=True,
        description="Indica sucesso da operação"
    )
    
    message: str = Field(
        description="Mensagem de sucesso",
        examples=["Operação realizada com sucesso"]
    )
    
    data: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Dados adicionais da resposta"
    )


class HealthCheckResponse(BaseSchema):
    """Response para verificação de saúde do sistema."""
    
    status: str = Field(
        description="Status geral do sistema",
        examples=["healthy", "degraded", "unhealthy"]
    )
    
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="Timestamp da verificação"
    )
    
    version: str = Field(
        description="Versão da aplicação",
        examples=["1.0.0"]
    )
    
    services: Dict[str, str] = Field(
        description="Status dos serviços individuais",
        examples={
            "database": "healthy",
            "redis": "healthy",
            "celery": "healthy"
        }
    )
    
    uptime: Optional[float] = Field(
        default=None,
        description="Tempo de atividade em segundos",
        examples=[3600.5]
    )


class MetricsResponse(BaseSchema):
    """Response para métricas do sistema."""
    
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="Timestamp das métricas"
    )
    
    metrics: Dict[str, Any] = Field(
        description="Métricas coletadas",
        examples={
            "requests_total": 1000,
            "response_time_avg": 0.25,
            "active_users": 15
        }
    )


class BulkOperationRequest(BaseSchema):
    """Request para operações em lote."""
    
    ids: List[UUID] = Field(
        min_length=1,
        max_length=100,
        description="Lista de IDs para operação em lote"
    )
    
    operation: str = Field(
        description="Tipo de operação",
        examples=["delete", "update", "activate"]
    )
    
    parameters: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Parâmetros adicionais para a operação"
    )


class BulkOperationResponse(BaseSchema):
    """Response para operações em lote."""
    
    total: int = Field(
        ge=0,
        description="Total de itens processados"
    )
    
    successful: int = Field(
        ge=0,
        description="Número de itens processados com sucesso"
    )
    
    failed: int = Field(
        ge=0,
        description="Número de itens que falharam"
    )
    
    errors: Optional[List[ErrorDetail]] = Field(
        default=None,
        description="Detalhes dos erros ocorridos"
    )
    
    results: Optional[List[Dict[str, Any]]] = Field(
        default=None,
        description="Resultados detalhados por item"
    )