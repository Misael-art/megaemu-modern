"""Exceções customizadas do MegaEmu Modern.

Define hierarquia de exceções específicas do domínio para
tratamento consistente de erros em toda a aplicação.
"""

from typing import Any, Dict, Optional


class MegaEmuException(Exception):
    """Exceção base do MegaEmu Modern.
    
    Todas as exceções customizadas devem herdar desta classe.
    """
    
    def __init__(
        self,
        message: str,
        error_code: str = "megaemu_error",
        status_code: int = 500,
        details: Optional[Dict[str, Any]] = None
    ):
        self.message = message
        self.error_code = error_code
        self.status_code = status_code
        self.details = details or {}
        super().__init__(self.message)


class ValidationError(MegaEmuException):
    """Erro de validação de dados."""
    
    def __init__(
        self,
        message: str,
        field: Optional[str] = None,
        value: Optional[Any] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        error_details = details or {}
        if field:
            error_details["field"] = field
        if value is not None:
            error_details["value"] = str(value)
            
        super().__init__(
            message=message,
            error_code="validation_error",
            status_code=422,
            details=error_details
        )


class DatabaseError(MegaEmuException):
    """Erro relacionado ao banco de dados."""
    
    def __init__(
        self,
        message: str,
        operation: Optional[str] = None,
        table: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        error_details = details or {}
        if operation:
            error_details["operation"] = operation
        if table:
            error_details["table"] = table
            
        super().__init__(
            message=message,
            error_code="database_error",
            status_code=500,
            details=error_details
        )


class AuthenticationError(MegaEmuException):
    """Erro de autenticação."""
    
    def __init__(self, message: str = "Credenciais inválidas"):
        super().__init__(
            message=message,
            error_code="authentication_error",
            status_code=401
        )


class AuthorizationError(MegaEmuException):
    """Erro de autorização/permissão."""
    
    def __init__(self, message: str = "Acesso negado"):
        super().__init__(
            message=message,
            error_code="authorization_error",
            status_code=403
        )


class NotFoundError(MegaEmuException):
    """Erro quando recurso não é encontrado."""
    
    def __init__(
        self,
        message: str,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None
    ):
        details = {}
        if resource_type:
            details["resource_type"] = resource_type
        if resource_id:
            details["resource_id"] = resource_id
            
        super().__init__(
            message=message,
            error_code="not_found",
            status_code=404,
            details=details
        )


class ConflictError(MegaEmuException):
    """Erro de conflito (recurso já existe, etc.)."""
    
    def __init__(
        self,
        message: str,
        conflicting_field: Optional[str] = None,
        conflicting_value: Optional[str] = None
    ):
        details = {}
        if conflicting_field:
            details["conflicting_field"] = conflicting_field
        if conflicting_value:
            details["conflicting_value"] = conflicting_value
            
        super().__init__(
            message=message,
            error_code="conflict_error",
            status_code=409,
            details=details
        )


class FileError(MegaEmuException):
    """Erro relacionado a operações de arquivo."""
    
    def __init__(
        self,
        message: str,
        file_path: Optional[str] = None,
        operation: Optional[str] = None
    ):
        details = {}
        if file_path:
            details["file_path"] = file_path
        if operation:
            details["operation"] = operation
            
        super().__init__(
            message=message,
            error_code="file_error",
            status_code=500,
            details=details
        )


class ExternalServiceError(MegaEmuException):
    """Erro ao comunicar com serviços externos."""
    
    def __init__(
        self,
        message: str,
        service_name: Optional[str] = None,
        status_code: int = 502
    ):
        details = {}
        if service_name:
            details["service_name"] = service_name
            
        super().__init__(
            message=message,
            error_code="external_service_error",
            status_code=status_code,
            details=details
        )


class RateLimitError(MegaEmuException):
    """Erro de limite de taxa excedido."""
    
    def __init__(
        self,
        message: str = "Limite de requisições excedido",
        retry_after: Optional[int] = None
    ):
        details = {}
        if retry_after:
            details["retry_after"] = retry_after
            
        super().__init__(
            message=message,
            error_code="rate_limit_error",
            status_code=429,
            details=details
        )


class TaskError(MegaEmuException):
    """Erro relacionado a tarefas assíncronas."""
    
    def __init__(
        self,
        message: str,
        task_id: Optional[str] = None,
        task_type: Optional[str] = None
    ):
        details = {}
        if task_id:
            details["task_id"] = task_id
        if task_type:
            details["task_type"] = task_type
            
        super().__init__(
            message=message,
            error_code="task_error",
            status_code=500,
            details=details
        )


class ConfigurationError(MegaEmuException):
    """Erro de configuração da aplicação."""
    
    def __init__(
        self,
        message: str,
        config_key: Optional[str] = None
    ):
        details = {}
        if config_key:
            details["config_key"] = config_key
            
        super().__init__(
            message=message,
            error_code="configuration_error",
            status_code=500,
            details=details
        )