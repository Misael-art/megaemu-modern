# MegaEmu DataBase ROMs - Modernized

## 🎮 Sistema Completo para Organização de ROMs de Videogames Retro

Uma modernização completa do MegaEmu DataBase ROMs com arquitetura web moderna, performance otimizada e interface responsiva.

## 🏗️ Arquitetura

### Backend (FastAPI)
- **FastAPI** com SQLAlchemy async para APIs REST de alta performance
- **PostgreSQL** como banco de dados principal com full-text search
- **Celery + Redis** para processamento assíncrono de tarefas
- **Alembic** para migrações de banco de dados
- **Playwright** para web scraping moderno
- **JWT** para autenticação e autorização
- **Rate limiting** e validação de entrada

### Frontend (React)
- **React 18** com TypeScript para type safety
- **Vite** como build tool para desenvolvimento rápido
- **Material-UI (MUI)** como design system
- **Redux Toolkit** para gerenciamento de estado
- **TanStack Query** para cache e sincronização de dados
- **PWA** com suporte offline

### Infraestrutura & DevOps
- **Docker** para containerização completa
- **Docker Compose** para orquestração de serviços
- **Redis** para cache, sessões e message broker
- **PostgreSQL** com otimizações e extensões
- **Prometheus + Grafana** para monitoramento
- **Nginx** como reverse proxy (produção)
- **Scripts automatizados** para backup, deploy e manutenção

## 🚀 Funcionalidades

### Core Features
- ✅ Importação de DAT/XML files
- ✅ Verificação automática de ROMs
- ✅ Catalogação de sistemas de videogame
- ✅ Web scraping de metadados (GameFAQs, MobyGames, Wikipedia)
- ✅ Full-text search otimizado
- ✅ Exportação em múltiplos formatos

### Melhorias UX
- 🎨 Interface responsiva (mobile-first)
- 🌙 Tema claro/escuro
- 📊 Dashboard com estatísticas
- 🧙‍♂️ Wizard de configuração inicial
- 🔍 Auto-detecção de pastas de ROMs
- 📱 Progressive Web App

### DevOps & Monitoramento
- 📈 Métricas com Prometheus
- 📊 Dashboards Grafana personalizados
- 🚨 Alertas automáticos
- 🔍 Health checks integrados
- 📦 Deploy automatizado
- 💾 Backup e restore automáticos
- 🧹 Manutenção programada

## 📁 Estrutura do Projeto

```
megaemu-modern/
├── backend/                 # FastAPI backend
│   ├── app/
│   │   ├── api/            # API endpoints
│   │   ├── core/           # Core configuration
│   │   ├── models/         # SQLAlchemy models
│   │   ├── schemas/        # Pydantic schemas
│   │   ├── services/       # Business logic
│   │   └── tasks/          # Celery tasks
│   ├── alembic/            # Database migrations
│   ├── config/             # Configuration files
│   ├── scripts/            # Database initialization
│   ├── tests/              # Backend tests
│   ├── Dockerfile          # Container definition
│   ├── .env.example        # Environment template
│   └── requirements.txt
├── frontend/               # React frontend
│   ├── src/
│   │   ├── components/     # React components
│   │   ├── pages/          # Page components
│   │   ├── store/          # Redux store
│   │   ├── services/       # API services
│   │   └── utils/          # Utilities
│   ├── public/             # Static assets
│   └── package.json
├── monitoring/             # Observability stack
│   ├── grafana/           # Dashboards e configurações
│   ├── prometheus.yml     # Configuração do Prometheus
│   └── rules/             # Regras de alertas
├── scripts/               # Scripts de automação
│   ├── backup.sh          # Backup automatizado
│   ├── restore.sh         # Restore de backups
│   ├── deploy.sh          # Deploy automatizado
│   ├── maintenance.sh     # Manutenção do sistema
│   └── health-check.sh    # Verificações de saúde
├── docker-compose.yml     # Orquestração de serviços
├── Makefile              # Comandos de desenvolvimento
└── docs/                 # Documentation
```

## 🛠️ Desenvolvimento

### Pré-requisitos
- Python 3.11+
- Node.js 18+
- Docker & Docker Compose
- PostgreSQL 15+
- Redis 7+

### Setup Rápido com Docker (Recomendado)

```bash
# Clone e entre no diretório
cd megaemu-modern

# Configure as variáveis de ambiente
cp backend/.env.example backend/.env
# Edite backend/.env conforme necessário

# Inicie todos os serviços
docker-compose up -d

# Aguarde a inicialização e acesse:
# - API: http://localhost:8000
# - Frontend: http://localhost:3000
# - Grafana: http://localhost:3001 (admin/admin)
# - Flower: http://localhost:5555
```

### Setup para Desenvolvimento

```bash
# Configure o backend
cd backend
pip install -r requirements.txt
cp .env.example .env
# Configure DATABASE_URL e outras variáveis
alembic upgrade head
uvicorn app.main:app --reload

# Configure o frontend (novo terminal)
cd frontend
npm install
npm run dev

# Inicie Redis e PostgreSQL separadamente
# ou use: docker-compose up -d postgres redis
```

### Variáveis de Ambiente

Copie `backend/.env.example` para `backend/.env` e configure:

```env
# Configurações Gerais
APP_NAME="MegaEmu Modern"
APP_VERSION="1.0.0"
ENVIRONMENT=development
DEBUG=true
API_V1_STR=/api/v1

# Servidor
HOST=0.0.0.0
PORT=8000
WORKERS=1

# Database (PostgreSQL)
DATABASE_URL=postgresql+asyncpg://megaemu:password@localhost:5432/megaemu_modern
DB_POOL_SIZE=20
DB_MAX_OVERFLOW=30
DB_POOL_TIMEOUT=30

# Database (SQLite - alternativa)
SQLITE_URL=sqlite+aiosqlite:///./megaemu.db

# Redis
REDIS_URL=redis://localhost:6379/0
REDIS_PASSWORD=
REDIS_DB=0
REDIS_MAX_CONNECTIONS=20

# Segurança e Autenticação
SECRET_KEY=your-super-secret-key-change-this-in-production
JWT_SECRET_KEY=your-jwt-secret-key
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7

# Políticas de Senha
PASSWORD_MIN_LENGTH=8
PASSWORD_REQUIRE_UPPERCASE=true
PASSWORD_REQUIRE_LOWERCASE=true
PASSWORD_REQUIRE_NUMBERS=true
PASSWORD_REQUIRE_SPECIAL=true

# CORS
CORS_ORIGINS=["http://localhost:3000","http://localhost:8080"]
CORS_ALLOW_CREDENTIALS=true

# Rate Limiting
RATE_LIMIT_ENABLED=true
RATE_LIMIT_REQUESTS=100
RATE_LIMIT_WINDOW=60

# Arquivos e Upload
UPLOAD_MAX_SIZE=100
UPLOAD_ALLOWED_EXTENSIONS=[".zip",".7z",".rar",".xml",".dat"]
STORAGE_PATH=./storage
TEMP_PATH=./temp

# Processamento e Tarefas
CELERY_BROKER_URL=redis://localhost:6379/1
CELERY_RESULT_BACKEND=redis://localhost:6379/2
CELERY_TASK_TIMEOUT=300
CELERY_MAX_RETRIES=3

# Serviços Externos
IGDB_CLIENT_ID=your_igdb_client_id
IGDB_CLIENT_SECRET=your_igdb_client_secret
MOBYGAMES_API_KEY=your_mobygames_api_key
SCREENSCRAPER_USERNAME=your_screenscraper_username
SCREENSCRAPER_PASSWORD=your_screenscraper_password

# Web Scraping
SCRAPING_DELAY=1
SCRAPING_TIMEOUT=30
SCRAPING_MAX_RETRIES=3
USE_PROXY_ROTATION=false
PROXY_LIST=[]

# Logging
LOG_LEVEL=INFO
LOG_FORMAT=detailed
LOG_FILE_ENABLED=true
LOG_FILE_PATH=./logs/app.log
LOG_FILE_MAX_SIZE=10
LOG_FILE_BACKUP_COUNT=5

# Monitoramento
PROMETHEUS_ENABLED=true
PROMETHEUS_PORT=8001
HEALTH_CHECK_ENABLED=true
HEALTH_CHECK_INTERVAL=30

# Desenvolvimento
RELOAD=true
SHOW_DOCS=true
SHOW_REDOC=true

# Diretórios de Emulação
ROMS_DIRECTORIES=["/path/to/roms1","/path/to/roms2"]
EMULATORS_PATH=/path/to/emulators
SAVES_PATH=/path/to/saves
STATES_PATH=/path/to/states
SCREENSHOTS_PATH=/path/to/screenshots

# Backup e Manutenção
BACKUP_ENABLED=true
BACKUP_SCHEDULE="0 2 * * *"
BACKUP_RETENTION_DAYS=30
BACKUP_PATH=./backups
MAINTENANCE_ENABLED=true
MAINTENANCE_SCHEDULE="0 3 * * 0"
```

## 📊 Comandos Úteis (Makefile)

O projeto inclui um Makefile com comandos para desenvolvimento e produção:

```bash
# Desenvolvimento
make install          # Instalar dependências
make dev             # Iniciar ambiente de desenvolvimento
make test            # Executar todos os testes
make lint            # Verificar código
make format          # Formatar código

# Docker
make docker-build    # Build das imagens
make docker-up       # Subir serviços
make docker-down     # Parar serviços
make docker-logs     # Ver logs
make docker-shell    # Shell no container

# Database
make db-migrate      # Criar migração
make db-upgrade      # Aplicar migrações
make db-downgrade    # Reverter migração
make db-reset        # Reset completo

# Backup e Restore
make backup          # Backup completo
make restore         # Restore de backup

# Monitoramento
make monitoring-up   # Subir Prometheus/Grafana
make monitoring-down # Parar monitoramento

# Produção
make deploy-prod     # Deploy em produção
make health-check    # Verificar saúde do sistema
```

## 📊 Migração de Dados

O sistema inclui scripts para migrar dados existentes:

```bash
# Migrar dados do SQLite existente
python scripts/migrate_from_sqlite.py

# Importar XMLs do HyperList
python scripts/import_hyperlist.py

# Processar dados do No-Intro
python scripts/process_nointro.py
```

## 🧪 Testes

```bash
# Backend tests
cd backend
pytest

# Frontend tests
cd frontend
npm test

# E2E tests
npm run test:e2e
```

## 📈 Performance & Monitoramento

### Performance
- **Async/await** em todo o backend
- **Connection pooling** otimizado
- **Redis caching** para queries frequentes
- **Lazy loading** no frontend
- **Code splitting** automático
- **Service Workers** para cache offline
- **Database indexing** otimizado
- **Query optimization** com SQLAlchemy

### Monitoramento
- **Prometheus** para coleta de métricas
- **Grafana** com dashboards personalizados
- **Alertas automáticos** via webhook/email
- **Health checks** integrados
- **Logs estruturados** com rotação
- **Métricas de negócio** específicas

### Dashboards Disponíveis
- **Overview**: Métricas gerais da aplicação
- **System**: CPU, memória, disco, rede
- **Database**: Performance do PostgreSQL
- **Redis**: Cache e sessões
- **Celery**: Filas e workers

## 🔒 Segurança

- **JWT** para autenticação e autorização
- **Rate limiting** nas APIs
- **Input validation** com Pydantic
- **SQL injection** protection
- **XSS** protection
- **CORS** configurado
- **Políticas de senha** robustas
- **Sanitização de dados** de entrada
- **Headers de segurança** configurados
- **Secrets management** via environment

## 🚀 Deploy e Automação

### Scripts de Automação
- **backup.sh**: Backup completo (DB, Redis, arquivos)
- **restore.sh**: Restore seletivo de backups
- **deploy.sh**: Deploy automatizado com rollback
- **maintenance.sh**: Limpeza e otimização
- **health-check.sh**: Monitoramento de saúde

### Deploy em Produção
```bash
# Deploy automatizado
./scripts/deploy.sh production

# Ou usando Makefile
make deploy-prod

# Verificar saúde após deploy
make health-check
```

### Backup e Restore
```bash
# Backup manual
./scripts/backup.sh

# Restore específico
./scripts/restore.sh /path/to/backup.tar.gz

# Manutenção programada
./scripts/maintenance.sh --dry-run
```

## 📝 Licença

MIT License - veja [LICENSE](LICENSE) para detalhes.

## Melhorias Recentes
- **Testes Adicionais**: Adicionado `test_favorites.py` para cobrir cenários de adicionar/remover favoritos, expandindo a cobertura de testes sem alterar funções existentes.
- **Otimização de Performance**: Índices adicionados na tabela `user_favorite_games` para otimizar consultas de favoritos.
- **Documentação**: Atualizações no README para incluir detalhes sobre o sistema de favoritos e melhores práticas de manutenção.

## 🤝 Contribuição

Contribuições são bem-vindas! Veja [CONTRIBUTING.md](CONTRIBUTING.md) para guidelines.

## 📞 Suporte

Para suporte e dúvidas, abra uma [issue](https://github.com/user/megaemu-modern/issues).