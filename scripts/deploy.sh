#!/bin/bash

# =============================================================================
# SCRIPT DE DEPLOY AUTOMATIZADO - MEGAEMU MODERN
# =============================================================================
# Script para automatizar o deploy do sistema MegaEmu Modern
# Suporta deploy em desenvolvimento, staging e produção

set -euo pipefail

# =============================================================================
# CONFIGURAÇÕES
# =============================================================================

# Configurações padrão
ENVIRONMENT="${DEPLOY_ENV:-development}"
VERSION="${DEPLOY_VERSION:-latest}"
BRANCH="${DEPLOY_BRANCH:-main}"
REPO_URL="${REPO_URL:-}"
DEPLOY_USER="${DEPLOY_USER:-$(whoami)}"
DEPLOY_PATH="${DEPLOY_PATH:-/opt/megaemu-modern}"
BACKUP_PATH="${BACKUP_PATH:-/opt/backups/megaemu}"
LOG_PATH="${LOG_PATH:-/var/log/megaemu}"

# Configurações de serviços
SERVICE_NAME="${SERVICE_NAME:-megaemu-modern}"
DOCKER_COMPOSE_FILE="${DOCKER_COMPOSE_FILE:-docker-compose.yml}"
DOCKER_COMPOSE_OVERRIDE="${DOCKER_COMPOSE_OVERRIDE:-docker-compose.override.yml}"

# Configurações de notificação
WEBHOOK_URL="${DEPLOY_WEBHOOK_URL:-}"
SLACK_WEBHOOK="${SLACK_WEBHOOK_URL:-}"
EMAIL_TO="${DEPLOY_EMAIL_TO:-}"

# Configurações de segurança
RUN_TESTS="${RUN_TESTS:-true}"
RUN_MIGRATIONS="${RUN_MIGRATIONS:-true}"
CREATE_BACKUP="${CREATE_BACKUP:-true}"
HEALTH_CHECK="${HEALTH_CHECK:-true}"
ROLLBACK_ON_FAILURE="${ROLLBACK_ON_FAILURE:-true}"

# Configurações de timeout
HEALTH_CHECK_TIMEOUT="${HEALTH_CHECK_TIMEOUT:-300}"
SERVICE_START_TIMEOUT="${SERVICE_START_TIMEOUT:-120}"
MIGRATION_TIMEOUT="${MIGRATION_TIMEOUT:-600}"

# Variáveis de estado
DEPLOY_START_TIME=$(date +%s)
DEPLOY_ID="deploy_$(date +%Y%m%d_%H%M%S)_$$"
TEMP_DIR="/tmp/megaemu-deploy-$DEPLOY_ID"
LOCK_FILE="/tmp/megaemu-deploy.lock"
ROLLBACK_INFO=""
PREVIOUS_VERSION=""

# Cores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# =============================================================================
# FUNÇÕES AUXILIARES
# =============================================================================

# Função de log
log() {
    local level="$1"
    shift
    local message="$*"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    
    case "$level" in
        "INFO")
            echo -e "${BLUE}[$timestamp] [INFO]${NC} $message"
            ;;
        "SUCCESS")
            echo -e "${GREEN}[$timestamp] [SUCCESS]${NC} $message"
            ;;
        "WARNING")
            echo -e "${YELLOW}[$timestamp] [WARNING]${NC} $message"
            ;;
        "ERROR")
            echo -e "${RED}[$timestamp] [ERROR]${NC} $message"
            ;;
        *)
            echo "[$timestamp] $message"
            ;;
    esac
    
    # Log para arquivo se o diretório existir
    if [[ -d "$LOG_PATH" ]]; then
        echo "[$timestamp] [$level] $message" >> "$LOG_PATH/deploy.log"
    fi
}

# Função de erro com saída
die() {
    log "ERROR" "$1"
    cleanup
    exit 1
}

# Função de limpeza
cleanup() {
    log "INFO" "Executando limpeza..."
    
    # Remover diretório temporário
    if [[ -d "$TEMP_DIR" ]]; then
        rm -rf "$TEMP_DIR"
    fi
    
    # Remover lock file
    if [[ -f "$LOCK_FILE" ]]; then
        rm -f "$LOCK_FILE"
    fi
}

# Função para mostrar ajuda
show_help() {
    cat << EOF
Uso: $0 [OPÇÕES]

OPÇÕES:
    -e, --environment ENV    Ambiente de deploy (development, staging, production)
    -v, --version VERSION    Versão a ser deployada (padrão: latest)
    -b, --branch BRANCH      Branch do Git (padrão: main)
    -p, --path PATH          Caminho de deploy (padrão: /opt/megaemu-modern)
    --no-tests              Pular execução de testes
    --no-migrations         Pular execução de migrações
    --no-backup             Pular criação de backup
    --no-health-check       Pular verificação de saúde
    --no-rollback           Não fazer rollback em caso de falha
    --force                 Forçar deploy mesmo com lock ativo
    -h, --help              Mostrar esta ajuda

AMBIENTES:
    development - Deploy local para desenvolvimento
    staging     - Deploy em ambiente de teste
    production  - Deploy em produção (com todas as verificações)

EXEMPLOS:
    $0                                    # Deploy development
    $0 -e production -v v1.2.3            # Deploy produção versão específica
    $0 -e staging --no-tests              # Deploy staging sem testes
    $0 --force                            # Forçar deploy ignorando lock

VARIÁVEIS DE AMBIENTE:
    DEPLOY_ENV              Ambiente padrão
    DEPLOY_VERSION          Versão padrão
    DEPLOY_BRANCH           Branch padrão
    DEPLOY_PATH             Caminho de instalação
    BACKUP_PATH             Caminho de backups
    REPO_URL                URL do repositório Git
    DEPLOY_WEBHOOK_URL      Webhook para notificações
    SLACK_WEBHOOK_URL       Webhook do Slack
    DEPLOY_EMAIL_TO         Email para notificações
EOF
}

# Função para enviar notificações
send_notification() {
    local status="$1"
    local message="$2"
    local details="${3:-}"
    
    local deploy_time=$(($(date +%s) - DEPLOY_START_TIME))
    
    # Webhook genérico
    if [[ -n "$WEBHOOK_URL" ]]; then
        curl -s -X POST "$WEBHOOK_URL" \
            -H "Content-Type: application/json" \
            -d "{
                \"event\": \"deploy\",
                \"status\": \"$status\",
                \"environment\": \"$ENVIRONMENT\",
                \"version\": \"$VERSION\",
                \"branch\": \"$BRANCH\",
                \"deploy_id\": \"$DEPLOY_ID\",
                \"deploy_time\": $deploy_time,
                \"message\": \"$message\",
                \"details\": \"$details\",
                \"timestamp\": \"$(date -Iseconds)\",
                \"user\": \"$DEPLOY_USER\"
            }" || log "WARNING" "Failed to send webhook notification"
    fi
    
    # Slack
    if [[ -n "$SLACK_WEBHOOK" ]]; then
        local color="good"
        case "$status" in
            "failed"|"error") color="danger" ;;
            "warning") color="warning" ;;
            "started") color="#439FE0" ;;
        esac
        
        curl -s -X POST "$SLACK_WEBHOOK" \
            -H "Content-Type: application/json" \
            -d "{
                \"attachments\": [{
                    \"color\": \"$color\",
                    \"title\": \"MegaEmu Deploy - $ENVIRONMENT\",
                    \"text\": \"$message\",
                    \"fields\": [
                        {\"title\": \"Status\", \"value\": \"$status\", \"short\": true},
                        {\"title\": \"Version\", \"value\": \"$VERSION\", \"short\": true},
                        {\"title\": \"Environment\", \"value\": \"$ENVIRONMENT\", \"short\": true},
                        {\"title\": \"Duration\", \"value\": \"${deploy_time}s\", \"short\": true}
                    ]
                }]
            }" || log "WARNING" "Failed to send Slack notification"
    fi
    
    # Email
    if [[ -n "$EMAIL_TO" ]] && command -v mail >/dev/null 2>&1; then
        local subject="MegaEmu Deploy $status - $ENVIRONMENT"
        local body="Deploy Status: $status\nEnvironment: $ENVIRONMENT\nVersion: $VERSION\nBranch: $BRANCH\nDuration: ${deploy_time}s\n\n$message\n\n$details"
        
        echo -e "$body" | mail -s "$subject" "$EMAIL_TO" || \
            log "WARNING" "Failed to send email notification"
    fi
}

# Função para verificar pré-requisitos
check_prerequisites() {
    log "INFO" "Verificando pré-requisitos..."
    
    # Verificar se está rodando como usuário correto
    if [[ "$ENVIRONMENT" == "production" ]] && [[ "$(whoami)" == "root" ]]; then
        die "Deploy em produção não deve ser executado como root"
    fi
    
    # Verificar comandos necessários
    local required_commands=("docker" "docker-compose" "git")
    
    for cmd in "${required_commands[@]}"; do
        if ! command -v "$cmd" >/dev/null 2>&1; then
            die "Comando necessário não encontrado: $cmd"
        fi
    done
    
    # Verificar se Docker está rodando
    if ! docker info >/dev/null 2>&1; then
        die "Docker não está rodando"
    fi
    
    # Verificar espaço em disco
    local available_space
    available_space=$(df "$DEPLOY_PATH" | tail -1 | awk '{print $4}')
    
    if [[ "$available_space" -lt 1048576 ]]; then  # 1GB em KB
        die "Espaço em disco insuficiente (menos de 1GB disponível)"
    fi
    
    # Verificar lock file
    if [[ -f "$LOCK_FILE" ]] && [[ "${FORCE:-false}" != "true" ]]; then
        local lock_pid
        lock_pid=$(cat "$LOCK_FILE" 2>/dev/null || echo "")
        
        if [[ -n "$lock_pid" ]] && kill -0 "$lock_pid" 2>/dev/null; then
            die "Deploy já está em execução (PID: $lock_pid). Use --force para ignorar."
        else
            log "WARNING" "Lock file órfão encontrado, removendo..."
            rm -f "$LOCK_FILE"
        fi
    fi
    
    # Criar lock file
    echo "$$" > "$LOCK_FILE"
    
    log "SUCCESS" "Pré-requisitos verificados"
}

# Função para preparar ambiente
prepare_environment() {
    log "INFO" "Preparando ambiente de deploy..."
    
    # Criar diretórios necessários
    mkdir -p "$TEMP_DIR"
    mkdir -p "$DEPLOY_PATH"
    mkdir -p "$BACKUP_PATH"
    mkdir -p "$LOG_PATH"
    
    # Definir configurações específicas do ambiente
    case "$ENVIRONMENT" in
        "development")
            DOCKER_COMPOSE_FILE="docker-compose.yml"
            RUN_TESTS="false"
            CREATE_BACKUP="false"
            ;;
        "staging")
            DOCKER_COMPOSE_FILE="docker-compose.staging.yml"
            RUN_TESTS="true"
            CREATE_BACKUP="true"
            ;;
        "production")
            DOCKER_COMPOSE_FILE="docker-compose.prod.yml"
            RUN_TESTS="true"
            CREATE_BACKUP="true"
            HEALTH_CHECK="true"
            ;;
        *)
            die "Ambiente inválido: $ENVIRONMENT"
            ;;
    esac
    
    log "SUCCESS" "Ambiente preparado"
}

# Função para obter código fonte
get_source_code() {
    log "INFO" "Obtendo código fonte..."
    
    cd "$TEMP_DIR"
    
    if [[ -n "$REPO_URL" ]]; then
        # Clone do repositório
        git clone --depth 1 --branch "$BRANCH" "$REPO_URL" source
        cd source
    else
        # Copiar código local
        if [[ -d "$DEPLOY_PATH" ]]; then
            cp -r "$DEPLOY_PATH" source
            cd source
            
            # Atualizar se for repositório Git
            if [[ -d ".git" ]]; then
                git fetch origin
                git checkout "$BRANCH"
                git pull origin "$BRANCH"
            fi
        else
            die "Código fonte não encontrado e REPO_URL não definido"
        fi
    fi
    
    # Verificar se a versão existe (se não for latest)
    if [[ "$VERSION" != "latest" ]]; then
        if git tag | grep -q "^$VERSION$"; then
            git checkout "$VERSION"
        else
            log "WARNING" "Tag $VERSION não encontrada, usando branch $BRANCH"
        fi
    fi
    
    # Obter informações da versão atual
    local current_commit
    current_commit=$(git rev-parse HEAD 2>/dev/null || echo "unknown")
    
    log "INFO" "Commit atual: $current_commit"
    
    log "SUCCESS" "Código fonte obtido"
}

# Função para executar testes
run_tests() {
    if [[ "$RUN_TESTS" != "true" ]]; then
        log "INFO" "Pulando execução de testes"
        return 0
    fi
    
    log "INFO" "Executando testes..."
    
    cd "$TEMP_DIR/source"
    
    # Executar testes usando Docker Compose
    if [[ -f "docker-compose.test.yml" ]]; then
        docker-compose -f docker-compose.test.yml up --build --abort-on-container-exit
        local test_result=$?
        docker-compose -f docker-compose.test.yml down -v
        
        if [[ $test_result -ne 0 ]]; then
            die "Testes falharam"
        fi
    else
        log "WARNING" "Arquivo de testes não encontrado, pulando..."
    fi
    
    log "SUCCESS" "Testes executados com sucesso"
}

# Função para criar backup
create_backup() {
    if [[ "$CREATE_BACKUP" != "true" ]]; then
        log "INFO" "Pulando criação de backup"
        return 0
    fi
    
    log "INFO" "Criando backup..."
    
    local backup_name="backup_${ENVIRONMENT}_$(date +%Y%m%d_%H%M%S)"
    local backup_dir="$BACKUP_PATH/$backup_name"
    
    mkdir -p "$backup_dir"
    
    # Backup do código atual
    if [[ -d "$DEPLOY_PATH" ]]; then
        tar -czf "$backup_dir/code.tar.gz" -C "$DEPLOY_PATH" .
    fi
    
    # Backup do banco de dados
    if [[ -f "$DEPLOY_PATH/.env" ]]; then
        source "$DEPLOY_PATH/.env"
        
        if [[ -n "${POSTGRES_HOST:-}" ]]; then
            local db_backup="$backup_dir/database.sql"
            
            PGPASSWORD="$POSTGRES_PASSWORD" pg_dump \
                -h "$POSTGRES_HOST" \
                -p "$POSTGRES_PORT" \
                -U "$POSTGRES_USER" \
                -d "$POSTGRES_DB" \
                > "$db_backup" || log "WARNING" "Falha no backup do banco"
        fi
    fi
    
    # Salvar informações do rollback
    ROLLBACK_INFO="$backup_dir"
    echo "$backup_name" > "$backup_dir/backup_info.txt"
    
    log "SUCCESS" "Backup criado: $backup_name"
}

# Função para parar serviços
stop_services() {
    log "INFO" "Parando serviços..."
    
    cd "$DEPLOY_PATH"
    
    if [[ -f "$DOCKER_COMPOSE_FILE" ]]; then
        docker-compose -f "$DOCKER_COMPOSE_FILE" down || log "WARNING" "Falha ao parar alguns serviços"
    fi
    
    # Aguardar serviços pararem completamente
    sleep 5
    
    log "SUCCESS" "Serviços parados"
}

# Função para atualizar código
update_code() {
    log "INFO" "Atualizando código..."
    
    # Backup do código atual se existir
    if [[ -d "$DEPLOY_PATH" ]] && [[ "$(ls -A $DEPLOY_PATH 2>/dev/null)" ]]; then
        PREVIOUS_VERSION="$DEPLOY_PATH.backup.$(date +%Y%m%d_%H%M%S)"
        mv "$DEPLOY_PATH" "$PREVIOUS_VERSION"
    fi
    
    # Copiar novo código
    mkdir -p "$DEPLOY_PATH"
    cp -r "$TEMP_DIR/source/"* "$DEPLOY_PATH/"
    
    # Definir permissões
    chown -R "$DEPLOY_USER:$DEPLOY_USER" "$DEPLOY_PATH" 2>/dev/null || true
    
    log "SUCCESS" "Código atualizado"
}

# Função para executar migrações
run_migrations() {
    if [[ "$RUN_MIGRATIONS" != "true" ]]; then
        log "INFO" "Pulando execução de migrações"
        return 0
    fi
    
    log "INFO" "Executando migrações..."
    
    cd "$DEPLOY_PATH"
    
    # Aguardar banco estar disponível
    local retries=0
    local max_retries=30
    
    while [[ $retries -lt $max_retries ]]; do
        if docker-compose -f "$DOCKER_COMPOSE_FILE" exec -T postgres pg_isready >/dev/null 2>&1; then
            break
        fi
        
        log "INFO" "Aguardando banco de dados... ($((retries + 1))/$max_retries)"
        sleep 10
        ((retries++))
    done
    
    if [[ $retries -eq $max_retries ]]; then
        die "Timeout aguardando banco de dados"
    fi
    
    # Executar migrações
    timeout "$MIGRATION_TIMEOUT" docker-compose -f "$DOCKER_COMPOSE_FILE" exec -T backend alembic upgrade head || \
        die "Falha na execução das migrações"
    
    log "SUCCESS" "Migrações executadas"
}

# Função para iniciar serviços
start_services() {
    log "INFO" "Iniciando serviços..."
    
    cd "$DEPLOY_PATH"
    
    # Construir e iniciar serviços
    docker-compose -f "$DOCKER_COMPOSE_FILE" up -d --build
    
    # Aguardar serviços iniciarem
    local retries=0
    local max_retries=$((SERVICE_START_TIMEOUT / 10))
    
    while [[ $retries -lt $max_retries ]]; do
        if docker-compose -f "$DOCKER_COMPOSE_FILE" ps | grep -q "Up"; then
            break
        fi
        
        log "INFO" "Aguardando serviços iniciarem... ($((retries + 1))/$max_retries)"
        sleep 10
        ((retries++))
    done
    
    if [[ $retries -eq $max_retries ]]; then
        die "Timeout aguardando serviços iniciarem"
    fi
    
    log "SUCCESS" "Serviços iniciados"
}

# Função para verificar saúde
check_health() {
    if [[ "$HEALTH_CHECK" != "true" ]]; then
        log "INFO" "Pulando verificação de saúde"
        return 0
    fi
    
    log "INFO" "Verificando saúde do sistema..."
    
    local health_script="$DEPLOY_PATH/scripts/health-check.sh"
    
    if [[ -f "$health_script" ]]; then
        # Aguardar sistema estar pronto
        local retries=0
        local max_retries=$((HEALTH_CHECK_TIMEOUT / 30))
        
        while [[ $retries -lt $max_retries ]]; do
            if bash "$health_script" -q; then
                log "SUCCESS" "Sistema saudável"
                return 0
            fi
            
            log "INFO" "Sistema ainda não está saudável... ($((retries + 1))/$max_retries)"
            sleep 30
            ((retries++))
        done
        
        die "Sistema não passou na verificação de saúde"
    else
        log "WARNING" "Script de health check não encontrado"
        
        # Verificação básica de conectividade
        local api_url="http://localhost:8000/health"
        
        if curl -f -s "$api_url" >/dev/null; then
            log "SUCCESS" "API respondendo"
        else
            die "API não está respondendo"
        fi
    fi
}

# Função para rollback
rollback() {
    if [[ "$ROLLBACK_ON_FAILURE" != "true" ]]; then
        log "WARNING" "Rollback desabilitado, sistema pode estar em estado inconsistente"
        return 0
    fi
    
    log "WARNING" "Executando rollback..."
    
    # Parar serviços atuais
    cd "$DEPLOY_PATH"
    docker-compose -f "$DOCKER_COMPOSE_FILE" down || true
    
    # Restaurar código anterior
    if [[ -n "$PREVIOUS_VERSION" ]] && [[ -d "$PREVIOUS_VERSION" ]]; then
        rm -rf "$DEPLOY_PATH"
        mv "$PREVIOUS_VERSION" "$DEPLOY_PATH"
        
        # Reiniciar serviços
        cd "$DEPLOY_PATH"
        docker-compose -f "$DOCKER_COMPOSE_FILE" up -d
        
        log "SUCCESS" "Rollback do código executado"
    fi
    
    # Restaurar banco se houver backup
    if [[ -n "$ROLLBACK_INFO" ]] && [[ -f "$ROLLBACK_INFO/database.sql" ]]; then
        source "$DEPLOY_PATH/.env"
        
        PGPASSWORD="$POSTGRES_PASSWORD" psql \
            -h "$POSTGRES_HOST" \
            -p "$POSTGRES_PORT" \
            -U "$POSTGRES_USER" \
            -d "$POSTGRES_DB" \
            < "$ROLLBACK_INFO/database.sql" || \
            log "WARNING" "Falha no rollback do banco"
    fi
    
    log "WARNING" "Rollback concluído"
}

# Função para limpeza pós-deploy
post_deploy_cleanup() {
    log "INFO" "Executando limpeza pós-deploy..."
    
    # Remover imagens Docker antigas
    docker image prune -f >/dev/null 2>&1 || true
    
    # Remover backups antigos (manter últimos 5)
    if [[ -d "$BACKUP_PATH" ]]; then
        find "$BACKUP_PATH" -maxdepth 1 -type d -name "backup_*" | \
            sort -r | tail -n +6 | xargs rm -rf 2>/dev/null || true
    fi
    
    # Remover versões antigas do código (manter últimas 3)
    find "$(dirname $DEPLOY_PATH)" -maxdepth 1 -type d -name "$(basename $DEPLOY_PATH).backup.*" | \
        sort -r | tail -n +4 | xargs rm -rf 2>/dev/null || true
    
    log "SUCCESS" "Limpeza concluída"
}

# =============================================================================
# FUNÇÃO PRINCIPAL
# =============================================================================

main() {
    log "INFO" "Iniciando deploy do MegaEmu Modern"
    log "INFO" "Ambiente: $ENVIRONMENT"
    log "INFO" "Versão: $VERSION"
    log "INFO" "Branch: $BRANCH"
    log "INFO" "Deploy ID: $DEPLOY_ID"
    
    send_notification "started" "Deploy iniciado" "Environment: $ENVIRONMENT\nVersion: $VERSION\nBranch: $BRANCH"
    
    # Trap para cleanup em caso de erro
    trap 'rollback; cleanup; send_notification "failed" "Deploy falhou" "Check logs for details"; exit 1' ERR
    
    # Executar etapas do deploy
    check_prerequisites
    prepare_environment
    get_source_code
    run_tests
    create_backup
    stop_services
    update_code
    start_services
    run_migrations
    check_health
    post_deploy_cleanup
    
    # Remover trap de erro
    trap - ERR
    
    local deploy_time=$(($(date +%s) - DEPLOY_START_TIME))
    
    log "SUCCESS" "Deploy concluído com sucesso em ${deploy_time}s"
    send_notification "success" "Deploy concluído com sucesso" "Duration: ${deploy_time}s\nEnvironment: $ENVIRONMENT\nVersion: $VERSION"
    
    cleanup
}

# =============================================================================
# PROCESSAMENTO DE ARGUMENTOS
# =============================================================================

parse_arguments() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            -e|--environment)
                ENVIRONMENT="$2"
                shift 2
                ;;
            -v|--version)
                VERSION="$2"
                shift 2
                ;;
            -b|--branch)
                BRANCH="$2"
                shift 2
                ;;
            -p|--path)
                DEPLOY_PATH="$2"
                shift 2
                ;;
            --no-tests)
                RUN_TESTS="false"
                shift
                ;;
            --no-migrations)
                RUN_MIGRATIONS="false"
                shift
                ;;
            --no-backup)
                CREATE_BACKUP="false"
                shift
                ;;
            --no-health-check)
                HEALTH_CHECK="false"
                shift
                ;;
            --no-rollback)
                ROLLBACK_ON_FAILURE="false"
                shift
                ;;
            --force)
                FORCE="true"
                shift
                ;;
            -h|--help)
                show_help
                exit 0
                ;;
            -*)
                echo "Opção desconhecida: $1" >&2
                exit 1
                ;;
            *)
                echo "Argumento inesperado: $1" >&2
                exit 1
                ;;
        esac
    done
    
    # Validar ambiente
    case "$ENVIRONMENT" in
        "development"|"staging"|"production")
            ;;
        *)
            echo "Ambiente inválido: $ENVIRONMENT" >&2
            exit 1
            ;;
    esac
}

# =============================================================================
# EXECUÇÃO
# =============================================================================

# Verificar se está sendo executado como script
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    parse_arguments "$@"
    main
fi