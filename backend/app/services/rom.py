"""Serviços para gerenciamento de ROMs.

Este módulo implementa a lógica de negócio para operações relacionadas
a ROMs, arquivos e verificação de integridade.
"""

import hashlib
import os
import zipfile
import rarfile
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.sql import Select

from app.models.rom import ROM, ROMFile, ROMVerification, ROMStatus, CompressionType, VerificationSource
from app.models.game import Game
from app.models.system import System
from app.schemas.rom import (
    ROMCreate,
    ROMUpdate,
    ROMFileCreate,
    ROMFileUpdate,
    ROMVerificationCreate,
    ROMFilterParams,
    ROMSearchRequest,
    ROMHashUpdate,
    ROMVerifyRequest,
    ROMBulkOperation,
    ROMImportRequest,
)
from app.services.base import BaseService
from app.core.config import settings


class ROMService(BaseService[ROM, ROMCreate, ROMUpdate]):
    """Serviço para operações com ROMs."""
    
    def __init__(self):
        super().__init__(ROM)
    
    async def get_by_id(
        self,
        db: AsyncSession,
        rom_id: UUID,
        *,
        load_relationships: bool = False
    ) -> Optional[ROM]:
        """Busca ROM por ID.
        
        Args:
            db: Sessão do banco de dados
            rom_id: ID da ROM
            load_relationships: Se deve carregar relacionamentos
            
        Returns:
            ROM encontrada ou None
        """
        return await self.get(db, rom_id, load_relationships=load_relationships)
    
    async def create_rom(
        self,
        db: AsyncSession,
        *,
        rom_in: ROMCreate
    ) -> ROM:
        """Cria uma nova ROM."""
        
        existing_rom = await self.get_by_file_path(db, file_path=rom_in.file_path)
        if existing_rom:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="ROM já existe"
            )
        
        rom_data = rom_in.dict()
        if os.path.exists(rom_in.file_path):
            try:
                hashes = await self._calculate_file_hashes(rom_in.file_path)
                rom_data.update(hashes)
            except Exception as e:
                logger.error(f"Falha ao calcular hashes para {rom_in.file_path}: {e}")
                # Fallback: Continuar sem hashes
                rom_data.update({
                    'crc32_hash': None,
                    'md5_hash': None,
                    'sha1_hash': None,
                    'sha256_hash': None
                })
        
        rom = ROM(**rom_data)
        
        # Auto-verificação se solicitada
        if rom_in.auto_verify:
            await self._auto_verify_rom(db, rom)
        
        # Auto-extração se solicitada
        if rom_in.auto_extract and rom.compression_type != CompressionType.NONE:
            await self._auto_extract_rom(rom)
        
        db.add(rom)
        await db.commit()
        await db.refresh(rom)
        
        return rom
    
    async def get_by_file_path(
        self,
        db: AsyncSession,
        *,
        file_path: str
    ) -> Optional[ROM]:
        """Busca ROM por caminho do arquivo.
        
        Args:
            db: Sessão do banco de dados
            file_path: Caminho do arquivo
            
        Returns:
            ROM encontrada ou None
        """
        return await self.get_by_field(db, "file_path", file_path)
    
    async def get_by_hash(
        self,
        db: AsyncSession,
        *,
        hash_type: str,
        hash_value: str
    ) -> Optional[ROM]:
        """Busca ROM por hash.
        
        Args:
            db: Sessão do banco de dados
            hash_type: Tipo do hash (crc32, md5, sha1, sha256)
            hash_value: Valor do hash
            
        Returns:
            ROM encontrada ou None
        """
        field_name = f"{hash_type.lower()}_hash"
        return await self.get_by_field(db, field_name, hash_value.lower())
    
    async def search_roms(
        self,
        db: AsyncSession,
        *,
        search_request: ROMSearchRequest
    ) -> Dict[str, Any]:
        """Busca ROMs com filtros e paginação.
        
        Args:
            db: Sessão do banco de dados
            search_request: Parâmetros de busca
            
        Returns:
            Resultado da busca com ROMs e metadados
        """
        query = select(ROM).options(
            selectinload(ROM.game),
            selectinload(ROM.system),
            selectinload(ROM.files),
            selectinload(ROM.verifications)
        )
        
        # Aplica filtros
        query = self._apply_filters(query, search_request.filters)
        
        # Busca por nome de arquivo
        if search_request.filename:
            query = query.where(
                ROM.filename.ilike(f"%{search_request.filename}%")
            )
        
        # Conta total
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await db.execute(count_query)
        total = total_result.scalar()
        
        # Aplica ordenação
        query = self._apply_sorting(query, search_request.sort_by, search_request.sort_order)
        
        # Aplica paginação
        offset = (search_request.page - 1) * search_request.page_size
        query = query.offset(offset).limit(search_request.page_size)
        
        # Executa query
        result = await db.execute(query)
        roms = result.scalars().all()
        
        return {
            "items": roms,
            "total": total,
            "page": search_request.page,
            "page_size": search_request.page_size,
            "total_pages": (total + search_request.page_size - 1) // search_request.page_size
        }
    
    async def get_roms_by_system(
        self,
        db: AsyncSession,
        *,
        system_id: UUID,
        status: Optional[ROMStatus] = None
    ) -> List[ROM]:
        """Busca ROMs por sistema.
        
        Args:
            db: Sessão do banco de dados
            system_id: ID do sistema
            status: Status da ROM (opcional)
            
        Returns:
            Lista de ROMs
        """
        conditions = [ROM.system_id == system_id]
        
        if status:
            conditions.append(ROM.status == status)
        
        query = (
            select(ROM)
            .where(and_(*conditions))
            .order_by(ROM.filename)
        )
        
        result = await db.execute(query)
        return result.scalars().all()
    
    async def get_roms_by_game(
        self,
        db: AsyncSession,
        *,
        game_id: UUID
    ) -> List[ROM]:
        """Busca ROMs por jogo.
        
        Args:
            db: Sessão do banco de dados
            game_id: ID do jogo
            
        Returns:
            Lista de ROMs
        """
        query = (
            select(ROM)
            .where(ROM.game_id == game_id)
            .order_by(ROM.filename)
        )
        
        result = await db.execute(query)
        return result.scalars().all()
    
    async def update_rom_hashes(
        self,
        db: AsyncSession,
        *,
        rom_id: UUID,
        hash_update: ROMHashUpdate
    ) -> ROM:
        """Atualiza hashes da ROM.
        
        Args:
            db: Sessão do banco de dados
            rom_id: ID da ROM
            hash_update: Dados dos hashes
            
        Returns:
            ROM atualizada
            
        Raises:
            HTTPException: Se ROM não encontrada
        """
        rom = await self.get(db, rom_id)
        if not rom:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="ROM não encontrada"
            )
        
        # Atualiza hashes
        update_data = hash_update.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(rom, field, value)
        
        await db.commit()
        await db.refresh(rom)
        
        return rom
    
    async def verify_rom(
        self,
        db: AsyncSession,
        *,
        rom_id: UUID,
        verify_request: ROMVerifyRequest
    ) -> ROM:
        """Verifica integridade da ROM.
        
        Args:
            db: Sessão do banco de dados
            rom_id: ID da ROM
            verify_request: Parâmetros de verificação
            
        Returns:
            ROM verificada
            
        Raises:
            HTTPException: Se ROM não encontrada
        """
        rom = await self.get(db, rom_id)
        if not rom:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="ROM não encontrada"
            )
        
        # Verifica se arquivo existe
        if not os.path.exists(rom.file_path):
            rom.status = ROMStatus.MISSING
            await db.commit()
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Arquivo da ROM não encontrado"
            )
        
        # Calcula hashes atuais
        current_hashes = await self._calculate_file_hashes(rom.file_path)
        
        # Compara hashes
        verification_results = {}
        is_valid = True
        
        for hash_type in ["crc32", "md5", "sha1", "sha256"]:
            stored_hash = getattr(rom, f"{hash_type}_hash")
            current_hash = current_hashes.get(f"{hash_type}_hash")
            
            if stored_hash and current_hash:
                matches = stored_hash.lower() == current_hash.lower()
                verification_results[hash_type] = matches
                if not matches:
                    is_valid = False
        
        # Atualiza status
        if is_valid:
            rom.status = ROMStatus.VERIFIED
            rom.is_verified = True
        else:
            rom.status = ROMStatus.INVALID
            rom.is_verified = False
        
        # Atualiza hashes se solicitado
        if verify_request.update_hashes:
            for hash_type, hash_value in current_hashes.items():
                setattr(rom, hash_type, hash_value)
        
        # Cria registro de verificação
        verification_service = ROMVerificationService()
        await verification_service.create_verification(
            db,
            verification_in=ROMVerificationCreate(
                rom_id=rom.id,
                source=verify_request.source,
                verification_type=verify_request.verification_type,
                is_successful=is_valid,
                crc32_match=verification_results.get("crc32"),
                md5_match=verification_results.get("md5"),
                sha1_match=verification_results.get("sha1"),
                sha256_match=verification_results.get("sha256"),
                notes=f"Verificação {'bem-sucedida' if is_valid else 'falhou'}"
            )
        )
        
        await db.commit()
        await db.refresh(rom)
        
        return rom
    
    async def bulk_operation(
        self,
        db: AsyncSession,
        *,
        operation: ROMBulkOperation
    ) -> Dict[str, Any]:
        """Executa operação em lote.
        
        Args:
            db: Sessão do banco de dados
            operation: Operação em lote
            
        Returns:
            Resultado da operação
        """
        results = {
            "success_count": 0,
            "error_count": 0,
            "errors": []
        }
        
        for rom_id in operation.rom_ids:
            try:
                if operation.operation == "verify":
                    await self.verify_rom(
                        db,
                        rom_id=rom_id,
                        verify_request=ROMVerifyRequest(
                            source=VerificationSource.MANUAL,
                            update_hashes=True
                        )
                    )
                elif operation.operation == "delete":
                    await self.remove(db, rom_id)
                elif operation.operation == "update_status":
                    rom = await self.get(db, rom_id)
                    if rom and operation.data and "status" in operation.data:
                        rom.status = ROMStatus(operation.data["status"])
                        await db.commit()
                    
                results["success_count"] += 1
                
            except Exception as e:
                logger.error(f"Bulk operation failed for ROM {rom_id}: {str(e)}")
                results["error_count"] += 1
                results["errors"].append({
                    "rom_id": str(rom_id),
                    "error": str(e)
                })
        
        return results
    
    async def import_roms(
        self,
        db: AsyncSession,
        *,
        import_request: ROMImportRequest
    ) -> Dict[str, Any]:
        """Importa ROMs de um diretório.
        
        Args:
            db: Sessão do banco de dados
            import_request: Parâmetros de importação
            
        Returns:
            Resultado da importação
        """
        results = {
            "imported_count": 0,
            "skipped_count": 0,
            "error_count": 0,
            "errors": []
        }
        
        source_path = Path(import_request.source_path)
        if not source_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Diretório de origem não encontrado"
            )
        
        # Extensões suportadas
        supported_extensions = {".zip", ".rar", ".7z", ".rom", ".bin", ".iso", ".img"}
        
        # Busca arquivos
        for file_path in source_path.rglob("*"):
            if file_path.is_file() and file_path.suffix.lower() in supported_extensions:
                try:
                    # Verifica se ROM já existe
                    existing_rom = await self.get_by_file_path(db, file_path=str(file_path))
                    if existing_rom:
                        results["skipped_count"] += 1
                        continue
                    
                    # Detecta sistema baseado no diretório ou extensão
                    system_id = await self._detect_system(db, file_path)
                    if not system_id:
                        results["skipped_count"] += 1
                        continue
                    
                    # Cria ROM
                    rom_data = {
                        "filename": file_path.name,
                        "file_path": str(file_path),
                        "file_size": file_path.stat().st_size,
                        "extension": file_path.suffix.lower(),
                        "system_id": system_id,
                        "import_source": import_request.source_path,
                        "auto_verify": import_request.auto_verify,
                        "auto_extract": import_request.auto_extract
                    }
                    
                    rom_create = ROMCreate(**rom_data)
                    await self.create_rom(db, rom_in=rom_create)
                    
                    results["imported_count"] += 1
                    
                except Exception as e:
                    logger.error(f"Import failed for file {file_path}: {str(e)}")
                    results["error_count"] += 1
                    results["errors"].append({
                        "file": str(file_path),
                        "error": str(e)
                    })
        
        return results
    
    async def _calculate_file_hashes(self, file_path: str) -> Dict[str, str]:
        """Calcula hashes do arquivo.
        
        Args:
            file_path: Caminho do arquivo
            
        Returns:
            Dicionário com hashes
        """
        hashes = {
            "crc32_hash": "",
            "md5_hash": "",
            "sha1_hash": "",
            "sha256_hash": ""
        }
        
        try:
            import zlib
            
            crc32 = 0
            md5_hash = hashlib.md5()
            sha1_hash = hashlib.sha1()
            sha256_hash = hashlib.sha256()
            
            with open(file_path, "rb") as f:
                while chunk := f.read(8192):
                    crc32 = zlib.crc32(chunk, crc32)
                    md5_hash.update(chunk)
                    sha1_hash.update(chunk)
                    sha256_hash.update(chunk)
            
            hashes["crc32_hash"] = f"{crc32 & 0xffffffff:08x}"
            hashes["md5_hash"] = md5_hash.hexdigest()
            hashes["sha1_hash"] = sha1_hash.hexdigest()
            hashes["sha256_hash"] = sha256_hash.hexdigest()
            
        except Exception as e:
            logger.error(f"Failed to calculate hashes for {file_path}: {str(e)}")
            pass
        
        return hashes
    
    async def _auto_verify_rom(self, db: AsyncSession, rom: ROM) -> None:
        """Verifica ROM automaticamente.
        
        Args:
            db: Sessão do banco de dados
            rom: ROM para verificar
        """
        # TODO: Implementar verificação automática contra DAT files
        pass
    
    async def _auto_extract_rom(self, rom: ROM) -> None:
        """Extrai ROM automaticamente se comprimida.
        
        Args:
            rom: ROM para extrair
        """
        # TODO: Implementar extração automática
        pass
    
    async def _detect_system(self, db: AsyncSession, file_path: Path) -> Optional[UUID]:
        """Detecta sistema baseado no arquivo.
        
        Args:
            db: Sessão do banco de dados
            file_path: Caminho do arquivo
            
        Returns:
            ID do sistema ou None
        """
        # TODO: Implementar detecção de sistema
        # Por enquanto retorna None
        return None
    
    def _apply_filters(self, query: Select, filters: ROMFilterParams) -> Select:
        """Aplica filtros à query.
        
        Args:
            query: Query base
            filters: Filtros
            
        Returns:
            Query com filtros
        """
        conditions = []
        
        if filters.system_id:
            conditions.append(ROM.system_id == filters.system_id)
        
        if filters.game_id:
            conditions.append(ROM.game_id == filters.game_id)
        
        if filters.status:
            conditions.append(ROM.status == filters.status)
        
        if filters.compression_type:
            conditions.append(ROM.compression_type == filters.compression_type)
        
        if filters.is_verified is not None:
            conditions.append(ROM.is_verified == filters.is_verified)
        
        if filters.region:
            conditions.append(ROM.region == filters.region)
        
        if filters.version:
            conditions.append(ROM.version.ilike(f"%{filters.version}%"))
        
        if filters.file_size_min:
            conditions.append(ROM.file_size >= filters.file_size_min)
        
        if filters.file_size_max:
            conditions.append(ROM.file_size <= filters.file_size_max)
        
        if filters.extension:
            conditions.append(ROM.extension == filters.extension)
        
        if conditions:
            query = query.where(and_(*conditions))
        
        return query
    
    def _apply_sorting(self, query: Select, sort_by: str, sort_order: str) -> Select:
        """Aplica ordenação à query.
        
        Args:
            query: Query base
            sort_by: Campo de ordenação
            sort_order: Ordem (asc/desc)
            
        Returns:
            Query com ordenação
        """
        order_field = getattr(ROM, sort_by, ROM.filename)
        
        if sort_order == "desc":
            order_field = order_field.desc()
        
        return query.order_by(order_field)
    
    def _add_relationship_loading(self, query: Select) -> Select:
        """Adiciona carregamento de relacionamentos.
        
        Args:
            query: Query base
            
        Returns:
            Query com relacionamentos
        """
        return query.options(
            selectinload(ROM.game),
            selectinload(ROM.system),
            selectinload(ROM.files),
            selectinload(ROM.verifications)
        )


class ROMFileService(BaseService[ROMFile, ROMFileCreate, ROMFileUpdate]):
    """Serviço para operações com arquivos de ROM."""
    
    def __init__(self):
        super().__init__(ROMFile)
    
    async def create_file(
        self,
        db: AsyncSession,
        *,
        file_in: ROMFileCreate
    ) -> ROMFile:
        """Cria um novo arquivo de ROM.
        
        Args:
            db: Sessão do banco de dados
            file_in: Dados do arquivo
            
        Returns:
            Arquivo criado
        """
        return await self.create(db, obj_in=file_in)
    
    async def get_by_rom(
        self,
        db: AsyncSession,
        *,
        rom_id: UUID
    ) -> List[ROMFile]:
        """Busca arquivos por ROM.
        
        Args:
            db: Sessão do banco de dados
            rom_id: ID da ROM
            
        Returns:
            Lista de arquivos
        """
        query = (
            select(ROMFile)
            .where(ROMFile.rom_id == rom_id)
            .order_by(ROMFile.filename)
        )
        
        result = await db.execute(query)
        return result.scalars().all()
    
    def _add_relationship_loading(self, query: Select) -> Select:
        """Adiciona carregamento de relacionamentos.
        
        Args:
            query: Query base
            
        Returns:
            Query com relacionamentos
        """
        return query.options(selectinload(ROMFile.rom))


class ROMVerificationService(BaseService[ROMVerification, ROMVerificationCreate, None]):
    """Serviço para operações com verificações de ROM."""
    
    def __init__(self):
        super().__init__(ROMVerification)
    
    async def create_verification(
        self,
        db: AsyncSession,
        *,
        verification_in: ROMVerificationCreate
    ) -> ROMVerification:
        """Cria uma nova verificação.
        
        Args:
            db: Sessão do banco de dados
            verification_in: Dados da verificação
            
        Returns:
            Verificação criada
        """
        return await self.create(db, obj_in=verification_in)
    
    async def get_by_rom(
        self,
        db: AsyncSession,
        *,
        rom_id: UUID,
        limit: Optional[int] = None
    ) -> List[ROMVerification]:
        """Busca verificações por ROM.
        
        Args:
            db: Sessão do banco de dados
            rom_id: ID da ROM
            limit: Limite de resultados
            
        Returns:
            Lista de verificações
        """
        query = (
            select(ROMVerification)
            .where(ROMVerification.rom_id == rom_id)
            .order_by(ROMVerification.created_at.desc())
        )
        
        if limit:
            query = query.limit(limit)
        
        result = await db.execute(query)
        return result.scalars().all()
    
    async def get_latest_verification(
        self,
        db: AsyncSession,
        *,
        rom_id: UUID
    ) -> Optional[ROMVerification]:
        """Busca verificação mais recente da ROM.
        
        Args:
            db: Sessão do banco de dados
            rom_id: ID da ROM
            
        Returns:
            Verificação mais recente ou None
        """
        query = (
            select(ROMVerification)
            .where(ROMVerification.rom_id == rom_id)
            .order_by(ROMVerification.created_at.desc())
            .limit(1)
        )
        
        result = await db.execute(query)
        return result.scalar_one_or_none()
    
    def _add_relationship_loading(self, query: Select) -> Select:
        """Adiciona carregamento de relacionamentos.
        
        Args:
            query: Query base
            
        Returns:
            Query com relacionamentos
        """
        return query.options(selectinload(ROMVerification.rom))