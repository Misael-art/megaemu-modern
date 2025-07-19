"""Utilitários para envio de emails.

Este módulo contém funções para envio de emails,
incluindo templates e configurações SMTP.
"""

import logging
from typing import List, Optional, Dict, Any
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import smtplib
import ssl
from pathlib import Path

from app.core.config import settings

logger = logging.getLogger(__name__)


async def send_email(
    to_email: str,
    subject: str,
    body: str,
    *,
    html_body: Optional[str] = None,
    attachments: Optional[List[Path]] = None,
    from_email: Optional[str] = None,
    from_name: Optional[str] = None
) -> bool:
    """Envia email usando configurações SMTP.
    
    Args:
        to_email: Email do destinatário
        subject: Assunto do email
        body: Corpo do email em texto
        html_body: Corpo do email em HTML (opcional)
        attachments: Lista de arquivos anexos (opcional)
        from_email: Email do remetente (opcional)
        from_name: Nome do remetente (opcional)
        
    Returns:
        True se email enviado com sucesso
        
    Raises:
        Exception: Se erro no envio
    """
    try:
        # Configurações padrão
        sender_email = from_email or settings.SMTP_USER
        sender_name = from_name or settings.PROJECT_NAME
        
        # Cria mensagem
        message = MIMEMultipart("alternative")
        message["Subject"] = subject
        message["From"] = f"{sender_name} <{sender_email}>"
        message["To"] = to_email
        
        # Adiciona corpo em texto
        text_part = MIMEText(body, "plain")
        message.attach(text_part)
        
        # Adiciona corpo em HTML se fornecido
        if html_body:
            html_part = MIMEText(html_body, "html")
            message.attach(html_part)
        
        # Adiciona anexos se fornecidos
        if attachments:
            for attachment_path in attachments:
                if attachment_path.exists():
                    with open(attachment_path, "rb") as attachment:
                        part = MIMEBase("application", "octet-stream")
                        part.set_payload(attachment.read())
                    
                    encoders.encode_base64(part)
                    part.add_header(
                        "Content-Disposition",
                        f"attachment; filename= {attachment_path.name}",
                    )
                    message.attach(part)
        
        # Envia email
        context = ssl.create_default_context()
        
        if settings.SMTP_TLS:
            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
                server.starttls(context=context)
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                server.sendmail(sender_email, to_email, message.as_string())
        else:
            with smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT, context=context) as server:
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                server.sendmail(sender_email, to_email, message.as_string())
        
        logger.info(f"Email enviado com sucesso para {to_email}")
        return True
        
    except Exception as e:
        logger.error(f"Erro ao enviar email para {to_email}: {e}")
        return False


async def send_verification_email(
    user_email: str,
    verification_token: str,
    user_name: Optional[str] = None
) -> bool:
    """Envia email de verificação de conta.
    
    Args:
        user_email: Email do usuário
        verification_token: Token de verificação
        user_name: Nome do usuário (opcional)
        
    Returns:
        True se email enviado com sucesso
    """
    verification_url = f"{settings.FRONTEND_URL}/verify-email?token={verification_token}"
    
    subject = f"Verificação de conta - {settings.PROJECT_NAME}"
    
    body = f"""
Olá{f' {user_name}' if user_name else ''},

Obrigado por se registrar no {settings.PROJECT_NAME}!

Para ativar sua conta, clique no link abaixo:
{verification_url}

Este link expira em 24 horas.

Se você não criou esta conta, ignore este email.

Atenciosamente,
Equipe {settings.PROJECT_NAME}
"""
    
    html_body = f"""
<html>
  <body>
    <h2>Verificação de conta - {settings.PROJECT_NAME}</h2>
    <p>Olá{f' {user_name}' if user_name else ''},</p>
    <p>Obrigado por se registrar no {settings.PROJECT_NAME}!</p>
    <p>Para ativar sua conta, clique no botão abaixo:</p>
    <p>
      <a href="{verification_url}" 
         style="background-color: #4CAF50; color: white; padding: 14px 20px; text-decoration: none; border-radius: 4px;">
        Verificar Email
      </a>
    </p>
    <p>Ou copie e cole este link no seu navegador:</p>
    <p><a href="{verification_url}">{verification_url}</a></p>
    <p><small>Este link expira em 24 horas.</small></p>
    <p>Se você não criou esta conta, ignore este email.</p>
    <br>
    <p>Atenciosamente,<br>Equipe {settings.PROJECT_NAME}</p>
  </body>
</html>
"""
    
    return await send_email(
        to_email=user_email,
        subject=subject,
        body=body,
        html_body=html_body
    )


async def send_password_reset_email(
    user_email: str,
    reset_token: str,
    user_name: Optional[str] = None
) -> bool:
    """Envia email de reset de senha.
    
    Args:
        user_email: Email do usuário
        reset_token: Token de reset
        user_name: Nome do usuário (opcional)
        
    Returns:
        True se email enviado com sucesso
    """
    reset_url = f"{settings.FRONTEND_URL}/reset-password?token={reset_token}"
    
    subject = f"Reset de senha - {settings.PROJECT_NAME}"
    
    body = f"""
Olá{f' {user_name}' if user_name else ''},

Recebemos uma solicitação para redefinir a senha da sua conta no {settings.PROJECT_NAME}.

Para redefinir sua senha, clique no link abaixo:
{reset_url}

Este link expira em 1 hora.

Se você não solicitou este reset, ignore este email.

Atenciosamente,
Equipe {settings.PROJECT_NAME}
"""
    
    html_body = f"""
<html>
  <body>
    <h2>Reset de senha - {settings.PROJECT_NAME}</h2>
    <p>Olá{f' {user_name}' if user_name else ''},</p>
    <p>Recebemos uma solicitação para redefinir a senha da sua conta no {settings.PROJECT_NAME}.</p>
    <p>Para redefinir sua senha, clique no botão abaixo:</p>
    <p>
      <a href="{reset_url}" 
         style="background-color: #f44336; color: white; padding: 14px 20px; text-decoration: none; border-radius: 4px;">
        Redefinir Senha
      </a>
    </p>
    <p>Ou copie e cole este link no seu navegador:</p>
    <p><a href="{reset_url}">{reset_url}</a></p>
    <p><small>Este link expira em 1 hora.</small></p>
    <p>Se você não solicitou este reset, ignore este email.</p>
    <br>
    <p>Atenciosamente,<br>Equipe {settings.PROJECT_NAME}</p>
  </body>
</html>
"""
    
    return await send_email(
        to_email=user_email,
        subject=subject,
        body=body,
        html_body=html_body
    )