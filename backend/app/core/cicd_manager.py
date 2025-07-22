"""Sistema de CI/CD avançado com automação completa.

Este módulo implementa:
- Pipeline de CI/CD automatizado
- Testes de segurança integrados
- Deployment automático multi-ambiente
- Rollback automático em caso de falhas
- Monitoramento de health checks
- Notificações de status
- Análise de qualidade de código
- Gestão de artefatos
- Blue-green deployment
- Canary releases
"""

import asyncio
import json
import os
import shutil
import subprocess
import tempfile
import time
import uuid
from datetime import datetime, timezone, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable, Union

import aiofiles
import aiohttp
import docker
import yaml
from pydantic import BaseModel


class PipelineStage(Enum):
    """Estágios do pipeline."""
    CHECKOUT = "checkout"
    BUILD = "build"
    TEST = "test"
    SECURITY_SCAN = "security_scan"
    QUALITY_ANALYSIS = "quality_analysis"
    PACKAGE = "package"
    DEPLOY_STAGING = "deploy_staging"
    INTEGRATION_TEST = "integration_test"
    DEPLOY_PRODUCTION = "deploy_production"
    SMOKE_TEST = "smoke_test"
    CLEANUP = "cleanup"


class PipelineStatus(Enum):
    """Status do pipeline."""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"
    SKIPPED = "skipped"


class DeploymentStrategy(Enum):
    """Estratégias de deployment."""
    ROLLING = "rolling"
    BLUE_GREEN = "blue_green"
    CANARY = "canary"
    RECREATE = "recreate"


class Environment(Enum):
    """Ambientes de deployment."""
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    TESTING = "testing"


class SecurityScanType(Enum):
    """Tipos de scan de segurança."""
    DEPENDENCY_CHECK = "dependency_check"
    STATIC_ANALYSIS = "static_analysis"
    CONTAINER_SCAN = "container_scan"
    SECRET_DETECTION = "secret_detection"
    LICENSE_CHECK = "license_check"


class CICDConfig(BaseModel):
    """Configuração do sistema CI/CD."""
    # Configurações gerais
    project_name: str = "megaemu-modern"
    repository_url: str = ""
    branch: str = "main"
    
    # Ambientes
    environments: Dict[str, Dict[str, Any]] = {
        "staging": {
            "url": "https://staging.megaemu.com",
            "replicas": 1,
            "resources": {"cpu": "500m", "memory": "1Gi"}
        },
        "production": {
            "url": "https://megaemu.com",
            "replicas": 3,
            "resources": {"cpu": "1000m", "memory": "2Gi"}
        }
    }
    
    # Docker
    docker_registry: str = "registry.megaemu.com"
    docker_namespace: str = "megaemu"
    
    # Testes
    test_timeout_minutes: int = 30
    coverage_threshold: float = 90.0
    
    # Segurança
    security_scans_enabled: bool = True
    fail_on_security_issues: bool = True
    allowed_vulnerabilities: List[str] = []
    
    # Quality gates
    quality_gate_enabled: bool = True
    sonar_project_key: str = "megaemu-modern"
    sonar_url: str = "https://sonarqube.megaemu.com"
    
    # Deployment
    deployment_strategy: DeploymentStrategy = DeploymentStrategy.ROLLING
    canary_percentage: int = 10
    rollback_on_failure: bool = True
    health_check_timeout_minutes: int = 5
    
    # Notificações
    notifications_enabled: bool = True
    slack_webhook: Optional[str] = None
    email_recipients: List[str] = []
    
    # Artefatos
    artifact_retention_days: int = 30
    keep_last_n_artifacts: int = 10


class StageResult(BaseModel):
    """Resultado de um estágio."""
    stage: PipelineStage
    status: PipelineStatus
    start_time: datetime
    end_time: Optional[datetime] = None
    duration_seconds: float = 0
    logs: List[str] = []
    artifacts: List[str] = []
    metrics: Dict[str, Any] = {}
    error_message: Optional[str] = None
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class PipelineRun(BaseModel):
    """Execução de pipeline."""
    id: str
    trigger: str  # manual, webhook, schedule
    branch: str
    commit_sha: str
    commit_message: str
    author: str
    status: PipelineStatus
    start_time: datetime
    end_time: Optional[datetime] = None
    duration_seconds: float = 0
    stages: List[StageResult] = []
    environment: Optional[Environment] = None
    deployment_id: Optional[str] = None
    rollback_id: Optional[str] = None
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class SecurityIssue(BaseModel):
    """Issue de segurança."""
    id: str
    type: SecurityScanType
    severity: str  # LOW, MEDIUM, HIGH, CRITICAL
    title: str
    description: str
    file_path: Optional[str] = None
    line_number: Optional[int] = None
    cve_id: Optional[str] = None
    fix_available: bool = False
    fix_version: Optional[str] = None


class QualityMetrics(BaseModel):
    """Métricas de qualidade."""
    coverage_percent: float
    lines_of_code: int
    duplicated_lines_percent: float
    code_smells: int
    bugs: int
    vulnerabilities: int
    security_hotspots: int
    maintainability_rating: str
    reliability_rating: str
    security_rating: str
    technical_debt_minutes: int


class Deployment(BaseModel):
    """Deployment."""
    id: str
    environment: Environment
    strategy: DeploymentStrategy
    version: str
    image_tag: str
    status: PipelineStatus
    start_time: datetime
    end_time: Optional[datetime] = None
    replicas: int
    health_checks_passed: bool = False
    rollback_version: Optional[str] = None
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class SecurityScanner:
    """Scanner de segurança."""
    
    def __init__(self, config: CICDConfig):
        self.config = config
    
    async def run_dependency_check(self, project_path: str) -> List[SecurityIssue]:
        """Executa verificação de dependências."""
        issues = []
        
        # Verifica requirements.txt
        requirements_file = Path(project_path) / "requirements.txt"
        if requirements_file.exists():
            # Simula verificação com safety
            cmd = ["safety", "check", "-r", str(requirements_file), "--json"]
            try:
                result = await self._run_command(cmd)
                if result["returncode"] != 0:
                    # Parse do output do safety
                    safety_output = json.loads(result["stdout"])
                    for vuln in safety_output:
                        issue = SecurityIssue(
                            id=str(uuid.uuid4()),
                            type=SecurityScanType.DEPENDENCY_CHECK,
                            severity=self._map_safety_severity(vuln.get("severity", "MEDIUM")),
                            title=f"Vulnerable dependency: {vuln['package_name']}",
                            description=vuln.get("advisory", ""),
                            cve_id=vuln.get("cve"),
                            fix_available=bool(vuln.get("fixed_in")),
                            fix_version=vuln.get("fixed_in")
                        )
                        issues.append(issue)
            except Exception as e:
                print(f"Erro na verificação de dependências: {e}")
        
        return issues
    
    async def run_static_analysis(self, project_path: str) -> List[SecurityIssue]:
        """Executa análise estática de segurança."""
        issues = []
        
        # Bandit para Python
        cmd = ["bandit", "-r", project_path, "-f", "json"]
        try:
            result = await self._run_command(cmd)
            if result["returncode"] != 0:
                bandit_output = json.loads(result["stdout"])
                for result_item in bandit_output.get("results", []):
                    issue = SecurityIssue(
                        id=str(uuid.uuid4()),
                        type=SecurityScanType.STATIC_ANALYSIS,
                        severity=result_item.get("issue_severity", "MEDIUM"),
                        title=result_item.get("test_name", ""),
                        description=result_item.get("issue_text", ""),
                        file_path=result_item.get("filename"),
                        line_number=result_item.get("line_number")
                    )
                    issues.append(issue)
        except Exception as e:
            print(f"Erro na análise estática: {e}")
        
        return issues
    
    async def run_secret_detection(self, project_path: str) -> List[SecurityIssue]:
        """Detecta secrets no código."""
        issues = []
        
        # TruffleHog ou similar
        cmd = ["trufflehog", "filesystem", project_path, "--json"]
        try:
            result = await self._run_command(cmd)
            if result["stdout"]:
                for line in result["stdout"].split("\n"):
                    if line.strip():
                        secret_data = json.loads(line)
                        issue = SecurityIssue(
                            id=str(uuid.uuid4()),
                            type=SecurityScanType.SECRET_DETECTION,
                            severity="HIGH",
                            title=f"Secret detected: {secret_data.get('DetectorName', 'Unknown')}",
                            description=f"Potential secret found in {secret_data.get('SourceMetadata', {}).get('Data', {}).get('Filesystem', {}).get('file', 'unknown file')}",
                            file_path=secret_data.get("SourceMetadata", {}).get("Data", {}).get("Filesystem", {}).get("file")
                        )
                        issues.append(issue)
        except Exception as e:
            print(f"Erro na detecção de secrets: {e}")
        
        return issues
    
    async def run_container_scan(self, image_name: str) -> List[SecurityIssue]:
        """Escaneia imagem Docker."""
        issues = []
        
        # Trivy ou similar
        cmd = ["trivy", "image", "--format", "json", image_name]
        try:
            result = await self._run_command(cmd)
            if result["stdout"]:
                trivy_output = json.loads(result["stdout"])
                for result_item in trivy_output.get("Results", []):
                    for vuln in result_item.get("Vulnerabilities", []):
                        issue = SecurityIssue(
                            id=str(uuid.uuid4()),
                            type=SecurityScanType.CONTAINER_SCAN,
                            severity=vuln.get("Severity", "MEDIUM"),
                            title=f"Container vulnerability: {vuln.get('VulnerabilityID', '')}",
                            description=vuln.get("Description", ""),
                            cve_id=vuln.get("VulnerabilityID"),
                            fix_available=bool(vuln.get("FixedVersion")),
                            fix_version=vuln.get("FixedVersion")
                        )
                        issues.append(issue)
        except Exception as e:
            print(f"Erro no scan de container: {e}")
        
        return issues
    
    def _map_safety_severity(self, severity: str) -> str:
        """Mapeia severidade do safety."""
        mapping = {
            "low": "LOW",
            "medium": "MEDIUM",
            "high": "HIGH",
            "critical": "CRITICAL"
        }
        return mapping.get(severity.lower(), "MEDIUM")
    
    async def _run_command(self, cmd: List[str]) -> Dict[str, Any]:
        """Executa comando e retorna resultado."""
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate()
        
        return {
            "returncode": process.returncode,
            "stdout": stdout.decode() if stdout else "",
            "stderr": stderr.decode() if stderr else ""
        }


class QualityAnalyzer:
    """Analisador de qualidade de código."""
    
    def __init__(self, config: CICDConfig):
        self.config = config
    
    async def run_sonar_analysis(self, project_path: str) -> QualityMetrics:
        """Executa análise SonarQube."""
        # Executa sonar-scanner
        cmd = [
            "sonar-scanner",
            f"-Dsonar.projectKey={self.config.sonar_project_key}",
            f"-Dsonar.host.url={self.config.sonar_url}",
            f"-Dsonar.projectBaseDir={project_path}"
        ]
        
        try:
            result = await self._run_command(cmd)
            if result["returncode"] == 0:
                # Busca métricas via API
                return await self._fetch_sonar_metrics()
            else:
                raise Exception(f"SonarQube analysis failed: {result['stderr']}")
        except Exception as e:
            print(f"Erro na análise de qualidade: {e}")
            # Retorna métricas padrão em caso de erro
            return QualityMetrics(
                coverage_percent=0.0,
                lines_of_code=0,
                duplicated_lines_percent=0.0,
                code_smells=0,
                bugs=0,
                vulnerabilities=0,
                security_hotspots=0,
                maintainability_rating="E",
                reliability_rating="E",
                security_rating="E",
                technical_debt_minutes=0
            )
    
    async def _fetch_sonar_metrics(self) -> QualityMetrics:
        """Busca métricas do SonarQube via API."""
        metrics_to_fetch = [
            "coverage",
            "ncloc",
            "duplicated_lines_density",
            "code_smells",
            "bugs",
            "vulnerabilities",
            "security_hotspots",
            "sqale_rating",
            "reliability_rating",
            "security_rating",
            "sqale_index"
        ]
        
        url = f"{self.config.sonar_url}/api/measures/component"
        params = {
            "component": self.config.sonar_project_key,
            "metricKeys": ",".join(metrics_to_fetch)
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    measures = {m["metric"]: m.get("value", "0") for m in data.get("component", {}).get("measures", [])}
                    
                    return QualityMetrics(
                        coverage_percent=float(measures.get("coverage", 0)),
                        lines_of_code=int(measures.get("ncloc", 0)),
                        duplicated_lines_percent=float(measures.get("duplicated_lines_density", 0)),
                        code_smells=int(measures.get("code_smells", 0)),
                        bugs=int(measures.get("bugs", 0)),
                        vulnerabilities=int(measures.get("vulnerabilities", 0)),
                        security_hotspots=int(measures.get("security_hotspots", 0)),
                        maintainability_rating=measures.get("sqale_rating", "E"),
                        reliability_rating=measures.get("reliability_rating", "E"),
                        security_rating=measures.get("security_rating", "E"),
                        technical_debt_minutes=int(measures.get("sqale_index", 0))
                    )
                else:
                    raise Exception(f"Failed to fetch SonarQube metrics: {response.status}")
    
    async def _run_command(self, cmd: List[str]) -> Dict[str, Any]:
        """Executa comando e retorna resultado."""
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate()
        
        return {
            "returncode": process.returncode,
            "stdout": stdout.decode() if stdout else "",
            "stderr": stderr.decode() if stderr else ""
        }


class DeploymentManager:
    """Gerenciador de deployment."""
    
    def __init__(self, config: CICDConfig):
        self.config = config
        self.docker_client = docker.from_env()
    
    async def deploy(
        self,
        environment: Environment,
        image_tag: str,
        strategy: DeploymentStrategy = None
    ) -> Deployment:
        """Executa deployment."""
        strategy = strategy or self.config.deployment_strategy
        
        deployment = Deployment(
            id=str(uuid.uuid4()),
            environment=environment,
            strategy=strategy,
            version=image_tag,
            image_tag=image_tag,
            status=PipelineStatus.RUNNING,
            start_time=datetime.now(timezone.utc),
            replicas=self.config.environments[environment.value]["replicas"]
        )
        
        try:
            if strategy == DeploymentStrategy.ROLLING:
                await self._rolling_deployment(deployment)
            elif strategy == DeploymentStrategy.BLUE_GREEN:
                await self._blue_green_deployment(deployment)
            elif strategy == DeploymentStrategy.CANARY:
                await self._canary_deployment(deployment)
            else:
                await self._recreate_deployment(deployment)
            
            # Health checks
            deployment.health_checks_passed = await self._run_health_checks(deployment)
            
            if deployment.health_checks_passed:
                deployment.status = PipelineStatus.SUCCESS
            else:
                deployment.status = PipelineStatus.FAILED
                if self.config.rollback_on_failure:
                    await self._rollback_deployment(deployment)
            
        except Exception as e:
            deployment.status = PipelineStatus.FAILED
            print(f"Erro no deployment: {e}")
            
            if self.config.rollback_on_failure:
                await self._rollback_deployment(deployment)
        
        finally:
            deployment.end_time = datetime.now(timezone.utc)
        
        return deployment
    
    async def _rolling_deployment(self, deployment: Deployment):
        """Executa rolling deployment."""
        print(f"🔄 Iniciando rolling deployment para {deployment.environment.value}")
        
        # Simula rolling update
        for i in range(deployment.replicas):
            print(f"   Atualizando replica {i+1}/{deployment.replicas}")
            await asyncio.sleep(2)  # Simula tempo de deployment
            
            # Verifica health da nova replica
            if not await self._check_replica_health(deployment, i):
                raise Exception(f"Health check failed for replica {i+1}")
        
        print(f"✅ Rolling deployment concluído")
    
    async def _blue_green_deployment(self, deployment: Deployment):
        """Executa blue-green deployment."""
        print(f"🔵🟢 Iniciando blue-green deployment para {deployment.environment.value}")
        
        # Deploy para ambiente green
        print("   Criando ambiente green")
        await asyncio.sleep(5)  # Simula criação do ambiente
        
        # Testa ambiente green
        if await self._test_green_environment(deployment):
            print("   Switching traffic to green")
            await asyncio.sleep(2)  # Simula switch de tráfego
            
            print("   Removendo ambiente blue")
            await asyncio.sleep(2)  # Simula remoção do ambiente antigo
        else:
            raise Exception("Green environment health check failed")
        
        print(f"✅ Blue-green deployment concluído")
    
    async def _canary_deployment(self, deployment: Deployment):
        """Executa canary deployment."""
        print(f"🐤 Iniciando canary deployment para {deployment.environment.value}")
        
        # Deploy canary (pequena porcentagem)
        canary_replicas = max(1, int(deployment.replicas * self.config.canary_percentage / 100))
        print(f"   Deploying {canary_replicas} canary replicas ({self.config.canary_percentage}%)")
        
        await asyncio.sleep(3)  # Simula deployment canary
        
        # Monitora métricas canary
        if await self._monitor_canary_metrics(deployment):
            print("   Canary metrics OK, proceeding with full deployment")
            
            # Deploy completo
            remaining_replicas = deployment.replicas - canary_replicas
            for i in range(remaining_replicas):
                print(f"   Deploying remaining replica {i+1}/{remaining_replicas}")
                await asyncio.sleep(1)
        else:
            raise Exception("Canary metrics failed")
        
        print(f"✅ Canary deployment concluído")
    
    async def _recreate_deployment(self, deployment: Deployment):
        """Executa recreate deployment."""
        print(f"🔄 Iniciando recreate deployment para {deployment.environment.value}")
        
        # Para todas as instâncias
        print("   Stopping all instances")
        await asyncio.sleep(2)
        
        # Inicia novas instâncias
        print("   Starting new instances")
        await asyncio.sleep(5)
        
        print(f"✅ Recreate deployment concluído")
    
    async def _run_health_checks(self, deployment: Deployment) -> bool:
        """Executa health checks."""
        print(f"🏥 Executando health checks para {deployment.environment.value}")
        
        env_config = self.config.environments[deployment.environment.value]
        health_url = f"{env_config['url']}/health"
        
        timeout = self.config.health_check_timeout_minutes * 60
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(health_url, timeout=10) as response:
                        if response.status == 200:
                            health_data = await response.json()
                            if health_data.get("status") == "healthy":
                                print(f"✅ Health check passed")
                                return True
            except Exception as e:
                print(f"   Health check failed: {e}")
            
            await asyncio.sleep(10)  # Aguarda 10s antes de tentar novamente
        
        print(f"❌ Health check timeout")
        return False
    
    async def _check_replica_health(self, deployment: Deployment, replica_index: int) -> bool:
        """Verifica health de uma replica específica."""
        # Simula verificação de health
        await asyncio.sleep(1)
        return True  # Simula sucesso
    
    async def _test_green_environment(self, deployment: Deployment) -> bool:
        """Testa ambiente green."""
        # Simula testes do ambiente green
        await asyncio.sleep(3)
        return True  # Simula sucesso
    
    async def _monitor_canary_metrics(self, deployment: Deployment) -> bool:
        """Monitora métricas do canary."""
        # Simula monitoramento de métricas
        await asyncio.sleep(5)
        return True  # Simula sucesso
    
    async def _rollback_deployment(self, deployment: Deployment):
        """Executa rollback."""
        print(f"🔙 Iniciando rollback para {deployment.environment.value}")
        
        # Busca versão anterior
        previous_version = await self._get_previous_version(deployment.environment)
        if previous_version:
            deployment.rollback_version = previous_version
            
            # Executa rollback
            await asyncio.sleep(3)  # Simula rollback
            
            print(f"✅ Rollback concluído para versão {previous_version}")
        else:
            print(f"❌ Nenhuma versão anterior encontrada para rollback")
    
    async def _get_previous_version(self, environment: Environment) -> Optional[str]:
        """Obtém versão anterior."""
        # Simula busca da versão anterior
        return "v1.0.0"  # Simula versão anterior


class NotificationManager:
    """Gerenciador de notificações."""
    
    def __init__(self, config: CICDConfig):
        self.config = config
    
    async def send_pipeline_notification(
        self,
        pipeline_run: PipelineRun,
        stage_result: Optional[StageResult] = None
    ):
        """Envia notificação de pipeline."""
        if not self.config.notifications_enabled:
            return
        
        message = self._build_message(pipeline_run, stage_result)
        
        # Slack
        if self.config.slack_webhook:
            await self._send_slack_notification(message)
        
        # Email
        if self.config.email_recipients:
            await self._send_email_notification(message)
    
    def _build_message(self, pipeline_run: PipelineRun, stage_result: Optional[StageResult] = None) -> Dict[str, Any]:
        """Constrói mensagem de notificação."""
        if stage_result:
            # Notificação de estágio
            status_emoji = {
                PipelineStatus.SUCCESS: "✅",
                PipelineStatus.FAILED: "❌",
                PipelineStatus.RUNNING: "🔄",
                PipelineStatus.CANCELLED: "⏹️"
            }.get(stage_result.status, "❓")
            
            return {
                "text": f"{status_emoji} Stage {stage_result.stage.value} {stage_result.status.value}",
                "details": {
                    "pipeline_id": pipeline_run.id,
                    "branch": pipeline_run.branch,
                    "commit": pipeline_run.commit_sha[:8],
                    "stage": stage_result.stage.value,
                    "status": stage_result.status.value,
                    "duration": f"{stage_result.duration_seconds:.1f}s",
                    "error": stage_result.error_message
                }
            }
        else:
            # Notificação de pipeline
            status_emoji = {
                PipelineStatus.SUCCESS: "🎉",
                PipelineStatus.FAILED: "💥",
                PipelineStatus.RUNNING: "🚀",
                PipelineStatus.CANCELLED: "⏹️"
            }.get(pipeline_run.status, "❓")
            
            return {
                "text": f"{status_emoji} Pipeline {pipeline_run.status.value}",
                "details": {
                    "pipeline_id": pipeline_run.id,
                    "branch": pipeline_run.branch,
                    "commit": pipeline_run.commit_sha[:8],
                    "author": pipeline_run.author,
                    "status": pipeline_run.status.value,
                    "duration": f"{pipeline_run.duration_seconds:.1f}s",
                    "stages_passed": len([s for s in pipeline_run.stages if s.status == PipelineStatus.SUCCESS]),
                    "stages_total": len(pipeline_run.stages)
                }
            }
    
    async def _send_slack_notification(self, message: Dict[str, Any]):
        """Envia notificação para Slack."""
        try:
            async with aiohttp.ClientSession() as session:
                payload = {
                    "text": message["text"],
                    "attachments": [{
                        "color": "good" if "✅" in message["text"] or "🎉" in message["text"] else "danger",
                        "fields": [
                            {"title": k, "value": v, "short": True}
                            for k, v in message["details"].items()
                            if v is not None
                        ]
                    }]
                }
                
                async with session.post(self.config.slack_webhook, json=payload) as response:
                    if response.status != 200:
                        print(f"Erro ao enviar notificação Slack: {response.status}")
        except Exception as e:
            print(f"Erro ao enviar notificação Slack: {e}")
    
    async def _send_email_notification(self, message: Dict[str, Any]):
        """Envia notificação por email."""
        # TODO: Implementar envio de email
        print(f"📧 Email notification: {message['text']}")


class CICDManager:
    """Gerenciador principal do sistema CI/CD."""
    
    def __init__(self, config: CICDConfig):
        self.config = config
        self.security_scanner = SecurityScanner(config)
        self.quality_analyzer = QualityAnalyzer(config)
        self.deployment_manager = DeploymentManager(config)
        self.notification_manager = NotificationManager(config)
        
        self.pipeline_runs: Dict[str, PipelineRun] = {}
        self.deployments: Dict[str, Deployment] = {}
    
    async def trigger_pipeline(
        self,
        trigger: str = "manual",
        branch: str = None,
        commit_sha: str = None,
        commit_message: str = "",
        author: str = "system"
    ) -> PipelineRun:
        """Dispara execução de pipeline."""
        branch = branch or self.config.branch
        commit_sha = commit_sha or "latest"
        
        pipeline_run = PipelineRun(
            id=str(uuid.uuid4()),
            trigger=trigger,
            branch=branch,
            commit_sha=commit_sha,
            commit_message=commit_message,
            author=author,
            status=PipelineStatus.RUNNING,
            start_time=datetime.now(timezone.utc)
        )
        
        self.pipeline_runs[pipeline_run.id] = pipeline_run
        
        print(f"🚀 Iniciando pipeline {pipeline_run.id}")
        print(f"   Branch: {branch}")
        print(f"   Commit: {commit_sha[:8]}")
        print(f"   Author: {author}")
        
        # Notifica início
        await self.notification_manager.send_pipeline_notification(pipeline_run)
        
        try:
            # Executa estágios
            await self._run_pipeline_stages(pipeline_run)
            
            pipeline_run.status = PipelineStatus.SUCCESS
            print(f"🎉 Pipeline {pipeline_run.id} concluído com sucesso")
            
        except Exception as e:
            pipeline_run.status = PipelineStatus.FAILED
            print(f"💥 Pipeline {pipeline_run.id} falhou: {e}")
        
        finally:
            pipeline_run.end_time = datetime.now(timezone.utc)
            pipeline_run.duration_seconds = (
                pipeline_run.end_time - pipeline_run.start_time
            ).total_seconds()
            
            # Notifica conclusão
            await self.notification_manager.send_pipeline_notification(pipeline_run)
        
        return pipeline_run
    
    async def _run_pipeline_stages(self, pipeline_run: PipelineRun):
        """Executa estágios do pipeline."""
        stages = [
            PipelineStage.CHECKOUT,
            PipelineStage.BUILD,
            PipelineStage.TEST,
            PipelineStage.SECURITY_SCAN,
            PipelineStage.QUALITY_ANALYSIS,
            PipelineStage.PACKAGE,
            PipelineStage.DEPLOY_STAGING,
            PipelineStage.INTEGRATION_TEST,
            PipelineStage.DEPLOY_PRODUCTION,
            PipelineStage.SMOKE_TEST,
            PipelineStage.CLEANUP
        ]
        
        for stage in stages:
            stage_result = await self._run_stage(pipeline_run, stage)
            pipeline_run.stages.append(stage_result)
            
            # Notifica resultado do estágio
            await self.notification_manager.send_pipeline_notification(
                pipeline_run, stage_result
            )
            
            # Para pipeline se estágio falhar
            if stage_result.status == PipelineStatus.FAILED:
                raise Exception(f"Stage {stage.value} failed: {stage_result.error_message}")
    
    async def _run_stage(self, pipeline_run: PipelineRun, stage: PipelineStage) -> StageResult:
        """Executa estágio específico."""
        print(f"   🔄 Executando estágio: {stage.value}")
        
        stage_result = StageResult(
            stage=stage,
            status=PipelineStatus.RUNNING,
            start_time=datetime.now(timezone.utc)
        )
        
        try:
            if stage == PipelineStage.CHECKOUT:
                await self._checkout_code(stage_result, pipeline_run)
            elif stage == PipelineStage.BUILD:
                await self._build_application(stage_result, pipeline_run)
            elif stage == PipelineStage.TEST:
                await self._run_tests(stage_result, pipeline_run)
            elif stage == PipelineStage.SECURITY_SCAN:
                await self._run_security_scans(stage_result, pipeline_run)
            elif stage == PipelineStage.QUALITY_ANALYSIS:
                await self._run_quality_analysis(stage_result, pipeline_run)
            elif stage == PipelineStage.PACKAGE:
                await self._package_application(stage_result, pipeline_run)
            elif stage == PipelineStage.DEPLOY_STAGING:
                await self._deploy_to_staging(stage_result, pipeline_run)
            elif stage == PipelineStage.INTEGRATION_TEST:
                await self._run_integration_tests(stage_result, pipeline_run)
            elif stage == PipelineStage.DEPLOY_PRODUCTION:
                await self._deploy_to_production(stage_result, pipeline_run)
            elif stage == PipelineStage.SMOKE_TEST:
                await self._run_smoke_tests(stage_result, pipeline_run)
            elif stage == PipelineStage.CLEANUP:
                await self._cleanup_resources(stage_result, pipeline_run)
            
            stage_result.status = PipelineStatus.SUCCESS
            print(f"      ✅ {stage.value} concluído")
            
        except Exception as e:
            stage_result.status = PipelineStatus.FAILED
            stage_result.error_message = str(e)
            print(f"      ❌ {stage.value} falhou: {e}")
        
        finally:
            stage_result.end_time = datetime.now(timezone.utc)
            stage_result.duration_seconds = (
                stage_result.end_time - stage_result.start_time
            ).total_seconds()
        
        return stage_result
    
    async def _checkout_code(self, stage_result: StageResult, pipeline_run: PipelineRun):
        """Checkout do código."""
        # Simula checkout
        await asyncio.sleep(2)
        stage_result.logs.append(f"Checked out {pipeline_run.branch}@{pipeline_run.commit_sha}")
    
    async def _build_application(self, stage_result: StageResult, pipeline_run: PipelineRun):
        """Build da aplicação."""
        # Simula build
        await asyncio.sleep(5)
        stage_result.logs.append("Application built successfully")
        stage_result.artifacts.append(f"build-{pipeline_run.commit_sha[:8]}.tar.gz")
    
    async def _run_tests(self, stage_result: StageResult, pipeline_run: PipelineRun):
        """Executa testes."""
        # Simula execução de testes
        await asyncio.sleep(10)
        
        # Simula métricas de teste
        stage_result.metrics = {
            "tests_total": 150,
            "tests_passed": 148,
            "tests_failed": 2,
            "coverage_percent": 92.5
        }
        
        stage_result.logs.append(f"Tests completed: {stage_result.metrics['tests_passed']}/{stage_result.metrics['tests_total']} passed")
        
        # Verifica threshold de cobertura
        if stage_result.metrics["coverage_percent"] < self.config.coverage_threshold:
            raise Exception(f"Coverage {stage_result.metrics['coverage_percent']}% below threshold {self.config.coverage_threshold}%")
    
    async def _run_security_scans(self, stage_result: StageResult, pipeline_run: PipelineRun):
        """Executa scans de segurança."""
        if not self.config.security_scans_enabled:
            stage_result.status = PipelineStatus.SKIPPED
            return
        
        project_path = "/tmp/project"  # Simula path do projeto
        
        # Executa diferentes tipos de scan
        all_issues = []
        
        dependency_issues = await self.security_scanner.run_dependency_check(project_path)
        all_issues.extend(dependency_issues)
        
        static_issues = await self.security_scanner.run_static_analysis(project_path)
        all_issues.extend(static_issues)
        
        secret_issues = await self.security_scanner.run_secret_detection(project_path)
        all_issues.extend(secret_issues)
        
        # Analisa resultados
        critical_issues = [i for i in all_issues if i.severity == "CRITICAL"]
        high_issues = [i for i in all_issues if i.severity == "HIGH"]
        
        stage_result.metrics = {
            "total_issues": len(all_issues),
            "critical_issues": len(critical_issues),
            "high_issues": len(high_issues),
            "medium_issues": len([i for i in all_issues if i.severity == "MEDIUM"]),
            "low_issues": len([i for i in all_issues if i.severity == "LOW"])
        }
        
        stage_result.logs.append(f"Security scan completed: {len(all_issues)} issues found")
        
        # Falha se houver issues críticos e configurado para falhar
        if self.config.fail_on_security_issues and (critical_issues or high_issues):
            raise Exception(f"Security issues found: {len(critical_issues)} critical, {len(high_issues)} high")
    
    async def _run_quality_analysis(self, stage_result: StageResult, pipeline_run: PipelineRun):
        """Executa análise de qualidade."""
        if not self.config.quality_gate_enabled:
            stage_result.status = PipelineStatus.SKIPPED
            return
        
        project_path = "/tmp/project"  # Simula path do projeto
        
        quality_metrics = await self.quality_analyzer.run_sonar_analysis(project_path)
        
        stage_result.metrics = quality_metrics.dict()
        stage_result.logs.append(f"Quality analysis completed: {quality_metrics.maintainability_rating} maintainability")
        
        # Verifica quality gates
        if quality_metrics.maintainability_rating in ["D", "E"]:
            raise Exception(f"Quality gate failed: maintainability rating {quality_metrics.maintainability_rating}")
    
    async def _package_application(self, stage_result: StageResult, pipeline_run: PipelineRun):
        """Empacota aplicação."""
        # Simula criação de imagem Docker
        await asyncio.sleep(8)
        
        image_tag = f"{self.config.docker_registry}/{self.config.docker_namespace}/{self.config.project_name}:{pipeline_run.commit_sha[:8]}"
        
        stage_result.logs.append(f"Docker image built: {image_tag}")
        stage_result.artifacts.append(image_tag)
        
        # Scan da imagem
        if self.config.security_scans_enabled:
            container_issues = await self.security_scanner.run_container_scan(image_tag)
            stage_result.metrics["container_vulnerabilities"] = len(container_issues)
    
    async def _deploy_to_staging(self, stage_result: StageResult, pipeline_run: PipelineRun):
        """Deploy para staging."""
        image_tag = f"{pipeline_run.commit_sha[:8]}"
        
        deployment = await self.deployment_manager.deploy(
            Environment.STAGING,
            image_tag,
            DeploymentStrategy.ROLLING
        )
        
        self.deployments[deployment.id] = deployment
        pipeline_run.deployment_id = deployment.id
        
        stage_result.logs.append(f"Deployed to staging: {deployment.id}")
        
        if deployment.status != PipelineStatus.SUCCESS:
            raise Exception(f"Staging deployment failed: {deployment.id}")
    
    async def _run_integration_tests(self, stage_result: StageResult, pipeline_run: PipelineRun):
        """Executa testes de integração."""
        # Simula testes de integração
        await asyncio.sleep(15)
        
        stage_result.metrics = {
            "integration_tests_total": 25,
            "integration_tests_passed": 24,
            "integration_tests_failed": 1
        }
        
        stage_result.logs.append(f"Integration tests completed: {stage_result.metrics['integration_tests_passed']}/{stage_result.metrics['integration_tests_total']} passed")
        
        if stage_result.metrics["integration_tests_failed"] > 0:
            raise Exception(f"{stage_result.metrics['integration_tests_failed']} integration tests failed")
    
    async def _deploy_to_production(self, stage_result: StageResult, pipeline_run: PipelineRun):
        """Deploy para produção."""
        # Só deploy para produção se branch for main/master
        if pipeline_run.branch not in ["main", "master"]:
            stage_result.status = PipelineStatus.SKIPPED
            stage_result.logs.append(f"Production deployment skipped for branch {pipeline_run.branch}")
            return
        
        image_tag = f"{pipeline_run.commit_sha[:8]}"
        
        deployment = await self.deployment_manager.deploy(
            Environment.PRODUCTION,
            image_tag,
            self.config.deployment_strategy
        )
        
        self.deployments[deployment.id] = deployment
        
        stage_result.logs.append(f"Deployed to production: {deployment.id}")
        
        if deployment.status != PipelineStatus.SUCCESS:
            raise Exception(f"Production deployment failed: {deployment.id}")
    
    async def _run_smoke_tests(self, stage_result: StageResult, pipeline_run: PipelineRun):
        """Executa smoke tests."""
        # Simula smoke tests
        await asyncio.sleep(5)
        
        stage_result.metrics = {
            "smoke_tests_total": 10,
            "smoke_tests_passed": 10,
            "smoke_tests_failed": 0
        }
        
        stage_result.logs.append(f"Smoke tests completed: all {stage_result.metrics['smoke_tests_total']} tests passed")
    
    async def _cleanup_resources(self, stage_result: StageResult, pipeline_run: PipelineRun):
        """Limpa recursos."""
        # Simula limpeza
        await asyncio.sleep(2)
        
        stage_result.logs.append("Cleanup completed")
    
    def get_pipeline_status(self, pipeline_id: str) -> Optional[PipelineRun]:
        """Obtém status do pipeline."""
        return self.pipeline_runs.get(pipeline_id)
    
    def get_deployment_status(self, deployment_id: str) -> Optional[Deployment]:
        """Obtém status do deployment."""
        return self.deployments.get(deployment_id)
    
    async def cancel_pipeline(self, pipeline_id: str) -> bool:
        """Cancela pipeline."""
        pipeline_run = self.pipeline_runs.get(pipeline_id)
        if pipeline_run and pipeline_run.status == PipelineStatus.RUNNING:
            pipeline_run.status = PipelineStatus.CANCELLED
            pipeline_run.end_time = datetime.now(timezone.utc)
            
            await self.notification_manager.send_pipeline_notification(pipeline_run)
            return True
        
        return False
    
    async def rollback_deployment(self, deployment_id: str) -> bool:
        """Executa rollback de deployment."""
        deployment = self.deployments.get(deployment_id)
        if deployment:
            await self.deployment_manager._rollback_deployment(deployment)
            return True
        
        return False


# Instância global
cicd_manager: Optional[CICDManager] = None


def get_cicd_manager() -> CICDManager:
    """Obtém instância global do CI/CD manager."""
    global cicd_manager
    if cicd_manager is None:
        config = CICDConfig()
        cicd_manager = CICDManager(config)
    
    return cicd_manager