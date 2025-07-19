"""Middlewares customizados do MegaEmu Modern.

Implementa middlewares para logging, segurança, rate limiting
e outras funcionalidades transversais da aplicação.
"""

import time
from typing import Callable, Dict, Any
from collections import defaultdict, deque
from datetime import datetime, timedelta

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from loguru import logger

from app.core.config import settings
from app.core.logging import log_request, log_security_event


class LoggingMiddleware(BaseHTTPMiddleware):
    """Middleware para logging de requisições HTTP.
    
    Registra todas as requisições com informações detalhadas
    incluindo duração, status, IP do cliente, etc.
    """
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Processa requisição e registra logs."""
        start_time = time.time()
        
        # Extrair informações da requisição
        client_ip = self._get_client_ip(request)
        user_agent = request.headers.get("user-agent", "Unknown")
        method = request.method
        url = str(request.url)
        
        # Processar requisição
        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception as e:
            logger.error(f"Erro durante processamento da requisição: {str(e)}")
            status_code = 500
            response = JSONResponse(
                status_code=500,
                content={"error": "internal_server_error", "message": "Erro interno do servidor"}
            )
        
        # Calcular duração
        duration = (time.time() - start_time) * 1000  # em ms
        
        # Extrair user_id se disponível
        user_id = getattr(request.state, "user_id", None)
        
        # Registrar log
        log_request(
            method=method,
            url=url,
            status_code=status_code,
            duration=duration,
            client_ip=client_ip,
            user_agent=user_agent,
            user_id=user_id
        )
        
        # Adicionar headers de timing
        if hasattr(response, "headers"):
            response.headers["X-Process-Time"] = str(round(duration, 2))
        
        return response
    
    def _get_client_ip(self, request: Request) -> str:
        """Extrai IP real do cliente considerando proxies."""
        # Verificar headers de proxy
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
        
        # Fallback para IP direto
        return request.client.host if request.client else "unknown"


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Middleware para adicionar headers de segurança.
    
    Adiciona headers importantes para segurança como
    HSTS, CSP, X-Frame-Options, etc.
    """
    
    def __init__(self, app, security_headers: Dict[str, str] = None):
        super().__init__(app)
        self.security_headers = security_headers or self._get_default_headers()
    
    def _get_default_headers(self) -> Dict[str, str]:
        """Retorna headers de segurança padrão."""
        return {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "X-XSS-Protection": "1; mode=block",
            "Referrer-Policy": "strict-origin-when-cross-origin",
            "Content-Security-Policy": (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
                "style-src 'self' 'unsafe-inline'; "
                "img-src 'self' data: https:; "
                "font-src 'self' data:; "
                "connect-src 'self';"
            ),
        }
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Adiciona headers de segurança à resposta."""
        response = await call_next(request)
        
        # Adicionar headers de segurança
        for header, value in self.security_headers.items():
            if hasattr(response, "headers"):
                response.headers[header] = value
        
        # HSTS apenas para HTTPS
        if request.url.scheme == "https" and hasattr(response, "headers"):
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains; preload"
            )
        
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Middleware para rate limiting.
    
    Implementa rate limiting baseado em IP com diferentes
    limites para diferentes tipos de endpoints.
    """
    
    def __init__(self, app):
        super().__init__(app)
        self.requests: Dict[str, deque] = defaultdict(deque)
        self.blocked_ips: Dict[str, datetime] = {}
        
        # Configurações de rate limit
        self.limits = {
            "default": {"requests": 100, "window": 60},  # 100 req/min
            "auth": {"requests": 10, "window": 60},      # 10 req/min para auth
            "upload": {"requests": 5, "window": 60},     # 5 req/min para upload
        }
        
        # Padrões de URL para diferentes limites
        self.url_patterns = {
            "auth": ["/api/v1/auth/"],
            "upload": ["/api/v1/roms/upload", "/api/v1/games/import"],
        }
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Verifica rate limit antes de processar requisição."""
        if not settings.ENABLE_RATE_LIMITING:
            return await call_next(request)
        
        client_ip = self._get_client_ip(request)
        
        # Verificar se IP está bloqueado temporariamente
        if self._is_ip_blocked(client_ip):
            log_security_event(
                event_type="rate_limit_blocked",
                client_ip=client_ip,
                details={"url": str(request.url)}
            )
            return JSONResponse(
                status_code=429,
                content={
                    "error": "rate_limit_exceeded",
                    "message": "Muitas requisições. Tente novamente mais tarde.",
                    "retry_after": 60
                },
                headers={"Retry-After": "60"}
            )
        
        # Determinar tipo de limite baseado na URL
        limit_type = self._get_limit_type(str(request.url))
        limit_config = self.limits[limit_type]
        
        # Verificar rate limit
        if self._is_rate_limited(client_ip, limit_config):
            # Bloquear IP temporariamente após muitas violações
            self._maybe_block_ip(client_ip)
            
            log_security_event(
                event_type="rate_limit_exceeded",
                client_ip=client_ip,
                details={
                    "url": str(request.url),
                    "limit_type": limit_type,
                    "limit": limit_config
                }
            )
            
            return JSONResponse(
                status_code=429,
                content={
                    "error": "rate_limit_exceeded",
                    "message": f"Limite de {limit_config['requests']} requisições por {limit_config['window']} segundos excedido.",
                    "retry_after": limit_config["window"]
                },
                headers={"Retry-After": str(limit_config["window"])}
            )
        
        # Registrar requisição
        self._record_request(client_ip)
        
        return await call_next(request)
    
    def _get_client_ip(self, request: Request) -> str:
        """Extrai IP do cliente."""
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        return request.client.host if request.client else "unknown"
    
    def _get_limit_type(self, url: str) -> str:
        """Determina tipo de limite baseado na URL."""
        for limit_type, patterns in self.url_patterns.items():
            for pattern in patterns:
                if pattern in url:
                    return limit_type
        return "default"
    
    def _is_rate_limited(self, client_ip: str, limit_config: Dict[str, int]) -> bool:
        """Verifica se cliente excedeu rate limit."""
        now = time.time()
        window = limit_config["window"]
        max_requests = limit_config["requests"]
        
        # Limpar requisições antigas
        requests = self.requests[client_ip]
        while requests and requests[0] < now - window:
            requests.popleft()
        
        # Verificar se excedeu limite
        return len(requests) >= max_requests
    
    def _record_request(self, client_ip: str) -> None:
        """Registra nova requisição."""
        self.requests[client_ip].append(time.time())
    
    def _is_ip_blocked(self, client_ip: str) -> bool:
        """Verifica se IP está bloqueado temporariamente."""
        if client_ip not in self.blocked_ips:
            return False
        
        # Verificar se bloqueio expirou
        if datetime.now() > self.blocked_ips[client_ip]:
            del self.blocked_ips[client_ip]
            return False
        
        return True
    
    def _maybe_block_ip(self, client_ip: str) -> None:
        """Bloqueia IP temporariamente após muitas violações."""
        # Contar violações recentes (últimos 5 minutos)
        now = time.time()
        recent_requests = [t for t in self.requests[client_ip] if t > now - 300]
        
        # Bloquear se muitas requisições em pouco tempo
        if len(recent_requests) > 200:  # Mais de 200 req em 5 min
            self.blocked_ips[client_ip] = datetime.now() + timedelta(minutes=15)
            logger.warning(f"IP {client_ip} bloqueado temporariamente por 15 minutos")


class TimingMiddleware(BaseHTTPMiddleware):
    """Middleware para medir tempo de resposta.
    
    Adiciona headers com informações de timing detalhadas
    para monitoramento de performance.
    """
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Mede tempo de processamento da requisição."""
        start_time = time.perf_counter()
        
        response = await call_next(request)
        
        process_time = time.perf_counter() - start_time
        
        if hasattr(response, "headers"):
            response.headers["X-Process-Time"] = str(round(process_time * 1000, 2))
            response.headers["X-Timestamp"] = str(int(time.time()))
        
        return response


class HealthCheckMiddleware(BaseHTTPMiddleware):
    """Middleware para health checks.
    
    Permite que health checks sejam processados rapidamente
    sem passar por outros middlewares pesados.
    """
    
    def __init__(self, app, health_paths: list = None):
        super().__init__(app)
        self.health_paths = health_paths or ["/health", "/api/v1/health"]
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Processa health checks de forma otimizada."""
        # Para health checks, processar rapidamente
        if any(request.url.path.startswith(path) for path in self.health_paths):
            # Adicionar header indicando que é health check
            response = await call_next(request)
            if hasattr(response, "headers"):
                response.headers["X-Health-Check"] = "true"
            return response
        
        return await call_next(request)