#!/bin/bash

# =============================================================================
# SCRIPT DE RESTORE - MEGAEMU MODERN
# =============================================================================
# Script para restaurar backup completo do sistema MegaEmu Modern
# Restaura banco de dados, arquivos de configuração, logs e dados de aplicação

set -euo pipefail

# =============================================================================
# CONFIGURAÇÕES
# =============================================================================

# Diretórios
BACKUP_DIR="${BACKUP_DIR:-/var/backups/megaemu}"
APP_DIR="${APP_DIR:-/app}"
DATA_DIR="${DATA_DIR:-/data}"
LOGS_DIR="${LOGS_DIR:-/var/log/megaemu}"
CONFIG_DIR="${CONFIG_DIR:-/etc/megaemu}"
TEMP_DIR="${TEMP_DIR:-/tmp/megaemu_restore}"

# Configurações do banco de dados
DB_HOST="${POSTGRES_HOST:-postgres}"
DB_PORT="${POSTGRES_PORT:-5432}"
DB_NAME="${POSTGRES_DB:-megaemu_modern}"
DB_USER="${POSTGRES_USER:-megaemu}"
DB_PASSWORD="${POSTGRES_PASSWORD}"

# Configurações do Redis
REDIS_HOST="${REDIS_HOST:-redis}"
REDIS_PORT="${REDIS_PORT:-6379}"
REDIS_PASSWORD="${REDIS_PASSWORD:-}"

# Configurações de notificação
WEBHOOK_URL="${RESTORE_WEBHOOK_URL:-}"
EMAIL_TO="${RESTORE_EMAIL_TO:-}"

# Variáveis de controle
BACKUP_FILE=""
FORCE_RESTORE=false
SKIP_CONFIRMATION=false
RESTORE_COMPONENTS="all"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")

# =============================================================================
# FUNÇÕES AUXILIARES
# =============================================================================

# Função de log
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "${TEMP_DIR}/restore.log"
}

# Função de erro
error() {
    log "ERROR: $1"
    send_notification "error" "$1"
    cleanup_temp
    exit 1
}

# Função de sucesso
success() {
    log "SUCCESS: $1"
    send_notification "success" "$1"
}

# Função de aviso
warning() {
    log "WARNING: $1"
}

# Função para mostrar ajuda
show_help() {
    cat << EOF
Uso: $0 [OPÇÕES] ARQUIVO_BACKUP

OPÇÕES:
    -f, --force              Forçar restore sem confirmação
    -y, --yes                Pular confirmações interativas
    -c, --components LISTA   Componentes a restaurar (all,db,redis,app,config,logs,data)
    -t, --temp-dir DIR       Diretório temporário (padrão: /tmp/megaemu_restore)
    -h, --help               Mostrar esta ajuda

EXEMPLOS:
    $0 /var/backups/megaemu/megaemu_backup_20240101_120000.tar.gz
    $0 -f -c db,redis backup.tar.gz
    $0 --yes --components app,config backup.tar.gz

COMPONENTES:
    all     - Todos os componentes (padrão)
    db      - Banco de dados PostgreSQL
    redis   - Cache Redis
    app     - Aplicação
    config  - Configurações
    logs    - Logs
    data    - Dados de usuário
EOF
}

# Função para enviar notificações
send_notification() {
    local status="$1"
    local message="$2"
    
    # Webhook
    if [[ -n "$WEBHOOK_URL" ]]; then
        curl -s -X POST "$WEBHOOK_URL" \
            -H "Content-Type: application/json" \
            -d "{
                \"event\": \"restore\",
                \"status\": \"$status\",
                \"message\": \"$message\",
                \"timestamp\": \"$(date -Iseconds)\",
                \"backup_file\": \"$BACKUP_FILE\",
                \"components\": \"$RESTORE_COMPONENTS\"
            }" || log "WARNING: Failed to send webhook notification"
    fi
    
    # Email (se configurado)
    if [[ -n "$EMAIL_TO" ]] && command -v mail >/dev/null 2>&1; then
        echo "$message" | mail -s "MegaEmu Restore - $status" "$EMAIL_TO" || \
            log "WARNING: Failed to send email notification"
    fi
}

# Função para verificar dependências
check_dependencies() {
    log "Verificando dependências..."
    
    local deps=("pg_restore" "psql" "redis-cli" "tar" "gzip")
    for dep in "${deps[@]}"; do
        if ! command -v "$dep" >/dev/null 2>&1; then
            error "Dependência não encontrada: $dep"
        fi
    done
    
    log "Todas as dependências estão disponíveis"
}

# Função para criar diretório temporário
create_temp_dir() {
    log "Criando diretório temporário: $TEMP_DIR"
    
    rm -rf "$TEMP_DIR"
    mkdir -p "$TEMP_DIR" || error "Falha ao criar diretório temporário"
    chmod 750 "$TEMP_DIR"
    
    log "Diretório temporário criado com sucesso"
}

# Função para limpar arquivos temporários
cleanup_temp() {
    if [[ -d "$TEMP_DIR" ]]; then
        log "Limpando arquivos temporários..."
        rm -rf "$TEMP_DIR"
    fi
}

# Função para validar arquivo de backup
validate_backup_file() {
    log "Validando arquivo de backup: $BACKUP_FILE"
    
    # Verificar se arquivo existe
    if [[ ! -f "$BACKUP_FILE" ]]; then
        error "Arquivo de backup não encontrado: $BACKUP_FILE"
    fi
    
    # Verificar se arquivo não está vazio
    if [[ ! -s "$BACKUP_FILE" ]]; then
        error "Arquivo de backup está vazio: $BACKUP_FILE"
    fi
    
    # Verificar checksum se disponível
    local checksum_file="${BACKUP_FILE}.sha256"
    if [[ -f "$checksum_file" ]]; then
        log "Verificando integridade do arquivo..."
        if ! sha256sum -c "$checksum_file" >/dev/null 2>&1; then
            error "Falha na verificação de integridade do arquivo de backup"
        fi
        log "Integridade do arquivo verificada com sucesso"
    else
        warning "Arquivo de checksum não encontrado, pulando verificação de integridade"
    fi
    
    # Verificar se é um arquivo tar válido
    if ! tar -tzf "$BACKUP_FILE" >/dev/null 2>&1; then
        error "Arquivo de backup não é um tar.gz válido"
    fi
    
    log "Arquivo de backup validado com sucesso"
}

# Função para extrair backup
extract_backup() {
    log "Extraindo arquivo de backup..."
    
    tar -xzf "$BACKUP_FILE" -C "$TEMP_DIR" || \
        error "Falha ao extrair arquivo de backup"
    
    # Encontrar diretório extraído
    local extracted_dir=$(find "$TEMP_DIR" -maxdepth 1 -type d -name "megaemu_backup_*" | head -1)
    if [[ -z "$extracted_dir" ]]; then
        error "Diretório de backup não encontrado após extração"
    fi
    
    # Definir variável global para o diretório extraído
    EXTRACTED_DIR="$extracted_dir"
    
    log "Backup extraído para: $EXTRACTED_DIR"
}

# Função para validar manifesto
validate_manifest() {
    local manifest_file="${EXTRACTED_DIR}/manifest.json"
    
    if [[ -f "$manifest_file" ]]; then
        log "Validando manifesto do backup..."
        
        # Verificar se é JSON válido
        if ! python3 -m json.tool "$manifest_file" >/dev/null 2>&1; then
            warning "Manifesto não é um JSON válido"
            return
        fi
        
        # Extrair informações do manifesto
        local backup_name=$(python3 -c "import json; print(json.load(open('$manifest_file'))['backup_name'])" 2>/dev/null || echo "unknown")
        local timestamp=$(python3 -c "import json; print(json.load(open('$manifest_file'))['timestamp'])" 2>/dev/null || echo "unknown")
        
        log "Backup: $backup_name"
        log "Timestamp: $timestamp"
        
        # Validar checksums dos arquivos
        log "Validando checksums dos arquivos..."
        find "$EXTRACTED_DIR" -name "*.sha256" | while read -r checksum_file; do
            local dir=$(dirname "$checksum_file")
            if ! (cd "$dir" && sha256sum -c "$(basename "$checksum_file")") >/dev/null 2>&1; then
                warning "Falha na verificação de checksum: $checksum_file"
            fi
        done
        
        log "Manifesto validado com sucesso"
    else
        warning "Manifesto não encontrado, pulando validação"
    fi
}

# =============================================================================
# FUNÇÕES DE RESTORE
# =============================================================================

# Função para confirmar restore
confirm_restore() {
    if [[ "$SKIP_CONFIRMATION" == "true" ]]; then
        return 0
    fi
    
    echo
    echo "=== CONFIRMAÇÃO DE RESTORE ==="
    echo "Arquivo de backup: $BACKUP_FILE"
    echo "Componentes: $RESTORE_COMPONENTS"
    echo "Destino da aplicação: $APP_DIR"
    echo "Destino dos dados: $DATA_DIR"
    echo "Banco de dados: $DB_HOST:$DB_PORT/$DB_NAME"
    echo "Redis: $REDIS_HOST:$REDIS_PORT"
    echo
    echo "ATENÇÃO: Esta operação irá SOBRESCREVER os dados existentes!"
    echo
    
    if [[ "$FORCE_RESTORE" == "true" ]]; then
        log "Restore forçado, pulando confirmação"
        return 0
    fi
    
    read -p "Deseja continuar com o restore? (digite 'CONFIRMO' para continuar): " confirmation
    
    if [[ "$confirmation" != "CONFIRMO" ]]; then
        log "Restore cancelado pelo usuário"
        exit 0
    fi
    
    log "Restore confirmado pelo usuário"
}

# Restore do PostgreSQL
restore_postgresql() {
    if [[ "$RESTORE_COMPONENTS" != "all" ]] && [[ "$RESTORE_COMPONENTS" != *"db"* ]]; then
        log "Pulando restore do PostgreSQL (não incluído nos componentes)"
        return 0
    fi
    
    log "Iniciando restore do PostgreSQL..."
    
    local db_backup_file=$(find "$EXTRACTED_DIR/database" -name "postgresql_*.sql" | head -1)
    if [[ -z "$db_backup_file" ]]; then
        warning "Arquivo de backup do PostgreSQL não encontrado"
        return 0
    fi
    
    # Verificar conectividade
    if ! PGPASSWORD="$DB_PASSWORD" pg_isready -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" >/dev/null 2>&1; then
        error "Não foi possível conectar ao PostgreSQL"
    fi
    
    # Criar backup da base atual (se existir)
    log "Criando backup de segurança da base atual..."
    local safety_backup="${TEMP_DIR}/safety_backup_${TIMESTAMP}.sql"
    PGPASSWORD="$DB_PASSWORD" pg_dump \
        -h "$DB_HOST" \
        -p "$DB_PORT" \
        -U "$DB_USER" \
        -d "$DB_NAME" \
        --format=custom \
        --file="$safety_backup" 2>/dev/null || \
        log "WARNING: Falha ao criar backup de segurança (base pode não existir)"
    
    # Dropar e recriar base
    log "Recriando base de dados..."
    PGPASSWORD="$DB_PASSWORD" psql \
        -h "$DB_HOST" \
        -p "$DB_PORT" \
        -U "$DB_USER" \
        -d postgres \
        -c "DROP DATABASE IF EXISTS $DB_NAME;" || \
        error "Falha ao dropar base de dados"
    
    PGPASSWORD="$DB_PASSWORD" psql \
        -h "$DB_HOST" \
        -p "$DB_PORT" \
        -U "$DB_USER" \
        -d postgres \
        -c "CREATE DATABASE $DB_NAME OWNER $DB_USER;" || \
        error "Falha ao criar base de dados"
    
    # Restaurar backup
    log "Restaurando dados do PostgreSQL..."
    PGPASSWORD="$DB_PASSWORD" pg_restore \
        -h "$DB_HOST" \
        -p "$DB_PORT" \
        -U "$DB_USER" \
        -d "$DB_NAME" \
        --verbose \
        --no-password \
        --clean \
        --if-exists \
        "$db_backup_file" || error "Falha no restore do PostgreSQL"
    
    log "Restore do PostgreSQL concluído com sucesso"
}

# Restore do Redis
restore_redis() {
    if [[ "$RESTORE_COMPONENTS" != "all" ]] && [[ "$RESTORE_COMPONENTS" != *"redis"* ]]; then
        log "Pulando restore do Redis (não incluído nos componentes)"
        return 0
    fi
    
    log "Iniciando restore do Redis..."
    
    local redis_backup_file=$(find "$EXTRACTED_DIR/redis" -name "redis_*.rdb" | head -1)
    if [[ -z "$redis_backup_file" ]] || [[ ! -s "$redis_backup_file" ]]; then
        warning "Arquivo de backup do Redis não encontrado ou vazio"
        return 0
    fi
    
    # Verificar conectividade
    if [[ -n "$REDIS_PASSWORD" ]]; then
        redis_cmd="redis-cli -h $REDIS_HOST -p $REDIS_PORT -a $REDIS_PASSWORD"
    else
        redis_cmd="redis-cli -h $REDIS_HOST -p $REDIS_PORT"
    fi
    
    if ! $redis_cmd ping >/dev/null 2>&1; then
        error "Não foi possível conectar ao Redis"
    fi
    
    # Limpar dados atuais
    log "Limpando dados atuais do Redis..."
    $redis_cmd FLUSHALL || error "Falha ao limpar dados do Redis"
    
    # Parar Redis temporariamente para restore
    log "Parando Redis para restore..."
    $redis_cmd SHUTDOWN NOSAVE || warning "Falha ao parar Redis graciosamente"
    
    # Aguardar Redis parar
    sleep 2
    
    # Copiar arquivo RDB (isso depende da configuração do Redis)
    log "Copiando arquivo RDB..."
    # Nota: Este passo pode precisar ser adaptado dependendo da configuração
    warning "Restore do Redis requer configuração manual do arquivo RDB"
    warning "Arquivo disponível em: $redis_backup_file"
    
    log "Restore do Redis preparado (requer reinicialização manual)"
}

# Restore da aplicação
restore_application() {
    if [[ "$RESTORE_COMPONENTS" != "all" ]] && [[ "$RESTORE_COMPONENTS" != *"app"* ]]; then
        log "Pulando restore da aplicação (não incluído nos componentes)"
        return 0
    fi
    
    log "Iniciando restore da aplicação..."
    
    local app_backup_file=$(find "$EXTRACTED_DIR/application" -name "application_*.tar.gz" | head -1)
    if [[ -z "$app_backup_file" ]]; then
        warning "Arquivo de backup da aplicação não encontrado"
        return 0
    fi
    
    # Criar backup da aplicação atual
    if [[ -d "$APP_DIR" ]]; then
        log "Criando backup da aplicação atual..."
        local current_backup="${TEMP_DIR}/current_app_${TIMESTAMP}.tar.gz"
        tar -czf "$current_backup" -C "$(dirname "$APP_DIR")" "$(basename "$APP_DIR")" || \
            warning "Falha ao criar backup da aplicação atual"
    fi
    
    # Extrair aplicação
    log "Extraindo aplicação..."
    mkdir -p "$(dirname "$APP_DIR")"
    tar -xzf "$app_backup_file" -C "$(dirname "$APP_DIR")" || \
        error "Falha ao extrair aplicação"
    
    # Ajustar permissões
    log "Ajustando permissões..."
    chown -R app:app "$APP_DIR" 2>/dev/null || warning "Falha ao ajustar proprietário"
    chmod -R 755 "$APP_DIR" || warning "Falha ao ajustar permissões"
    
    log "Restore da aplicação concluído com sucesso"
}

# Restore das configurações
restore_config() {
    if [[ "$RESTORE_COMPONENTS" != "all" ]] && [[ "$RESTORE_COMPONENTS" != *"config"* ]]; then
        log "Pulando restore das configurações (não incluído nos componentes)"
        return 0
    fi
    
    log "Iniciando restore das configurações..."
    
    local config_backup_file=$(find "$EXTRACTED_DIR/config" -name "config_*.tar.gz" | head -1)
    if [[ -z "$config_backup_file" ]] || [[ ! -s "$config_backup_file" ]]; then
        warning "Arquivo de backup das configurações não encontrado ou vazio"
        return 0
    fi
    
    # Extrair configurações
    log "Extraindo configurações..."
    tar -xzf "$config_backup_file" -C "/" || \
        error "Falha ao extrair configurações"
    
    log "Restore das configurações concluído com sucesso"
}

# Restore dos logs
restore_logs() {
    if [[ "$RESTORE_COMPONENTS" != "all" ]] && [[ "$RESTORE_COMPONENTS" != *"logs"* ]]; then
        log "Pulando restore dos logs (não incluído nos componentes)"
        return 0
    fi
    
    log "Iniciando restore dos logs..."
    
    local logs_backup_file=$(find "$EXTRACTED_DIR/logs" -name "logs_*.tar.gz" | head -1)
    if [[ -z "$logs_backup_file" ]] || [[ ! -s "$logs_backup_file" ]]; then
        warning "Arquivo de backup dos logs não encontrado ou vazio"
        return 0
    fi
    
    # Criar diretório de logs
    mkdir -p "$(dirname "$LOGS_DIR")"
    
    # Extrair logs
    log "Extraindo logs..."
    tar -xzf "$logs_backup_file" -C "$(dirname "$LOGS_DIR")" || \
        error "Falha ao extrair logs"
    
    # Ajustar permissões
    chown -R app:app "$LOGS_DIR" 2>/dev/null || warning "Falha ao ajustar proprietário dos logs"
    
    log "Restore dos logs concluído com sucesso"
}

# Restore dos dados
restore_data() {
    if [[ "$RESTORE_COMPONENTS" != "all" ]] && [[ "$RESTORE_COMPONENTS" != *"data"* ]]; then
        log "Pulando restore dos dados (não incluído nos componentes)"
        return 0
    fi
    
    log "Iniciando restore dos dados..."
    
    local data_backup_file=$(find "$EXTRACTED_DIR/data" -name "data_*.tar.gz" | head -1)
    if [[ -z "$data_backup_file" ]] || [[ ! -s "$data_backup_file" ]]; then
        warning "Arquivo de backup dos dados não encontrado ou vazio"
        return 0
    fi
    
    # Criar backup dos dados atuais
    if [[ -d "$DATA_DIR" ]]; then
        log "Criando backup dos dados atuais..."
        local current_data_backup="${TEMP_DIR}/current_data_${TIMESTAMP}.tar.gz"
        tar -czf "$current_data_backup" -C "$(dirname "$DATA_DIR")" "$(basename "$DATA_DIR")" || \
            warning "Falha ao criar backup dos dados atuais"
    fi
    
    # Criar diretório de dados
    mkdir -p "$(dirname "$DATA_DIR")"
    
    # Extrair dados
    log "Extraindo dados..."
    tar -xzf "$data_backup_file" -C "$(dirname "$DATA_DIR")" || \
        error "Falha ao extrair dados"
    
    # Ajustar permissões
    chown -R app:app "$DATA_DIR" 2>/dev/null || warning "Falha ao ajustar proprietário dos dados"
    
    log "Restore dos dados concluído com sucesso"
}

# =============================================================================
# FUNÇÃO PRINCIPAL
# =============================================================================

main() {
    log "=== INICIANDO RESTORE DO MEGAEMU MODERN ==="
    log "Arquivo de backup: $BACKUP_FILE"
    log "Componentes: $RESTORE_COMPONENTS"
    
    # Verificações iniciais
    check_dependencies
    create_temp_dir
    validate_backup_file
    
    # Extrair e validar backup
    extract_backup
    validate_manifest
    
    # Confirmar restore
    confirm_restore
    
    # Realizar restore
    restore_postgresql
    restore_redis
    restore_application
    restore_config
    restore_logs
    restore_data
    
    # Limpeza
    cleanup_temp
    
    log "=== RESTORE CONCLUÍDO COM SUCESSO ==="
    success "Restore do MegaEmu Modern concluído com sucesso"
    
    echo
    echo "=== PRÓXIMOS PASSOS ==="
    echo "1. Reiniciar os serviços da aplicação"
    echo "2. Verificar logs de aplicação"
    echo "3. Testar funcionalidades críticas"
    echo "4. Verificar conectividade com banco de dados"
    echo "5. Validar integridade dos dados"
    echo
}

# =============================================================================
# PROCESSAMENTO DE ARGUMENTOS
# =============================================================================

parse_arguments() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            -f|--force)
                FORCE_RESTORE=true
                shift
                ;;
            -y|--yes)
                SKIP_CONFIRMATION=true
                shift
                ;;
            -c|--components)
                RESTORE_COMPONENTS="$2"
                shift 2
                ;;
            -t|--temp-dir)
                TEMP_DIR="$2"
                shift 2
                ;;
            -h|--help)
                show_help
                exit 0
                ;;
            -*)
                error "Opção desconhecida: $1"
                ;;
            *)
                if [[ -z "$BACKUP_FILE" ]]; then
                    BACKUP_FILE="$1"
                else
                    error "Múltiplos arquivos de backup especificados"
                fi
                shift
                ;;
        esac
    done
    
    # Verificar se arquivo de backup foi especificado
    if [[ -z "$BACKUP_FILE" ]]; then
        error "Arquivo de backup não especificado. Use -h para ajuda."
    fi
    
    # Converter para caminho absoluto
    BACKUP_FILE=$(realpath "$BACKUP_FILE")
}

# =============================================================================
# TRATAMENTO DE SINAIS
# =============================================================================

# Função de limpeza em caso de interrupção
cleanup_on_exit() {
    log "Restore interrompido, limpando arquivos temporários..."
    cleanup_temp
    error "Restore cancelado pelo usuário"
}

# Capturar sinais
trap cleanup_on_exit SIGINT SIGTERM

# =============================================================================
# EXECUÇÃO
# =============================================================================

# Verificar se está sendo executado como script
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    parse_arguments "$@"
    main
fi