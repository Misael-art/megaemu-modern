# =============================================================================
# DOCKERFILE PARA MEGAEMU MODERN BACKEND
# =============================================================================
# Multi-stage build para otimizar o tamanho da imagem final

# =============================================================================
# STAGE 1: Base Python com dependências do sistema
# =============================================================================
FROM python:3.11-slim as base

# Metadados da imagem
LABEL maintainer="MegaEmu Modern Team"
LABEL description="Backend API para sistema de gerenciamento de ROMs"
LABEL version="1.0.0"

# Variáveis de ambiente para Python
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    POETRY_VERSION=1.6.1

# Instalar dependências do sistema
RUN apt-get update && apt-get install -y \
    # Dependências básicas
    curl \
    wget \
    git \
    # Dependências para PostgreSQL
    libpq-dev \
    # Dependências para compilação
    gcc \
    g++ \
    # Dependências para processamento de imagens
    libjpeg-dev \
    libpng-dev \
    # Dependências para arquivos comprimidos
    unzip \
    p7zip-full \
    # Dependências para Playwright
    libnss3 \
    libatk-bridge2.0-0 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    libgbm1 \
    libxss1 \
    libasound2 \
    # Limpeza
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# =============================================================================
# STAGE 2: Dependências Python
# =============================================================================
FROM base as dependencies

# Instalar Poetry
RUN pip install poetry==$POETRY_VERSION

# Configurar Poetry
ENV POETRY_NO_INTERACTION=1 \
    POETRY_VENV_IN_PROJECT=1 \
    POETRY_CACHE_DIR=/tmp/poetry_cache

# Criar diretório de trabalho
WORKDIR /app

# Copiar arquivos de dependências
COPY requirements.txt .

# Instalar dependências Python
RUN pip install --no-cache-dir -r requirements.txt

# Instalar browsers para Playwright (se necessário)
RUN playwright install chromium

# =============================================================================
# STAGE 3: Aplicação
# =============================================================================
FROM dependencies as application

# Criar usuário não-root para segurança
RUN groupadd -r megaemu && useradd -r -g megaemu megaemu

# Criar diretórios necessários
RUN mkdir -p /app/data/{roms,covers,screenshots,temp,bios,saves,states} \
    && mkdir -p /app/logs \
    && mkdir -p /app/backups \
    && mkdir -p /app/emulators

# Copiar código da aplicação
COPY --chown=megaemu:megaemu . .

# Definir permissões
RUN chown -R megaemu:megaemu /app

# Mudar para usuário não-root
USER megaemu

# Expor porta da aplicação
EXPOSE 8000

# Variáveis de ambiente padrão
ENV ENVIRONMENT=production \
    HOST=0.0.0.0 \
    PORT=8000 \
    WORKERS=4

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Comando padrão
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

# =============================================================================
# STAGE 4: Desenvolvimento (opcional)
# =============================================================================
FROM application as development

# Voltar para root temporariamente para instalar dependências de dev
USER root

# Instalar dependências de desenvolvimento
RUN pip install --no-cache-dir \
    pytest \
    pytest-asyncio \
    pytest-cov \
    black \
    isort \
    flake8 \
    mypy \
    pre-commit

# Voltar para usuário não-root
USER megaemu

# Configurações para desenvolvimento
ENV ENVIRONMENT=development \
    DEBUG=true \
    RELOAD=true

# Comando para desenvolvimento com reload
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]