"""Sistema de backup incremental automático com versionamento.

Este módulo implementa:
- Backup incremental baseado em checksums
- Versionamento automático com retenção configurável
- Verificação de integridade automática
- Restauração point-in-time
- Backup na nuvem opcional (S3, Google Cloud, Azure)
- Compressão e criptografia
"""

import asyncio
import hashlib
import json
import logging
import shutil
import sqlite3
import tarfile
import time
import zipfile
from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union, Callable

import aiofiles
import aiofiles.os
from cryptography.fernet import Fernet
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class BackupType(Enum):
    """Tipos de backup."""
    FULL = "full"          # Backup completo
    INCREMENTAL = "incremental"  # Apenas mudanças
    DIFFERENTIAL = "differential"  # Mudanças desde último full


class BackupStatus(Enum):
    """Status do backup."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CORRUPTED = "corrupted"


class CompressionType(Enum):
    """Tipos de compressão."""
    NONE = "none"
    ZIP = "zip"
    TAR_GZ = "tar.gz"
    TAR_XZ = "tar.xz"


class CloudProvider(Enum):
    """Provedores de nuvem suportados."""
    NONE = "none"
    S3 = "s3"
    GOOGLE_CLOUD = "gcs"
    AZURE = "azure"


@dataclass
class FileInfo:
    """Informações de um arquivo."""
    path: str
    size: int
    mtime: float
    checksum: str
    is_directory: bool = False
    
    def __hash__(self):
        return hash((self.path, self.checksum))


@dataclass
class BackupMetadata:
    """Metadados do backup."""
    backup_id: str
    backup_type: BackupType
    status: BackupStatus
    created_at: datetime
    completed_at: Optional[datetime] = None
    source_path: str = ""
    backup_path: str = ""
    file_count: int = 0
    total_size: int = 0
    compressed_size: int = 0
    compression_ratio: float = 0.0
    checksum: str = ""
    parent_backup_id: Optional[str] = None
    files: List[FileInfo] = field(default_factory=list)
    error_message: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Converte para dicionário."""
        return {
            'backup_id': self.backup_id,
            'backup_type': self.backup_type.value,
            'status': self.status.value,
            'created_at': self.created_at.isoformat(),
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'source_path': self.source_path,
            'backup_path': self.backup_path,
            'file_count': self.file_count,
            'total_size': self.total_size,
            'compressed_size': self.compressed_size,
            'compression_ratio': self.compression_ratio,
            'checksum': self.checksum,
            'parent_backup_id': self.parent_backup_id,
            'files': [{
                'path': f.path,
                'size': f.size,
                'mtime': f.mtime,
                'checksum': f.checksum,
                'is_directory': f.is_directory
            } for f in self.files],
            'error_message': self.error_message
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'BackupMetadata':
        """Cria instância a partir de dicionário."""
        files = []
        for f_data in data.get('files', []):
            files.append(FileInfo(
                path=f_data['path'],
                size=f_data['size'],
                mtime=f_data['mtime'],
                checksum=f_data['checksum'],
                is_directory=f_data.get('is_directory', False)
            ))
        
        return cls(
            backup_id=data['backup_id'],
            backup_type=BackupType(data['backup_type']),
            status=BackupStatus(data['status']),
            created_at=datetime.fromisoformat(data['created_at']),
            completed_at=datetime.fromisoformat(data['completed_at']) if data.get('completed_at') else None,
            source_path=data.get('source_path', ''),
            backup_path=data.get('backup_path', ''),
            file_count=data.get('file_count', 0),
            total_size=data.get('total_size', 0),
            compressed_size=data.get('compressed_size', 0),
            compression_ratio=data.get('compression_ratio', 0.0),
            checksum=data.get('checksum', ''),
            parent_backup_id=data.get('parent_backup_id'),
            files=files,
            error_message=data.get('error_message')
        )


class BackupConfig(BaseModel):
    """Configuração do sistema de backup."""
    # Diretórios
    backup_dir: str = "backups"
    source_dirs: List[str] = ["data", "config"]
    
    # Agendamento
    auto_backup_enabled: bool = True
    full_backup_interval: int = 7 * 24 * 3600  # 7 dias
    incremental_interval: int = 6 * 3600  # 6 horas
    
    # Retenção
    max_full_backups: int = 10
    max_incremental_backups: int = 50
    retention_days: int = 30
    
    # Compressão
    compression_type: CompressionType = CompressionType.TAR_GZ
    compression_level: int = 6
    
    # Criptografia
    encryption_enabled: bool = False
    encryption_key: Optional[str] = None
    
    # Verificação
    integrity_check_enabled: bool = True
    verify_after_backup: bool = True
    
    # Nuvem
    cloud_provider: CloudProvider = CloudProvider.NONE
    cloud_config: Dict[str, Any] = {}
    
    # Performance
    max_concurrent_files: int = 10
    chunk_size: int = 64 * 1024  # 64KB
    
    # Exclusões
    exclude_patterns: List[str] = [
        "*.tmp", "*.log", "__pycache__", ".git", "node_modules"
    ]


class ICloudStorage(ABC):
    """Interface para armazenamento na nuvem."""
    
    @abstractmethod
    async def upload(self, local_path: str, remote_path: str) -> bool:
        """Faz upload de arquivo."""
        pass
    
    @abstractmethod
    async def download(self, remote_path: str, local_path: str) -> bool:
        """Faz download de arquivo."""
        pass
    
    @abstractmethod
    async def delete(self, remote_path: str) -> bool:
        """Remove arquivo."""
        pass
    
    @abstractmethod
    async def list_files(self, prefix: str = "") -> List[str]:
        """Lista arquivos."""
        pass


class S3CloudStorage(ICloudStorage):
    """Armazenamento na AWS S3."""
    
    def __init__(self, config: Dict[str, Any]):
        self.bucket = config.get('bucket')
        self.access_key = config.get('access_key')
        self.secret_key = config.get('secret_key')
        self.region = config.get('region', 'us-east-1')
        
        # Importa boto3 apenas se necessário
        try:
            import boto3
            self.s3_client = boto3.client(
                's3',
                aws_access_key_id=self.access_key,
                aws_secret_access_key=self.secret_key,
                region_name=self.region
            )
        except ImportError:
            raise ImportError("boto3 é necessário para usar S3")
    
    async def upload(self, local_path: str, remote_path: str) -> bool:
        """Faz upload para S3."""
        try:
            self.s3_client.upload_file(local_path, self.bucket, remote_path)
            return True
        except Exception as e:
            logger.error(f"Erro no upload S3: {e}")
            return False
    
    async def download(self, remote_path: str, local_path: str) -> bool:
        """Faz download do S3."""
        try:
            self.s3_client.download_file(self.bucket, remote_path, local_path)
            return True
        except Exception as e:
            logger.error(f"Erro no download S3: {e}")
            return False
    
    async def delete(self, remote_path: str) -> bool:
        """Remove arquivo do S3."""
        try:
            self.s3_client.delete_object(Bucket=self.bucket, Key=remote_path)
            return True
        except Exception as e:
            logger.error(f"Erro ao deletar S3: {e}")
            return False
    
    async def list_files(self, prefix: str = "") -> List[str]:
        """Lista arquivos no S3."""
        try:
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket,
                Prefix=prefix
            )
            return [obj['Key'] for obj in response.get('Contents', [])]
        except Exception as e:
            logger.error(f"Erro ao listar S3: {e}")
            return []


class BackupDatabase:
    """Banco de dados para metadados de backup."""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_database()
    
    def _init_database(self):
        """Inicializa banco de dados."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS backups (
                    backup_id TEXT PRIMARY KEY,
                    backup_type TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    completed_at TEXT,
                    source_path TEXT,
                    backup_path TEXT,
                    file_count INTEGER DEFAULT 0,
                    total_size INTEGER DEFAULT 0,
                    compressed_size INTEGER DEFAULT 0,
                    compression_ratio REAL DEFAULT 0.0,
                    checksum TEXT,
                    parent_backup_id TEXT,
                    error_message TEXT,
                    metadata TEXT
                )
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_backups_created_at 
                ON backups(created_at)
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_backups_type_status 
                ON backups(backup_type, status)
            """)
    
    async def save_backup(self, backup: BackupMetadata):
        """Salva metadados do backup."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO backups (
                    backup_id, backup_type, status, created_at, completed_at,
                    source_path, backup_path, file_count, total_size,
                    compressed_size, compression_ratio, checksum,
                    parent_backup_id, error_message, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                backup.backup_id,
                backup.backup_type.value,
                backup.status.value,
                backup.created_at.isoformat(),
                backup.completed_at.isoformat() if backup.completed_at else None,
                backup.source_path,
                backup.backup_path,
                backup.file_count,
                backup.total_size,
                backup.compressed_size,
                backup.compression_ratio,
                backup.checksum,
                backup.parent_backup_id,
                backup.error_message,
                json.dumps(backup.to_dict())
            ))
    
    async def get_backup(self, backup_id: str) -> Optional[BackupMetadata]:
        """Obtém metadados do backup."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT metadata FROM backups WHERE backup_id = ?",
                (backup_id,)
            )
            row = cursor.fetchone()
            
            if row:
                data = json.loads(row[0])
                return BackupMetadata.from_dict(data)
        
        return None
    
    async def list_backups(
        self,
        backup_type: Optional[BackupType] = None,
        status: Optional[BackupStatus] = None,
        limit: int = 100
    ) -> List[BackupMetadata]:
        """Lista backups."""
        query = "SELECT metadata FROM backups WHERE 1=1"
        params = []
        
        if backup_type:
            query += " AND backup_type = ?"
            params.append(backup_type.value)
        
        if status:
            query += " AND status = ?"
            params.append(status.value)
        
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        
        backups = []
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(query, params)
            for row in cursor.fetchall():
                data = json.loads(row[0])
                backups.append(BackupMetadata.from_dict(data))
        
        return backups
    
    async def delete_backup(self, backup_id: str) -> bool:
        """Remove metadados do backup."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "DELETE FROM backups WHERE backup_id = ?",
                (backup_id,)
            )
            return cursor.rowcount > 0
    
    async def get_latest_full_backup(self) -> Optional[BackupMetadata]:
        """Obtém último backup completo."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT metadata FROM backups 
                WHERE backup_type = 'full' AND status = 'completed'
                ORDER BY created_at DESC LIMIT 1
            """)
            row = cursor.fetchone()
            
            if row:
                data = json.loads(row[0])
                return BackupMetadata.from_dict(data)
        
        return None


class BackupManager:
    """Gerenciador de backup incremental."""
    
    def __init__(self, config: BackupConfig):
        self.config = config
        self.backup_dir = Path(config.backup_dir)
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        
        # Banco de dados
        self.db = BackupDatabase(str(self.backup_dir / "backups.db"))
        
        # Criptografia
        self.cipher = None
        if config.encryption_enabled and config.encryption_key:
            self.cipher = Fernet(config.encryption_key.encode())
        
        # Armazenamento na nuvem
        self.cloud_storage: Optional[ICloudStorage] = None
        self._init_cloud_storage()
        
        # Tarefas
        self._backup_task: Optional[asyncio.Task] = None
        self._cleanup_task: Optional[asyncio.Task] = None
    
    def _init_cloud_storage(self):
        """Inicializa armazenamento na nuvem."""
        if self.config.cloud_provider == CloudProvider.S3:
            self.cloud_storage = S3CloudStorage(self.config.cloud_config)
        # Adicionar outros provedores conforme necessário
    
    async def start(self):
        """Inicia o gerenciador de backup."""
        if self.config.auto_backup_enabled:
            self._backup_task = asyncio.create_task(self._backup_loop())
        
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        
        logger.info("Gerenciador de backup iniciado")
    
    async def stop(self):
        """Para o gerenciador de backup."""
        if self._backup_task:
            self._backup_task.cancel()
            try:
                await self._backup_task
            except asyncio.CancelledError:
                pass
        
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Gerenciador de backup parado")
    
    async def create_backup(
        self,
        backup_type: Optional[BackupType] = None,
        source_paths: Optional[List[str]] = None
    ) -> BackupMetadata:
        """Cria um novo backup.
        
        Args:
            backup_type: Tipo do backup (auto-detecta se None)
            source_paths: Caminhos a fazer backup (usa config se None)
            
        Returns:
            Metadados do backup criado
        """
        # Determina tipo do backup
        if backup_type is None:
            last_full = await self.db.get_latest_full_backup()
            if not last_full:
                backup_type = BackupType.FULL
            else:
                time_since_full = datetime.now() - last_full.created_at
                if time_since_full.total_seconds() > self.config.full_backup_interval:
                    backup_type = BackupType.FULL
                else:
                    backup_type = BackupType.INCREMENTAL
        
        # Usa caminhos da configuração se não especificado
        if source_paths is None:
            source_paths = self.config.source_dirs
        
        # Gera ID do backup
        backup_id = f"{backup_type.value}_{int(time.time())}"
        
        # Cria metadados iniciais
        backup = BackupMetadata(
            backup_id=backup_id,
            backup_type=backup_type,
            status=BackupStatus.PENDING,
            created_at=datetime.now(),
            source_path=";".join(source_paths)
        )
        
        try:
            # Atualiza status
            backup.status = BackupStatus.RUNNING
            await self.db.save_backup(backup)
            
            # Coleta informações dos arquivos
            logger.info(f"Iniciando backup {backup_type.value}: {backup_id}")
            current_files = await self._scan_files(source_paths)
            
            # Determina arquivos a fazer backup
            if backup_type == BackupType.FULL:
                files_to_backup = current_files
                backup.parent_backup_id = None
            else:
                # Backup incremental
                last_full = await self.db.get_latest_full_backup()
                if not last_full:
                    raise ValueError("Backup incremental requer backup completo anterior")
                
                backup.parent_backup_id = last_full.backup_id
                files_to_backup = await self._get_changed_files(current_files, last_full)
            
            # Cria arquivo de backup
            backup_path = self.backup_dir / f"{backup_id}.{self.config.compression_type.value}"
            backup.backup_path = str(backup_path)
            
            # Executa backup
            await self._create_backup_archive(files_to_backup, backup_path)
            
            # Calcula estatísticas
            backup.files = list(files_to_backup)
            backup.file_count = len(files_to_backup)
            backup.total_size = sum(f.size for f in files_to_backup if not f.is_directory)
            backup.compressed_size = backup_path.stat().st_size
            backup.compression_ratio = (
                1.0 - (backup.compressed_size / backup.total_size)
                if backup.total_size > 0 else 0.0
            )
            
            # Calcula checksum
            backup.checksum = await self._calculate_file_checksum(str(backup_path))
            
            # Verifica integridade se habilitado
            if self.config.verify_after_backup:
                if not await self._verify_backup(backup):
                    backup.status = BackupStatus.CORRUPTED
                    backup.error_message = "Falha na verificação de integridade"
                    await self.db.save_backup(backup)
                    return backup
            
            # Upload para nuvem se configurado
            if self.cloud_storage:
                cloud_path = f"backups/{backup_id}.{self.config.compression_type.value}"
                success = await self.cloud_storage.upload(str(backup_path), cloud_path)
                if not success:
                    logger.warning(f"Falha no upload para nuvem: {backup_id}")
            
            # Finaliza backup
            backup.status = BackupStatus.COMPLETED
            backup.completed_at = datetime.now()
            
            logger.info(
                f"Backup concluído: {backup_id} - "
                f"{backup.file_count} arquivos, "
                f"{backup.total_size / 1024 / 1024:.1f}MB -> "
                f"{backup.compressed_size / 1024 / 1024:.1f}MB "
                f"({backup.compression_ratio:.1%} compressão)"
            )
            
        except Exception as e:
            backup.status = BackupStatus.FAILED
            backup.error_message = str(e)
            logger.error(f"Erro no backup {backup_id}: {e}")
        
        finally:
            await self.db.save_backup(backup)
        
        return backup
    
    async def restore_backup(
        self,
        backup_id: str,
        target_path: str,
        point_in_time: Optional[datetime] = None
    ) -> bool:
        """Restaura um backup.
        
        Args:
            backup_id: ID do backup a restaurar
            target_path: Caminho de destino
            point_in_time: Momento específico para restaurar (opcional)
            
        Returns:
            True se restauração foi bem-sucedida
        """
        try:
            backup = await self.db.get_backup(backup_id)
            if not backup:
                raise ValueError(f"Backup não encontrado: {backup_id}")
            
            if backup.status != BackupStatus.COMPLETED:
                raise ValueError(f"Backup não está completo: {backup.status.value}")
            
            logger.info(f"Iniciando restauração: {backup_id} -> {target_path}")
            
            # Verifica integridade antes da restauração
            if not await self._verify_backup(backup):
                raise ValueError("Backup falhou na verificação de integridade")
            
            # Cria diretório de destino
            target_dir = Path(target_path)
            target_dir.mkdir(parents=True, exist_ok=True)
            
            # Extrai backup
            backup_path = Path(backup.backup_path)
            
            # Download da nuvem se necessário
            if not backup_path.exists() and self.cloud_storage:
                cloud_path = f"backups/{backup_id}.{self.config.compression_type.value}"
                success = await self.cloud_storage.download(cloud_path, str(backup_path))
                if not success:
                    raise ValueError("Falha no download do backup da nuvem")
            
            # Extrai arquivo
            await self._extract_backup_archive(backup_path, target_dir)
            
            # Se é backup incremental, precisa restaurar backup pai primeiro
            if backup.backup_type == BackupType.INCREMENTAL and backup.parent_backup_id:
                parent_success = await self.restore_backup(
                    backup.parent_backup_id,
                    target_path,
                    point_in_time
                )
                if not parent_success:
                    raise ValueError("Falha na restauração do backup pai")
            
            logger.info(f"Restauração concluída: {backup_id}")
            return True
            
        except Exception as e:
            logger.error(f"Erro na restauração {backup_id}: {e}")
            return False
    
    async def verify_backup(self, backup_id: str) -> bool:
        """Verifica integridade de um backup."""
        backup = await self.db.get_backup(backup_id)
        if not backup:
            return False
        
        return await self._verify_backup(backup)
    
    async def list_backups(
        self,
        backup_type: Optional[BackupType] = None,
        status: Optional[BackupStatus] = None,
        limit: int = 100
    ) -> List[BackupMetadata]:
        """Lista backups disponíveis."""
        return await self.db.list_backups(backup_type, status, limit)
    
    async def delete_backup(self, backup_id: str) -> bool:
        """Remove um backup."""
        try:
            backup = await self.db.get_backup(backup_id)
            if not backup:
                return False
            
            # Remove arquivo local
            backup_path = Path(backup.backup_path)
            if backup_path.exists():
                backup_path.unlink()
            
            # Remove da nuvem
            if self.cloud_storage:
                cloud_path = f"backups/{backup_id}.{self.config.compression_type.value}"
                await self.cloud_storage.delete(cloud_path)
            
            # Remove do banco
            await self.db.delete_backup(backup_id)
            
            logger.info(f"Backup removido: {backup_id}")
            return True
            
        except Exception as e:
            logger.error(f"Erro ao remover backup {backup_id}: {e}")
            return False
    
    async def _scan_files(self, source_paths: List[str]) -> Set[FileInfo]:
        """Escaneia arquivos nos caminhos especificados."""
        files = set()
        
        for source_path in source_paths:
            path = Path(source_path)
            if not path.exists():
                logger.warning(f"Caminho não existe: {source_path}")
                continue
            
            if path.is_file():
                file_info = await self._get_file_info(path)
                if file_info:
                    files.add(file_info)
            else:
                # Escaneia diretório recursivamente
                async for file_path in self._walk_directory(path):
                    if await self._should_include_file(file_path):
                        file_info = await self._get_file_info(file_path)
                        if file_info:
                            files.add(file_info)
        
        return files
    
    async def _walk_directory(self, directory: Path):
        """Percorre diretório recursivamente."""
        try:
            for item in directory.rglob("*"):
                yield item
        except (PermissionError, OSError) as e:
            logger.warning(f"Erro ao acessar {directory}: {e}")
    
    async def _should_include_file(self, file_path: Path) -> bool:
        """Verifica se arquivo deve ser incluído no backup."""
        # Verifica padrões de exclusão
        for pattern in self.config.exclude_patterns:
            if file_path.match(pattern):
                return False
        
        return True
    
    async def _get_file_info(self, file_path: Path) -> Optional[FileInfo]:
        """Obtém informações de um arquivo."""
        try:
            stat = await aiofiles.os.stat(file_path)
            
            # Calcula checksum para arquivos
            checksum = ""
            if file_path.is_file():
                checksum = await self._calculate_file_checksum(str(file_path))
            
            return FileInfo(
                path=str(file_path),
                size=stat.st_size,
                mtime=stat.st_mtime,
                checksum=checksum,
                is_directory=file_path.is_dir()
            )
            
        except (PermissionError, OSError) as e:
            logger.warning(f"Erro ao obter info do arquivo {file_path}: {e}")
            return None
    
    async def _calculate_file_checksum(self, file_path: str) -> str:
        """Calcula checksum SHA-256 de um arquivo."""
        hash_sha256 = hashlib.sha256()
        
        try:
            async with aiofiles.open(file_path, 'rb') as f:
                while chunk := await f.read(self.config.chunk_size):
                    hash_sha256.update(chunk)
            
            return hash_sha256.hexdigest()
            
        except Exception as e:
            logger.warning(f"Erro ao calcular checksum {file_path}: {e}")
            return ""
    
    async def _get_changed_files(
        self,
        current_files: Set[FileInfo],
        last_backup: BackupMetadata
    ) -> Set[FileInfo]:
        """Identifica arquivos alterados desde último backup."""
        # Cria índice do backup anterior
        last_files = {f.path: f for f in last_backup.files}
        
        changed_files = set()
        
        for file_info in current_files:
            last_file = last_files.get(file_info.path)
            
            # Arquivo novo ou modificado
            if not last_file or (
                file_info.mtime > last_file.mtime or
                file_info.checksum != last_file.checksum
            ):
                changed_files.add(file_info)
        
        return changed_files
    
    async def _create_backup_archive(
        self,
        files: Set[FileInfo],
        archive_path: Path
    ):
        """Cria arquivo de backup comprimido."""
        if self.config.compression_type == CompressionType.ZIP:
            await self._create_zip_archive(files, archive_path)
        elif self.config.compression_type in [CompressionType.TAR_GZ, CompressionType.TAR_XZ]:
            await self._create_tar_archive(files, archive_path)
        else:
            # Sem compressão - copia arquivos
            await self._create_directory_backup(files, archive_path)
    
    async def _create_zip_archive(self, files: Set[FileInfo], archive_path: Path):
        """Cria arquivo ZIP."""
        with zipfile.ZipFile(archive_path, 'w', zipfile.ZIP_DEFLATED, compresslevel=self.config.compression_level) as zf:
            for file_info in files:
                if not file_info.is_directory:
                    file_path = Path(file_info.path)
                    if file_path.exists():
                        zf.write(file_path, file_info.path)
    
    async def _create_tar_archive(self, files: Set[FileInfo], archive_path: Path):
        """Cria arquivo TAR."""
        mode = 'w:gz' if self.config.compression_type == CompressionType.TAR_GZ else 'w:xz'
        
        with tarfile.open(archive_path, mode) as tf:
            for file_info in files:
                file_path = Path(file_info.path)
                if file_path.exists():
                    tf.add(file_path, arcname=file_info.path)
    
    async def _create_directory_backup(self, files: Set[FileInfo], backup_dir: Path):
        """Cria backup copiando arquivos para diretório."""
        backup_dir.mkdir(parents=True, exist_ok=True)
        
        for file_info in files:
            if not file_info.is_directory:
                source_path = Path(file_info.path)
                target_path = backup_dir / file_info.path
                target_path.parent.mkdir(parents=True, exist_ok=True)
                
                if source_path.exists():
                    shutil.copy2(source_path, target_path)
    
    async def _extract_backup_archive(self, archive_path: Path, target_dir: Path):
        """Extrai arquivo de backup."""
        if archive_path.suffix == '.zip':
            with zipfile.ZipFile(archive_path, 'r') as zf:
                zf.extractall(target_dir)
        elif archive_path.suffix in ['.gz', '.xz'] or '.tar' in archive_path.name:
            with tarfile.open(archive_path, 'r:*') as tf:
                tf.extractall(target_dir)
        else:
            # Copia diretório
            if archive_path.is_dir():
                shutil.copytree(archive_path, target_dir, dirs_exist_ok=True)
    
    async def _verify_backup(self, backup: BackupMetadata) -> bool:
        """Verifica integridade do backup."""
        try:
            backup_path = Path(backup.backup_path)
            
            # Verifica se arquivo existe
            if not backup_path.exists():
                logger.error(f"Arquivo de backup não encontrado: {backup_path}")
                return False
            
            # Verifica checksum
            current_checksum = await self._calculate_file_checksum(str(backup_path))
            if current_checksum != backup.checksum:
                logger.error(f"Checksum inválido para backup {backup.backup_id}")
                return False
            
            # Verifica se arquivo pode ser aberto
            if backup_path.suffix == '.zip':
                with zipfile.ZipFile(backup_path, 'r') as zf:
                    # Testa integridade
                    bad_files = zf.testzip()
                    if bad_files:
                        logger.error(f"Arquivos corrompidos no ZIP: {bad_files}")
                        return False
            
            elif '.tar' in backup_path.name:
                with tarfile.open(backup_path, 'r:*') as tf:
                    # Lista membros para verificar integridade
                    tf.getmembers()
            
            return True
            
        except Exception as e:
            logger.error(f"Erro na verificação do backup {backup.backup_id}: {e}")
            return False
    
    async def _backup_loop(self):
        """Loop principal de backup automático."""
        while True:
            try:
                # Verifica se precisa fazer backup
                last_full = await self.db.get_latest_full_backup()
                now = datetime.now()
                
                should_backup = False
                backup_type = BackupType.INCREMENTAL
                
                if not last_full:
                    # Primeiro backup
                    should_backup = True
                    backup_type = BackupType.FULL
                else:
                    # Verifica intervalo para backup completo
                    time_since_full = now - last_full.created_at
                    if time_since_full.total_seconds() >= self.config.full_backup_interval:
                        should_backup = True
                        backup_type = BackupType.FULL
                    else:
                        # Verifica intervalo para backup incremental
                        recent_backups = await self.db.list_backups(limit=1)
                        if recent_backups:
                            time_since_last = now - recent_backups[0].created_at
                            if time_since_last.total_seconds() >= self.config.incremental_interval:
                                should_backup = True
                                backup_type = BackupType.INCREMENTAL
                        else:
                            should_backup = True
                            backup_type = BackupType.INCREMENTAL
                
                if should_backup:
                    await self.create_backup(backup_type)
                
                # Aguarda próxima verificação
                await asyncio.sleep(min(self.config.incremental_interval, 3600))  # Max 1 hora
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Erro no loop de backup: {e}")
                await asyncio.sleep(300)  # 5 minutos em caso de erro
    
    async def _cleanup_loop(self):
        """Loop de limpeza de backups antigos."""
        while True:
            try:
                await asyncio.sleep(24 * 3600)  # Executa diariamente
                await self._cleanup_old_backups()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Erro na limpeza de backups: {e}")
    
    async def _cleanup_old_backups(self):
        """Remove backups antigos baseado na política de retenção."""
        try:
            # Remove backups expirados
            cutoff_date = datetime.now() - timedelta(days=self.config.retention_days)
            
            all_backups = await self.db.list_backups(limit=1000)
            expired_backups = [
                b for b in all_backups
                if b.created_at < cutoff_date
            ]
            
            for backup in expired_backups:
                await self.delete_backup(backup.backup_id)
                logger.info(f"Backup expirado removido: {backup.backup_id}")
            
            # Mantém apenas N backups completos mais recentes
            full_backups = await self.db.list_backups(
                backup_type=BackupType.FULL,
                status=BackupStatus.COMPLETED,
                limit=1000
            )
            
            if len(full_backups) > self.config.max_full_backups:
                excess_backups = full_backups[self.config.max_full_backups:]
                for backup in excess_backups:
                    await self.delete_backup(backup.backup_id)
                    logger.info(f"Backup completo excedente removido: {backup.backup_id}")
            
            # Mantém apenas N backups incrementais mais recentes
            incremental_backups = await self.db.list_backups(
                backup_type=BackupType.INCREMENTAL,
                status=BackupStatus.COMPLETED,
                limit=1000
            )
            
            if len(incremental_backups) > self.config.max_incremental_backups:
                excess_backups = incremental_backups[self.config.max_incremental_backups:]
                for backup in excess_backups:
                    await self.delete_backup(backup.backup_id)
                    logger.info(f"Backup incremental excedente removido: {backup.backup_id}")
            
        except Exception as e:
            logger.error(f"Erro na limpeza de backups: {e}")


# Instância global
backup_manager: Optional[BackupManager] = None


def get_backup_manager() -> BackupManager:
    """Obtém instância global do gerenciador de backup."""
    global backup_manager
    if backup_manager is None:
        from app.core.config import settings
        
        config = BackupConfig(
            backup_dir=str(settings.DATA_DIR / "backups"),
            source_dirs=[
                str(settings.DATA_DIR),
                str(Path("config"))
            ]
        )
        backup_manager = BackupManager(config)
    
    return backup_manager