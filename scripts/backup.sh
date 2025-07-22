#!/bin/bash

# =============================================================================
# SCRIPT DE BACKUP - MEGAEMU MODERN
# =============================================================================
# Script para realizar backup completo do sistema MegaEmu Modern
# Inclui banco de dados, arquivos de configuração, logs e dados de aplicação

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
CLOUD_BACKUP_ENABLED="${CLOUD_BACKUP_ENABLED:-false}"
AWS_S3_BUCKET="${AWS_S3_BUCKET:-}"
AWS_S3_REGION="${AWS_S3_REGION:-us-east-1}"
AWS_ACCESS_KEY_ID="${AWS_ACCESS_KEY_ID:-}"
AWS_SECRET_ACCESS_KEY="${AWS_SECRET_ACCESS_KEY:-}"

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

# Configurações de retenção
RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-30}"
COMPRESSION_LEVEL="${BACKUP_COMPRESSION_LEVEL:-6}"

# Configurações de notificação
WEBHOOK_URL="${BACKUP_WEBHOOK_URL:-}"
EMAIL_TO="${BACKUP_EMAIL_TO:-}"

# Timestamp
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_NAME="megaemu_backup_${TIMESTAMP}"
BACKUP_PATH="${BACKUP_DIR}/${BACKUP_NAME}"

# =============================================================================
# FUNÇÕES AUXILIARES
# =============================================================================

# Função de log
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "${BACKUP_PATH}/backup.log"
}

# Função de erro
error() {
    log "ERROR: $1"
    send_notification "error" "$1"
    exit 1
}

# Função de sucesso
success() {
    log "SUCCESS: $1"
    send_notification "success" "$1"
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
                \"event\": \"backup\",
                \"status\": \"$status\",
                \"message\": \"$message\",
                \"timestamp\": \"$(date -Iseconds)\",
                \"backup_name\": \"$BACKUP_NAME\",
                \"backup_path\": \"$BACKUP_PATH\"
            }" || log "WARNING: Failed to send webhook notification"
    fi
    
    # Email (se configurado)
    if [[ -n "$EMAIL_TO" ]] && command -v mail >/dev/null 2>&1; then
        echo "$message" | mail -s "MegaEmu Backup - $status" "$EMAIL_TO" || \
            log "WARNING: Failed to send email notification"
    fi
}

# Função para verificar dependências
check_dependencies() {
    log "Verificando dependências..."
    
    local deps=("pg_dump" "redis-cli" "tar" "gzip")
    for dep in "${deps[@]}"; do
        if ! command -v "$dep" >/dev/null 2>&1; then
            error "Dependência não encontrada: $dep"
        fi
    done
    
    log "Todas as dependências estão disponíveis"
}

# Função para criar diretório de backup
create_backup_dir() {
    log "Criando diretório de backup: $BACKUP_PATH"
    
    mkdir -p "$BACKUP_PATH" || error "Falha ao criar diretório de backup"
    chmod 750 "$BACKUP_PATH"
    
    # Criar subdiretórios
    mkdir -p "${BACKUP_PATH}/database"
    mkdir -p "${BACKUP_PATH}/redis"
    mkdir -p "${BACKUP_PATH}/application"
    mkdir -p "${BACKUP_PATH}/config"
    mkdir -p "${BACKUP_PATH}/logs"
    mkdir -p "${BACKUP_PATH}/data"
    
    log "Diretório de backup criado com sucesso"
}

# =============================================================================
# FUNÇÕES DE BACKUP
# =============================================================================

# Adicionar suporte para backup incremental
INCREMENTAL=false
LAST_TIME=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --incremental)
            INCREMENTAL=true
            LAST_TIME="$2"
            shift 2
            ;;
        *)
            shift
            ;;
    esac
done

# Modificar backup_postgresql para suportar incremental
backup_postgresql() {
    log "Iniciando backup do PostgreSQL..."
    
    local db_backup_file="${BACKUP_PATH}/database/postgresql_${TIMESTAMP}.sql"
    
    # Verificar conectividade
    if ! PGPASSWORD="$DB_PASSWORD" pg_isready -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" >/dev/null 2>&1; then
        error "Não foi possível conectar ao PostgreSQL"
    fi
    
    if $INCREMENTAL; then
        log "Modo incremental ativado desde $LAST_TIME"
        # Lógica incremental: dump apenas tabelas modificadas (exemplo simplificado, ajustar conforme schema)
        PGPASSWORD="$DB_PASSWORD" pg_dump \
            -h "$DB_HOST" \
            -p "$DB_PORT" \
            -U "$DB_USER" \
            -d "$DB_NAME" \
            --verbose \
            --no-password \
            --format=custom \
            --compress="$COMPRESSION_LEVEL" \
            --table='public.games' --where="updated_at > '$LAST_TIME'" \
            --file="$db_backup_file" || error "Falha no backup incremental do PostgreSQL"
    else
        # Backup completo existente
        PGPASSWORD="$DB_PASSWORD" pg_dump \
            -h "$DB_HOST" \
            -p "$DB_PORT" \
            -U "$DB_USER" \
            -d "$DB_NAME" \
            --verbose \
            --no-password \
            --format=custom \
            --compress="$COMPRESSION_LEVEL" \
            --file="$db_backup_file" || error "Falha no backup do PostgreSQL"
    fi
    
    # Verificar integridade e checksum (existente)
    if [[ ! -f "$db_backup_file" ]] || [[ ! -s "$db_backup_file" ]]; then
        error "Arquivo de backup do PostgreSQL está vazio ou não existe"
    fi
    sha256sum "$db_backup_file" > "${db_backup_file}.sha256"
    
    log "Backup do PostgreSQL concluído: $(du -h "$db_backup_file" | cut -f1)"
}

# Modificar backup_redis para suportar incremental
backup_redis() {
    log "Iniciando backup do Redis..."
    
    local redis_backup_file="${BACKUP_PATH}/redis/redis_${TIMESTAMP}.rdb"
    
    # Configuração redis_cmd existente
    if [[ -n "$REDIS_PASSWORD" ]]; then
        redis_cmd="redis-cli -h $REDIS_HOST -p $REDIS_PORT -a $REDIS_PASSWORD"
    else
        redis_cmd="redis-cli -h $REDIS_HOST -p $REDIS_PORT"
    fi
    
    if ! $redis_cmd ping >/dev/null 2>&1; then
        error "Não foi possível conectar ao Redis"
    fi
    
    if $INCREMENTAL; then
        log "Modo incremental ativado desde $LAST_TIME"
        # Lógica incremental para Redis: exportar chaves modificadas (exemplo usando AOF ou scan)
        $redis_cmd --rdb "$redis_backup_file" || error "Falha ao copiar RDB do Redis"
        # Para verdadeiro incremental, talvez usar AOF append only
    else
        # Backup completo existente
        $redis_cmd BGSAVE || error "Falha ao executar BGSAVE no Redis"
        while [[ "$($redis_cmd LASTSAVE)" == "$($redis_cmd LASTSAVE)" ]]; do
            sleep 1
        done
        $redis_cmd --rdb "$redis_backup_file" || error "Falha ao copiar RDB do Redis"
    fi
    
    # Checksum existente
    if [[ -f "$redis_backup_file" ]]; then
        sha256sum "$redis_backup_file" > "${redis_backup_file}.sha256"
        log "Backup do Redis concluído: $(du -h "$redis_backup_file" | cut -f1)"
    fi
}

# Backup da aplicação
backup_application() {
    log "Iniciando backup da aplicação..."
    
    local app_backup_file="${BACKUP_PATH}/application/application_${TIMESTAMP}.tar.gz"
    
    if [[ -d "$APP_DIR" ]]; then
        tar -czf "$app_backup_file" \
            -C "$(dirname "$APP_DIR")" \
            "$(basename "$APP_DIR")" \
            --exclude="*.pyc" \
            --exclude="__pycache__" \
            --exclude=".git" \
            --exclude="node_modules" \
            --exclude="*.log" || error "Falha no backup da aplicação"
        
        # Gerar checksum
        sha256sum "$app_backup_file" > "${app_backup_file}.sha256"
        
        log "Backup da aplicação concluído: $(du -h "$app_backup_file" | cut -f1)"
    else
        log "WARNING: Diretório da aplicação não encontrado: $APP_DIR"
    fi
}

# Backup das configurações
backup_config() {
    log "Iniciando backup das configurações..."
    
    local config_backup_file="${BACKUP_PATH}/config/config_${TIMESTAMP}.tar.gz"
    
    # Arquivos de configuração a serem incluídos
    local config_files=()
    
    # Adicionar arquivos se existirem
    [[ -d "$CONFIG_DIR" ]] && config_files+=("$CONFIG_DIR")
    [[ -f "/app/.env" ]] && config_files+=("/app/.env")
    [[ -f "/app/alembic.ini" ]] && config_files+=("/app/alembic.ini")
    [[ -d "/app/config" ]] && config_files+=("/app/config")
    
    if [[ ${#config_files[@]} -gt 0 ]]; then
        tar -czf "$config_backup_file" "${config_files[@]}" || \
            error "Falha no backup das configurações"
        
        # Gerar checksum
        sha256sum "$config_backup_file" > "${config_backup_file}.sha256"
        
        log "Backup das configurações concluído: $(du -h "$config_backup_file" | cut -f1)"
    else
        log "WARNING: Nenhum arquivo de configuração encontrado"
        touch "$config_backup_file"
    fi
}

# Backup dos logs
backup_logs() {
    log "Iniciando backup dos logs..."
    
    local logs_backup_file="${BACKUP_PATH}/logs/logs_${TIMESTAMP}.tar.gz"
    
    if [[ -d "$LOGS_DIR" ]]; then
        tar -czf "$logs_backup_file" \
            -C "$(dirname "$LOGS_DIR")" \
            "$(basename "$LOGS_DIR")" || error "Falha no backup dos logs"
        
        # Gerar checksum
        sha256sum "$logs_backup_file" > "${logs_backup_file}.sha256"
        
        log "Backup dos logs concluído: $(du -h "$logs_backup_file" | cut -f1)"
    else
        log "WARNING: Diretório de logs não encontrado: $LOGS_DIR"
        touch "$logs_backup_file"
    fi
}

# Backup dos dados
backup_data() {
    log "Iniciando backup dos dados..."
    
    local data_backup_file="${BACKUP_PATH}/data/data_${TIMESTAMP}.tar.gz"
    
    if [[ -d "$DATA_DIR" ]]; then
        tar -czf "$data_backup_file" \
            -C "$(dirname "$DATA_DIR")" \
            "$(basename "$DATA_DIR")" \
            --exclude="*.tmp" \
            --exclude="*.temp" || error "Falha no backup dos dados"
        
        # Gerar checksum
        sha256sum "$data_backup_file" > "${data_backup_file}.sha256"
        
        log "Backup dos dados concluído: $(du -h "$data_backup_file" | cut -f1)"
    else
        log "WARNING: Diretório de dados não encontrado: $DATA_DIR"
        touch "$data_backup_file"
    fi
}

# Função para upload para nuvem
upload_to_cloud() {
    local final_backup="$1"
    if [[ "$CLOUD_BACKUP_ENABLED" == "true" ]] && [[ -n "$AWS_S3_BUCKET" ]] && [[ -n "$AWS_S3_REGION" ]]; then
        log "Iniciando upload para AWS S3..."
        if ! command -v aws >/dev/null 2>&1; then
            error "AWS CLI não encontrada. Instale para habilitar backup na nuvem."
        fi
        export AWS_ACCESS_KEY_ID="$AWS_ACCESS_KEY_ID"
        export AWS_SECRET_ACCESS_KEY="$AWS_SECRET_ACCESS_KEY"
        export AWS_DEFAULT_REGION="$AWS_S3_REGION"
        aws s3 cp "$final_backup" "s3://$AWS_S3_BUCKET/backups/$(basename "$final_backup")" || error "Falha no upload para S3"
        log "Upload para S3 concluído com sucesso"
    else
        log "Backup na nuvem desabilitado ou não configurado"
    fi
}

# =============================================================================
# FUNÇÕES DE MANUTENÇÃO
# =============================================================================

# Gerar manifesto do backup
generate_manifest() {
    log "Gerando manifesto do backup..."
    
    local manifest_file="${BACKUP_PATH}/manifest.json"
    
    cat > "$manifest_file" << EOF
{
    "backup_name": "$BACKUP_NAME",
    "timestamp": "$(date -Iseconds)",
    "version": "1.0.0",
    "retention_days": $RETENTION_DAYS,
    "compression_level": $COMPRESSION_LEVEL,
    "components": {
        "postgresql": {
            "included": true,
            "host": "$DB_HOST",
            "database": "$DB_NAME",
            "user": "$DB_USER"
        },
        "redis": {
            "included": true,
            "host": "$REDIS_HOST",
            "port": $REDIS_PORT
        },
        "application": {
            "included": true,
            "path": "$APP_DIR"
        },
        "config": {
            "included": true,
            "path": "$CONFIG_DIR"
        },
        "logs": {
            "included": true,
            "path": "$LOGS_DIR"
        },
        "data": {
            "included": true,
            "path": "$DATA_DIR"
        }
    },
    "files": [
EOF
    
    # Adicionar lista de arquivos
    find "$BACKUP_PATH" -type f -name "*.sql" -o -name "*.rdb" -o -name "*.tar.gz" | \
        while read -r file; do
            local size=$(stat -c%s "$file")
            local checksum=$(sha256sum "$file" | cut -d' ' -f1)
            echo "        {
            \"path\": \"$(basename "$file")\",
            \"size\": $size,
            \"checksum\": \"$checksum\"
        }," >> "$manifest_file"
        done
    
    # Remover última vírgula e fechar JSON
    sed -i '$ s/,$//' "$manifest_file"
    echo "    ]
}" >> "$manifest_file"
    
    log "Manifesto gerado: $manifest_file"
}

# Comprimir backup final
compress_backup() {
    log "Comprimindo backup final..."
    
    local final_backup="${BACKUP_DIR}/${BACKUP_NAME}.tar.gz"
    
    tar -czf "$final_backup" \
        -C "$BACKUP_DIR" \
        "$BACKUP_NAME" || error "Falha ao comprimir backup final"
    
    # Gerar checksum do arquivo final
    sha256sum "$final_backup" > "${final_backup}.sha256"
    
    # Remover diretório temporário
    rm -rf "$BACKUP_PATH"
    
    log "Backup final criado: $final_backup ($(du -h "$final_backup" | cut -f1))"
}

# Limpar backups antigos
cleanup_old_backups() {
    log "Limpando backups antigos (retenção: $RETENTION_DAYS dias)..."
    
    find "$BACKUP_DIR" -name "megaemu_backup_*.tar.gz" -type f -mtime +"$RETENTION_DAYS" | \
        while read -r old_backup; do
            log "Removendo backup antigo: $old_backup"
            rm -f "$old_backup" "${old_backup}.sha256"
        done
    
    log "Limpeza de backups antigos concluída"
}

# =============================================================================
# FUNÇÃO PRINCIPAL
# =============================================================================

main() {
    log "=== INICIANDO BACKUP DO MEGAEMU MODERN ==="
    log "Backup: $BACKUP_NAME"
    log "Destino: $BACKUP_PATH"
    
    # Verificações iniciais
    check_dependencies
    create_backup_dir
    
    # Realizar backups
    backup_postgresql
    backup_redis
    backup_application
    backup_config
    backup_logs
    backup_data
    
    # Finalizar
    generate_manifest
    compress_backup
    upload_to_cloud "${BACKUP_DIR}/${BACKUP_NAME}.tar.gz"
    cleanup_old_backups
    
    log "=== BACKUP CONCLUÍDO COM SUCESSO ==="
    success "Backup do MegaEmu Modern concluído: ${BACKUP_NAME}.tar.gz"
}

# =============================================================================
# TRATAMENTO DE SINAIS
# =============================================================================

# Função de limpeza em caso de interrupção
cleanup_on_exit() {
    log "Backup interrompido, limpando arquivos temporários..."
    [[ -d "$BACKUP_PATH" ]] && rm -rf "$BACKUP_PATH"
    error "Backup cancelado pelo usuário"
}

# Capturar sinais
trap cleanup_on_exit SIGINT SIGTERM

# =============================================================================
# EXECUÇÃO
# =============================================================================

# Verificar se está sendo executado como script
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi