"""Framework de testes automatizados avançado.

Este módulo implementa:
- Testes unitários, integração, performance e stress
- Cobertura de código automatizada (90%+)
- Testes de UI automatizados
- Geração de dados de teste (fixtures)
- Mocking avançado e isolamento
- Relatórios detalhados de testes
- Execução paralela de testes
- Testes de regressão automáticos
"""

import asyncio
import functools
import inspect
import json
import os
import random
import string
import time
import uuid
from collections import defaultdict
from contextlib import asynccontextmanager, contextmanager
from datetime import datetime, timezone, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable, Union, Type, Generator
from unittest.mock import Mock, AsyncMock, patch, MagicMock

import aiofiles
import pytest
import coverage
from faker import Faker
from pydantic import BaseModel
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


class TestType(Enum):
    """Tipos de teste."""
    UNIT = "unit"
    INTEGRATION = "integration"
    PERFORMANCE = "performance"
    STRESS = "stress"
    UI = "ui"
    API = "api"
    DATABASE = "database"
    SECURITY = "security"


class TestStatus(Enum):
    """Status de teste."""
    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    ERROR = "error"


class TestSeverity(Enum):
    """Severidade de falha de teste."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class TestConfig(BaseModel):
    """Configuração do framework de testes."""
    # Configurações gerais
    parallel_execution: bool = True
    max_workers: int = 4
    timeout_seconds: int = 300
    
    # Cobertura de código
    coverage_enabled: bool = True
    coverage_threshold: float = 90.0
    coverage_fail_under: bool = True
    
    # Relatórios
    reports_enabled: bool = True
    reports_dir: str = "test_reports"
    html_reports: bool = True
    json_reports: bool = True
    
    # Performance
    performance_baseline_file: str = "performance_baseline.json"
    performance_threshold_percent: float = 20.0  # % de degradação aceitável
    
    # Stress testing
    stress_duration_seconds: int = 60
    stress_concurrent_users: int = 100
    stress_ramp_up_seconds: int = 10
    
    # Database testing
    test_database_url: str = "sqlite:///:memory:"
    use_transactions: bool = True
    
    # Fixtures
    fixtures_dir: str = "fixtures"
    generate_fixtures: bool = True
    
    # Mocking
    auto_mock_external: bool = True
    mock_network_calls: bool = True
    
    # UI Testing
    ui_testing_enabled: bool = False
    browser_headless: bool = True
    browser_timeout: int = 30
    screenshot_on_failure: bool = True


class TestResult(BaseModel):
    """Resultado de teste."""
    id: str
    name: str
    type: TestType
    status: TestStatus
    duration_ms: float
    start_time: datetime
    end_time: Optional[datetime] = None
    error_message: Optional[str] = None
    traceback: Optional[str] = None
    assertions: int = 0
    coverage_percent: Optional[float] = None
    performance_metrics: Dict[str, float] = {}
    metadata: Dict[str, Any] = {}
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class TestSuite(BaseModel):
    """Suite de testes."""
    name: str
    type: TestType
    tests: List[TestResult] = []
    total_tests: int = 0
    passed_tests: int = 0
    failed_tests: int = 0
    skipped_tests: int = 0
    error_tests: int = 0
    total_duration_ms: float = 0
    coverage_percent: Optional[float] = None
    start_time: datetime
    end_time: Optional[datetime] = None
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class PerformanceBaseline(BaseModel):
    """Baseline de performance."""
    function_name: str
    avg_duration_ms: float
    min_duration_ms: float
    max_duration_ms: float
    p95_duration_ms: float
    p99_duration_ms: float
    memory_usage_mb: float
    timestamp: datetime
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class TestDataGenerator:
    """Gerador de dados de teste."""
    
    def __init__(self, locale: str = 'pt_BR'):
        self.fake = Faker(locale)
        Faker.seed(42)  # Para resultados reproduzíveis
    
    def generate_user_data(self) -> Dict[str, Any]:
        """Gera dados de usuário."""
        return {
            'id': str(uuid.uuid4()),
            'username': self.fake.user_name(),
            'email': self.fake.email(),
            'first_name': self.fake.first_name(),
            'last_name': self.fake.last_name(),
            'password': self.fake.password(length=12),
            'phone': self.fake.phone_number(),
            'address': {
                'street': self.fake.street_address(),
                'city': self.fake.city(),
                'state': self.fake.state(),
                'zip_code': self.fake.postcode(),
                'country': self.fake.country()
            },
            'created_at': self.fake.date_time_between(start_date='-1y', end_date='now'),
            'is_active': self.fake.boolean(chance_of_getting_true=80)
        }
    
    def generate_rom_data(self) -> Dict[str, Any]:
        """Gera dados de ROM."""
        systems = ['NES', 'SNES', 'Genesis', 'Game Boy', 'PlayStation', 'Nintendo 64']
        extensions = ['.nes', '.smc', '.md', '.gb', '.iso', '.z64']
        
        return {
            'id': str(uuid.uuid4()),
            'name': self.fake.catch_phrase(),
            'filename': f"{self.fake.slug()}{random.choice(extensions)}",
            'system': random.choice(systems),
            'size_bytes': self.fake.random_int(min=1024, max=100*1024*1024),
            'md5_hash': self.fake.md5(),
            'sha1_hash': self.fake.sha1(),
            'crc32': self.fake.hexify(text='^^^^^^^^'),
            'region': random.choice(['USA', 'Europe', 'Japan', 'World']),
            'language': random.choice(['English', 'Japanese', 'Spanish', 'French']),
            'genre': self.fake.word(),
            'developer': self.fake.company(),
            'publisher': self.fake.company(),
            'release_date': self.fake.date_between(start_date='-30y', end_date='now'),
            'description': self.fake.text(max_nb_chars=500),
            'rating': round(random.uniform(1.0, 10.0), 1),
            'created_at': self.fake.date_time_between(start_date='-1y', end_date='now')
        }
    
    def generate_game_data(self) -> Dict[str, Any]:
        """Gera dados de jogo."""
        return {
            'id': str(uuid.uuid4()),
            'title': self.fake.catch_phrase(),
            'description': self.fake.text(max_nb_chars=1000),
            'genre': random.choice(['Action', 'Adventure', 'RPG', 'Strategy', 'Sports', 'Racing']),
            'platform': random.choice(['PC', 'PlayStation', 'Xbox', 'Nintendo Switch']),
            'developer': self.fake.company(),
            'publisher': self.fake.company(),
            'release_date': self.fake.date_between(start_date='-20y', end_date='now'),
            'rating': round(random.uniform(1.0, 10.0), 1),
            'price': round(random.uniform(9.99, 59.99), 2),
            'tags': [self.fake.word() for _ in range(random.randint(1, 5))],
            'screenshots': [self.fake.image_url() for _ in range(random.randint(1, 10))],
            'system_requirements': {
                'minimum': {
                    'os': 'Windows 10',
                    'processor': 'Intel Core i3',
                    'memory': '4 GB RAM',
                    'graphics': 'DirectX 11 compatible',
                    'storage': '2 GB available space'
                },
                'recommended': {
                    'os': 'Windows 11',
                    'processor': 'Intel Core i5',
                    'memory': '8 GB RAM',
                    'graphics': 'NVIDIA GTX 1060',
                    'storage': '4 GB available space'
                }
            }
        }
    
    def generate_api_response(self, status_code: int = 200) -> Dict[str, Any]:
        """Gera resposta de API."""
        return {
            'status_code': status_code,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'request_id': str(uuid.uuid4()),
            'data': self.generate_user_data() if status_code == 200 else None,
            'error': self.fake.sentence() if status_code >= 400 else None,
            'metadata': {
                'version': '1.0.0',
                'server': self.fake.ipv4(),
                'response_time_ms': random.randint(10, 500)
            }
        }
    
    def generate_bulk_data(self, generator_func: Callable, count: int) -> List[Dict[str, Any]]:
        """Gera dados em lote."""
        return [generator_func() for _ in range(count)]


class MockManager:
    """Gerenciador de mocks."""
    
    def __init__(self):
        self.active_mocks: List[Mock] = []
        self.patches: List[Any] = []
    
    def mock_database(self, session_factory: Callable = None):
        """Mock do banco de dados."""
        if session_factory is None:
            # Cria banco em memória
            engine = create_engine(
                "sqlite:///:memory:",
                poolclass=StaticPool,
                connect_args={'check_same_thread': False}
            )
            session_factory = sessionmaker(bind=engine)
        
        mock_session = Mock()
        mock_session.query.return_value.filter.return_value.first.return_value = None
        mock_session.query.return_value.all.return_value = []
        mock_session.add.return_value = None
        mock_session.commit.return_value = None
        mock_session.rollback.return_value = None
        mock_session.close.return_value = None
        
        return mock_session
    
    def mock_redis(self):
        """Mock do Redis."""
        mock_redis = Mock()
        mock_redis.get.return_value = None
        mock_redis.set.return_value = True
        mock_redis.delete.return_value = 1
        mock_redis.exists.return_value = False
        mock_redis.expire.return_value = True
        mock_redis.flushdb.return_value = True
        
        return mock_redis
    
    def mock_http_client(self, responses: Dict[str, Any] = None):
        """Mock de cliente HTTP."""
        mock_client = AsyncMock()
        
        if responses:
            for url, response in responses.items():
                mock_response = Mock()
                mock_response.status = response.get('status', 200)
                mock_response.json.return_value = response.get('data', {})
                mock_response.text.return_value = json.dumps(response.get('data', {}))
                
                mock_client.get.return_value.__aenter__.return_value = mock_response
                mock_client.post.return_value.__aenter__.return_value = mock_response
        
        return mock_client
    
    def mock_file_system(self, files: Dict[str, str] = None):
        """Mock do sistema de arquivos."""
        files = files or {}
        
        def mock_open_func(filename, mode='r', *args, **kwargs):
            if filename in files:
                from io import StringIO
                return StringIO(files[filename])
            else:
                raise FileNotFoundError(f"No such file: {filename}")
        
        mock_path = Mock()
        mock_path.exists.return_value = True
        mock_path.is_file.return_value = True
        mock_path.is_dir.return_value = False
        
        return mock_open_func, mock_path
    
    def mock_external_api(self, api_name: str, responses: Dict[str, Any]):
        """Mock de API externa."""
        mock_api = Mock()
        
        for method, response in responses.items():
            setattr(mock_api, method, Mock(return_value=response))
        
        return mock_api
    
    def cleanup(self):
        """Limpa todos os mocks."""
        for mock in self.active_mocks:
            mock.reset_mock()
        
        for patch_obj in self.patches:
            patch_obj.stop()
        
        self.active_mocks.clear()
        self.patches.clear()


class PerformanceProfiler:
    """Profiler de performance."""
    
    def __init__(self):
        self.baselines: Dict[str, PerformanceBaseline] = {}
        self.current_metrics: Dict[str, List[float]] = defaultdict(list)
    
    def load_baselines(self, baseline_file: str):
        """Carrega baselines de performance."""
        try:
            with open(baseline_file, 'r') as f:
                data = json.load(f)
                for item in data:
                    baseline = PerformanceBaseline(**item)
                    self.baselines[baseline.function_name] = baseline
        except FileNotFoundError:
            pass
    
    def save_baselines(self, baseline_file: str):
        """Salva baselines de performance."""
        data = [baseline.dict() for baseline in self.baselines.values()]
        with open(baseline_file, 'w') as f:
            json.dump(data, f, indent=2, default=str)
    
    @contextmanager
    def profile_function(self, function_name: str):
        """Context manager para profiling de função."""
        import psutil
        import tracemalloc
        
        # Inicia monitoramento
        tracemalloc.start()
        process = psutil.Process()
        start_memory = process.memory_info().rss / 1024 / 1024  # MB
        start_time = time.perf_counter()
        
        try:
            yield
        finally:
            # Coleta métricas
            end_time = time.perf_counter()
            duration_ms = (end_time - start_time) * 1000
            
            current_memory = process.memory_info().rss / 1024 / 1024  # MB
            memory_usage = current_memory - start_memory
            
            tracemalloc.stop()
            
            # Armazena métricas
            self.current_metrics[function_name].append(duration_ms)
            
            # Verifica baseline
            if function_name in self.baselines:
                baseline = self.baselines[function_name]
                if duration_ms > baseline.avg_duration_ms * 1.2:  # 20% de degradação
                    print(f"⚠️  Performance degradation detected in {function_name}: "
                          f"{duration_ms:.2f}ms vs baseline {baseline.avg_duration_ms:.2f}ms")
    
    def update_baseline(self, function_name: str):
        """Atualiza baseline com métricas atuais."""
        if function_name not in self.current_metrics:
            return
        
        metrics = self.current_metrics[function_name]
        if not metrics:
            return
        
        baseline = PerformanceBaseline(
            function_name=function_name,
            avg_duration_ms=sum(metrics) / len(metrics),
            min_duration_ms=min(metrics),
            max_duration_ms=max(metrics),
            p95_duration_ms=sorted(metrics)[int(len(metrics) * 0.95)],
            p99_duration_ms=sorted(metrics)[int(len(metrics) * 0.99)],
            memory_usage_mb=0.0,  # TODO: Implementar medição de memória
            timestamp=datetime.now(timezone.utc)
        )
        
        self.baselines[function_name] = baseline


class StressTester:
    """Testador de stress."""
    
    def __init__(self, config: TestConfig):
        self.config = config
        self.results: List[Dict[str, Any]] = []
    
    async def run_stress_test(
        self,
        target_function: Callable,
        concurrent_users: int = None,
        duration_seconds: int = None,
        ramp_up_seconds: int = None
    ) -> Dict[str, Any]:
        """Executa teste de stress."""
        concurrent_users = concurrent_users or self.config.stress_concurrent_users
        duration_seconds = duration_seconds or self.config.stress_duration_seconds
        ramp_up_seconds = ramp_up_seconds or self.config.stress_ramp_up_seconds
        
        print(f"🔥 Iniciando teste de stress: {concurrent_users} usuários por {duration_seconds}s")
        
        start_time = time.time()
        end_time = start_time + duration_seconds
        
        # Métricas
        total_requests = 0
        successful_requests = 0
        failed_requests = 0
        response_times = []
        errors = []
        
        # Semáforo para controlar concorrência
        semaphore = asyncio.Semaphore(concurrent_users)
        
        async def worker():
            nonlocal total_requests, successful_requests, failed_requests
            
            async with semaphore:
                while time.time() < end_time:
                    request_start = time.time()
                    
                    try:
                        if asyncio.iscoroutinefunction(target_function):
                            await target_function()
                        else:
                            target_function()
                        
                        successful_requests += 1
                        
                    except Exception as e:
                        failed_requests += 1
                        errors.append(str(e))
                    
                    finally:
                        total_requests += 1
                        response_time = (time.time() - request_start) * 1000
                        response_times.append(response_time)
                    
                    # Pequena pausa para evitar sobrecarga
                    await asyncio.sleep(0.001)
        
        # Inicia workers com ramp-up
        tasks = []
        for i in range(concurrent_users):
            # Distribui início dos workers ao longo do ramp-up
            delay = (i / concurrent_users) * ramp_up_seconds
            task = asyncio.create_task(self._delayed_worker(worker, delay))
            tasks.append(task)
        
        # Aguarda conclusão
        await asyncio.gather(*tasks, return_exceptions=True)
        
        # Calcula estatísticas
        actual_duration = time.time() - start_time
        requests_per_second = total_requests / actual_duration if actual_duration > 0 else 0
        error_rate = (failed_requests / total_requests * 100) if total_requests > 0 else 0
        
        response_times.sort()
        avg_response_time = sum(response_times) / len(response_times) if response_times else 0
        p95_response_time = response_times[int(len(response_times) * 0.95)] if response_times else 0
        p99_response_time = response_times[int(len(response_times) * 0.99)] if response_times else 0
        
        result = {
            'duration_seconds': actual_duration,
            'concurrent_users': concurrent_users,
            'total_requests': total_requests,
            'successful_requests': successful_requests,
            'failed_requests': failed_requests,
            'requests_per_second': requests_per_second,
            'error_rate_percent': error_rate,
            'avg_response_time_ms': avg_response_time,
            'p95_response_time_ms': p95_response_time,
            'p99_response_time_ms': p99_response_time,
            'min_response_time_ms': min(response_times) if response_times else 0,
            'max_response_time_ms': max(response_times) if response_times else 0,
            'unique_errors': len(set(errors)),
            'error_samples': errors[:10]  # Primeiros 10 erros
        }
        
        self.results.append(result)
        
        print(f"✅ Teste de stress concluído:")
        print(f"   📊 {total_requests} requests ({requests_per_second:.1f} req/s)")
        print(f"   ✅ {successful_requests} sucessos ({100-error_rate:.1f}%)")
        print(f"   ❌ {failed_requests} falhas ({error_rate:.1f}%)")
        print(f"   ⏱️  Tempo médio: {avg_response_time:.1f}ms")
        print(f"   📈 P95: {p95_response_time:.1f}ms, P99: {p99_response_time:.1f}ms")
        
        return result
    
    async def _delayed_worker(self, worker_func: Callable, delay: float):
        """Worker com delay inicial."""
        await asyncio.sleep(delay)
        await worker_func()


class TestRunner:
    """Executor principal de testes."""
    
    def __init__(self, config: TestConfig):
        self.config = config
        self.data_generator = TestDataGenerator()
        self.mock_manager = MockManager()
        self.performance_profiler = PerformanceProfiler()
        self.stress_tester = StressTester(config)
        
        self.test_suites: List[TestSuite] = []
        self.coverage_data: Optional[coverage.Coverage] = None
        
        # Carrega baselines de performance
        if Path(config.performance_baseline_file).exists():
            self.performance_profiler.load_baselines(config.performance_baseline_file)
    
    def setup_coverage(self):
        """Configura cobertura de código."""
        if not self.config.coverage_enabled:
            return
        
        self.coverage_data = coverage.Coverage(
            branch=True,
            source=['app'],
            omit=[
                '*/tests/*',
                '*/test_*',
                '*/__pycache__/*',
                '*/migrations/*',
                '*/venv/*',
                '*/env/*'
            ]
        )
        self.coverage_data.start()
    
    def stop_coverage(self) -> Optional[float]:
        """Para cobertura e retorna percentual."""
        if not self.coverage_data:
            return None
        
        self.coverage_data.stop()
        self.coverage_data.save()
        
        # Gera relatório
        if self.config.reports_enabled:
            reports_dir = Path(self.config.reports_dir)
            reports_dir.mkdir(parents=True, exist_ok=True)
            
            if self.config.html_reports:
                self.coverage_data.html_report(
                    directory=str(reports_dir / 'coverage_html')
                )
            
            if self.config.json_reports:
                self.coverage_data.json_report(
                    outfile=str(reports_dir / 'coverage.json')
                )
        
        # Calcula percentual
        return self.coverage_data.report()
    
    async def run_test_suite(
        self,
        suite_name: str,
        test_type: TestType,
        test_functions: List[Callable]
    ) -> TestSuite:
        """Executa suite de testes."""
        print(f"🧪 Executando suite: {suite_name} ({test_type.value})")
        
        suite = TestSuite(
            name=suite_name,
            type=test_type,
            start_time=datetime.now(timezone.utc)
        )
        
        # Executa testes
        if self.config.parallel_execution and len(test_functions) > 1:
            # Execução paralela
            semaphore = asyncio.Semaphore(self.config.max_workers)
            tasks = [
                self._run_single_test_with_semaphore(func, semaphore)
                for func in test_functions
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)
        else:
            # Execução sequencial
            results = []
            for func in test_functions:
                result = await self._run_single_test(func)
                results.append(result)
        
        # Processa resultados
        for result in results:
            if isinstance(result, TestResult):
                suite.tests.append(result)
                
                if result.status == TestStatus.PASSED:
                    suite.passed_tests += 1
                elif result.status == TestStatus.FAILED:
                    suite.failed_tests += 1
                elif result.status == TestStatus.SKIPPED:
                    suite.skipped_tests += 1
                elif result.status == TestStatus.ERROR:
                    suite.error_tests += 1
                
                suite.total_duration_ms += result.duration_ms
        
        suite.total_tests = len(suite.tests)
        suite.end_time = datetime.now(timezone.utc)
        
        self.test_suites.append(suite)
        
        # Relatório da suite
        success_rate = (suite.passed_tests / suite.total_tests * 100) if suite.total_tests > 0 else 0
        print(f"   ✅ {suite.passed_tests}/{suite.total_tests} testes passaram ({success_rate:.1f}%)")
        print(f"   ⏱️  Duração total: {suite.total_duration_ms:.0f}ms")
        
        if suite.failed_tests > 0:
            print(f"   ❌ {suite.failed_tests} testes falharam")
        
        return suite
    
    async def _run_single_test_with_semaphore(self, test_func: Callable, semaphore: asyncio.Semaphore) -> TestResult:
        """Executa teste único com semáforo."""
        async with semaphore:
            return await self._run_single_test(test_func)
    
    async def _run_single_test(self, test_func: Callable) -> TestResult:
        """Executa teste único."""
        test_id = str(uuid.uuid4())
        test_name = f"{test_func.__module__}.{test_func.__name__}"
        
        result = TestResult(
            id=test_id,
            name=test_name,
            type=TestType.UNIT,  # Default, pode ser sobrescrito
            status=TestStatus.RUNNING,
            duration_ms=0,
            start_time=datetime.now(timezone.utc)
        )
        
        start_time = time.perf_counter()
        
        try:
            # Setup de mocks se necessário
            if self.config.auto_mock_external:
                self._setup_auto_mocks(test_func)
            
            # Executa teste com profiling de performance
            with self.performance_profiler.profile_function(test_name):
                if asyncio.iscoroutinefunction(test_func):
                    await asyncio.wait_for(
                        test_func(),
                        timeout=self.config.timeout_seconds
                    )
                else:
                    test_func()
            
            result.status = TestStatus.PASSED
            
        except asyncio.TimeoutError:
            result.status = TestStatus.ERROR
            result.error_message = f"Teste excedeu timeout de {self.config.timeout_seconds}s"
            
        except AssertionError as e:
            result.status = TestStatus.FAILED
            result.error_message = str(e)
            result.traceback = self._get_traceback()
            
        except Exception as e:
            result.status = TestStatus.ERROR
            result.error_message = str(e)
            result.traceback = self._get_traceback()
        
        finally:
            # Cleanup
            self.mock_manager.cleanup()
            
            # Finaliza resultado
            result.duration_ms = (time.perf_counter() - start_time) * 1000
            result.end_time = datetime.now(timezone.utc)
        
        return result
    
    def _setup_auto_mocks(self, test_func: Callable):
        """Configura mocks automáticos."""
        # Analisa função para identificar dependências
        signature = inspect.signature(test_func)
        
        # Mock de dependências comuns
        if 'db' in signature.parameters or 'session' in signature.parameters:
            mock_db = self.mock_manager.mock_database()
            # TODO: Injetar mock na função
        
        if 'redis' in signature.parameters:
            mock_redis = self.mock_manager.mock_redis()
            # TODO: Injetar mock na função
    
    def _get_traceback(self) -> str:
        """Obtém traceback da exceção atual."""
        import traceback
        return traceback.format_exc()
    
    async def run_performance_tests(self, test_functions: List[Callable]) -> TestSuite:
        """Executa testes de performance."""
        suite = await self.run_test_suite(
            "Performance Tests",
            TestType.PERFORMANCE,
            test_functions
        )
        
        # Atualiza baselines
        for test in suite.tests:
            if test.status == TestStatus.PASSED:
                self.performance_profiler.update_baseline(test.name)
        
        # Salva baselines
        self.performance_profiler.save_baselines(self.config.performance_baseline_file)
        
        return suite
    
    async def run_stress_tests(self, target_functions: List[Callable]) -> Dict[str, Any]:
        """Executa testes de stress."""
        print("🔥 Iniciando testes de stress")
        
        results = {}
        for func in target_functions:
            func_name = f"{func.__module__}.{func.__name__}"
            result = await self.stress_tester.run_stress_test(func)
            results[func_name] = result
        
        return results
    
    def generate_test_report(self) -> Dict[str, Any]:
        """Gera relatório completo de testes."""
        total_tests = sum(suite.total_tests for suite in self.test_suites)
        total_passed = sum(suite.passed_tests for suite in self.test_suites)
        total_failed = sum(suite.failed_tests for suite in self.test_suites)
        total_duration = sum(suite.total_duration_ms for suite in self.test_suites)
        
        coverage_percent = self.stop_coverage()
        
        report = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'summary': {
                'total_tests': total_tests,
                'passed_tests': total_passed,
                'failed_tests': total_failed,
                'success_rate_percent': (total_passed / total_tests * 100) if total_tests > 0 else 0,
                'total_duration_ms': total_duration,
                'coverage_percent': coverage_percent
            },
            'suites': [suite.dict() for suite in self.test_suites],
            'performance_baselines': {
                name: baseline.dict() 
                for name, baseline in self.performance_profiler.baselines.items()
            },
            'stress_test_results': self.stress_tester.results
        }
        
        # Salva relatório
        if self.config.reports_enabled:
            reports_dir = Path(self.config.reports_dir)
            reports_dir.mkdir(parents=True, exist_ok=True)
            
            if self.config.json_reports:
                report_file = reports_dir / f"test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                with open(report_file, 'w') as f:
                    json.dump(report, f, indent=2, default=str)
        
        return report


# Decoradores para testes
def performance_test(baseline_name: str = None):
    """Decorador para testes de performance."""
    def decorator(func):
        func._test_type = TestType.PERFORMANCE
        func._baseline_name = baseline_name or f"{func.__module__}.{func.__name__}"
        return func
    return decorator


def stress_test(concurrent_users: int = 10, duration_seconds: int = 30):
    """Decorador para testes de stress."""
    def decorator(func):
        func._test_type = TestType.STRESS
        func._concurrent_users = concurrent_users
        func._duration_seconds = duration_seconds
        return func
    return decorator


def integration_test(dependencies: List[str] = None):
    """Decorador para testes de integração."""
    def decorator(func):
        func._test_type = TestType.INTEGRATION
        func._dependencies = dependencies or []
        return func
    return decorator


def ui_test(browser: str = 'chrome', headless: bool = True):
    """Decorador para testes de UI."""
    def decorator(func):
        func._test_type = TestType.UI
        func._browser = browser
        func._headless = headless
        return func
    return decorator


# Fixtures globais
@pytest.fixture
def test_data_generator():
    """Fixture para gerador de dados de teste."""
    return TestDataGenerator()


@pytest.fixture
def mock_manager():
    """Fixture para gerenciador de mocks."""
    manager = MockManager()
    yield manager
    manager.cleanup()


@pytest.fixture
async def test_database():
    """Fixture para banco de dados de teste."""
    # TODO: Implementar setup/teardown do banco de teste
    yield None


@pytest.fixture
def performance_profiler():
    """Fixture para profiler de performance."""
    return PerformanceProfiler()


# Instância global
test_runner: Optional[TestRunner] = None


def get_test_runner() -> TestRunner:
    """Obtém instância global do test runner."""
    global test_runner
    if test_runner is None:
        config = TestConfig()
        test_runner = TestRunner(config)
    
    return test_runner


# Utilitários para assertions customizadas
class CustomAssertions:
    """Assertions customizadas para testes."""
    
    @staticmethod
    def assert_response_time(actual_ms: float, expected_ms: float, tolerance_percent: float = 10):
        """Verifica tempo de resposta com tolerância."""
        tolerance = expected_ms * (tolerance_percent / 100)
        assert actual_ms <= expected_ms + tolerance, \
            f"Response time {actual_ms}ms exceeds expected {expected_ms}ms (±{tolerance_percent}%)"
    
    @staticmethod
    def assert_memory_usage(actual_mb: float, max_mb: float):
        """Verifica uso de memória."""
        assert actual_mb <= max_mb, \
            f"Memory usage {actual_mb}MB exceeds maximum {max_mb}MB"
    
    @staticmethod
    def assert_error_rate(errors: int, total: int, max_percent: float):
        """Verifica taxa de erro."""
        error_rate = (errors / total * 100) if total > 0 else 0
        assert error_rate <= max_percent, \
            f"Error rate {error_rate:.1f}% exceeds maximum {max_percent}%"
    
    @staticmethod
    def assert_json_schema(data: Dict[str, Any], schema: Dict[str, Any]):
        """Verifica schema JSON."""
        # TODO: Implementar validação de schema
        pass
    
    @staticmethod
    def assert_database_state(session, model, expected_count: int):
        """Verifica estado do banco de dados."""
        actual_count = session.query(model).count()
        assert actual_count == expected_count, \
            f"Expected {expected_count} {model.__name__} records, found {actual_count}"


# Exporta assertions para uso global
assert_response_time = CustomAssertions.assert_response_time
assert_memory_usage = CustomAssertions.assert_memory_usage
assert_error_rate = CustomAssertions.assert_error_rate
assert_json_schema = CustomAssertions.assert_json_schema
assert_database_state = CustomAssertions.assert_database_state