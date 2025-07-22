"""Serviços de processamento para importação, verificação e metadados.

Este módulo implementa a lógica de negócio para operações de processamento
como importação de ROMs, verificação de integridade, manipulação de arquivos
e coleta de metadados.
"""

import asyncio
import hashlib
import os
import zipfile
import rarfile
import py7zr
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple, Set
from app.core.redis import get_cache, set_cache
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.rom import ROM, ROMFile, ROMVerification, ROMStatus, CompressionType, VerificationType
from app.models.game import Game
from app.models.system import System
from app.models.task import Task, TaskType, TaskStatus
from app.schemas.rom import ROMCreate, ROMImportRequest
from app.schemas.task import TaskCreate
from app.services.base import BaseService
from app.services.rom import ROMService
from app.services.task import TaskService
from app.core.config import settings
from app.utils.file_utils import (
    calculate_file_hash,
    get_file_size,
    is_archive_file,
    extract_archive,
    get_file_extension,
    normalize_path
)

import json
import gzip
from prometheus_client import Counter


class ImportService:
    """Serviço para importação de ROMs e dados."""
    
    def __init__(
        self,
        rom_service: ROMService,
        task_service: TaskService
    ):
        self.rom_service = rom_service
        self.task_service = task_service
        self.supported_extensions = {
            '.zip', '.rar', '.7z', '.gz', '.tar',
            '.nes', '.smc', '.sfc', '.gb', '.gbc', '.gba',
            '.md', '.gen', '.sms', '.gg', '.pce', '.tg16',
            '.n64', '.z64', '.v64', '.ndd', '.iso', '.cue',
            '.bin', '.img', '.rom', '.a26', '.a52', '.a78'
        }
    
    async def import_roms_from_directory(
        self,
        db: AsyncSession,
        *,
        import_request: ROMImportRequest,
        user_id: UUID
    ) -> Task:
        """Importa ROMs de um diretório.
        
        Args:
            db: Sessão do banco de dados
            import_request: Parâmetros de importação
            user_id: ID do usuário
            
        Returns:
            Tarefa de importação criada
        """
        # Valida diretório
        source_path = Path(import_request.source_path)
        if not source_path.exists() or not source_path.is_dir():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Diretório de origem não encontrado"
            )
        
        # Cria tarefa de importação
        task_data = TaskCreate(
            name=f"Importação de ROMs - {source_path.name}",
            description=f"Importando ROMs do diretório: {source_path}",
            task_type=TaskType.ROM_IMPORT,
            user_id=user_id,
            parameters={
                "source_path": str(source_path),
                "recursive": import_request.recursive,
                "auto_verify": import_request.auto_verify,
                "auto_extract": import_request.auto_extract,
                "system_id": str(import_request.system_id) if import_request.system_id else None,
                "overwrite_existing": import_request.overwrite_existing
            }
        )
        
        task = await self.task_service.create_task(db, task_in=task_data)
        
        # Registra handler se não estiver registrado
        if TaskType.ROM_IMPORT not in self.task_service._task_handlers:
            self.task_service.register_task_handler(
                TaskType.ROM_IMPORT,
                self._handle_rom_import
            )
        
        return task
    
    async def import_dat_file(
        self,
        db: AsyncSession,
        *,
        dat_file_path: str,
        system_id: UUID,
        user_id: UUID
    ) -> Task:
        """Importa arquivo DAT/XML.
        
        Args:
            db: Sessão do banco de dados
            dat_file_path: Caminho do arquivo DAT
            system_id: ID do sistema
            user_id: ID do usuário
            
        Returns:
            Tarefa de importação criada
        """
        # Valida arquivo
        dat_path = Path(dat_file_path)
        if not dat_path.exists() or not dat_path.is_file():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Arquivo DAT não encontrado"
            )
        
        # Cria tarefa de importação
        task_data = TaskCreate(
            name=f"Importação DAT - {dat_path.name}",
            description=f"Importando dados do arquivo DAT: {dat_path}",
            task_type=TaskType.DAT_IMPORT,
            user_id=user_id,
            parameters={
                "dat_file_path": str(dat_path),
                "system_id": str(system_id)
            }
        )
        
        task = await self.task_service.create_task(db, task_in=task_data)
        
        # Registra handler se não estiver registrado
        if TaskType.DAT_IMPORT not in self.task_service._task_handlers:
            self.task_service.register_task_handler(
                TaskType.DAT_IMPORT,
                self._handle_dat_import
            )
        
        return task
    
    async def _handle_rom_import(
        self,
        db: AsyncSession,
        task: Task
    ) -> None:
        """Handler para importação de ROMs.
        
        Args:
            db: Sessão do banco de dados
            task: Tarefa de importação
        """
        params = task.parameters
        source_path = Path(params["source_path"])
        recursive = params.get("recursive", True)
        auto_verify = params.get("auto_verify", True)
        auto_extract = params.get("auto_extract", False)
        system_id = UUID(params["system_id"]) if params.get("system_id") else None
        overwrite_existing = params.get("overwrite_existing", False)
        
        try:
            # Encontra arquivos ROM
            rom_files = await self._find_rom_files(source_path, recursive)
            total_files = len(rom_files)
            
            if total_files == 0:
                task.status_message = "Nenhum arquivo ROM encontrado"
                return
            
            task.total_steps = total_files
            task.status_message = f"Importando {total_files} arquivos"
            await db.commit()
            
            imported_count = 0
            skipped_count = 0
            error_count = 0
            batch_size = 50  # Tamanho do lote para processamento incremental
            
            for batch_start in range(0, total_files, batch_size):
                batch = rom_files[batch_start:batch_start + batch_size]
                batch_tasks = []
                
                for file_path in batch:
                    batch_tasks.append(self._process_single_rom(db, file_path, overwrite_existing, system_id, auto_verify, auto_extract))
                
                results = await asyncio.gather(*batch_tasks, return_exceptions=True)
                
                for result in results:
                    if isinstance(result, Exception):
                        error_count += 1
                        print(f"Erro ao processar ROM: {result}")
                    elif result == 'skipped':
                        skipped_count += 1
                    elif result == 'imported':
                        imported_count += 1
                
                # Atualiza progresso por lote
                current_progress = int(((batch_start + len(batch)) / total_files) * 100)
                task.progress = min(current_progress, 100)
                task.status_message = f"Processando lote {batch_start // batch_size + 1} de {total_files // batch_size + 1}"
                await db.commit()
            
                async def _process_single_rom(self, db: AsyncSession, file_path: Path, overwrite_existing: bool, system_id: Optional[UUID], auto_verify: bool, auto_extract: bool) -> str:
        try:
            existing_rom = await self._check_existing_rom(db, file_path)
            if existing_rom and not overwrite_existing:
                return 'skipped'
            
            rom_data = await self._create_rom_data(file_path, system_id, auto_verify, auto_extract)
            
            if existing_rom and overwrite_existing:
                await self.rom_service.update(db, db_obj=existing_rom, obj_in=rom_data)
            else:
                await self.rom_service.create(db, obj_in=rom_data)
            
            return 'imported'
        except Exception as e:
            raise e

            # Finaliza tarefa
            task.progress = 100
            task.status_message = (
                f"Importação concluída: {imported_count} importados, "
                f"{skipped_count} ignorados, {error_count} erros"
            )
            
        except Exception as e:
            task.status = TaskStatus.FAILED
            task.error_message = str(e)
    
    async def _handle_dat_import(
        self,
        db: AsyncSession,
        task: Task
    ) -> None:
        """Handler para importação de DAT.
        
        Args:
            db: Sessão do banco de dados
            task: Tarefa de importação
        """
        params = task.parameters
        dat_file_path = Path(params["dat_file_path"])
        system_id = UUID(params["system_id"])
        
        try:
            # Parse do arquivo DAT
            dat_data = await self._parse_dat_file(dat_file_path)
            games = dat_data.get("games", [])
            total_games = len(games)
            
            if total_games == 0:
                task.status_message = "Nenhum jogo encontrado no arquivo DAT"
                return
            
            task.total_steps = total_games
            task.status_message = f"Importando {total_games} jogos"
            await db.commit()
            
            imported_count = 0
            progress_counter = 0
            
            async def import_single_game(game_data):
                nonlocal imported_count, progress_counter
                try:
                    async with AsyncSessionLocal() as session:  # Assumindo AsyncSessionLocal como factory de sessão
                        await self._import_game_from_dat(session, game_data, system_id)
                        await session.commit()
                    imported_count += 1
                except Exception as e:
                    print(f"Erro ao importar jogo {game_data.get('name', 'Unknown')}: {e}")
                finally:
                    progress_counter += 1
                    task.progress = int((progress_counter / total_games) * 100)
                    task.current_step = progress_counter
                    task.status_message = f"Processando jogo {progress_counter}/{total_games}"
                    await db.commit()
            
            import_tasks = [import_single_game(game) for game in games]
            await asyncio.gather(*import_tasks)
            
            # Finaliza tarefa
            task.progress = 100
            task.status_message = f"Importação DAT concluída: {imported_count} jogos importados"
            
        except Exception as e:
            task.status = TaskStatus.FAILED
            task.error_message = str(e)
            raise
    
    async def _find_rom_files(
        self,
        directory: Path,
        recursive: bool = True
    ) -> List[Path]:
        """Encontra arquivos ROM em um diretório.
        
        Args:
            directory: Diretório para buscar
            recursive: Se deve buscar recursivamente
            
        Returns:
            Lista de caminhos de arquivos ROM
        """
        rom_files = []
        
        if recursive:
            pattern = "**/*"
        else:
            pattern = "*"
        
        for file_path in directory.glob(pattern):
            if file_path.is_file() and file_path.suffix.lower() in self.supported_extensions:
                rom_files.append(file_path)
        
        return sorted(rom_files)
    
    async def _check_existing_rom(
        self,
        db: AsyncSession,
        file_path: Path
    ) -> Optional[ROM]:
        """Verifica se ROM já existe no banco.
        
        Args:
            db: Sessão do banco de dados
            file_path: Caminho do arquivo
            
        Returns:
            ROM existente ou None
        """
        # Busca por caminho do arquivo
        query = select(ROM).where(ROM.file_path == str(file_path))
        result = await db.execute(query)
        existing_rom = result.scalar_one_or_none()
        
        if existing_rom:
            return existing_rom
        
        # Busca por nome do arquivo
        query = select(ROM).where(ROM.filename == file_path.name)
        result = await db.execute(query)
        return result.scalar_one_or_none()
    
    async def _create_rom_data(
        self,
        file_path: Path,
        system_id: Optional[UUID],
        auto_verify: bool,
        auto_extract: bool
    ) -> ROMCreate:
        """Cria dados da ROM a partir do arquivo.
        
        Args:
            file_path: Caminho do arquivo
            system_id: ID do sistema
            auto_verify: Se deve verificar automaticamente
            auto_extract: Se deve extrair automaticamente
            
        Returns:
            Dados da ROM
        """
        # Informações básicas do arquivo
        file_size = get_file_size(file_path)
        extension = get_file_extension(file_path)
        
        # Calcula hashes de forma incremental
        crc32 = await self._calculate_hash_incremental(file_path, "crc32")
        md5 = await self._calculate_hash_incremental(file_path, "md5")
        sha1 = await self._calculate_hash_incremental(file_path, "sha1")
        
        # Detecta compressão
        compression_type = self._detect_compression_type(file_path)
        compressed_size = None
        uncompressed_size = file_size
        
        if compression_type == CompressionType.NONE:
            # Comprime automaticamente se não estiver comprimido
            compressed_path = file_path.with_suffix('.zip')
            await compress_file(file_path, compressed_path, 'zip')
            file_path = compressed_path
            compressed_size = get_file_size(compressed_path)
            compression_type = CompressionType.ZIP
        else:
            compressed_size = file_size
            try:
                uncompressed_size = await self._calculate_uncompressed_size(file_path, compression_type)
            except Exception as e:
                uncompressed_size = None

        # Detecta sistema se não fornecido
        if not system_id:
            system_id = await self._detect_system_from_file(file_path)
        
        return ROMCreate(
            filename=file_path.name,
            file_path=str(file_path),
            file_size=file_size,
            extension=extension,
            crc32=crc32,
            md5=md5,
            sha1=sha1,
            status=ROMStatus.UNVERIFIED,
            compression_type=compression_type,
            compressed_size=compressed_size,
            uncompressed_size=uncompressed_size,
            system_id=system_id,
            auto_verify=auto_verify,
            auto_extract=auto_extract,
            import_source="directory_scan"
        )
    
    def _detect_compression_type(self, file_path: Path) -> CompressionType:
        """Detecta tipo de compressão do arquivo.
        
        Args:
            file_path: Caminho do arquivo
            
        Returns:
            Tipo de compressão
        """
        extension = file_path.suffix.lower()
        
        if extension == '.zip':
            return CompressionType.ZIP
        elif extension == '.rar':
            return CompressionType.RAR
        elif extension == '.7z':
            return CompressionType.SEVEN_ZIP
        elif extension in ['.gz', '.tar']:
            return CompressionType.GZIP
        else:
            return CompressionType.UNKNOWN
    
    async def _detect_system_from_file(self, file_path: Path) -> Optional[UUID]:
        """Detecta sistema a partir do arquivo.
        
        Args:
            file_path: Caminho do arquivo
            
        Returns:
            ID do sistema detectado ou None
        """
        extension = file_path.suffix.lower()
        system_map = {
            '.nes': UUID('system_id_for_nes'),  # Substitua por IDs reais
            '.smc': UUID('system_id_for_snes'),
            # Adicione mais mapeamentos conforme necessário
        }
        detected_id = system_map.get(extension)
        if detected_id:
            print(f"[LOG] Sistema detectado para {file_path}: {detected_id}")
            return detected_id
        else:
            print(f"[WARNING] Nenhum sistema detectado para {file_path}")
            return None
    
    async def _parse_dat_file(self, dat_path: Path) -> List[Dict[str, Any]]:
        current_mtime = os.path.getmtime(dat_path)
        cache_key = str(dat_path)
        cache_dir = Path('.cache')
        cache_dir.mkdir(exist_ok=True)
        cache_file = cache_dir / f"{hashlib.md5(cache_key.encode()).hexdigest()}.json.gz"
        
        # Check Redis cache with TTL invalidation
        cached = await get_cache(cache_key)
        if cached and cached['mtime'] == current_mtime and (datetime.utcnow() - datetime.fromisoformat(cached['cached_at'])).total_seconds() <= 86400:
            if 'dependencies' in cached and await self._check_dependencies(cached['dependencies']):
                CACHE_HITS.labels('redis').inc()
                return cached['data']
        CACHE_MISSES.labels('redis').inc()
        
        # Check memory cache with TTL and dependency invalidation
    if cache_key in self.dat_cache:
        cached = self.dat_cache[cache_key]
        if cached['mtime'] == current_mtime and (datetime.utcnow() - datetime.fromisoformat(cached['cached_at'])).total_seconds() <= 86400:
            if 'dependencies' in cached and await self._check_dependencies(cached['dependencies']):
                CACHE_HITS.labels('memory').inc()
                return cached['data']
    CACHE_MISSES.labels('memory').inc()
    
    # Check disk cache with TTL and dependency invalidation
    if cache_file.exists():
        with gzip.open(cache_file, 'rt', encoding='utf-8') as f:
            cached = json.load(f)
        if cached['mtime'] == current_mtime and (datetime.utcnow() - datetime.fromisoformat(cached['cached_at'])).total_seconds() <= 86400:
            if 'dependencies' in cached and await self._check_dependencies(cached['dependencies']):
                self.dat_cache[cache_key] = cached
                CACHE_HITS.labels('disk').inc()
                return cached['data']
    CACHE_MISSES.labels('disk').inc()
        # Parse
        roms_data = []
        context = ET.iterparse(str(dat_path), events=('end',))
        for event, elem in context:
            if elem.tag == 'game':
                rom_data = {
                    'name': elem.get('name'),
                    'description': elem.find('description').text if elem.find('description') is not None else None,
                    'year': elem.find('year').text if elem.find('year') is not None else None,
                    # Add other fields as needed
                }
                roms_data.append(rom_data)
                elem.clear()
        cached_data = {
        'data': roms_data,
        'mtime': current_mtime,
        'cached_at': datetime.utcnow().isoformat(),
        'dependencies': self._get_current_dependencies()  # Assumindo que há um método para obter dependências
    }
        # Save to Redis
        await set_cache(cache_key, cached_data, ttl=86400)
        # Save to disk
        with gzip.open(cache_file, 'wt', encoding='utf-8') as f:
            json.dump(cached_data, f)
        # Save to memory
        self.dat_cache[cache_key] = cached_data
        return roms_data
    
    async def _import_game_from_dat(
        self,
        db: AsyncSession,
        game_data: Dict[str, Any],
        system_id: UUID
    ) -> None:
        """Importa jogo a partir de dados DAT.
        
        Args:
            db: Sessão do banco de dados
            game_data: Dados do jogo do DAT
            system_id: ID do sistema
        """
        try:
            # Verifique se jogo existe
            existing_game = await db.execute(select(Game).where(Game.name == game_data['name']))
            if existing_game.scalar_one_or_none():
                print(f"[WARNING] Jogo {game_data['name']} já existe, ignorando")
                return
            new_game = Game(name=game_data['name'], system_id=system_id)
            db.add(new_game)
            await db.commit()
            print(f"[LOG] Jogo importado de DAT: {game_data['name']}")
        except Exception as e:
            print(f"[ERROR] Falha ao importar jogo de DAT: {str(e)}")
            await db.rollback()


class VerificationService:
    """Serviço para verificação de integridade de ROMs."""
    
    def __init__(self, rom_service: ROMService, task_service: TaskService):
        self.rom_service = rom_service
        self.task_service = task_service
    
    async def verify_rom(
        self,
        db: AsyncSession,
        *,
        rom_id: UUID,
        verification_type: VerificationType = VerificationType.HASH_CHECK
    ) -> ROMVerification:
        """Verifica integridade de uma ROM.
        
        Args:
            db: Sessão do banco de dados
            rom_id: ID da ROM
            verification_type: Tipo de verificação
            
        Returns:
            Resultado da verificação
            
        Raises:
            HTTPException: Se ROM não encontrada
        """
        rom = await self.rom_service.get(db, rom_id)
        if not rom:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="ROM não encontrada"
            )
        
        # Executa verificação
        verification_result = await self._perform_verification(rom, verification_type)
        
        # Salva resultado
        verification = ROMVerification(
            rom_id=rom_id,
            verification_type=verification_type,
            **verification_result
        )
        
        db.add(verification)
        
        # Atualiza status da ROM
        if verification_result["success"]:
            rom.status = ROMStatus.VERIFIED
        else:
            rom.status = ROMStatus.INVALID
        
        await db.commit()
        await db.refresh(verification)
        
        return verification
    
    async def verify_roms_batch(
        self,
        db: AsyncSession,
        *,
        rom_ids: List[UUID],
        user_id: UUID
    ) -> Task:
        """Verifica múltiplas ROMs em lote."""
        
        task_data = TaskCreate(
            name=f"Verificação em lote - {len(rom_ids)} ROMs",
            description=f"Verificando integridade de {len(rom_ids)} ROMs",
            task_type=TaskType.ROM_VERIFICATION,
            user_id=user_id,
            parameters={
                "rom_ids": [str(rom_id) for rom_id in rom_ids]
            }
        )
        
        task = await self.task_service.create_task(db, task_in=task_data)
        
        if TaskType.ROM_VERIFICATION not in self.task_service._task_handlers:
            self.task_service.register_task_handler(
                TaskType.ROM_VERIFICATION,
                self._handle_rom_verification
            )
        
        return task
    
    async def _handle_rom_verification(
        self,
        db: AsyncSession,
        task: Task
    ) -> None:
        params = task.parameters
        rom_ids = [UUID(id_str) for id_str in params["rom_ids"]]
        total = len(rom_ids)
        task.total_steps = total
        await db.commit()
        
        success_count = 0
        failure_count = 0
        
        for i, rom_id in enumerate(rom_ids):
            try:
                verification = await self.verify_rom(db, rom_id=rom_id)
                if verification.success:
                    success_count += 1
                else:
                    failure_count += 1
            except Exception as e:
                failure_count += 1
                print(f"Erro ao verificar ROM {rom_id}: {str(e)}")
            
            task.current_step = i + 1
            task.progress = int((task.current_step / total) * 100)
            task.status_message = f"Verificado {task.current_step}/{total}"
            await db.commit()
        
        task.status_message = f"Verificação concluída: {success_count} sucessos, {failure_count} falhas"
        await db.commit()
    
    async def _perform_verification(
        self,
        rom: ROM,
        verification_type: VerificationType
    ) -> Dict[str, Any]:
        """Executa verificação da ROM.
        
        Args:
            rom: ROM para verificar
            verification_type: Tipo de verificação
            
        Returns:
            Resultado da verificação
        """
        file_path = Path(rom.file_path)
        
        if not file_path.exists():
            return {
                "success": False,
                "error_message": "Arquivo não encontrado",
                "verified_at": datetime.utcnow()
            }
        
        try:
            if verification_type == VerificationType.HASH_COMPARISON:
                return await self._verify_by_hash(rom, file_path)
            elif verification_type == VerificationType.FILE_SIZE:
                return await self._verify_by_size(rom, file_path)
            elif verification_type == VerificationType.CHECKSUM:
                return await self._verify_by_checksum(rom, file_path)
            else:
                return {
                    "success": False,
                    "error_message": "Tipo de verificação não suportado",
                    "verified_at": datetime.utcnow()
                }
        
        except Exception as e:
            return {
                "success": False,
                "error_message": str(e),
                "verified_at": datetime.utcnow()
            }
    
    async def _verify_by_hash(
        self,
        rom: ROM,
        file_path: Path
    ) -> Dict[str, Any]:
        """Verifica ROM por hash.
        
        Args:
            rom: ROM para verificar
            file_path: Caminho do arquivo
            
        Returns:
            Resultado da verificação
        """
        # Calcula hashes atuais
        current_crc32 = await calculate_file_hash(file_path, "crc32")
        current_md5 = await calculate_file_hash(file_path, "md5")
        current_sha1 = await calculate_file_hash(file_path, "sha1")
        
        # Compara com hashes armazenados
        hash_matches = {
            "crc32_match": rom.crc32 == current_crc32 if rom.crc32 else None,
            "md5_match": rom.md5 == current_md5 if rom.md5 else None,
            "sha1_match": rom.sha1 == current_sha1 if rom.sha1 else None
        }
        
        # Verifica se pelo menos um hash confere
        success = any(match for match in hash_matches.values() if match is not None)
        
        return {
            "success": success,
            "hash_matches": hash_matches,
            "current_hashes": {
                "crc32": current_crc32,
                "md5": current_md5,
                "sha1": current_sha1
            },
            "verified_at": datetime.utcnow()
        }
    
    async def _verify_by_size(
        self,
        rom: ROM,
        file_path: Path
    ) -> Dict[str, Any]:
        """Verifica ROM por tamanho.
        
        Args:
            rom: ROM para verificar
            file_path: Caminho do arquivo
            
        Returns:
            Resultado da verificação
        """
        current_size = get_file_size(file_path)
        success = rom.file_size == current_size
        
        return {
            "success": success,
            "size_match": success,
            "current_size": current_size,
            "expected_size": rom.file_size,
            "verified_at": datetime.utcnow()
        }
    
    async def _verify_by_checksum(
        self,
        rom: ROM,
        file_path: Path
    ) -> Dict[str, Any]:
        """Verifica ROM por checksum.
        
        Args:
            rom: ROM para verificar
            file_path: Caminho do arquivo
            
        Returns:
            Resultado da verificação
        """
        system_checksum = 'expected_checksum'  # Obtenha do sistema ou config
        current_checksum = await calculate_file_hash(file_path, 'sha256')  # Exemplo
        success = current_checksum == system_checksum
        return {
            "success": success,
            "checksum_match": success,
            "current_checksum": current_checksum,
            "expected_checksum": system_checksum,
            "verified_at": datetime.utcnow()
        }


class FileService:
    """Serviço para manipulação de arquivos."""
    
    async def extract_archive(
        self,
        archive_path: Path,
        extract_to: Path,
        password: Optional[str] = None
    ) -> List[Path]:
        """Extrai arquivo comprimido.
        
        Args:
            archive_path: Caminho do arquivo
            extract_to: Diretório de destino
            password: Senha do arquivo (opcional)
            
        Returns:
            Lista de arquivos extraídos
        """
        extract_to.mkdir(parents=True, exist_ok=True)
        extracted_files = []
        
        try:
            if archive_path.suffix.lower() == '.zip':
                extracted_files = await self._extract_zip(archive_path, extract_to, password)
            elif archive_path.suffix.lower() == '.rar':
                extracted_files = await self._extract_rar(archive_path, extract_to, password)
            elif archive_path.suffix.lower() == '.7z':
                extracted_files = await self._extract_7z(archive_path, extract_to, password)
            else:
                raise ValueError(f"Formato de arquivo não suportado: {archive_path.suffix}")
        
        except (OSError, ValueError) as e:
            logger.error(f"Erro ao importar ROMs: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))
        
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Erro ao extrair arquivo: {e}"
            )
        
        return extracted_files
    
    async def _extract_zip(
        self,
        zip_path: Path,
        extract_to: Path,
        password: Optional[str] = None
    ) -> List[Path]:
        """Extrai arquivo ZIP.
        
        Args:
            zip_path: Caminho do ZIP
            extract_to: Diretório de destino
            password: Senha do arquivo
            
        Returns:
            Lista de arquivos extraídos
        """
        extracted_files = []
        
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            if password:
                zip_ref.setpassword(password.encode())
            
            for file_info in zip_ref.filelist:
                if not file_info.is_dir():
                    extracted_path = extract_to / file_info.filename
                    extracted_path.parent.mkdir(parents=True, exist_ok=True)
                    
                    with zip_ref.open(file_info) as source, open(extracted_path, 'wb') as target:
                        target.write(source.read())
                    
                    extracted_files.append(extracted_path)
        
        return extracted_files
    
    async def _extract_rar(
        self,
        rar_path: Path,
        extract_to: Path,
        password: Optional[str] = None
    ) -> List[Path]:
        """Extrai arquivo RAR.
        
        Args:
            rar_path: Caminho do RAR
            extract_to: Diretório de destino
            password: Senha do arquivo
            
        Returns:
            Lista de arquivos extraídos
        """
        extracted_files = []
        
        with rarfile.RarFile(rar_path, 'r') as rar_ref:
            if password:
                rar_ref.setpassword(password)
            
            for file_info in rar_ref.infolist():
                if not file_info.is_dir():
                    extracted_path = extract_to / file_info.filename
                    extracted_path.parent.mkdir(parents=True, exist_ok=True)
                    
                    with rar_ref.open(file_info) as source, open(extracted_path, 'wb') as target:
                        target.write(source.read())
                    
                    extracted_files.append(extracted_path)
        
        return extracted_files
    
    async def _extract_7z(
        self,
        seven_z_path: Path,
        extract_to: Path,
        password: Optional[str] = None
    ) -> List[Path]:
        """Extrai arquivo 7Z.
        
        Args:
            seven_z_path: Caminho do 7Z
            extract_to: Diretório de destino
            password: Senha do arquivo
            
        Returns:
            Lista de arquivos extraídos
        """
        extracted_files = []
        
        with py7zr.SevenZipFile(seven_z_path, 'r', password=password) as seven_z_ref:
            for file_info in seven_z_ref.list():
                if not file_info.is_dir:
                    extracted_path = extract_to / file_info.filename
                    extracted_path.parent.mkdir(parents=True, exist_ok=True)
                    
                    seven_z_ref.extract(path=extract_to, targets=[file_info.filename])
                    extracted_files.append(extracted_path)
        
        return extracted_files
    
    async def calculate_directory_size(
        self,
        directory: Path
    ) -> int:
        """Calcula tamanho total de um diretório.
        
        Args:
            directory: Diretório para calcular
            
        Returns:
            Tamanho total em bytes
        """
        total_size = 0
        
        for file_path in directory.rglob('*'):
            if file_path.is_file():
                total_size += file_path.stat().st_size
        
        return total_size
    
    async def clean_temp_files(
        self,
        temp_directory: Path,
        max_age_hours: int = 24
    ) -> int:
        """Limpa arquivos temporários antigos.
        
        Args:
            temp_directory: Diretório temporário
            max_age_hours: Idade máxima em horas
            
        Returns:
            Número de arquivos removidos
        """
        if not temp_directory.exists():
            return 0
        
        max_age_seconds = max_age_hours * 3600
        current_time = datetime.now().timestamp()
        removed_count = 0
        
        for file_path in temp_directory.rglob('*'):
            if file_path.is_file():
                file_age = current_time - file_path.stat().st_mtime
                if file_age > max_age_seconds:
                    try:
                        file_path.unlink()
                        removed_count += 1
                    except OSError:
                        pass  # Ignora erros de remoção
        
        return removed_count


class MetadataService:
    """Serviço para coleta e gerenciamento de metadados."""
    
    def __init__(self):
        self.scrapers = {}
        self.cache = {}
    
    async def collect_game_metadata(
        self,
        game_name: str,
        system_name: str,
        sources: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Coleta metadados de um jogo.
        
        Args:
            game_name: Nome do jogo
            system_name: Nome do sistema
            sources: Fontes de dados (opcional)
            
        Returns:
            Metadados coletados
        """
        if not sources:
            sources = ["gamefaqs", "mobygames", "wikipedia"]
        
        metadata = {
            "title": game_name,
            "system": system_name,
            "sources": {},
            "collected_at": datetime.utcnow().isoformat()
        }
        
        for source in sources:
            try:
                source_data = await self._collect_from_source(source, game_name, system_name)
                metadata["sources"][source] = source_data
            except Exception as e:
                metadata["sources"][source] = {"error": str(e)}
        
        # Consolida dados de múltiplas fontes
        consolidated = await self._consolidate_metadata(metadata)
        
        return consolidated
    
    async def _collect_from_source(
        self,
        source: str,
        game_name: str,
        system_name: str
    ) -> Dict[str, Any]:
        """Coleta dados de uma fonte específica.
        
        Args:
            source: Nome da fonte
            game_name: Nome do jogo
            system_name: Nome do sistema
            
        Returns:
            Dados da fonte
        """
        # Implementação de exemplo para scraper; expanda conforme necessário
        if source == 'wikipedia':
            # Lógica de scraping
            return {"title": game_name, "description": "Exemplo de descrição"}
        else:
            return {
                "title": game_name,
                "system": system_name,
                "source": source,
                "collected_at": datetime.utcnow().isoformat()
            }
    
    async def _consolidate_metadata(
        self,
        metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Consolida metadados de múltiplas fontes.
        
        Args:
            metadata: Metadados de múltiplas fontes
            
        Returns:
            Metadados consolidados
        """
        consolidated = {"title": metadata.get('title')}
        # Lógica de priorização: exemplo simples
        for source in ['gamefaqs', 'mobygames', 'wikipedia']:
            if source in metadata['sources']:
                consolidated.update(metadata['sources'][source])
                break
        print(f"[LOG] Metadados consolidados para {consolidated['title']}")
        return consolidated
    
    def register_scraper(self, source: str, scraper_class) -> None:
        """Registra um scraper para uma fonte.
        
        Args:
            source: Nome da fonte
            scraper_class: Classe do scraper
        """
        self.scrapers[source] = scraper_class
    
    async def clear_cache(self, max_age_hours: int = 24) -> int:
        """Limpa cache de metadados antigos.
        
        Args:
            max_age_hours: Idade máxima em horas
            
        Returns:
            Número de entradas removidas
        """
        max_age_seconds = max_age_hours * 3600
        current_time = datetime.now().timestamp()
        removed = 0
        for key in list(self.cache.keys()):
            if current_time - self.cache[key]['timestamp'] > max_age_seconds:
                del self.cache[key]
                removed += 1
        print(f"[LOG] Cache limpo: {removed} entradas removidas")
        return removed


async def _calculate_hash_incremental(self, file_path: Path, algorithm: str) -> str:
    """Calcula hash de arquivo de forma incremental para arquivos grandes."""
    chunk_size = 8192
    hash_func = hashlib.new(algorithm)
    with open(file_path, 'rb') as f:
        while chunk := f.read(chunk_size):
            hash_func.update(chunk)
    return hash_func.hexdigest()


class VerificationService:
    """Serviço para verificação de integridade de ROMs."""
    
    def __init__(self, rom_service: ROMService, task_service: TaskService):
        self.rom_service = rom_service
        self.task_service = task_service
    
    async def verify_rom(
        self,
        db: AsyncSession,
        *,
        rom_id: UUID,
        verification_type: VerificationType = VerificationType.HASH_CHECK
    ) -> ROMVerification:
        """Verifica integridade de uma ROM.
        
        Args:
            db: Sessão do banco de dados
            rom_id: ID da ROM
            verification_type: Tipo de verificação
            
        Returns:
            Resultado da verificação
            
        Raises:
            HTTPException: Se ROM não encontrada
        """
        rom = await self.rom_service.get(db, rom_id)
        if not rom:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="ROM não encontrada"
            )
        
        # Executa verificação
        verification_result = await self._perform_verification(rom, verification_type)
        
        # Salva resultado
        verification = ROMVerification(
            rom_id=rom_id,
            verification_type=verification_type,
            **verification_result
        )
        
        db.add(verification)
        
        # Atualiza status da ROM
        if verification_result["success"]:
            rom.status = ROMStatus.VERIFIED
        else:
            rom.status = ROMStatus.INVALID
        
        await db.commit()
        await db.refresh(verification)
        
        return verification
    
    async def verify_roms_batch(
        self,
        db: AsyncSession,
        *,
        rom_ids: List[UUID],
        user_id: UUID
    ) -> Task:
        """Verifica múltiplas ROMs em lote."""
        
        task_data = TaskCreate(
            name=f"Verificação em lote - {len(rom_ids)} ROMs",
            description=f"Verificando integridade de {len(rom_ids)} ROMs",
            task_type=TaskType.ROM_VERIFICATION,
            user_id=user_id,
            parameters={
                "rom_ids": [str(rom_id) for rom_id in rom_ids]
            }
        )
        
        task = await self.task_service.create_task(db, task_in=task_data)
        
        if TaskType.ROM_VERIFICATION not in self.task_service._task_handlers:
            self.task_service.register_task_handler(
                TaskType.ROM_VERIFICATION,
                self._handle_rom_verification
            )
        
        return task
    
    async def _handle_rom_verification(
        self,
        db: AsyncSession,
        task: Task
    ) -> None:
        params = task.parameters
        rom_ids = [UUID(id_str) for id_str in params["rom_ids"]]
        total = len(rom_ids)
        task.total_steps = total
        await db.commit()
        
        success_count = 0
        failure_count = 0
        
        for i, rom_id in enumerate(rom_ids):
            try:
                verification = await self.verify_rom(db, rom_id=rom_id)
                if verification.success:
                    success_count += 1
                else:
                    failure_count += 1
            except Exception as e:
                failure_count += 1
                print(f"Erro ao verificar ROM {rom_id}: {str(e)}")
            
            task.current_step = i + 1
            task.progress = int((task.current_step / total) * 100)
            task.status_message = f"Verificado {task.current_step}/{total}"
            await db.commit()
        
        task.status_message = f"Verificação concluída: {success_count} sucessos, {failure_count} falhas"
        await db.commit()
    
    async def _perform_verification(
        self,
        rom: ROM,
        verification_type: VerificationType
    ) -> Dict[str, Any]:
        """Executa verificação da ROM.
        
        Args:
            rom: ROM para verificar
            verification_type: Tipo de verificação
            
        Returns:
            Resultado da verificação
        """
        file_path = Path(rom.file_path)
        
        if not file_path.exists():
            return {
                "success": False,
                "error_message": "Arquivo não encontrado",
                "verified_at": datetime.utcnow()
            }
        
        try:
            if verification_type == VerificationType.HASH_COMPARISON:
                return await self._verify_by_hash(rom, file_path)
            elif verification_type == VerificationType.FILE_SIZE:
                return await self._verify_by_size(rom, file_path)
            elif verification_type == VerificationType.CHECKSUM:
                return await self._verify_by_checksum(rom, file_path)
            else:
                return {
                    "success": False,
                    "error_message": "Tipo de verificação não suportado",
                    "verified_at": datetime.utcnow()
                }
        
        except Exception as e:
            return {
                "success": False,
                "error_message": str(e),
                "verified_at": datetime.utcnow()
            }
    
    async def _verify_by_hash(
        self,
        rom: ROM,
        file_path: Path
    ) -> Dict[str, Any]:
        """Verifica ROM por hash.
        
        Args:
            rom: ROM para verificar
            file_path: Caminho do arquivo
            
        Returns:
            Resultado da verificação
        """
        # Calcula hashes atuais
        current_crc32 = await calculate_file_hash(file_path, "crc32")
        current_md5 = await calculate_file_hash(file_path, "md5")
        current_sha1 = await calculate_file_hash(file_path, "sha1")
        
        # Compara com hashes armazenados
        hash_matches = {
            "crc32_match": rom.crc32 == current_crc32 if rom.crc32 else None,
            "md5_match": rom.md5 == current_md5 if rom.md5 else None,
            "sha1_match": rom.sha1 == current_sha1 if rom.sha1 else None
        }
        
        # Verifica se pelo menos um hash confere
        success = any(match for match in hash_matches.values() if match is not None)
        
        return {
            "success": success,
            "hash_matches": hash_matches,
            "current_hashes": {
                "crc32": current_crc32,
                "md5": current_md5,
                "sha1": current_sha1
            },
            "verified_at": datetime.utcnow()
        }
    
    async def _verify_by_size(
        self,
        rom: ROM,
        file_path: Path
    ) -> Dict[str, Any]:
        """Verifica ROM por tamanho.
        
        Args:
            rom: ROM para verificar
            file_path: Caminho do arquivo
            
        Returns:
            Resultado da verificação
        """
        current_size = get_file_size(file_path)
        success = rom.file_size == current_size
        
        return {
            "success": success,
            "size_match": success,
            "current_size": current_size,
            "expected_size": rom.file_size,
            "verified_at": datetime.utcnow()
        }
    
    async def _verify_by_checksum(
        self,
        rom: ROM,
        file_path: Path
    ) -> Dict[str, Any]:
        """Verifica ROM por checksum.
        
        Args:
            rom: ROM para verificar
            file_path: Caminho do arquivo
            
        Returns:
            Resultado da verificação
        """
        system_checksum = 'expected_checksum'  # Obtenha do sistema ou config
        current_checksum = await calculate_file_hash(file_path, 'sha256')  # Exemplo
        success = current_checksum == system_checksum
        return {
            "success": success,
            "checksum_match": success,
            "current_checksum": current_checksum,
            "expected_checksum": system_checksum,
            "verified_at": datetime.utcnow()
        }


class FileService:
    """Serviço para manipulação de arquivos."""
    
    async def extract_archive(
        self,
        archive_path: Path,
        extract_to: Path,
        password: Optional[str] = None
    ) -> List[Path]:
        """Extrai arquivo comprimido.
        
        Args:
            archive_path: Caminho do arquivo
            extract_to: Diretório de destino
            password: Senha do arquivo (opcional)
            
        Returns:
            Lista de arquivos extraídos
        """
        extract_to.mkdir(parents=True, exist_ok=True)
        extracted_files = []
        
        try:
            if archive_path.suffix.lower() == '.zip':
                extracted_files = await self._extract_zip(archive_path, extract_to, password)
            elif archive_path.suffix.lower() == '.rar':
                extracted_files = await self._extract_rar(archive_path, extract_to, password)
            elif archive_path.suffix.lower() == '.7z':
                extracted_files = await self._extract_7z(archive_path, extract_to, password)
            else:
                raise ValueError(f"Formato de arquivo não suportado: {archive_path.suffix}")
        
        except (OSError, ValueError) as e:
            logger.error(f"Erro ao importar ROMs: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))
        
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Erro ao extrair arquivo: {e}"
            )
        
        return extracted_files
    
    async def _extract_zip(
        self,
        zip_path: Path,
        extract_to: Path,
        password: Optional[str] = None
    ) -> List[Path]:
        """Extrai arquivo ZIP.
        
        Args:
            zip_path: Caminho do ZIP
            extract_to: Diretório de destino
            password: Senha do arquivo
            
        Returns:
            Lista de arquivos extraídos
        """
        extracted_files = []
        
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            if password:
                zip_ref.setpassword(password.encode())
            
            for file_info in zip_ref.filelist:
                if not file_info.is_dir():
                    extracted_path = extract_to / file_info.filename
                    extracted_path.parent.mkdir(parents=True, exist_ok=True)
                    
                    with zip_ref.open(file_info) as source, open(extracted_path, 'wb') as target:
                        target.write(source.read())
                    
                    extracted_files.append(extracted_path)
        
        return extracted_files
    
    async def _extract_rar(
        self,
        rar_path: Path,
        extract_to: Path,
        password: Optional[str] = None
    ) -> List[Path]:
        """Extrai arquivo RAR.
        
        Args:
            rar_path: Caminho do RAR
            extract_to: Diretório de destino
            password: Senha do arquivo
            
        Returns:
            Lista de arquivos extraídos
        """
        extracted_files = []
        
        with rarfile.RarFile(rar_path, 'r') as rar_ref:
            if password:
                rar_ref.setpassword(password)
            
            for file_info in rar_ref.infolist():
                if not file_info.is_dir():
                    extracted_path = extract_to / file_info.filename
                    extracted_path.parent.mkdir(parents=True, exist_ok=True)
                    
                    with rar_ref.open(file_info) as source, open(extracted_path, 'wb') as target:
                        target.write(source.read())
                    
                    extracted_files.append(extracted_path)
        
        return extracted_files
    
    async def _extract_7z(
        self,
        seven_z_path: Path,
        extract_to: Path,
        password: Optional[str] = None
    ) -> List[Path]:
        """Extrai arquivo 7Z.
        
        Args:
            seven_z_path: Caminho do 7Z
            extract_to: Diretório de destino
            password: Senha do arquivo
            
        Returns:
            Lista de arquivos extraídos
        """
        extracted_files = []
        
        with py7zr.SevenZipFile(seven_z_path, 'r', password=password) as seven_z_ref:
            for file_info in seven_z_ref.list():
                if not file_info.is_dir:
                    extracted_path = extract_to / file_info.filename
                    extracted_path.parent.mkdir(parents=True, exist_ok=True)
                    
                    seven_z_ref.extract(path=extract_to, targets=[file_info.filename])
                    extracted_files.append(extracted_path)
        
        return extracted_files
    
    async def calculate_directory_size(
        self,
        directory: Path
    ) -> int:
        """Calcula tamanho total de um diretório.
        
        Args:
            directory: Diretório para calcular
            
        Returns:
            Tamanho total em bytes
        """
        total_size = 0
        
        for file_path in directory.rglob('*'):
            if file_path.is_file():
                total_size += file_path.stat().st_size
        
        return total_size
    
    async def clean_temp_files(
        self,
        temp_directory: Path,
        max_age_hours: int = 24
    ) -> int:
        """Limpa arquivos temporários antigos.
        
        Args:
            temp_directory: Diretório temporário
            max_age_hours: Idade máxima em horas
            
        Returns:
            Número de arquivos removidos
        """
        if not temp_directory.exists():
            return 0
        
        max_age_seconds = max_age_hours * 3600
        current_time = datetime.now().timestamp()
        removed_count = 0
        
        for file_path in temp_directory.rglob('*'):
            if file_path.is_file():
                file_age = current_time - file_path.stat().st_mtime
                if file_age > max_age_seconds:
                    try:
                        file_path.unlink()
                        removed_count += 1
                    except OSError:
                        pass  # Ignora erros de remoção
        
        return removed_count


class MetadataService:
    """Serviço para coleta e gerenciamento de metadados."""
    
    def __init__(self):
        self.scrapers = {}
        self.cache = {}
    
    async def collect_game_metadata(
        self,
        game_name: str,
        system_name: str,
        sources: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Coleta metadados de um jogo.
        
        Args:
            game_name: Nome do jogo
            system_name: Nome do sistema
            sources: Fontes de dados (opcional)
            
        Returns:
            Metadados coletados
        """
        if not sources:
            sources = ["gamefaqs", "mobygames", "wikipedia"]
        
        metadata = {
            "title": game_name,
            "system": system_name,
            "sources": {},
            "collected_at": datetime.utcnow().isoformat()
        }
        
        for source in sources:
            try:
                source_data = await self._collect_from_source(source, game_name, system_name)
                metadata["sources"][source] = source_data
            except Exception as e:
                metadata["sources"][source] = {"error": str(e)}
        
        # Consolida dados de múltiplas fontes
        consolidated = await self._consolidate_metadata(metadata)
        
        return consolidated
    
    async def _collect_from_source(
        self,
        source: str,
        game_name: str,
        system_name: str
    ) -> Dict[str, Any]:
        """Coleta dados de uma fonte específica.
        
        Args:
            source: Nome da fonte
            game_name: Nome do jogo
            system_name: Nome do sistema
            
        Returns:
            Dados da fonte
        """
        # Implementação de exemplo para scraper; expanda conforme necessário
        if source == 'wikipedia':
            # Lógica de scraping
            return {"title": game_name, "description": "Exemplo de descrição"}
        else:
            return {
                "title": game_name,
                "system": system_name,
                "source": source,
                "collected_at": datetime.utcnow().isoformat()
            }
    
    async def _consolidate_metadata(
        self,
        metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Consolida metadados de múltiplas fontes.
        
        Args:
            metadata: Metadados de múltiplas fontes
            
        Returns:
            Metadados consolidados
        """
        consolidated = {"title": metadata.get('title')}
        # Lógica de priorização: exemplo simples
        for source in ['gamefaqs', 'mobygames', 'wikipedia']:
            if source in metadata['sources']:
                consolidated.update(metadata['sources'][source])
                break
        print(f"[LOG] Metadados consolidados para {consolidated['title']}")
        return consolidated
    
    def register_scraper(self, source: str, scraper_class) -> None:
        """Registra um scraper para uma fonte.
        
        Args:
            source: Nome da fonte
            scraper_class: Classe do scraper
        """
        self.scrapers[source] = scraper_class
    
    async def clear_cache(self, max_age_hours: int = 24) -> int:
        """Limpa cache de metadados antigos.
        
        Args:
            max_age_hours: Idade máxima em horas
            
        Returns:
            Número de entradas removidas
        """
        max_age_seconds = max_age_hours * 3600
        current_time = datetime.now().timestamp()
        removed = 0
        for key in list(self.cache.keys()):
            if current_time - self.cache[key]['timestamp'] > max_age_seconds:
                del self.cache[key]
                removed += 1
        print(f"[LOG] Cache limpo: {removed} entradas removidas")
        return removed


async def _calculate_hash_incremental(self, file_path: Path, algorithm: str) -> str:
    """Calcula hash de arquivo de forma incremental para arquivos grandes."""
    chunk_size = 8192
    hash_func = hashlib.new(algorithm)
    with open(file_path, 'rb') as f:
        while chunk := f.read(chunk_size):
            hash_func.update(chunk)
    return hash_func.hexdigest()


class VerificationService:
    """Serviço para verificação de integridade de ROMs."""
    
    def __init__(self, rom_service: ROMService, task_service: TaskService):
        self.rom_service = rom_service
        self.task_service = task_service
    
    async def verify_rom(
        self,
        db: AsyncSession,
        *,
        rom_id: UUID,
        verification_type: VerificationType = VerificationType.HASH_CHECK
    ) -> ROMVerification:
        """Verifica integridade de uma ROM.
        
        Args:
            db: Sessão do banco de dados
            rom_id: ID da ROM
            verification_type: Tipo de verificação
            
        Returns:
            Resultado da verificação
            
        Raises:
            HTTPException: Se ROM não encontrada
        """
        rom = await self.rom_service.get(db, rom_id)
        if not rom:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="ROM não encontrada"
            )
        
        # Executa verificação
        verification_result = await self._perform_verification(rom, verification_type)
        
        # Salva resultado
        verification = ROMVerification(
            rom_id=rom_id,
            verification_type=verification_type,
            **verification_result
        )
        
        db.add(verification)
        
        # Atualiza status da ROM
        if verification_result["success"]:
            rom.status = ROMStatus.VERIFIED
        else:
            rom.status = ROMStatus.INVALID
        
        await db.commit()
        await db.refresh(verification)
        
        return verification
    
    async def verify_roms_batch(
        self,
        db: AsyncSession,
        *,
        rom_ids: List[UUID],
        user_id: UUID
    ) -> Task:
        """Verifica múltiplas ROMs em lote."""
        
        task_data = TaskCreate(
            name=f"Verificação em lote - {len(rom_ids)} ROMs",
            description=f"Verificando integridade de {len(rom_ids)} ROMs",
            task_type=TaskType.ROM_VERIFICATION,
            user_id=user_id,
            parameters={
                "rom_ids": [str(rom_id) for rom_id in rom_ids]
            }
        )
        
        task = await self.task_service.create_task(db, task_in=task_data)
        
        if TaskType.ROM_VERIFICATION not in self.task_service._task_handlers:
            self.task_service.register_task_handler(
                TaskType.ROM_VERIFICATION,
                self._handle_rom_verification
            )
        
        return task
    
    async def _handle_rom_verification(
        self,
        db: AsyncSession,
        task: Task
    ) -> None:
        params = task.parameters
        rom_ids = [UUID(id_str) for id_str in params["rom_ids"]]
        total = len(rom_ids)
        task.total_steps = total
        await db.commit()
        
        success_count = 0
        failure_count = 0
        
        for i, rom_id in enumerate(rom_ids):
            try:
                verification = await self.verify_rom(db, rom_id=rom_id)
                if verification.success:
                    success_count += 1
                else:
                    failure_count += 1
            except Exception as e:
                failure_count += 1
                print(f"Erro ao verificar ROM {rom_id}: {str(e)}")
            
            task.current_step = i + 1
            task.progress = int((task.current_step / total) * 100)
            task.status_message = f"Verificado {task.current_step}/{total}"
            await db.commit()
        
        task.status_message = f"Verificação concluída: {success_count} sucessos, {failure_count} falhas"
        await db.commit()
    
    async def _perform_verification(
        self,
        rom: ROM,
        verification_type: VerificationType
    ) -> Dict[str, Any]:
        """Executa verificação da ROM.
        
        Args:
            rom: ROM para verificar
            verification_type: Tipo de verificação
            
        Returns:
            Resultado da verificação
        """
        file_path = Path(rom.file_path)
        
        if not file_path.exists():
            return {
                "success": False,
                "error_message": "Arquivo não encontrado",
                "verified_at": datetime.utcnow()
            }
        
        try:
            if verification_type == VerificationType.HASH_COMPARISON:
                return await self._verify_by_hash(rom, file_path)
            elif verification_type == VerificationType.FILE_SIZE:
                return await self._verify_by_size(rom, file_path)
            elif verification_type == VerificationType.CHECKSUM:
                return await self._verify_by_checksum(rom, file_path)
            else:
                return {
                    "success": False,
                    "error_message": "Tipo de verificação não suportado",
                    "verified_at": datetime.utcnow()
                }
        
        except Exception as e:
            return {
                "success": False,
                "error_message": str(e),
                "verified_at": datetime.utcnow()
            }
    
    async def _verify_by_hash(
        self,
        rom: ROM,
        file_path: Path
    ) -> Dict[str, Any]:
        """Verifica ROM por hash.
        
        Args:
            rom: ROM para verificar
            file_path: Caminho do arquivo
            
        Returns:
            Resultado da verificação
        """
        # Calcula hashes atuais
        current_crc32 = await calculate_file_hash(file_path, "crc32")
        current_md5 = await calculate_file_hash(file_path, "md5")
        current_sha1 = await calculate_file_hash(file_path, "sha1")
        
        # Compara com hashes armazenados
        hash_matches = {
            "crc32_match": rom.crc32 == current_crc32 if rom.crc32 else None,
            "md5_match": rom.md5 == current_md5 if rom.md5 else None,
            "sha1_match": rom.sha1 == current_sha1 if rom.sha1 else None
        }
        
        # Verifica se pelo menos um hash confere
        success = any(match for match in hash_matches.values() if match is not None)
        
        return {
            "success": success,
            "hash_matches": hash_matches,
            "current_hashes": {
                "crc32": current_crc32,
                "md5": current_md5,
                "sha1": current_sha1
            },
            "verified_at": datetime.utcnow()
        }
    
    async def _verify_by_size(
        self,
        rom: ROM,
        file_path: Path
    ) -> Dict[str, Any]:
        """Verifica ROM por tamanho.
        
        Args:
            rom: ROM para verificar
            file_path: Caminho do arquivo
            
        Returns:
            Resultado da verificação
        """
        current_size = get_file_size(file_path)
        success = rom.file_size == current_size
        
        return {
            "success": success,
            "size_match": success,
            "current_size": current_size,
            "expected_size": rom.file_size,
            "verified_at": datetime.utcnow()
        }
    
    async def _verify_by_checksum(
        self,
        rom: ROM,
        file_path: Path
    ) -> Dict[str, Any]:
        """Verifica ROM por checksum.
        
        Args:
            rom: ROM para verificar
            file_path: Caminho do arquivo
            
        Returns:
            Resultado da verificação
        """
        system_checksum = 'expected_checksum'  # Obtenha do sistema ou config
        current_checksum = await calculate_file_hash(file_path, 'sha256')  # Exemplo
        success = current_checksum == system_checksum
        return {
            "success": success,
            "checksum_match": success,
            "current_checksum": current_checksum,
            "expected_checksum": system_checksum,
            "verified_at": datetime.utcnow()
        }


class FileService:
    """Serviço para manipulação de arquivos."""
    
    async def extract_archive(
        self,
        archive_path: Path,
        extract_to: Path,
        password: Optional[str] = None
    ) -> List[Path]:
        """Extrai arquivo comprimido.
        
        Args:
            archive_path: Caminho do arquivo
            extract_to: Diretório de destino
            password: Senha do arquivo (opcional)
            
        Returns:
            Lista de arquivos extraídos
        """
        extract_to.mkdir(parents=True, exist_ok=True)
        extracted_files = []
        
        try:
            if archive_path.suffix.lower() == '.zip':
                extracted_files = await self._extract_zip(archive_path, extract_to, password)
            elif archive_path.suffix.lower() == '.rar':
                extracted_files = await self._extract_rar(archive_path, extract_to, password)
            elif archive_path.suffix.lower() == '.7z':
                extracted_files = await self._extract_7z(archive_path, extract_to, password)
            else:
                raise ValueError(f"Formato de arquivo não suportado: {archive_path.suffix}")
        
        except (OSError, ValueError) as e:
            logger.error(f"Erro ao importar ROMs: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))
        
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Erro ao extrair arquivo: {e}"
            )
        
        return extracted_files
    
    async def _extract_zip(
        self,
        zip_path: Path,
        extract_to: Path,
        password: Optional[str] = None
    ) -> List[Path]:
        """Extrai arquivo ZIP.
        
        Args:
            zip_path: Caminho do ZIP
            extract_to: Diretório de destino
            password: Senha do arquivo
            
        Returns:
            Lista de arquivos extraídos
        """
        extracted_files = []
        
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            if password:
                zip_ref.setpassword(password.encode())
            
            for file_info in zip_ref.filelist:
                if not file_info.is_dir():
                    extracted_path = extract_to / file_info.filename
                    extracted_path.parent.mkdir(parents=True, exist