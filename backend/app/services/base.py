"""Serviço base para operações CRUD comuns.

Este módulo define a classe base que todos os serviços devem herdar,
fornecendo funcionalidades comuns como operações CRUD, paginação,
filtros e gerenciamento de sessão de banco de dados.
"""

from typing import Any, Dict, Generic, List, Optional, Type, TypeVar, Union
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import and_, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.sql import Select

from app.models.base import BaseModel
from app.schemas.base import (
    FilterParams,
    PaginatedResponse,
    PaginationParams,
    SortParams,
)

# Type variables para genericidade
ModelType = TypeVar("ModelType")
CreateSchemaType = TypeVar("CreateSchemaType")
UpdateSchemaType = TypeVar("UpdateSchemaType")


class BaseService(Generic[ModelType, CreateSchemaType, UpdateSchemaType]):
    """Serviço base com operações CRUD comuns.
    
    Fornece implementações padrão para:
    - Operações CRUD (Create, Read, Update, Delete)
    - Paginação e ordenação
    - Filtros básicos
    - Validações comuns
    - Gerenciamento de erros
    """
    
    def __init__(self, model: Type[ModelType]):
        """Inicializa o serviço com o modelo SQLAlchemy.
        
        Args:
            model: Classe do modelo SQLAlchemy
        """
        self.model = model
    
    async def create(
        self,
        db: AsyncSession,
        *,
        obj_in: CreateSchemaType,
        **kwargs: Any
    ) -> ModelType:
        """Cria um novo registro.
        
        Args:
            db: Sessão do banco de dados
            obj_in: Dados para criação
            **kwargs: Argumentos adicionais
            
        Returns:
            Registro criado
            
        Raises:
            HTTPException: Se houver erro na criação
        """
        try:
            # Converte schema para dict
            if hasattr(obj_in, 'model_dump'):
                obj_data = obj_in.model_dump(exclude_unset=True)
            else:
                obj_data = obj_in.dict(exclude_unset=True)
            
            # Adiciona argumentos extras
            obj_data.update(kwargs)
            
            # Cria instância do modelo
            db_obj = self.model(**obj_data)
            
            # Salva no banco
            db.add(db_obj)
            await db.commit()
            await db.refresh(db_obj)
            
            return db_obj
            
        except Exception as e:
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Erro ao criar {self.model.__name__}: {str(e)}"
            )
    
    async def get(
        self,
        db: AsyncSession,
        id: Union[UUID, str, int],
        *,
        load_relationships: bool = False
    ) -> Optional[ModelType]:
        """Busca um registro por ID.
        
        Args:
            db: Sessão do banco de dados
            id: ID do registro
            load_relationships: Se deve carregar relacionamentos
            
        Returns:
            Registro encontrado ou None
        """
        query = select(self.model).where(self.model.id == id)
        
        # Carrega relacionamentos se solicitado
        if load_relationships:
            query = self._add_relationship_loading(query)
        
        result = await db.execute(query)
        return result.scalar_one_or_none()
    
    async def get_by_field(
        self,
        db: AsyncSession,
        field_name: str,
        field_value: Any,
        *,
        load_relationships: bool = False
    ) -> Optional[ModelType]:
        """Busca um registro por campo específico.
        
        Args:
            db: Sessão do banco de dados
            field_name: Nome do campo
            field_value: Valor do campo
            load_relationships: Se deve carregar relacionamentos
            
        Returns:
            Registro encontrado ou None
        """
        if not hasattr(self.model, field_name):
            raise ValueError(f"Campo '{field_name}' não existe no modelo {self.model.__name__}")
        
        field = getattr(self.model, field_name)
        query = select(self.model).where(field == field_value)
        
        if load_relationships:
            query = self._add_relationship_loading(query)
        
        result = await db.execute(query)
        return result.scalar_one_or_none()
    
    async def get_multi(
        self,
        db: AsyncSession,
        *,
        pagination: Optional[PaginationParams] = None,
        sort: Optional[SortParams] = None,
        filters: Optional[FilterParams] = None,
        load_relationships: bool = False
    ) -> PaginatedResponse[ModelType]:
        """Busca múltiplos registros com paginação, ordenação e filtros.
        
        Args:
            db: Sessão do banco de dados
            pagination: Parâmetros de paginação
            sort: Parâmetros de ordenação
            filters: Parâmetros de filtro
            load_relationships: Se deve carregar relacionamentos
            
        Returns:
            Resposta paginada com registros
        """
        # Query base
        query = select(self.model)
        
        # Aplica filtros
        if filters:
            query = self._apply_filters(query, filters)
        
        # Conta total de registros
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await db.execute(count_query)
        total = total_result.scalar()
        
        # Aplica ordenação
        if sort:
            query = self._apply_sorting(query, sort)
        
        # Carrega relacionamentos
        if load_relationships:
            query = self._add_relationship_loading(query)
        
        # Aplica paginação
        if pagination:
            offset = (pagination.page - 1) * pagination.size
            query = query.offset(offset).limit(pagination.size)
        
        # Executa query
        result = await db.execute(query)
        items = result.scalars().all()
        
        # Calcula metadados de paginação
        page = pagination.page if pagination else 1
        size = pagination.size if pagination else len(items)
        total_pages = (total + size - 1) // size if size > 0 else 1
        
        return PaginatedResponse(
            items=items,
            total=total,
            page=page,
            size=size,
            total_pages=total_pages,
            has_next=page < total_pages,
            has_prev=page > 1
        )
    
    async def update(
        self,
        db: AsyncSession,
        *,
        db_obj: ModelType,
        obj_in: Union[UpdateSchemaType, Dict[str, Any]]
    ) -> ModelType:
        """Atualiza um registro existente.
        
        Args:
            db: Sessão do banco de dados
            db_obj: Registro existente
            obj_in: Dados para atualização
            
        Returns:
            Registro atualizado
            
        Raises:
            HTTPException: Se houver erro na atualização
        """
        try:
            # Converte para dict se necessário
            if hasattr(obj_in, 'model_dump'):
                update_data = obj_in.model_dump(exclude_unset=True)
            elif hasattr(obj_in, 'dict'):
                update_data = obj_in.dict(exclude_unset=True)
            else:
                update_data = obj_in
            
            # Atualiza campos
            for field, value in update_data.items():
                if hasattr(db_obj, field):
                    setattr(db_obj, field, value)
            
            # Salva alterações
            await db.commit()
            await db.refresh(db_obj)
            
            return db_obj
            
        except Exception as e:
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Erro ao atualizar {self.model.__name__}: {str(e)}"
            )
    
    async def delete(
        self,
        db: AsyncSession,
        *,
        id: Union[UUID, str, int]
    ) -> bool:
        """Remove um registro.
        
        Args:
            db: Sessão do banco de dados
            id: ID do registro
            
        Returns:
            True se removido com sucesso
            
        Raises:
            HTTPException: Se registro não encontrado ou erro na remoção
        """
        try:
            # Busca registro
            db_obj = await self.get(db, id)
            if not db_obj:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"{self.model.__name__} não encontrado"
                )
            
            # Remove registro
            await db.delete(db_obj)
            await db.commit()
            
            return True
            
        except HTTPException:
            raise
        except Exception as e:
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Erro ao remover {self.model.__name__}: {str(e)}"
            )
    
    async def exists(
        self,
        db: AsyncSession,
        *,
        id: Union[UUID, str, int]
    ) -> bool:
        """Verifica se um registro existe.
        
        Args:
            db: Sessão do banco de dados
            id: ID do registro
            
        Returns:
            True se existe
        """
        query = select(func.count()).where(self.model.id == id)
        result = await db.execute(query)
        count = result.scalar()
        return count > 0
    
    async def count(
        self,
        db: AsyncSession,
        *,
        filters: Optional[FilterParams] = None
    ) -> int:
        """Conta registros com filtros opcionais.
        
        Args:
            db: Sessão do banco de dados
            filters: Filtros opcionais
            
        Returns:
            Número de registros
        """
        query = select(func.count()).select_from(self.model)
        
        if filters:
            # Aplica filtros básicos
            conditions = []
            
            if hasattr(filters, 'search') and filters.search:
                # Implementação básica de busca textual
                search_conditions = []
                for column in self.model.__table__.columns:
                    if column.type.python_type == str:
                        search_conditions.append(
                            getattr(self.model, column.name).ilike(f"%{filters.search}%")
                        )
                if search_conditions:
                    conditions.append(or_(*search_conditions))
            
            if conditions:
                query = query.where(and_(*conditions))
        
        result = await db.execute(query)
        return result.scalar()
    
    def _apply_filters(self, query: Select, filters: FilterParams) -> Select:
        """Aplica filtros à query.
        
        Args:
            query: Query base
            filters: Parâmetros de filtro
            
        Returns:
            Query com filtros aplicados
        """
        # Implementação básica - deve ser sobrescrita em serviços específicos
        conditions = []
        
        if hasattr(filters, 'search') and filters.search:
            # Busca textual básica
            search_conditions = []
            for column in self.model.__table__.columns:
                if column.type.python_type == str:
                    search_conditions.append(
                        getattr(self.model, column.name).ilike(f"%{filters.search}%")
                    )
            if search_conditions:
                conditions.append(or_(*search_conditions))
        
        if conditions:
            query = query.where(and_(*conditions))
        
        return query
    
    def _apply_sorting(self, query: Select, sort: SortParams) -> Select:
        """Aplica ordenação à query.
        
        Args:
            query: Query base
            sort: Parâmetros de ordenação
            
        Returns:
            Query com ordenação aplicada
        """
        if not hasattr(self.model, sort.field):
            # Campo inválido, usa ordenação padrão
            if hasattr(self.model, 'created_at'):
                return query.order_by(desc(self.model.created_at))
            return query
        
        field = getattr(self.model, sort.field)
        
        if sort.direction == 'desc':
            return query.order_by(desc(field))
        else:
            return query.order_by(field)
    
    def _add_relationship_loading(self, query: Select) -> Select:
        """Adiciona carregamento de relacionamentos à query.
        
        Args:
            query: Query base
            
        Returns:
            Query com relacionamentos carregados
        """
        # Implementação básica - deve ser sobrescrita em serviços específicos
        # que precisam carregar relacionamentos específicos
        return query
    
    async def bulk_create(
        self,
        db: AsyncSession,
        *,
        objs_in: List[CreateSchemaType],
        **kwargs: Any
    ) -> List[ModelType]:
        """Cria múltiplos registros em lote.
        
        Args:
            db: Sessão do banco de dados
            objs_in: Lista de dados para criação
            **kwargs: Argumentos adicionais
            
        Returns:
            Lista de registros criados
            
        Raises:
            HTTPException: Se houver erro na criação
        """
        try:
            db_objs = []
            
            for obj_in in objs_in:
                # Converte schema para dict
                if hasattr(obj_in, 'model_dump'):
                    obj_data = obj_in.model_dump(exclude_unset=True)
                else:
                    obj_data = obj_in.dict(exclude_unset=True)
                
                # Adiciona argumentos extras
                obj_data.update(kwargs)
                
                # Cria instância do modelo
                db_obj = self.model(**obj_data)
                db_objs.append(db_obj)
            
            # Adiciona todos os objetos
            db.add_all(db_objs)
            await db.commit()
            
            # Refresh todos os objetos
            for db_obj in db_objs:
                await db.refresh(db_obj)
            
            return db_objs
            
        except Exception as e:
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Erro ao criar {self.model.__name__} em lote: {str(e)}"
            )
    
    async def bulk_delete(
        self,
        db: AsyncSession,
        *,
        ids: List[Union[UUID, str, int]]
    ) -> int:
        """Remove múltiplos registros em lote.
        
        Args:
            db: Sessão do banco de dados
            ids: Lista de IDs para remoção
            
        Returns:
            Número de registros removidos
            
        Raises:
            HTTPException: Se houver erro na remoção
        """
        try:
            # Busca registros existentes
            query = select(self.model).where(self.model.id.in_(ids))
            result = await db.execute(query)
            db_objs = result.scalars().all()
            
            # Remove registros
            for db_obj in db_objs:
                await db.delete(db_obj)
            
            await db.commit()
            
            return len(db_objs)
            
        except Exception as e:
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Erro ao remover {self.model.__name__} em lote: {str(e)}"
            )