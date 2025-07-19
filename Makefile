# =============================================================================
# MAKEFILE - MEGAEMU MODERN
# =============================================================================
# Automação de tarefas para desenvolvimento e deployment

.PHONY: help install dev prod test lint format clean docker-build docker-up docker-down migrate backup restore

# Configurações padrão
PYTHON := python
PIP := pip
DOCKER_COMPOSE := docker-compose
ALEMBIC := alembic

# Cores para output
RED := \033[31m
GREEN := \033[32m
YELLOW := \033[33m
BLUE := \033[34m
MAGENTA := \033[35m
CYAN := \033[36m
WHITE := \033[37m
RESET := \033[0m

# =============================================================================
# HELP
# =============================================================================
help: ## Mostra esta mensagem de ajuda
	@echo "$(CYAN)MegaEmu Modern - Comandos Disponíveis$(RESET)"
	@echo ""
	@echo "$(YELLOW)Desenvolvimento:$(RESET)"
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  $(GREEN)%-15s$(RESET) %s\n", $$1, $$2}' $(MAKEFILE_LIST) | grep -E "install|dev|test|lint|format|clean"
	@echo ""
	@echo "$(YELLOW)Docker:$(RESET)"
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  $(GREEN)%-15s$(RESET) %s\n", $$1, $$2}' $(MAKEFILE_LIST) | grep -E "docker"
	@echo ""
	@echo "$(YELLOW)Banco de Dados:$(RESET)"
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  $(GREEN)%-15s$(RESET) %s\n", $$1, $$2}' $(MAKEFILE_LIST) | grep -E "migrate|backup|restore"
	@echo ""
	@echo "$(YELLOW)Produção:$(RESET)"
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  $(GREEN)%-15s$(RESET) %s\n", $$1, $$2}' $(MAKEFILE_LIST) | grep -E "prod|deploy"

# =============================================================================
# INSTALAÇÃO E CONFIGURAÇÃO
# =============================================================================
install: ## Instala dependências do projeto
	@echo "$(BLUE)Instalando dependências...$(RESET)"
	cd backend && $(PIP) install -r requirements.txt
	@echo "$(GREEN)Dependências instaladas com sucesso!$(RESET)"

install-dev: ## Instala dependências de desenvolvimento
	@echo "$(BLUE)Instalando dependências de desenvolvimento...$(RESET)"
	cd backend && $(PIP) install -r requirements.txt
	cd backend && $(PIP) install pytest pytest-asyncio pytest-cov black isort flake8 mypy pre-commit
	@echo "$(GREEN)Dependências de desenvolvimento instaladas!$(RESET)"

setup: ## Configuração inicial do projeto
	@echo "$(BLUE)Configurando projeto...$(RESET)"
	@if [ ! -f backend/.env ]; then \
		cp backend/.env.example backend/.env; \
		echo "$(YELLOW)Arquivo .env criado. Configure as variáveis necessárias.$(RESET)"; \
	else \
		echo "$(YELLOW)Arquivo .env já existe.$(RESET)"; \
	fi
	@mkdir -p backend/data/{roms,covers,screenshots,temp,bios,saves,states}
	@mkdir -p backend/logs
	@mkdir -p backend/backups
	@echo "$(GREEN)Projeto configurado com sucesso!$(RESET)"

# =============================================================================
# DESENVOLVIMENTO
# =============================================================================
dev: ## Inicia servidor de desenvolvimento
	@echo "$(BLUE)Iniciando servidor de desenvolvimento...$(RESET)"
	cd backend && $(PYTHON) -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

dev-worker: ## Inicia worker Celery para desenvolvimento
	@echo "$(BLUE)Iniciando worker Celery...$(RESET)"
	cd backend && celery -A app.core.celery worker --loglevel=info --reload

dev-flower: ## Inicia Flower para monitoramento Celery
	@echo "$(BLUE)Iniciando Flower...$(RESET)"
	cd backend && celery -A app.core.celery flower --port=5555

shell: ## Abre shell interativo Python
	@echo "$(BLUE)Abrindo shell Python...$(RESET)"
	cd backend && $(PYTHON) -c "from app.core.database import get_session; from app.models import *; print('Shell MegaEmu Modern - Modelos importados')"

# =============================================================================
# TESTES E QUALIDADE
# =============================================================================
test: ## Executa todos os testes
	@echo "$(BLUE)Executando testes...$(RESET)"
	cd backend && $(PYTHON) -m pytest tests/ -v --cov=app --cov-report=html --cov-report=term

test-unit: ## Executa apenas testes unitários
	@echo "$(BLUE)Executando testes unitários...$(RESET)"
	cd backend && $(PYTHON) -m pytest tests/unit/ -v

test-integration: ## Executa testes de integração
	@echo "$(BLUE)Executando testes de integração...$(RESET)"
	cd backend && $(PYTHON) -m pytest tests/integration/ -v

test-api: ## Executa testes da API
	@echo "$(BLUE)Executando testes da API...$(RESET)"
	cd backend && $(PYTHON) -m pytest tests/api/ -v

lint: ## Executa linting do código
	@echo "$(BLUE)Executando linting...$(RESET)"
	cd backend && flake8 app/ tests/
	cd backend && mypy app/
	@echo "$(GREEN)Linting concluído!$(RESET)"

format: ## Formata código com black e isort
	@echo "$(BLUE)Formatando código...$(RESET)"
	cd backend && black app/ tests/
	cd backend && isort app/ tests/
	@echo "$(GREEN)Código formatado!$(RESET)"

format-check: ## Verifica formatação sem modificar
	@echo "$(BLUE)Verificando formatação...$(RESET)"
	cd backend && black --check app/ tests/
	cd backend && isort --check-only app/ tests/

# =============================================================================
# BANCO DE DADOS
# =============================================================================
migrate-create: ## Cria nova migração
	@echo "$(BLUE)Criando nova migração...$(RESET)"
	cd backend && $(ALEMBIC) revision --autogenerate -m "$(msg)"

migrate-up: ## Aplica migrações
	@echo "$(BLUE)Aplicando migrações...$(RESET)"
	cd backend && $(ALEMBIC) upgrade head

migrate-down: ## Reverte última migração
	@echo "$(BLUE)Revertendo migração...$(RESET)"
	cd backend && $(ALEMBIC) downgrade -1

migrate-history: ## Mostra histórico de migrações
	@echo "$(BLUE)Histórico de migrações:$(RESET)"
	cd backend && $(ALEMBIC) history

migrate-current: ## Mostra migração atual
	@echo "$(BLUE)Migração atual:$(RESET)"
	cd backend && $(ALEMBIC) current

db-reset: ## Reseta banco de dados (CUIDADO!)
	@echo "$(RED)ATENÇÃO: Isso irá apagar todos os dados!$(RESET)"
	@read -p "Tem certeza? (y/N): " confirm && [ "$$confirm" = "y" ] || exit 1
	cd backend && $(ALEMBIC) downgrade base
	cd backend && $(ALEMBIC) upgrade head
	@echo "$(GREEN)Banco de dados resetado!$(RESET)"

# =============================================================================
# DOCKER
# =============================================================================
docker-build: ## Constrói imagens Docker
	@echo "$(BLUE)Construindo imagens Docker...$(RESET)"
	$(DOCKER_COMPOSE) build
	@echo "$(GREEN)Imagens construídas!$(RESET)"

docker-up: ## Inicia serviços com Docker
	@echo "$(BLUE)Iniciando serviços Docker...$(RESET)"
	$(DOCKER_COMPOSE) up -d
	@echo "$(GREEN)Serviços iniciados!$(RESET)"

docker-down: ## Para serviços Docker
	@echo "$(BLUE)Parando serviços Docker...$(RESET)"
	$(DOCKER_COMPOSE) down
	@echo "$(GREEN)Serviços parados!$(RESET)"

docker-logs: ## Mostra logs dos serviços
	@echo "$(BLUE)Logs dos serviços:$(RESET)"
	$(DOCKER_COMPOSE) logs -f

docker-shell: ## Acessa shell do container backend
	@echo "$(BLUE)Acessando shell do backend...$(RESET)"
	$(DOCKER_COMPOSE) exec backend /bin/bash

docker-clean: ## Remove containers, volumes e imagens
	@echo "$(RED)Removendo containers, volumes e imagens...$(RESET)"
	$(DOCKER_COMPOSE) down -v --rmi all
	docker system prune -f
	@echo "$(GREEN)Limpeza concluída!$(RESET)"

docker-dev: ## Inicia ambiente de desenvolvimento com Docker
	@echo "$(BLUE)Iniciando ambiente de desenvolvimento...$(RESET)"
	BUILD_TARGET=development $(DOCKER_COMPOSE) up -d
	@echo "$(GREEN)Ambiente de desenvolvimento iniciado!$(RESET)"

docker-prod: ## Inicia ambiente de produção com Docker
	@echo "$(BLUE)Iniciando ambiente de produção...$(RESET)"
	ENVIRONMENT=production BUILD_TARGET=application $(DOCKER_COMPOSE) up -d
	@echo "$(GREEN)Ambiente de produção iniciado!$(RESET)"

# =============================================================================
# MONITORAMENTO
# =============================================================================
monitoring-up: ## Inicia serviços de monitoramento
	@echo "$(BLUE)Iniciando monitoramento...$(RESET)"
	$(DOCKER_COMPOSE) --profile monitoring up -d
	@echo "$(GREEN)Monitoramento iniciado!$(RESET)"

monitoring-down: ## Para serviços de monitoramento
	@echo "$(BLUE)Parando monitoramento...$(RESET)"
	$(DOCKER_COMPOSE) --profile monitoring down
	@echo "$(GREEN)Monitoramento parado!$(RESET)"

# =============================================================================
# BACKUP E RESTORE
# =============================================================================
backup: ## Cria backup do banco de dados
	@echo "$(BLUE)Criando backup...$(RESET)"
	@mkdir -p backups
	@timestamp=$$(date +%Y%m%d_%H%M%S); \
	docker-compose exec -T postgres pg_dump -U megaemu megaemu_modern > backups/backup_$$timestamp.sql
	@echo "$(GREEN)Backup criado em backups/backup_$$timestamp.sql$(RESET)"

restore: ## Restaura backup do banco de dados
	@echo "$(BLUE)Restaurando backup...$(RESET)"
	@if [ -z "$(file)" ]; then \
		echo "$(RED)Erro: Especifique o arquivo com file=caminho/arquivo.sql$(RESET)"; \
		exit 1; \
	fi
	@echo "$(RED)ATENÇÃO: Isso irá sobrescrever o banco atual!$(RESET)"
	@read -p "Continuar? (y/N): " confirm && [ "$$confirm" = "y" ] || exit 1
	docker-compose exec -T postgres psql -U megaemu -d megaemu_modern < $(file)
	@echo "$(GREEN)Backup restaurado!$(RESET)"

# =============================================================================
# PRODUÇÃO
# =============================================================================
prod: ## Inicia ambiente de produção
	@echo "$(BLUE)Iniciando ambiente de produção...$(RESET)"
	$(MAKE) docker-prod
	$(MAKE) migrate-up
	@echo "$(GREEN)Ambiente de produção iniciado!$(RESET)"

deploy: ## Deploy completo (build + up + migrate)
	@echo "$(BLUE)Iniciando deploy...$(RESET)"
	$(MAKE) docker-build
	$(MAKE) docker-up
	$(MAKE) migrate-up
	@echo "$(GREEN)Deploy concluído!$(RESET)"

health-check: ## Verifica saúde dos serviços
	@echo "$(BLUE)Verificando saúde dos serviços...$(RESET)"
	@curl -f http://localhost:8000/health || echo "$(RED)Backend não está respondendo$(RESET)"
	@curl -f http://localhost:8000/health/detailed || echo "$(RED)Health check detalhado falhou$(RESET)"

# =============================================================================
# LIMPEZA
# =============================================================================
clean: ## Remove arquivos temporários e cache
	@echo "$(BLUE)Limpando arquivos temporários...$(RESET)"
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name ".pytest_cache" -delete
	find . -type d -name ".mypy_cache" -delete
	find . -type f -name ".coverage" -delete
	find . -type d -name "htmlcov" -delete
	@echo "$(GREEN)Limpeza concluída!$(RESET)"

clean-all: ## Limpeza completa (inclui Docker)
	@echo "$(BLUE)Limpeza completa...$(RESET)"
	$(MAKE) clean
	$(MAKE) docker-clean
	@echo "$(GREEN)Limpeza completa concluída!$(RESET)"

# =============================================================================
# UTILITÁRIOS
# =============================================================================
status: ## Mostra status dos serviços
	@echo "$(BLUE)Status dos serviços:$(RESET)"
	$(DOCKER_COMPOSE) ps

ports: ## Mostra portas em uso
	@echo "$(BLUE)Portas em uso:$(RESET)"
	@echo "Backend API: http://localhost:8000"
	@echo "Flower (Celery): http://localhost:5555"
	@echo "Prometheus: http://localhost:9090"
	@echo "Grafana: http://localhost:3001"
	@echo "PostgreSQL: localhost:5432"
	@echo "Redis: localhost:6379"

info: ## Mostra informações do projeto
	@echo "$(CYAN)MegaEmu Modern$(RESET)"
	@echo "Sistema moderno de gerenciamento de ROMs e emulação"
	@echo ""
	@echo "$(YELLOW)Estrutura do projeto:$(RESET)"
	@echo "  backend/     - API FastAPI"
	@echo "  meta/        - Metadados de jogos"
	@echo "  monitoring/ - Configurações de monitoramento"
	@echo ""
	@echo "$(YELLOW)Tecnologias:$(RESET)"
	@echo "  - FastAPI + SQLAlchemy + Alembic"
	@echo "  - PostgreSQL + Redis"
	@echo "  - Celery + Flower"
	@echo "  - Docker + Docker Compose"
	@echo "  - Prometheus + Grafana"