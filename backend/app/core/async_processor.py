"""Sistema avançado de processamento assíncrono.

Fornece ThreadPoolExecutor otimizado, sistema de comunicação thread-safe,
cancelamento gracioso e callbacks de progresso detalhados.
"""

import asyncio
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor, Future
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, TypeVar, Generic
from uuid import uuid4, UUID
from queue import Queue, Empty
from contextlib import asynccontextmanager

from pydantic import BaseModel

logger = logging.getLogger(__name__)

T = TypeVar('T')


class TaskStatus(str, Enum):
    """Status possíveis de uma tarefa."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskPriority(int, Enum):
    """Prioridades de tarefas (menor número = maior prioridade)."""
    CRITICAL = 1
    HIGH = 2
    NORMAL = 3
    LOW = 4
    BACKGROUND = 5


@dataclass
class ProgressInfo:
    """Informações de progresso de uma tarefa."""
    current: int = 0
    total: int = 100
    message: str = ""
    percentage: float = field(init=False)
    eta_seconds: Optional[float] = None
    
    def __post_init__(self):
        self.percentage = (self.current / self.total * 100) if self.total > 0 else 0


class TaskResult(BaseModel, Generic[T]):
    """Resultado de uma tarefa assíncrona."""
    task_id: UUID
    status: TaskStatus
    result: Optional[T] = None
    error: Optional[str] = None
    progress: Optional[ProgressInfo] = None
    created_at: float
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    
    @property
    def duration(self) -> Optional[float]:
        """Duração da execução em segundos."""
        if self.started_at and self.completed_at:
            return self.completed_at - self.started_at
        return None


class CancellationToken:
    """Token para cancelamento gracioso de tarefas."""
    
    def __init__(self):
        self._cancelled = threading.Event()
    
    def cancel(self):
        """Marca o token como cancelado."""
        self._cancelled.set()
    
    @property
    def is_cancelled(self) -> bool:
        """Verifica se o token foi cancelado."""
        return self._cancelled.is_set()
    
    def check_cancelled(self):
        """Levanta exceção se cancelado."""
        if self.is_cancelled:
            raise asyncio.CancelledError("Task was cancelled")


class ProgressCallback:
    """Callback thread-safe para atualizações de progresso."""
    
    def __init__(self, task_id: UUID, processor: 'AsyncProcessor'):
        self.task_id = task_id
        self.processor = processor
        self._lock = threading.Lock()
    
    def update(self, current: int, total: int = 100, message: str = "", eta_seconds: Optional[float] = None):
        """Atualiza o progresso da tarefa de forma thread-safe."""
        with self._lock:
            progress = ProgressInfo(
                current=current,
                total=total,
                message=message,
                eta_seconds=eta_seconds
            )
            self.processor._update_progress(self.task_id, progress)


@dataclass
class TaskInfo:
    """Informações completas de uma tarefa."""
    task_id: UUID
    name: str
    priority: TaskPriority
    func: Callable
    args: tuple
    kwargs: dict
    future: Future
    cancellation_token: CancellationToken
    progress_callback: ProgressCallback
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None


class AsyncProcessor:
    """Processador assíncrono avançado com suporte a priorização e cancelamento."""
    
    def __init__(
        self,
        max_workers: Optional[int] = None,
        thread_name_prefix: str = "AsyncProcessor",
        enable_metrics: bool = True
    ):
        self.max_workers = max_workers
        self.thread_name_prefix = thread_name_prefix
        self.enable_metrics = enable_metrics
        
        # ThreadPoolExecutor com configuração otimizada
        self._executor = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix=thread_name_prefix
        )
        
        # Armazenamento thread-safe de tarefas
        self._tasks: Dict[UUID, TaskInfo] = {}
        self._results: Dict[UUID, TaskResult] = {}
        self._lock = threading.RLock()
        
        # Fila de prioridades para tarefas pendentes
        self._pending_queue = Queue()
        
        # Métricas
        self._metrics = {
            "total_tasks": 0,
            "completed_tasks": 0,
            "failed_tasks": 0,
            "cancelled_tasks": 0,
            "active_tasks": 0
        } if enable_metrics else None
        
        # Worker para processar fila de prioridades
        self._queue_worker_running = True
        self._queue_worker = threading.Thread(
            target=self._process_priority_queue,
            name=f"{thread_name_prefix}-QueueWorker",
            daemon=True
        )
        self._queue_worker.start()
        
        logger.info(f"AsyncProcessor iniciado com {max_workers or 'auto'} workers")
    
    def submit_task(
        self,
        func: Callable[..., T],
        *args,
        name: str = None,
        priority: TaskPriority = TaskPriority.NORMAL,
        **kwargs
    ) -> UUID:
        """Submete uma tarefa para execução assíncrona.
        
        Args:
            func: Função a ser executada
            *args: Argumentos posicionais
            name: Nome da tarefa (para logging)
            priority: Prioridade da tarefa
            **kwargs: Argumentos nomeados
            
        Returns:
            UUID da tarefa
        """
        task_id = uuid4()
        cancellation_token = CancellationToken()
        progress_callback = ProgressCallback(task_id, self)
        
        # Injeta token de cancelamento e callback nos kwargs
        kwargs['cancellation_token'] = cancellation_token
        kwargs['progress_callback'] = progress_callback
        
        # Cria future placeholder
        future = Future()
        
        task_info = TaskInfo(
            task_id=task_id,
            name=name or func.__name__,
            priority=priority,
            func=func,
            args=args,
            kwargs=kwargs,
            future=future,
            cancellation_token=cancellation_token,
            progress_callback=progress_callback
        )
        
        with self._lock:
            self._tasks[task_id] = task_info
            self._results[task_id] = TaskResult(
                task_id=task_id,
                status=TaskStatus.PENDING,
                created_at=time.time()
            )
            
            if self._metrics:
                self._metrics["total_tasks"] += 1
        
        # Adiciona à fila de prioridades
        self._pending_queue.put((priority.value, time.time(), task_id))
        
        logger.debug(f"Tarefa {task_id} ({name}) submetida com prioridade {priority.name}")
        return task_id
    
    def _process_priority_queue(self):
        """Worker que processa a fila de prioridades."""
        while self._queue_worker_running:
            try:
                # Pega próxima tarefa (timeout para permitir shutdown)
                priority, timestamp, task_id = self._pending_queue.get(timeout=1.0)
                
                with self._lock:
                    if task_id not in self._tasks:
                        continue
                    
                    task_info = self._tasks[task_id]
                    
                    # Verifica se foi cancelada
                    if task_info.cancellation_token.is_cancelled:
                        self._mark_cancelled(task_id)
                        continue
                
                # Submete para ThreadPoolExecutor
                future = self._executor.submit(self._execute_task, task_id)
                
                with self._lock:
                    task_info.future = future
                    self._update_status(task_id, TaskStatus.RUNNING)
                    task_info.started_at = time.time()
                    
                    if self._metrics:
                        self._metrics["active_tasks"] += 1
                
            except Empty:
                continue  # Timeout normal
            except Exception as e:
                logger.error(f"Erro no worker da fila de prioridades: {e}")
    
    def _execute_task(self, task_id: UUID) -> Any:
        """Executa uma tarefa e gerencia seu ciclo de vida."""
        with self._lock:
            task_info = self._tasks.get(task_id)
            if not task_info:
                return None
        
        try:
            # Verifica cancelamento antes de iniciar
            task_info.cancellation_token.check_cancelled()
            
            logger.debug(f"Iniciando execução da tarefa {task_id} ({task_info.name})")
            
            # Executa a função
            result = task_info.func(*task_info.args, **task_info.kwargs)
            
            # Verifica cancelamento após execução
            task_info.cancellation_token.check_cancelled()
            
            # Marca como completada
            with self._lock:
                self._update_status(task_id, TaskStatus.COMPLETED, result=result)
                
                if self._metrics:
                    self._metrics["completed_tasks"] += 1
                    self._metrics["active_tasks"] -= 1
            
            logger.debug(f"Tarefa {task_id} completada com sucesso")
            return result
            
        except asyncio.CancelledError:
            logger.info(f"Tarefa {task_id} foi cancelada")
            self._mark_cancelled(task_id)
            raise
            
        except Exception as e:
            logger.error(f"Erro na execução da tarefa {task_id}: {e}")
            
            with self._lock:
                self._update_status(task_id, TaskStatus.FAILED, error=str(e))
                
                if self._metrics:
                    self._metrics["failed_tasks"] += 1
                    self._metrics["active_tasks"] -= 1
            
            raise
    
    def _mark_cancelled(self, task_id: UUID):
        """Marca uma tarefa como cancelada."""
        with self._lock:
            self._update_status(task_id, TaskStatus.CANCELLED)
            
            if self._metrics:
                self._metrics["cancelled_tasks"] += 1
                if self._metrics["active_tasks"] > 0:
                    self._metrics["active_tasks"] -= 1
    
    def _update_status(self, task_id: UUID, status: TaskStatus, result: Any = None, error: str = None):
        """Atualiza o status de uma tarefa."""
        if task_id in self._results:
            task_result = self._results[task_id]
            task_result.status = status
            
            if result is not None:
                task_result.result = result
            if error is not None:
                task_result.error = error
            
            if status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]:
                task_result.completed_at = time.time()
            elif status == TaskStatus.RUNNING:
                task_result.started_at = time.time()
    
    def _update_progress(self, task_id: UUID, progress: ProgressInfo):
        """Atualiza o progresso de uma tarefa."""
        with self._lock:
            if task_id in self._results:
                self._results[task_id].progress = progress
    
    def get_task_result(self, task_id: UUID) -> Optional[TaskResult]:
        """Obtém o resultado de uma tarefa."""
        with self._lock:
            return self._results.get(task_id)
    
    def cancel_task(self, task_id: UUID) -> bool:
        """Cancela uma tarefa.
        
        Returns:
            True se a tarefa foi cancelada, False se não foi possível
        """
        with self._lock:
            task_info = self._tasks.get(task_id)
            if not task_info:
                return False
            
            # Marca token como cancelado
            task_info.cancellation_token.cancel()
            
            # Tenta cancelar o future se ainda não iniciou
            if task_info.future and not task_info.future.running():
                task_info.future.cancel()
            
            logger.info(f"Cancelamento solicitado para tarefa {task_id}")
            return True
    
    def get_metrics(self) -> Optional[Dict[str, Any]]:
        """Obtém métricas do processador."""
        if not self._metrics:
            return None
        
        with self._lock:
            return self._metrics.copy()
    
    def list_active_tasks(self) -> List[UUID]:
        """Lista tarefas ativas."""
        with self._lock:
            return [
                task_id for task_id, result in self._results.items()
                if result.status in [TaskStatus.PENDING, TaskStatus.RUNNING]
            ]
    
    async def wait_for_task(self, task_id: UUID, timeout: Optional[float] = None) -> TaskResult:
        """Aguarda a conclusão de uma tarefa de forma assíncrona.
        
        Args:
            task_id: ID da tarefa
            timeout: Timeout em segundos
            
        Returns:
            Resultado da tarefa
            
        Raises:
            asyncio.TimeoutError: Se timeout for atingido
            ValueError: Se tarefa não existir
        """
        with self._lock:
            if task_id not in self._tasks:
                raise ValueError(f"Tarefa {task_id} não encontrada")
        
        start_time = time.time()
        
        while True:
            result = self.get_task_result(task_id)
            if result and result.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]:
                return result
            
            if timeout and (time.time() - start_time) > timeout:
                raise asyncio.TimeoutError(f"Timeout aguardando tarefa {task_id}")
            
            await asyncio.sleep(0.1)  # Polling interval
    
    def shutdown(self, wait: bool = True, timeout: Optional[float] = None):
        """Finaliza o processador graciosamente."""
        logger.info("Iniciando shutdown do AsyncProcessor")
        
        # Para o worker da fila
        self._queue_worker_running = False
        
        # Cancela todas as tarefas pendentes
        with self._lock:
            pending_tasks = [
                task_id for task_id, result in self._results.items()
                if result.status == TaskStatus.PENDING
            ]
        
        for task_id in pending_tasks:
            self.cancel_task(task_id)
        
        # Finaliza o executor
        self._executor.shutdown(wait=wait, timeout=timeout)
        
        # Aguarda o worker da fila
        if self._queue_worker.is_alive():
            self._queue_worker.join(timeout=5.0)
        
        logger.info("AsyncProcessor finalizado")
    
    @asynccontextmanager
    async def task_context(self, func: Callable[..., T], *args, **kwargs):
        """Context manager para execução de tarefas com cleanup automático."""
        task_id = self.submit_task(func, *args, **kwargs)
        try:
            result = await self.wait_for_task(task_id)
            yield result
        finally:
            # Cleanup automático
            with self._lock:
                self._tasks.pop(task_id, None)
                self._results.pop(task_id, None)


# Instância global
_global_processor: Optional[AsyncProcessor] = None


def get_async_processor() -> AsyncProcessor:
    """Obtém a instância global do processador assíncrono."""
    global _global_processor
    if _global_processor is None:
        _global_processor = AsyncProcessor()
    return _global_processor


def shutdown_async_processor():
    """Finaliza a instância global do processador."""
    global _global_processor
    if _global_processor:
        _global_processor.shutdown()
        _global_processor = None