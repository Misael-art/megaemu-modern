"""Configuração e utilitários para Redis no MegaEmu Modern.

Gerencia conexões com Redis para cache, sessões e
filas de tarefas assíncronas.
"""

import json
import pickle
from typing import Any, Optional, Union, Dict, List
from datetime import timedelta

import redis.asyncio as redis
from loguru import logger

from app.core.config import settings


class RedisManager:
    """Gerenciador de conexões e operações Redis.
    
    Fornece interface unificada para operações de cache,
    sessões e filas com Redis.
    """
    
    def __init__(self):
        self._client: Optional[redis.Redis] = None
        self._pool: Optional[redis.ConnectionPool] = None
    
    async def connect(self) -> None:
        """Estabelece conexão com Redis."""
        try:
            # Criar pool de conexões
            self._pool = redis.ConnectionPool.from_url(
                settings.REDIS_URL,
                max_connections=20,
                retry_on_timeout=True,
                socket_keepalive=True,
                socket_keepalive_options={},
                health_check_interval=30,
            )
            
            # Criar cliente Redis
            self._client = redis.Redis(
                connection_pool=self._pool,
                decode_responses=False,  # Manter bytes para pickle
            )
            
            # Testar conexão
            await self._client.ping()
            logger.info("✅ Conexão com Redis estabelecida")
            
        except Exception as e:
            logger.error(f"❌ Erro ao conectar com Redis: {e}")
            raise
    
    async def disconnect(self) -> None:
        """Fecha conexão com Redis."""
        if self._client:
            await self._client.close()
        if self._pool:
            await self._pool.disconnect()
        logger.info("Redis desconectado")
    
    @property
    def client(self) -> redis.Redis:
        """Retorna cliente Redis."""
        if not self._client:
            raise RuntimeError("Redis não está conectado")
        return self._client
    
    async def ping(self) -> bool:
        """Verifica se Redis está respondendo."""
        try:
            await self.client.ping()
            return True
        except Exception:
            return False
    
    async def get_info(self) -> Dict[str, Any]:
        """Retorna informações do servidor Redis."""
        try:
            info = await self.client.info()
            return {
                "version": info.get("redis_version"),
                "uptime": info.get("uptime_in_seconds"),
                "connected_clients": info.get("connected_clients"),
                "used_memory": info.get("used_memory_human"),
                "total_commands_processed": info.get("total_commands_processed"),
                "keyspace_hits": info.get("keyspace_hits"),
                "keyspace_misses": info.get("keyspace_misses"),
            }
        except Exception as e:
            logger.error(f"Erro ao obter informações do Redis: {e}")
            return {}


class CacheManager:
    """Gerenciador de cache usando Redis.
    
    Fornece interface simples para operações de cache
    com serialização automática.
    """
    
    def __init__(self, redis_manager: RedisManager, prefix: str = "cache:"):
        self.redis_manager = redis_manager
        self.prefix = prefix
    
    def _make_key(self, key: str) -> str:
        """Cria chave com prefixo."""
        return f"{self.prefix}{key}"
    
    async def get(self, key: str, default: Any = None) -> Any:
        """Recupera valor do cache.
        
        Args:
            key: Chave do cache
            default: Valor padrão se não encontrado
            
        Returns:
            Valor deserializado ou default
        """
        try:
            value = await self.redis_manager.client.get(self._make_key(key))
            if value is None:
                return default
            return pickle.loads(value)
        except Exception as e:
            logger.warning(f"Erro ao recuperar cache {key}: {e}")
            return default
    
    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[Union[int, timedelta]] = None
    ) -> bool:
        """Armazena valor no cache.
        
        Args:
            key: Chave do cache
            value: Valor a ser armazenado
            ttl: Tempo de vida (segundos ou timedelta)
            
        Returns:
            True se armazenado com sucesso
        """
        try:
            serialized = pickle.dumps(value)
            
            if ttl:
                if isinstance(ttl, timedelta):
                    ttl = int(ttl.total_seconds())
                await self.redis_manager.client.setex(
                    self._make_key(key), ttl, serialized
                )
            else:
                await self.redis_manager.client.set(
                    self._make_key(key), serialized
                )
            return True
        except Exception as e:
            logger.error(f"Erro ao armazenar cache {key}: {e}")
            return False
    
    async def delete(self, key: str) -> bool:
        """Remove valor do cache.
        
        Args:
            key: Chave do cache
            
        Returns:
            True se removido com sucesso
        """
        try:
            result = await self.redis_manager.client.delete(self._make_key(key))
            return result > 0
        except Exception as e:
            logger.error(f"Erro ao remover cache {key}: {e}")
            return False
    
    async def exists(self, key: str) -> bool:
        """Verifica se chave existe no cache.
        
        Args:
            key: Chave do cache
            
        Returns:
            True se existe
        """
        try:
            result = await self.redis_manager.client.exists(self._make_key(key))
            return result > 0
        except Exception as e:
            logger.error(f"Erro ao verificar cache {key}: {e}")
            return False
    
    async def clear_pattern(self, pattern: str) -> int:
        """Remove todas as chaves que correspondem ao padrão.
        
        Args:
            pattern: Padrão de chaves (ex: "user:*")
            
        Returns:
            Número de chaves removidas
        """
        try:
            keys = await self.redis_manager.client.keys(self._make_key(pattern))
            if keys:
                return await self.redis_manager.client.delete(*keys)
            return 0
        except Exception as e:
            logger.error(f"Erro ao limpar cache com padrão {pattern}: {e}")
            return 0
    
    async def increment(self, key: str, amount: int = 1) -> int:
        """Incrementa valor numérico no cache.
        
        Args:
            key: Chave do cache
            amount: Valor a incrementar
            
        Returns:
            Novo valor após incremento
        """
        try:
            return await self.redis_manager.client.incrby(
                self._make_key(key), amount
            )
        except Exception as e:
            logger.error(f"Erro ao incrementar cache {key}: {e}")
            return 0
    
    async def get_ttl(self, key: str) -> int:
        """Retorna tempo de vida restante da chave.
        
        Args:
            key: Chave do cache
            
        Returns:
            TTL em segundos (-1 se sem TTL, -2 se não existe)
        """
        try:
            return await self.redis_manager.client.ttl(self._make_key(key))
        except Exception as e:
            logger.error(f"Erro ao obter TTL do cache {key}: {e}")
            return -2


class SessionManager:
    """Gerenciador de sessões usando Redis.
    
    Armazena dados de sessão de usuários com expiração automática.
    """
    
    def __init__(self, redis_manager: RedisManager, prefix: str = "session:"):
        self.redis_manager = redis_manager
        self.prefix = prefix
        self.default_ttl = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    
    def _make_key(self, session_id: str) -> str:
        """Cria chave de sessão."""
        return f"{self.prefix}{session_id}"
    
    async def create_session(
        self,
        session_id: str,
        data: Dict[str, Any],
        ttl: Optional[int] = None
    ) -> bool:
        """Cria nova sessão.
        
        Args:
            session_id: ID da sessão
            data: Dados da sessão
            ttl: Tempo de vida em segundos
            
        Returns:
            True se criada com sucesso
        """
        try:
            serialized = json.dumps(data)
            ttl = ttl or self.default_ttl
            
            await self.redis_manager.client.setex(
                self._make_key(session_id), ttl, serialized
            )
            return True
        except Exception as e:
            logger.error(f"Erro ao criar sessão {session_id}: {e}")
            return False
    
    async def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Recupera dados da sessão.
        
        Args:
            session_id: ID da sessão
            
        Returns:
            Dados da sessão ou None se não encontrada
        """
        try:
            data = await self.redis_manager.client.get(self._make_key(session_id))
            if data:
                return json.loads(data)
            return None
        except Exception as e:
            logger.error(f"Erro ao recuperar sessão {session_id}: {e}")
            return None
    
    async def update_session(
        self,
        session_id: str,
        data: Dict[str, Any],
        extend_ttl: bool = True
    ) -> bool:
        """Atualiza dados da sessão.
        
        Args:
            session_id: ID da sessão
            data: Novos dados da sessão
            extend_ttl: Se deve estender TTL
            
        Returns:
            True se atualizada com sucesso
        """
        try:
            key = self._make_key(session_id)
            
            # Obter TTL atual se não deve estender
            ttl = self.default_ttl
            if not extend_ttl:
                current_ttl = await self.redis_manager.client.ttl(key)
                if current_ttl > 0:
                    ttl = current_ttl
            
            serialized = json.dumps(data)
            await self.redis_manager.client.setex(key, ttl, serialized)
            return True
        except Exception as e:
            logger.error(f"Erro ao atualizar sessão {session_id}: {e}")
            return False
    
    async def delete_session(self, session_id: str) -> bool:
        """Remove sessão.
        
        Args:
            session_id: ID da sessão
            
        Returns:
            True se removida com sucesso
        """
        try:
            result = await self.redis_manager.client.delete(
                self._make_key(session_id)
            )
            return result > 0
        except Exception as e:
            logger.error(f"Erro ao remover sessão {session_id}: {e}")
            return False
    
    async def extend_session(self, session_id: str, ttl: Optional[int] = None) -> bool:
        """Estende tempo de vida da sessão.
        
        Args:
            session_id: ID da sessão
            ttl: Novo TTL em segundos
            
        Returns:
            True se estendida com sucesso
        """
        try:
            ttl = ttl or self.default_ttl
            result = await self.redis_manager.client.expire(
                self._make_key(session_id), ttl
            )
            return result
        except Exception as e:
            logger.error(f"Erro ao estender sessão {session_id}: {e}")
            return False


# Instâncias globais
redis_manager = RedisManager()
cache_manager = CacheManager(redis_manager)
session_manager = SessionManager(redis_manager)


# Funções de conveniência
async def init_redis() -> None:
    """Inicializa conexão com Redis."""
    await redis_manager.connect()


async def close_redis() -> None:
    """Fecha conexão com Redis."""
    await redis_manager.disconnect()


async def get_cache(key: str, default: Any = None) -> Any:
    """Função de conveniência para obter cache."""
    return await cache_manager.get(key, default)


async def set_cache(
    key: str,
    value: Any,
    ttl: Optional[Union[int, timedelta]] = None
) -> bool:
    """Função de conveniência para definir cache."""
    return await cache_manager.set(key, value, ttl)


async def delete_cache(key: str) -> bool:
    """Função de conveniência para deletar cache."""
    return await cache_manager.delete(key)