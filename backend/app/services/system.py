"""Serviços para gerenciamento de sistemas.

Este módulo implementa a lógica de negócio para operações relacionadas
a sistemas de videogame, emuladores e metadados de sistemas.
"""

from typing import List, Optional, Union
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.sql import Select

from app.models.system import System, SystemEmulator, SystemMetadata
from app.models.game import Game
from app.models.rom import ROM
from app.schemas.system import (
    SystemCreate,
    SystemUpdate,
    SystemEmulatorCreate,
    SystemEmulatorUpdate,
    SystemMetadataCreate,
    SystemMetadataUpdate,
    SystemFilterParams,
)
from app.services.base import BaseService


class SystemService(BaseService[System, SystemCreate, SystemUpdate]):
    """Serviço para operações com sistemas."""
    
    def __init__(self):
        super().__init__(System)
    
    async def get_by_id(
        self,
        db: AsyncSession,
        system_id: UUID,
        *,
        load_relationships: bool = False
    ) -> Optional[System]:
        """Busca sistema por ID.
        
        Args:
            db: Sessão do banco de dados
            system_id: ID do sistema
            load_relationships: Se deve carregar relacionamentos
            
        Returns:
            Sistema encontrado ou None
        """
        return await self.get(db, system_id, load_relationships=load_relationships)
    
    async def create_system(
        self,
        db: AsyncSession,
        *,
        system_in: SystemCreate
    ) -> System:
        """Cria um novo sistema.
        
        Args:
            db: Sessão do banco de dados
            system_in: Dados do sistema
            
        Returns:
            Sistema criado
            
        Raises:
            HTTPException: Se sistema já existe
        """
        # Verifica se sistema já existe
        existing_system = await self.get_by_name(db, name=system_in.name)
        if existing_system:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Sistema já existe"
            )
        
        return await self.create(db, obj_in=system_in)
    
    async def get_by_name(
        self,
        db: AsyncSession,
        *,
        name: str
    ) -> Optional[System]:
        """Busca sistema por nome.
        
        Args:
            db: Sessão do banco de dados
            name: Nome do sistema
            
        Returns:
            Sistema encontrado ou None
        """
        return await self.get_by_field(db, "name", name)
    
    async def get_by_short_name(
        self,
        db: AsyncSession,
        *,
        short_name: str
    ) -> Optional[System]:
        """Busca sistema por nome curto.
        
        Args:
            db: Sessão do banco de dados
            short_name: Nome curto do sistema
            
        Returns:
            Sistema encontrado ou None
        """
        return await self.get_by_field(db, "short_name", short_name)
    
    async def get_with_stats(
        self,
        db: AsyncSession,
        *,
        system_id: UUID
    ) -> Optional[System]:
        """Busca sistema com estatísticas.
        
        Args:
            db: Sessão do banco de dados
            system_id: ID do sistema
            
        Returns:
            Sistema com estatísticas ou None
        """
        # Query base com relacionamentos
        query = (
            select(System)
            .options(
                selectinload(System.emulators),
                selectinload(System.metadata)
            )
            .where(System.id == system_id)
        )
        
        result = await db.execute(query)
        system = result.scalar_one_or_none()
        
        if not system:
            return None
        
        # Calcula estatísticas
        await self._calculate_system_stats(db, system)
        
        return system
    
    async def get_systems_with_filters(
        self,
        db: AsyncSession,
        *,
        filters: SystemFilterParams
    ) -> List[System]:
        """Busca sistemas com filtros.
        
        Args:
            db: Sessão do banco de dados
            filters: Filtros de busca
            
        Returns:
            Lista de sistemas
        """
        query = select(System)
        
        # Aplica filtros
        conditions = []
        
        if filters.manufacturer:
            conditions.append(
                System.manufacturer.ilike(f"%{filters.manufacturer}%")
            )
        
        if filters.release_year_min:
            conditions.append(System.release_year >= filters.release_year_min)
        
        if filters.release_year_max:
            conditions.append(System.release_year <= filters.release_year_max)
        
        if filters.cpu_type:
            conditions.append(
                System.cpu_type.ilike(f"%{filters.cpu_type}%")
            )
        
        if filters.has_emulator is not None:
            if filters.has_emulator:
                query = query.join(SystemEmulator)
            else:
                query = query.outerjoin(SystemEmulator).where(
                    SystemEmulator.id.is_(None)
                )
        
        if filters.supported_extensions:
            for ext in filters.supported_extensions:
                conditions.append(
                    System.supported_extensions.contains([ext])
                )
        
        if filters.search:
            search_conditions = [
                System.name.ilike(f"%{filters.search}%"),
                System.short_name.ilike(f"%{filters.search}%"),
                System.manufacturer.ilike(f"%{filters.search}%"),
                System.description.ilike(f"%{filters.search}%")
            ]
            conditions.append(or_(*search_conditions))
        
        if conditions:
            query = query.where(and_(*conditions))
        
        # Ordenação
        if filters.sort_by == "name":
            query = query.order_by(System.name)
        elif filters.sort_by == "manufacturer":
            query = query.order_by(System.manufacturer, System.name)
        elif filters.sort_by == "release_year":
            query = query.order_by(System.release_year.desc(), System.name)
        else:
            query = query.order_by(System.name)
        
        result = await db.execute(query)
        return result.scalars().all()
    
    async def get_systems_by_manufacturer(
        self,
        db: AsyncSession,
        *,
        manufacturer: str
    ) -> List[System]:
        """Busca sistemas por fabricante.
        
        Args:
            db: Sessão do banco de dados
            manufacturer: Nome do fabricante
            
        Returns:
            Lista de sistemas
        """
        query = (
            select(System)
            .where(System.manufacturer.ilike(f"%{manufacturer}%"))
            .order_by(System.release_year.desc(), System.name)
        )
        
        result = await db.execute(query)
        return result.scalars().all()
    
    async def get_systems_by_generation(
        self,
        db: AsyncSession,
        *,
        generation: int
    ) -> List[System]:
        """Busca sistemas por geração.
        
        Args:
            db: Sessão do banco de dados
            generation: Número da geração
            
        Returns:
            Lista de sistemas
        """
        query = (
            select(System)
            .where(System.generation == generation)
            .order_by(System.release_year, System.name)
        )
        
        result = await db.execute(query)
        return result.scalars().all()
    
    async def update_system_stats(
        self,
        db: AsyncSession,
        *,
        system_id: UUID
    ) -> System:
        """Atualiza estatísticas do sistema.
        
        Args:
            db: Sessão do banco de dados
            system_id: ID do sistema
            
        Returns:
            Sistema atualizado
            
        Raises:
            HTTPException: Se sistema não encontrado
        """
        system = await self.get(db, system_id)
        if not system:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Sistema não encontrado"
            )
        
        await self._calculate_system_stats(db, system)
        await db.commit()
        await db.refresh(system)
        
        return system
    
    async def _calculate_system_stats(
        self,
        db: AsyncSession,
        system: System
    ) -> None:
        """Calcula estatísticas do sistema.
        
        Args:
            db: Sessão do banco de dados
            system: Sistema
        """
        # Conta jogos
        games_query = select(func.count()).where(Game.system_id == system.id)
        games_result = await db.execute(games_query)
        system.game_count = games_result.scalar()
        
        # Conta ROMs
        roms_query = select(func.count()).where(ROM.system_id == system.id)
        roms_result = await db.execute(roms_query)
        system.rom_count = roms_result.scalar()
        
        # Calcula tamanho total das ROMs
        size_query = select(func.sum(ROM.file_size)).where(ROM.system_id == system.id)
        size_result = await db.execute(size_query)
        total_size = size_result.scalar() or 0
        system.total_rom_size = total_size
    
    def _add_relationship_loading(self, query: Select) -> Select:
        """Adiciona carregamento de relacionamentos.
        
        Args:
            query: Query base
            
        Returns:
            Query com relacionamentos
        """
        return query.options(
            selectinload(System.emulators),
            selectinload(System.metadata),
            selectinload(System.games),
            selectinload(System.roms)
        )


class SystemEmulatorService(BaseService[SystemEmulator, SystemEmulatorCreate, SystemEmulatorUpdate]):
    """Serviço para operações com emuladores de sistema."""
    
    def __init__(self):
        super().__init__(SystemEmulator)
    
    async def create_emulator(
        self,
        db: AsyncSession,
        *,
        emulator_in: SystemEmulatorCreate
    ) -> SystemEmulator:
        """Cria um novo emulador.
        
        Args:
            db: Sessão do banco de dados
            emulator_in: Dados do emulador
            
        Returns:
            Emulador criado
            
        Raises:
            HTTPException: Se emulador já existe para o sistema
        """
        # Verifica se emulador já existe para o sistema
        existing_emulator = await self.get_by_system_and_name(
            db,
            system_id=emulator_in.system_id,
            name=emulator_in.name
        )
        if existing_emulator:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Emulador já existe para este sistema"
            )
        
        return await self.create(db, obj_in=emulator_in)
    
    async def get_by_system_and_name(
        self,
        db: AsyncSession,
        *,
        system_id: UUID,
        name: str
    ) -> Optional[SystemEmulator]:
        """Busca emulador por sistema e nome.
        
        Args:
            db: Sessão do banco de dados
            system_id: ID do sistema
            name: Nome do emulador
            
        Returns:
            Emulador encontrado ou None
        """
        query = select(SystemEmulator).where(
            and_(
                SystemEmulator.system_id == system_id,
                SystemEmulator.name == name
            )
        )
        
        result = await db.execute(query)
        return result.scalar_one_or_none()
    
    async def get_by_system(
        self,
        db: AsyncSession,
        *,
        system_id: UUID
    ) -> List[SystemEmulator]:
        """Busca emuladores por sistema.
        
        Args:
            db: Sessão do banco de dados
            system_id: ID do sistema
            
        Returns:
            Lista de emuladores
        """
        query = (
            select(SystemEmulator)
            .where(SystemEmulator.system_id == system_id)
            .order_by(SystemEmulator.is_default.desc(), SystemEmulator.name)
        )
        
        result = await db.execute(query)
        return result.scalars().all()
    
    async def get_default_emulator(
        self,
        db: AsyncSession,
        *,
        system_id: UUID
    ) -> Optional[SystemEmulator]:
        """Busca emulador padrão do sistema.
        
        Args:
            db: Sessão do banco de dados
            system_id: ID do sistema
            
        Returns:
            Emulador padrão ou None
        """
        query = select(SystemEmulator).where(
            and_(
                SystemEmulator.system_id == system_id,
                SystemEmulator.is_default == True
            )
        )
        
        result = await db.execute(query)
        return result.scalar_one_or_none()
    
    async def set_default_emulator(
        self,
        db: AsyncSession,
        *,
        emulator_id: UUID
    ) -> SystemEmulator:
        """Define emulador como padrão.
        
        Args:
            db: Sessão do banco de dados
            emulator_id: ID do emulador
            
        Returns:
            Emulador atualizado
            
        Raises:
            HTTPException: Se emulador não encontrado
        """
        emulator = await self.get(db, emulator_id)
        if not emulator:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Emulador não encontrado"
            )
        
        # Remove padrão de outros emuladores do mesmo sistema
        query = (
            select(SystemEmulator)
            .where(
                and_(
                    SystemEmulator.system_id == emulator.system_id,
                    SystemEmulator.is_default == True
                )
            )
        )
        result = await db.execute(query)
        current_defaults = result.scalars().all()
        
        for default_emulator in current_defaults:
            default_emulator.is_default = False
        
        # Define novo padrão
        emulator.is_default = True
        
        await db.commit()
        await db.refresh(emulator)
        
        return emulator
    
    def _add_relationship_loading(self, query: Select) -> Select:
        """Adiciona carregamento de relacionamentos.
        
        Args:
            query: Query base
            
        Returns:
            Query com relacionamentos
        """
        return query.options(selectinload(SystemEmulator.system))


class SystemMetadataService(BaseService[SystemMetadata, SystemMetadataCreate, SystemMetadataUpdate]):
    """Serviço para operações com metadados de sistema."""
    
    def __init__(self):
        super().__init__(SystemMetadata)
    
    async def create_metadata(
        self,
        db: AsyncSession,
        *,
        metadata_in: SystemMetadataCreate
    ) -> SystemMetadata:
        """Cria novos metadados.
        
        Args:
            db: Sessão do banco de dados
            metadata_in: Dados dos metadados
            
        Returns:
            Metadados criados
            
        Raises:
            HTTPException: Se metadados já existem para o sistema
        """
        # Verifica se metadados já existem
        existing_metadata = await self.get_by_system(
            db, system_id=metadata_in.system_id
        )
        if existing_metadata:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Metadados já existem para este sistema"
            )
        
        return await self.create(db, obj_in=metadata_in)
    
    async def get_by_system(
        self,
        db: AsyncSession,
        *,
        system_id: UUID
    ) -> Optional[SystemMetadata]:
        """Busca metadados por sistema.
        
        Args:
            db: Sessão do banco de dados
            system_id: ID do sistema
            
        Returns:
            Metadados encontrados ou None
        """
        return await self.get_by_field(db, "system_id", system_id)
    
    async def update_metadata(
        self,
        db: AsyncSession,
        *,
        system_id: UUID,
        metadata_in: SystemMetadataUpdate
    ) -> SystemMetadata:
        """Atualiza metadados do sistema.
        
        Args:
            db: Sessão do banco de dados
            system_id: ID do sistema
            metadata_in: Dados dos metadados
            
        Returns:
            Metadados atualizados
            
        Raises:
            HTTPException: Se metadados não encontrados
        """
        metadata = await self.get_by_system(db, system_id=system_id)
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
        return query.options(selectinload(SystemMetadata.system))