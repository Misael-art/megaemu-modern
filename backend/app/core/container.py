"""Container avançado para injeção de dependências.

Fornece sistema de DI com lazy loading, factory patterns,
configuração de lifetime e resolução automática de dependências.
"""

import asyncio
import inspect
import logging
import threading
import weakref
from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
from typing import Any, Callable, Dict, List, Optional, Type, TypeVar, Union, get_type_hints
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)

T = TypeVar('T')


class ServiceLifetime(str, Enum):
    """Lifetimes disponíveis para serviços."""
    SINGLETON = "singleton"  # Uma instância para toda a aplicação
    SCOPED = "scoped"       # Uma instância por escopo (request)
    TRANSIENT = "transient" # Nova instância a cada resolução
    LAZY = "lazy"           # Singleton com inicialização lazy


@dataclass
class ServiceDescriptor:
    """Descritor de um serviço registrado."""
    interface: Type
    implementation: Optional[Type] = None
    factory: Optional[Callable] = None
    lifetime: ServiceLifetime = ServiceLifetime.TRANSIENT
    dependencies: List[Type] = None
    lazy_init: bool = False
    
    def __post_init__(self):
        if self.dependencies is None:
            self.dependencies = []


class ServiceScope:
    """Escopo para serviços com lifetime SCOPED."""
    
    def __init__(self, container: 'Container'):
        self.container = container
        self._scoped_instances: Dict[Type, Any] = {}
        self._lock = threading.RLock()
    
    def get_scoped_instance(self, service_type: Type[T]) -> Optional[T]:
        """Obtém instância no escopo atual."""
        with self._lock:
            return self._scoped_instances.get(service_type)
    
    def set_scoped_instance(self, service_type: Type[T], instance: T):
        """Define instância no escopo atual."""
        with self._lock:
            self._scoped_instances[service_type] = instance
    
    def dispose(self):
        """Limpa o escopo e chama dispose em instâncias que suportam."""
        with self._lock:
            for instance in self._scoped_instances.values():
                if hasattr(instance, 'dispose'):
                    try:
                        instance.dispose()
                    except Exception as e:
                        logger.warning(f"Erro ao fazer dispose de {type(instance)}: {e}")
            self._scoped_instances.clear()


class IServiceFactory(ABC):
    """Interface para factories de serviços."""
    
    @abstractmethod
    def create(self, container: 'Container', scope: Optional[ServiceScope] = None) -> Any:
        """Cria uma instância do serviço."""
        pass


class LazyProxy:
    """Proxy para inicialização lazy de serviços."""
    
    def __init__(self, container: 'Container', service_type: Type[T]):
        self._container = container
        self._service_type = service_type
        self._instance: Optional[T] = None
        self._lock = threading.RLock()
    
    def _get_instance(self) -> T:
        """Obtém a instância, criando se necessário."""
        if self._instance is None:
            with self._lock:
                if self._instance is None:
                    self._instance = self._container._create_instance(self._service_type)
        return self._instance
    
    def __getattr__(self, name: str):
        return getattr(self._get_instance(), name)
    
    def __call__(self, *args, **kwargs):
        return self._get_instance()(*args, **kwargs)


class Container:
    """Container avançado para gerenciamento de dependências."""
    
    def __init__(self):
        self._descriptors: Dict[Type, ServiceDescriptor] = {}
        self._singletons: Dict[Type, Any] = {}
        self._lazy_proxies: Dict[Type, LazyProxy] = {}
        self._lock = threading.RLock()
        self._current_scope: Optional[ServiceScope] = None
        self._scope_stack: List[ServiceScope] = []
        
        # Cache de dependências resolvidas
        self._dependency_cache: Dict[Type, List[Type]] = {}
        
        # Registro de factories customizadas
        self._custom_factories: Dict[Type, IServiceFactory] = {}
    
    def register(
        self,
        interface: Type[T],
        implementation: Optional[Type[T]] = None,
        factory: Optional[Callable[..., T]] = None,
        lifetime: ServiceLifetime = ServiceLifetime.TRANSIENT,
        lazy_init: bool = False
    ) -> 'Container':
        """Registra um serviço no container.
        
        Args:
            interface: Interface ou tipo do serviço
            implementation: Implementação concreta (opcional)
            factory: Factory function (opcional)
            lifetime: Lifetime do serviço
            lazy_init: Se deve usar inicialização lazy
            
        Returns:
            Self para method chaining
        """
        if not implementation and not factory:
            # Auto-registro: interface é a própria implementação
            implementation = interface
        
        if implementation and factory:
            raise ValueError("Forneça apenas implementation OU factory, não ambos")
        
        # Resolve dependências automaticamente
        dependencies = self._resolve_dependencies(implementation or factory)
        
        descriptor = ServiceDescriptor(
            interface=interface,
            implementation=implementation,
            factory=factory,
            lifetime=lifetime,
            dependencies=dependencies,
            lazy_init=lazy_init
        )
        
        with self._lock:
            self._descriptors[interface] = descriptor
            
            # Remove instâncias existentes se re-registrando
            self._singletons.pop(interface, None)
            self._lazy_proxies.pop(interface, None)
        
        logger.debug(f"Serviço registrado: {interface.__name__} -> {lifetime.value}")
        return self
    
    def get(self, interface: Type[T], scope: Optional[ServiceScope] = None) -> T:
        """Resolve uma dependência.
        
        Args:
            interface: Tipo do serviço a resolver
            scope: Escopo atual (opcional)
            
        Returns:
            Instância do serviço
            
        Raises:
            ValueError: Se serviço não estiver registrado
        """
        with self._lock:
            if interface not in self._descriptors:
                raise ValueError(f"Serviço não registrado: {interface.__name__}")
            
            descriptor = self._descriptors[interface]
            current_scope = scope or self._current_scope
            
            # Singleton: retorna instância existente ou cria nova
            if descriptor.lifetime == ServiceLifetime.SINGLETON:
                if interface in self._singletons:
                    return self._singletons[interface]
                
                instance = self._create_instance(interface, current_scope)
                self._singletons[interface] = instance
                return instance
            
            # Lazy: retorna proxy que criará instância quando necessário
            elif descriptor.lifetime == ServiceLifetime.LAZY or descriptor.lazy_init:
                if interface not in self._lazy_proxies:
                    self._lazy_proxies[interface] = LazyProxy(self, interface)
                return self._lazy_proxies[interface]
            
            # Scoped: uma instância por escopo
            elif descriptor.lifetime == ServiceLifetime.SCOPED:
                if current_scope:
                    scoped_instance = current_scope.get_scoped_instance(interface)
                    if scoped_instance is not None:
                        return scoped_instance
                    
                    instance = self._create_instance(interface, current_scope)
                    current_scope.set_scoped_instance(interface, instance)
                    return instance
                else:
                    # Sem escopo, comporta-se como transient
                    return self._create_instance(interface, current_scope)
            
            # Transient: nova instância a cada resolução
            else:
                return self._create_instance(interface, current_scope)
    
    def _create_instance(self, interface: Type[T], scope: Optional[ServiceScope] = None) -> T:
        """Cria uma nova instância do serviço."""
        descriptor = self._descriptors[interface]
        
        try:
            # Factory customizada
            if interface in self._custom_factories:
                return self._custom_factories[interface].create(self, scope)
            
            # Factory function
            elif descriptor.factory:
                # Injeta dependências na factory
                return self._call_with_injection(descriptor.factory, scope)
            
            # Implementação concreta
            elif descriptor.implementation:
                # Injeta dependências no construtor
                return self._call_with_injection(descriptor.implementation, scope)
            
            else:
                raise ValueError(f"Nenhuma implementação ou factory definida para {interface.__name__}")
                
        except Exception as e:
            logger.error(f"Erro ao criar instância de {interface.__name__}: {e}")
            raise
    
    def _call_with_injection(self, callable_obj: Callable, scope: Optional[ServiceScope] = None) -> Any:
        """Chama um callable injetando suas dependências automaticamente."""
        # Obtém assinatura do callable
        sig = inspect.signature(callable_obj)
        kwargs = {}
        
        for param_name, param in sig.parameters.items():
            # Pula parâmetros sem type hint ou com valores padrão
            if param.annotation == inspect.Parameter.empty:
                continue
            
            if param.default != inspect.Parameter.empty:
                continue
            
            # Resolve dependência
            try:
                dependency = self.get(param.annotation, scope)
                kwargs[param_name] = dependency
            except ValueError:
                # Dependência não registrada, pula se tiver valor padrão
                if param.default == inspect.Parameter.empty:
                    logger.warning(f"Dependência não registrada: {param.annotation.__name__}")
        
        return callable_obj(**kwargs)
    
    def _resolve_dependencies(self, target: Optional[Callable]) -> List[Type]:
        """Resolve dependências de um callable automaticamente."""
        if not target:
            return []
        
        if target in self._dependency_cache:
            return self._dependency_cache[target]
        
        dependencies = []
        
        try:
            sig = inspect.signature(target)
            for param in sig.parameters.values():
                if param.annotation != inspect.Parameter.empty:
                    # Adiciona apenas se não for tipo primitivo
                    if not self._is_primitive_type(param.annotation):
                        dependencies.append(param.annotation)
        except (ValueError, TypeError):
            # Não conseguiu obter assinatura
            pass
        
        self._dependency_cache[target] = dependencies
        return dependencies
    
    def _is_primitive_type(self, type_hint: Type) -> bool:
        """Verifica se um tipo é primitivo (não deve ser injetado)."""
        primitive_types = {int, float, str, bool, bytes, type(None)}
        return type_hint in primitive_types
    
    def register_instance(self, interface: Type[T], instance: T) -> 'Container':
        """Registra uma instância específica como singleton.
        
        Args:
            interface: Interface do serviço
            instance: Instância a ser registrada
            
        Returns:
            Self para method chaining
        """
        with self._lock:
            self._singletons[interface] = instance
            
            # Cria descriptor para a instância
            descriptor = ServiceDescriptor(
                interface=interface,
                lifetime=ServiceLifetime.SINGLETON
            )
            self._descriptors[interface] = descriptor
        
        logger.debug(f"Instância registrada: {interface.__name__}")
        return self
    
    def register_singleton(self, interface: Type[T], implementation: Optional[Type[T]] = None, factory: Optional[Callable[..., T]] = None) -> 'Container':
        """Registra um serviço como singleton.
        
        Args:
            interface: Interface do serviço
            implementation: Implementação concreta (opcional)
            factory: Factory function (opcional)
            
        Returns:
            Self para method chaining
        """
        return self.register(interface, implementation, factory, ServiceLifetime.SINGLETON)
    
    def register_scoped(self, interface: Type[T], implementation: Optional[Type[T]] = None, factory: Optional[Callable[..., T]] = None) -> 'Container':
        """Registra um serviço como scoped.
        
        Args:
            interface: Interface do serviço
            implementation: Implementação concreta (opcional)
            factory: Factory function (opcional)
            
        Returns:
            Self para method chaining
        """
        return self.register(interface, implementation, factory, ServiceLifetime.SCOPED)
    
    def register_transient(self, interface: Type[T], implementation: Optional[Type[T]] = None, factory: Optional[Callable[..., T]] = None) -> 'Container':
        """Registra um serviço como transient.
        
        Args:
            interface: Interface do serviço
            implementation: Implementação concreta (opcional)
            factory: Factory function (opcional)
            
        Returns:
            Self para method chaining
        """
        return self.register(interface, implementation, factory, ServiceLifetime.TRANSIENT)
    
    def register_factory(self, interface: Type[T], factory: IServiceFactory) -> 'Container':
        """Registra uma factory customizada.
        
        Args:
            interface: Interface do serviço
            factory: Factory customizada
            
        Returns:
            Self para method chaining
        """
        with self._lock:
            self._custom_factories[interface] = factory
        
        logger.debug(f"Factory customizada registrada: {interface.__name__}")
        return self
    
    @asynccontextmanager
    async def create_scope(self):
        """Cria um novo escopo para serviços scoped.
        
        Yields:
            ServiceScope: Escopo criado
        """
        scope = ServiceScope(self)
        
        # Adiciona à pilha de escopos
        self._scope_stack.append(scope)
        old_scope = self._current_scope
        self._current_scope = scope
        
        try:
            yield scope
        finally:
            # Restaura escopo anterior
            self._current_scope = old_scope
            if self._scope_stack:
                self._scope_stack.pop()
            
            # Limpa o escopo
            scope.dispose()
    
    def is_registered(self, interface: Type) -> bool:
        """Verifica se um serviço está registrado.
        
        Args:
            interface: Interface do serviço
            
        Returns:
            True se registrado, False caso contrário
        """
        with self._lock:
            return interface in self._descriptors
    
    def get_registration_info(self, interface: Type) -> Optional[ServiceDescriptor]:
        """Obtém informações de registro de um serviço.
        
        Args:
            interface: Interface do serviço
            
        Returns:
            ServiceDescriptor se registrado, None caso contrário
        """
        with self._lock:
            return self._descriptors.get(interface)
    
    def list_registrations(self) -> Dict[Type, ServiceDescriptor]:
        """Lista todos os serviços registrados.
        
        Returns:
            Dicionário com todos os registros
        """
        with self._lock:
            return self._descriptors.copy()
    
    def clear(self):
        """Limpa todos os registros e instâncias."""
        with self._lock:
            # Chama dispose em singletons que suportam
            for instance in self._singletons.values():
                if hasattr(instance, 'dispose'):
                    try:
                        instance.dispose()
                    except Exception as e:
                        logger.warning(f"Erro ao fazer dispose de {type(instance)}: {e}")
            
            self._descriptors.clear()
            self._singletons.clear()
            self._lazy_proxies.clear()
            self._dependency_cache.clear()
            self._custom_factories.clear()
        
        logger.info("Container limpo")

container = Container()  # Instância global