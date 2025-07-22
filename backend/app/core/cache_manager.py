"""Sistema de cache inteligente em múltiplas camadas.

Este módulo implementa um sistema de cache avançado com:
- Cache em memória (L1) e disco (L2)
- Invalidação inteligente baseada em TTL e dependências
- Compressão automática para economizar espaço
- Métricas detalhadas de hit/miss ratio
- Suporte para cache distribuído
"""

import asyncio
import hashlib
import json
import logging
import pickle
import time
import zlib
from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from threading import Lock, RLock
from typing import Any, Dict, List, Optional, Set, Tuple, Union, Callable

import aiofiles
import redis.asyncio as redis
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class CacheLevel(Enum):
    """Níveis de cache disponíveis."""
    MEMORY = "memory"  # L1 - Cache em memória
    DISK = "disk"      # L2 - Cache em disco
    REDIS = "redis"    # Cache distribuído


class CompressionType(Enum):
    """Tipos de compressão suportados."""
    NONE = "none"
    ZLIB = "zlib"
    GZIP = "gzip"


@dataclass
class CacheEntry:
    """Entrada do cache com metadados."""
    key: str
    value: Any
    created_at: float
    expires_at: Optional[float] = None
    access_count: int = 0
    last_accessed: float = field(default_factory=time.time)
    size_bytes: int = 0
    compressed: bool = False
    compression_type: CompressionType = CompressionType.NONE
    dependencies: Set[str] = field(default_factory=set)
    tags: Set[str] = field(default_factory=set)
    
    def is_expired(self) -> bool:
        """Verifica se a entrada expirou."""
        if self.expires_at is None:
            return False
        return time.time() > self.expires_at
    
    def touch(self):
        """Atualiza timestamp de último acesso."""
        self.last_accessed = time.time()
        self.access_count += 1


@dataclass
class CacheMetrics:
    """Métricas do cache."""
    hits: int = 0
    misses: int = 0
    evictions: int = 0
    memory_usage_bytes: int = 0
    disk_usage_bytes: int = 0
    total_entries: int = 0
    compression_ratio: float = 0.0
    
    @property
    def hit_ratio(self) -> float:
        """Calcula taxa de acerto."""
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0
    
    @property
    def miss_ratio(self) -> float:
        """Calcula taxa de erro."""
        return 1.0 - self.hit_ratio


class CacheConfig(BaseModel):
    """Configuração do cache."""
    # Configurações gerais
    max_memory_size: int = 100 * 1024 * 1024  # 100MB
    max_disk_size: int = 1024 * 1024 * 1024   # 1GB
    default_ttl: int = 3600  # 1 hora
    
    # Compressão
    enable_compression: bool = True
    compression_threshold: int = 1024  # Comprimir se > 1KB
    compression_type: CompressionType = CompressionType.ZLIB
    
    # Limpeza automática
    cleanup_interval: int = 300  # 5 minutos
    max_entries_per_level: int = 10000
    
    # Cache em disco
    disk_cache_dir: str = "cache"
    
    # Redis (cache distribuído)
    redis_url: Optional[str] = None
    redis_prefix: str = "megaemu:cache:"
    
    # Métricas
    enable_metrics: bool = True
    metrics_interval: int = 60  # 1 minuto


class ICacheProvider(ABC):
    """Interface para provedores de cache."""
    
    @abstractmethod
    async def get(self, key: str) -> Optional[CacheEntry]:
        """Obtém entrada do cache."""
        pass
    
    @abstractmethod
    async def set(self, entry: CacheEntry) -> bool:
        """Armazena entrada no cache."""
        pass
    
    @abstractmethod
    async def delete(self, key: str) -> bool:
        """Remove entrada do cache."""
        pass
    
    @abstractmethod
    async def clear(self) -> bool:
        """Limpa todo o cache."""
        pass
    
    @abstractmethod
    async def get_size(self) -> int:
        """Retorna tamanho atual do cache em bytes."""
        pass
    
    @abstractmethod
    async def get_keys(self) -> List[str]:
        """Retorna todas as chaves do cache."""
        pass


class MemoryCacheProvider(ICacheProvider):
    """Provedor de cache em memória (L1)."""
    
    def __init__(self, config: CacheConfig):
        self.config = config
        self._cache: Dict[str, CacheEntry] = {}
        self._lock = RLock()
        self._current_size = 0
    
    async def get(self, key: str) -> Optional[CacheEntry]:
        """Obtém entrada do cache em memória."""
        with self._lock:
            entry = self._cache.get(key)
            if entry and not entry.is_expired():
                entry.touch()
                return entry
            elif entry:
                # Remove entrada expirada
                del self._cache[key]
                self._current_size -= entry.size_bytes
        return None
    
    async def set(self, entry: CacheEntry) -> bool:
        """Armazena entrada no cache em memória."""
        with self._lock:
            # Verifica se precisa fazer limpeza
            await self._ensure_space(entry.size_bytes)
            
            # Remove entrada existente se houver
            if entry.key in self._cache:
                old_entry = self._cache[entry.key]
                self._current_size -= old_entry.size_bytes
            
            # Adiciona nova entrada
            self._cache[entry.key] = entry
            self._current_size += entry.size_bytes
            
            return True
    
    async def delete(self, key: str) -> bool:
        """Remove entrada do cache em memória."""
        with self._lock:
            if key in self._cache:
                entry = self._cache.pop(key)
                self._current_size -= entry.size_bytes
                return True
        return False
    
    async def clear(self) -> bool:
        """Limpa todo o cache em memória."""
        with self._lock:
            self._cache.clear()
            self._current_size = 0
        return True
    
    async def get_size(self) -> int:
        """Retorna tamanho atual do cache em bytes."""
        return self._current_size
    
    async def get_keys(self) -> List[str]:
        """Retorna todas as chaves do cache."""
        with self._lock:
            return list(self._cache.keys())
    
    async def _ensure_space(self, needed_bytes: int):
        """Garante espaço suficiente no cache."""
        if self._current_size + needed_bytes <= self.config.max_memory_size:
            return
        
        # Ordena por último acesso (LRU)
        entries = sorted(
            self._cache.values(),
            key=lambda e: e.last_accessed
        )
        
        # Remove entradas até ter espaço suficiente
        for entry in entries:
            if self._current_size + needed_bytes <= self.config.max_memory_size:
                break
            
            del self._cache[entry.key]
            self._current_size -= entry.size_bytes


class DiskCacheProvider(ICacheProvider):
    """Provedor de cache em disco (L2)."""
    
    def __init__(self, config: CacheConfig):
        self.config = config
        self.cache_dir = Path(config.disk_cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._lock = asyncio.Lock()
    
    def _get_file_path(self, key: str) -> Path:
        """Gera caminho do arquivo para uma chave."""
        # Usa hash para evitar problemas com caracteres especiais
        key_hash = hashlib.sha256(key.encode()).hexdigest()
        return self.cache_dir / f"{key_hash}.cache"
    
    async def get(self, key: str) -> Optional[CacheEntry]:
        """Obtém entrada do cache em disco."""
        file_path = self._get_file_path(key)
        
        if not file_path.exists():
            return None
        
        try:
            async with aiofiles.open(file_path, 'rb') as f:
                data = await f.read()
                entry = pickle.loads(data)
                
                if entry.is_expired():
                    # Remove arquivo expirado
                    file_path.unlink(missing_ok=True)
                    return None
                
                entry.touch()
                return entry
                
        except Exception as e:
            logger.warning(f"Erro ao ler cache do disco {key}: {e}")
            file_path.unlink(missing_ok=True)
            return None
    
    async def set(self, entry: CacheEntry) -> bool:
        """Armazena entrada no cache em disco."""
        file_path = self._get_file_path(entry.key)
        
        try:
            async with self._lock:
                # Verifica espaço disponível
                await self._ensure_space(entry.size_bytes)
                
                # Serializa e salva
                data = pickle.dumps(entry)
                async with aiofiles.open(file_path, 'wb') as f:
                    await f.write(data)
                
                return True
                
        except Exception as e:
            logger.error(f"Erro ao salvar cache no disco {entry.key}: {e}")
            return False
    
    async def delete(self, key: str) -> bool:
        """Remove entrada do cache em disco."""
        file_path = self._get_file_path(key)
        try:
            file_path.unlink(missing_ok=True)
            return True
        except Exception as e:
            logger.warning(f"Erro ao remover cache do disco {key}: {e}")
            return False
    
    async def clear(self) -> bool:
        """Limpa todo o cache em disco."""
        try:
            for file_path in self.cache_dir.glob("*.cache"):
                file_path.unlink(missing_ok=True)
            return True
        except Exception as e:
            logger.error(f"Erro ao limpar cache do disco: {e}")
            return False
    
    async def get_size(self) -> int:
        """Retorna tamanho atual do cache em bytes."""
        total_size = 0
        try:
            for file_path in self.cache_dir.glob("*.cache"):
                total_size += file_path.stat().st_size
        except Exception as e:
            logger.warning(f"Erro ao calcular tamanho do cache: {e}")
        return total_size
    
    async def get_keys(self) -> List[str]:
        """Retorna todas as chaves do cache."""
        keys = []
        try:
            for file_path in self.cache_dir.glob("*.cache"):
                try:
                    async with aiofiles.open(file_path, 'rb') as f:
                        data = await f.read()
                        entry = pickle.loads(data)
                        if not entry.is_expired():
                            keys.append(entry.key)
                        else:
                            # Remove arquivo expirado
                            file_path.unlink(missing_ok=True)
                except Exception:
                    # Remove arquivo corrompido
                    file_path.unlink(missing_ok=True)
        except Exception as e:
            logger.warning(f"Erro ao listar chaves do cache: {e}")
        return keys
    
    async def _ensure_space(self, needed_bytes: int):
        """Garante espaço suficiente no cache."""
        current_size = await self.get_size()
        
        if current_size + needed_bytes <= self.config.max_disk_size:
            return
        
        # Lista arquivos por data de modificação (LRU)
        files = []
        for file_path in self.cache_dir.glob("*.cache"):
            try:
                stat = file_path.stat()
                files.append((file_path, stat.st_mtime, stat.st_size))
            except Exception:
                continue
        
        # Ordena por último acesso
        files.sort(key=lambda x: x[1])
        
        # Remove arquivos até ter espaço suficiente
        for file_path, _, file_size in files:
            if current_size + needed_bytes <= self.config.max_disk_size:
                break
            
            try:
                file_path.unlink()
                current_size -= file_size
            except Exception:
                continue


class RedisCacheProvider(ICacheProvider):
    """Provedor de cache distribuído usando Redis."""
    
    def __init__(self, config: CacheConfig):
        self.config = config
        self._redis: Optional[redis.Redis] = None
        self._lock = asyncio.Lock()
    
    async def _get_redis(self) -> redis.Redis:
        """Obtém conexão Redis."""
        if self._redis is None:
            if not self.config.redis_url:
                raise ValueError("URL do Redis não configurada")
            
            self._redis = redis.from_url(self.config.redis_url)
        
        return self._redis
    
    def _get_key(self, key: str) -> str:
        """Adiciona prefixo à chave."""
        return f"{self.config.redis_prefix}{key}"
    
    async def get(self, key: str) -> Optional[CacheEntry]:
        """Obtém entrada do cache Redis."""
        try:
            redis_client = await self._get_redis()
            data = await redis_client.get(self._get_key(key))
            
            if data:
                entry = pickle.loads(data)
                if not entry.is_expired():
                    entry.touch()
                    return entry
                else:
                    # Remove entrada expirada
                    await redis_client.delete(self._get_key(key))
            
        except Exception as e:
            logger.warning(f"Erro ao ler cache do Redis {key}: {e}")
        
        return None
    
    async def set(self, entry: CacheEntry) -> bool:
        """Armazena entrada no cache Redis."""
        try:
            redis_client = await self._get_redis()
            data = pickle.dumps(entry)
            
            # Calcula TTL
            ttl = None
            if entry.expires_at:
                ttl = int(entry.expires_at - time.time())
                if ttl <= 0:
                    return False
            
            # Armazena no Redis
            await redis_client.set(
                self._get_key(entry.key),
                data,
                ex=ttl
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Erro ao salvar cache no Redis {entry.key}: {e}")
            return False
    
    async def delete(self, key: str) -> bool:
        """Remove entrada do cache Redis."""
        try:
            redis_client = await self._get_redis()
            result = await redis_client.delete(self._get_key(key))
            return result > 0
        except Exception as e:
            logger.warning(f"Erro ao remover cache do Redis {key}: {e}")
            return False
    
    async def clear(self) -> bool:
        """Limpa todo o cache Redis."""
        try:
            redis_client = await self._get_redis()
            pattern = f"{self.config.redis_prefix}*"
            
            # Busca todas as chaves com o prefixo
            keys = []
            async for key in redis_client.scan_iter(match=pattern):
                keys.append(key)
            
            # Remove em lotes
            if keys:
                await redis_client.delete(*keys)
            
            return True
            
        except Exception as e:
            logger.error(f"Erro ao limpar cache do Redis: {e}")
            return False
    
    async def get_size(self) -> int:
        """Retorna tamanho aproximado do cache Redis."""
        try:
            redis_client = await self._get_redis()
            total_size = 0
            
            pattern = f"{self.config.redis_prefix}*"
            async for key in redis_client.scan_iter(match=pattern):
                size = await redis_client.memory_usage(key)
                if size:
                    total_size += size
            
            return total_size
            
        except Exception as e:
            logger.warning(f"Erro ao calcular tamanho do cache Redis: {e}")
            return 0
    
    async def get_keys(self) -> List[str]:
        """Retorna todas as chaves do cache Redis."""
        try:
            redis_client = await self._get_redis()
            keys = []
            
            pattern = f"{self.config.redis_prefix}*"
            async for key in redis_client.scan_iter(match=pattern):
                # Remove prefixo
                clean_key = key.decode().replace(self.config.redis_prefix, "")
                keys.append(clean_key)
            
            return keys
            
        except Exception as e:
            logger.warning(f"Erro ao listar chaves do cache Redis: {e}")
            return []


class MultiLevelCacheManager:
    """Gerenciador de cache em múltiplas camadas."""
    
    def __init__(self, config: CacheConfig):
        self.config = config
        self.metrics = CacheMetrics()
        self._providers: Dict[CacheLevel, ICacheProvider] = {}
        self._compression_cache: Dict[str, bytes] = {}
        self._dependency_graph: Dict[str, Set[str]] = {}
        self._tag_index: Dict[str, Set[str]] = {}
        self._cleanup_task: Optional[asyncio.Task] = None
        self._metrics_task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()
        
        # Inicializa provedores
        self._init_providers()
    
    def _init_providers(self):
        """Inicializa provedores de cache."""
        # Cache em memória (L1)
        self._providers[CacheLevel.MEMORY] = MemoryCacheProvider(self.config)
        
        # Cache em disco (L2)
        self._providers[CacheLevel.DISK] = DiskCacheProvider(self.config)
        
        # Cache Redis (distribuído)
        if self.config.redis_url:
            self._providers[CacheLevel.REDIS] = RedisCacheProvider(self.config)
    
    async def start(self):
        """Inicia o gerenciador de cache."""
        # Inicia tarefas de limpeza e métricas
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        
        if self.config.enable_metrics:
            self._metrics_task = asyncio.create_task(self._metrics_loop())
        
        logger.info("Gerenciador de cache iniciado")
    
    async def stop(self):
        """Para o gerenciador de cache."""
        # Cancela tarefas
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        
        if self._metrics_task:
            self._metrics_task.cancel()
            try:
                await self._metrics_task
            except asyncio.CancelledError:
                pass
        
        # Fecha conexões Redis
        if CacheLevel.REDIS in self._providers:
            redis_provider = self._providers[CacheLevel.REDIS]
            if hasattr(redis_provider, '_redis') and redis_provider._redis:
                await redis_provider._redis.close()
        
        logger.info("Gerenciador de cache parado")
    
    async def get(self, key: str, default: Any = None) -> Any:
        """Obtém valor do cache.
        
        Busca em ordem: Memória -> Disco -> Redis
        Promove valores encontrados para níveis superiores.
        """
        # Busca em cada nível
        for level in [CacheLevel.MEMORY, CacheLevel.DISK, CacheLevel.REDIS]:
            if level not in self._providers:
                continue
            
            provider = self._providers[level]
            entry = await provider.get(key)
            
            if entry:
                # Hit - atualiza métricas
                self.metrics.hits += 1
                
                # Descomprime se necessário
                value = await self._decompress_value(entry)
                
                # Promove para níveis superiores
                await self._promote_entry(entry, level)
                
                return value
        
        # Miss - atualiza métricas
        self.metrics.misses += 1
        return default
    
    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
        tags: Optional[Set[str]] = None,
        dependencies: Optional[Set[str]] = None,
        levels: Optional[List[CacheLevel]] = None
    ) -> bool:
        """Armazena valor no cache.
        
        Args:
            key: Chave do cache
            value: Valor a ser armazenado
            ttl: Tempo de vida em segundos
            tags: Tags para agrupamento
            dependencies: Dependências para invalidação
            levels: Níveis específicos para armazenar
        """
        # Calcula TTL
        expires_at = None
        if ttl is not None:
            expires_at = time.time() + ttl
        elif self.config.default_ttl > 0:
            expires_at = time.time() + self.config.default_ttl
        
        # Comprime valor se necessário
        compressed_value, compressed, compression_type = await self._compress_value(value)
        
        # Calcula tamanho
        size_bytes = len(pickle.dumps(compressed_value))
        
        # Cria entrada
        entry = CacheEntry(
            key=key,
            value=compressed_value,
            created_at=time.time(),
            expires_at=expires_at,
            size_bytes=size_bytes,
            compressed=compressed,
            compression_type=compression_type,
            dependencies=dependencies or set(),
            tags=tags or set()
        )
        
        # Atualiza índices
        await self._update_indexes(entry)
        
        # Armazena nos níveis especificados
        target_levels = levels or [CacheLevel.MEMORY, CacheLevel.DISK]
        if CacheLevel.REDIS in self._providers and CacheLevel.REDIS not in target_levels:
            target_levels.append(CacheLevel.REDIS)
        
        success = True
        for level in target_levels:
            if level in self._providers:
                result = await self._providers[level].set(entry)
                success = success and result
        
        return success
    
    async def delete(self, key: str) -> bool:
        """Remove entrada do cache."""
        success = True
        
        # Remove de todos os níveis
        for provider in self._providers.values():
            result = await provider.delete(key)
            success = success and result
        
        # Remove dos índices
        await self._remove_from_indexes(key)
        
        return success
    
    async def invalidate_by_tag(self, tag: str) -> int:
        """Invalida todas as entradas com uma tag específica."""
        if tag not in self._tag_index:
            return 0
        
        keys = self._tag_index[tag].copy()
        count = 0
        
        for key in keys:
            if await self.delete(key):
                count += 1
        
        return count
    
    async def invalidate_by_dependency(self, dependency: str) -> int:
        """Invalida todas as entradas que dependem de uma chave."""
        if dependency not in self._dependency_graph:
            return 0
        
        keys = self._dependency_graph[dependency].copy()
        count = 0
        
        for key in keys:
            if await self.delete(key):
                count += 1
        
        return count
    
    async def clear(self, levels: Optional[List[CacheLevel]] = None) -> bool:
        """Limpa cache."""
        target_levels = levels or list(self._providers.keys())
        success = True
        
        for level in target_levels:
            if level in self._providers:
                result = await self._providers[level].clear()
                success = success and result
        
        # Limpa índices
        self._dependency_graph.clear()
        self._tag_index.clear()
        
        return success
    
    async def get_metrics(self) -> CacheMetrics:
        """Retorna métricas atuais do cache."""
        # Atualiza métricas de uso
        self.metrics.memory_usage_bytes = await self._providers[CacheLevel.MEMORY].get_size()
        self.metrics.disk_usage_bytes = await self._providers[CacheLevel.DISK].get_size()
        
        # Conta total de entradas
        total_entries = 0
        for provider in self._providers.values():
            keys = await provider.get_keys()
            total_entries += len(keys)
        
        self.metrics.total_entries = total_entries
        
        return self.metrics
    
    async def _compress_value(self, value: Any) -> Tuple[Any, bool, CompressionType]:
        """Comprime valor se necessário."""
        if not self.config.enable_compression:
            return value, False, CompressionType.NONE
        
        # Serializa valor
        data = pickle.dumps(value)
        
        # Verifica se deve comprimir
        if len(data) < self.config.compression_threshold:
            return value, False, CompressionType.NONE
        
        # Comprime
        try:
            if self.config.compression_type == CompressionType.ZLIB:
                compressed_data = zlib.compress(data)
            else:
                compressed_data = data
            
            # Verifica se compressão foi efetiva
            if len(compressed_data) < len(data):
                return compressed_data, True, self.config.compression_type
            else:
                return value, False, CompressionType.NONE
                
        except Exception as e:
            logger.warning(f"Erro na compressão: {e}")
            return value, False, CompressionType.NONE
    
    async def _decompress_value(self, entry: CacheEntry) -> Any:
        """Descomprime valor se necessário."""
        if not entry.compressed:
            return entry.value
        
        try:
            if entry.compression_type == CompressionType.ZLIB:
                decompressed_data = zlib.decompress(entry.value)
                return pickle.loads(decompressed_data)
            else:
                return entry.value
                
        except Exception as e:
            logger.error(f"Erro na descompressão: {e}")
            return entry.value
    
    async def _promote_entry(self, entry: CacheEntry, found_level: CacheLevel):
        """Promove entrada para níveis superiores."""
        # Define ordem de prioridade
        level_priority = {
            CacheLevel.MEMORY: 0,
            CacheLevel.DISK: 1,
            CacheLevel.REDIS: 2
        }
        
        current_priority = level_priority[found_level]
        
        # Promove para níveis com prioridade maior
        for level, priority in level_priority.items():
            if priority < current_priority and level in self._providers:
                await self._providers[level].set(entry)
    
    async def _update_indexes(self, entry: CacheEntry):
        """Atualiza índices de tags e dependências."""
        # Índice de tags
        for tag in entry.tags:
            if tag not in self._tag_index:
                self._tag_index[tag] = set()
            self._tag_index[tag].add(entry.key)
        
        # Índice de dependências
        for dependency in entry.dependencies:
            if dependency not in self._dependency_graph:
                self._dependency_graph[dependency] = set()
            self._dependency_graph[dependency].add(entry.key)
    
    async def _remove_from_indexes(self, key: str):
        """Remove chave dos índices."""
        # Remove de tags
        for tag_keys in self._tag_index.values():
            tag_keys.discard(key)
        
        # Remove de dependências
        for dep_keys in self._dependency_graph.values():
            dep_keys.discard(key)
    
    async def _cleanup_loop(self):
        """Loop de limpeza automática."""
        while True:
            try:
                await asyncio.sleep(self.config.cleanup_interval)
                await self._cleanup_expired()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Erro na limpeza automática: {e}")
    
    async def _cleanup_expired(self):
        """Remove entradas expiradas."""
        for provider in self._providers.values():
            try:
                keys = await provider.get_keys()
                for key in keys:
                    entry = await provider.get(key)
                    if entry and entry.is_expired():
                        await provider.delete(key)
                        self.metrics.evictions += 1
            except Exception as e:
                logger.warning(f"Erro na limpeza de expirados: {e}")
    
    async def _metrics_loop(self):
        """Loop de coleta de métricas."""
        while True:
            try:
                await asyncio.sleep(self.config.metrics_interval)
                metrics = await self.get_metrics()
                logger.info(
                    f"Cache metrics - Hit ratio: {metrics.hit_ratio:.2%}, "
                    f"Memory: {metrics.memory_usage_bytes / 1024 / 1024:.1f}MB, "
                    f"Disk: {metrics.disk_usage_bytes / 1024 / 1024:.1f}MB, "
                    f"Entries: {metrics.total_entries}"
                )
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Erro na coleta de métricas: {e}")


# Instância global
cache_manager: Optional[MultiLevelCacheManager] = None


def get_cache_manager() -> MultiLevelCacheManager:
    """Obtém instância global do gerenciador de cache."""
    global cache_manager
    if cache_manager is None:
        from app.core.config import settings
        
        config = CacheConfig(
            redis_url=settings.REDIS_URL,
            disk_cache_dir=str(settings.DATA_DIR / "cache")
        )
        cache_manager = MultiLevelCacheManager(config)
    
    return cache_manager


# Decorador para cache automático
def cached(
    ttl: Optional[int] = None,
    tags: Optional[Set[str]] = None,
    dependencies: Optional[Set[str]] = None,
    key_func: Optional[Callable] = None
):
    """Decorador para cache automático de funções.
    
    Args:
        ttl: Tempo de vida em segundos
        tags: Tags para agrupamento
        dependencies: Dependências para invalidação
        key_func: Função para gerar chave customizada
    """
    def decorator(func):
        async def wrapper(*args, **kwargs):
            # Gera chave do cache
            if key_func:
                cache_key = key_func(*args, **kwargs)
            else:
                # Gera chave baseada no nome da função e argumentos
                key_parts = [func.__name__]
                key_parts.extend(str(arg) for arg in args)
                key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
                cache_key = ":".join(key_parts)
            
            # Busca no cache
            cache = get_cache_manager()
            result = await cache.get(cache_key)
            
            if result is not None:
                return result
            
            # Executa função
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
            
            # Armazena no cache
            await cache.set(
                cache_key,
                result,
                ttl=ttl,
                tags=tags,
                dependencies=dependencies
            )
            
            return result
        
        return wrapper
    return decorator