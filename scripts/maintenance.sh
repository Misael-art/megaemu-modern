#!/bin/bash

# =============================================================================
# SCRIPT DE MANUTENÇÃO - MEGAEMU MODERN
# =============================================================================
# Script para realizar tarefas de manutenção do sistema MegaEmu Modern
# Inclui limpeza de logs, otimização de banco, limpeza de cache, etc.

set -euo pipefail

# =============================================================================
# CONFIGURAÇÕES
# =============================================================================

# Diretórios
APP_DIR="${APP_DIR:-/app}"
DATA_DIR="${DATA_DIR:-/data}"
LOGS_DIR="${LOGS_DIR:-/var/log/megaemu}"
CACHE_DIR="${CACHE_DIR:-/tmp/megaemu}"
UPLOADS_DIR="${UPLOADS_DIR:-/data/uploads}"
TEMP_DIR="${TEMP_DIR:-/tmp}"

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

# Configurações de limpeza
LOG_RETENTION_DAYS="${LOG_RETENTION_DAYS:-30}"
TEMP_RETENTION_HOURS="${TEMP_RETENTION_HOURS:-24}"
CACHE_RETENTION_DAYS="${CACHE_RETENTION_DAYS:-7}"
ORPHAN_RETENTION_DAYS="${ORPHAN_RETENTION_DAYS:-7}"

# Configurações de otimização
VACUUM_THRESHOLD="${VACUUM_THRESHOLD:-20}"
ANALYZE_THRESHOLD="${ANALYZE_THRESHOLD:-10}"
REINDEX_THRESHOLD="${REINDEX_THRESHOLD:-50}"

# Configurações de notificação
WEBHOOK_URL="${MAINTENANCE_WEBHOOK_URL:-}"
EMAIL_TO="${MAINTENANCE_EMAIL_TO:-}"

# Variáveis de controle
DRY_RUN=false
VERBOSE=false
TASKS="all"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
MAINTENANCE_LOG="${LOGS_DIR}/maintenance_${TIMESTAMP}.log"

# =============================================================================
# FUNÇÕES AUXILIARES
# =============================================================================

# Função de log
log() {
    local message="[$(date '+%Y-%m-%d %H:%M:%S')] $1"
    echo "$message"
    
    # Salvar em arquivo se diretório existir
    if [[ -d "$(dirname "$MAINTENANCE_LOG")" ]]; then
        echo "$message" >> "$MAINTENANCE_LOG"
    fi
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

# Função de aviso
warning() {
    log "WARNING: $1"
}

# Função de debug (apenas se verbose)
debug() {
    if [[ "$VERBOSE" == "true" ]]; then
        log "DEBUG: $1"
    fi
}

# Função para mostrar ajuda
show_help() {
    cat << EOF
Uso: $0 [OPÇÕES]

OPÇÕES:
    -d, --dry-run            Simular execução sem fazer alterações
    -v, --verbose            Saída detalhada
    -t, --tasks LISTA        Tarefas a executar (all,logs,db,redis,cache,files,orphans)
    -h, --help               Mostrar esta ajuda

TAREFAS:
    all      - Todas as tarefas (padrão)
    logs     - Limpeza de logs antigos
    db       - Otimização do banco de dados
    redis    - Limpeza do cache Redis
    cache    - Limpeza de arquivos de cache
    files    - Limpeza de arquivos temporários
    orphans  - Limpeza de arquivos órfãos
    stats    - Coleta de estatísticas do sistema

EXEMPLOS:
    $0                           # Executar todas as tarefas
    $0 -d -v                     # Simular com saída detalhada
    $0 -t logs,cache             # Apenas limpeza de logs e cache
    $0 --dry-run --tasks db      # Simular otimização do banco

CONFIGURAÇÕES (variáveis de ambiente):
    LOG_RETENTION_DAYS=30        # Dias para manter logs
    TEMP_RETENTION_HOURS=24      # Horas para manter arquivos temporários
    CACHE_RETENTION_DAYS=7       # Dias para manter cache
    VACUUM_THRESHOLD=20          # Limite para VACUUM (%)
    ANALYZE_THRESHOLD=10         # Limite para ANALYZE (%)
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
                \"event\": \"maintenance\",
                \"status\": \"$status\",
                \"message\": \"$message\",
                \"timestamp\": \"$(date -Iseconds)\",
                \"tasks\": \"$TASKS\",
                \"dry_run\": $DRY_RUN
            }" || debug "Failed to send webhook notification"
    fi
    
    # Email (se configurado)
    if [[ -n "$EMAIL_TO" ]] && command -v mail >/dev/null 2>&1; then
        echo "$message" | mail -s "MegaEmu Maintenance - $status" "$EMAIL_TO" || \
            debug "Failed to send email notification"
    fi
}

# Função para verificar dependências
check_dependencies() {
    log "Verificando dependências..."
    
    local deps=("psql" "redis-cli" "find" "du" "df")
    for dep in "${deps[@]}"; do
        if ! command -v "$dep" >/dev/null 2>&1; then
            warning "Dependência não encontrada: $dep (algumas funcionalidades podem não funcionar)"
        fi
    done
    
    debug "Verificação de dependências concluída"
}

# Função para verificar conectividade
check_connectivity() {
    log "Verificando conectividade dos serviços..."
    
    # PostgreSQL
    if command -v psql >/dev/null 2>&1; then
        if PGPASSWORD="$DB_PASSWORD" pg_isready -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" >/dev/null 2>&1; then
            debug "PostgreSQL: Conectado"
        else
            warning "PostgreSQL: Não foi possível conectar"
        fi
    fi
    
    # Redis
    if command -v redis-cli >/dev/null 2>&1; then
        local redis_cmd
        if [[ -n "$REDIS_PASSWORD" ]]; then
            redis_cmd="redis-cli -h $REDIS_HOST -p $REDIS_PORT -a $REDIS_PASSWORD"
        else
            redis_cmd="redis-cli -h $REDIS_HOST -p $REDIS_PORT"
        fi
        
        if $redis_cmd ping >/dev/null 2>&1; then
            debug "Redis: Conectado"
        else
            warning "Redis: Não foi possível conectar"
        fi
    fi
}

# Função para obter tamanho de diretório
get_dir_size() {
    local dir="$1"
    if [[ -d "$dir" ]]; then
        du -sh "$dir" 2>/dev/null | cut -f1 || echo "0"
    else
        echo "0"
    fi
}

# Função para contar arquivos
count_files() {
    local dir="$1"
    if [[ -d "$dir" ]]; then
        find "$dir" -type f 2>/dev/null | wc -l || echo "0"
    else
        echo "0"
    fi
}

# =============================================================================
# TAREFAS DE MANUTENÇÃO
# =============================================================================

# Limpeza de logs
cleanup_logs() {
    if [[ "$TASKS" != "all" ]] && [[ "$TASKS" != *"logs"* ]]; then
        return 0
    fi
    
    log "=== LIMPEZA DE LOGS ==="
    
    if [[ ! -d "$LOGS_DIR" ]]; then
        warning "Diretório de logs não encontrado: $LOGS_DIR"
        return 0
    fi
    
    local initial_size=$(get_dir_size "$LOGS_DIR")
    local initial_count=$(count_files "$LOGS_DIR")
    
    log "Tamanho inicial: $initial_size ($initial_count arquivos)"
    log "Removendo logs com mais de $LOG_RETENTION_DAYS dias..."
    
    # Encontrar arquivos antigos
    local old_files
    old_files=$(find "$LOGS_DIR" -type f -name "*.log" -mtime +"$LOG_RETENTION_DAYS" 2>/dev/null || true)
    
    if [[ -n "$old_files" ]]; then
        local count=0
        while IFS= read -r file; do
            if [[ -n "$file" ]]; then
                debug "Removendo: $file"
                if [[ "$DRY_RUN" == "false" ]]; then
                    rm -f "$file" || warning "Falha ao remover: $file"
                fi
                ((count++))
            fi
        done <<< "$old_files"
        
        log "Removidos $count arquivos de log antigos"
    else
        log "Nenhum arquivo de log antigo encontrado"
    fi
    
    # Comprimir logs grandes
    log "Comprimindo logs grandes..."
    find "$LOGS_DIR" -type f -name "*.log" -size +10M ! -name "*.gz" 2>/dev/null | \
        while IFS= read -r file; do
            if [[ -n "$file" ]]; then
                debug "Comprimindo: $file"
                if [[ "$DRY_RUN" == "false" ]]; then
                    gzip "$file" || warning "Falha ao comprimir: $file"
                fi
            fi
        done
    
    # Limpar logs vazios
    log "Removendo logs vazios..."
    find "$LOGS_DIR" -type f -name "*.log" -empty 2>/dev/null | \
        while IFS= read -r file; do
            if [[ -n "$file" ]]; then
                debug "Removendo log vazio: $file"
                if [[ "$DRY_RUN" == "false" ]]; then
                    rm -f "$file" || warning "Falha ao remover: $file"
                fi
            fi
        done
    
    local final_size=$(get_dir_size "$LOGS_DIR")
    local final_count=$(count_files "$LOGS_DIR")
    
    log "Tamanho final: $final_size ($final_count arquivos)"
    log "Limpeza de logs concluída"
}

# Otimização do banco de dados
optimize_database() {
    if [[ "$TASKS" != "all" ]] && [[ "$TASKS" != *"db"* ]]; then
        return 0
    fi
    
    log "=== OTIMIZAÇÃO DO BANCO DE DADOS ==="
    
    if ! command -v psql >/dev/null 2>&1; then
        warning "psql não encontrado, pulando otimização do banco"
        return 0
    fi
    
    if ! PGPASSWORD="$DB_PASSWORD" pg_isready -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" >/dev/null 2>&1; then
        warning "Não foi possível conectar ao PostgreSQL"
        return 0
    fi
    
    # Obter estatísticas das tabelas
    log "Coletando estatísticas das tabelas..."
    
    local stats_query="
        SELECT 
            schemaname,
            tablename,
            n_tup_ins + n_tup_upd + n_tup_del as total_changes,
            n_dead_tup,
            n_live_tup,
            CASE 
                WHEN n_live_tup > 0 
                THEN round(100.0 * n_dead_tup / (n_live_tup + n_dead_tup), 2)
                ELSE 0 
            END as dead_tuple_percent
        FROM pg_stat_user_tables 
        WHERE schemaname = 'public'
        ORDER BY dead_tuple_percent DESC;
    "
    
    if [[ "$VERBOSE" == "true" ]]; then
        PGPASSWORD="$DB_PASSWORD" psql \
            -h "$DB_HOST" \
            -p "$DB_PORT" \
            -U "$DB_USER" \
            -d "$DB_NAME" \
            -c "$stats_query" || warning "Falha ao obter estatísticas"
    fi
    
    # VACUUM em tabelas com muitas tuplas mortas
    log "Executando VACUUM em tabelas necessárias..."
    
    local vacuum_query="
        SELECT tablename 
        FROM pg_stat_user_tables 
        WHERE schemaname = 'public' 
        AND n_live_tup > 0 
        AND (100.0 * n_dead_tup / (n_live_tup + n_dead_tup)) > $VACUUM_THRESHOLD;
    "
    
    local tables_to_vacuum
    tables_to_vacuum=$(PGPASSWORD="$DB_PASSWORD" psql \
        -h "$DB_HOST" \
        -p "$DB_PORT" \
        -U "$DB_USER" \
        -d "$DB_NAME" \
        -t -c "$vacuum_query" 2>/dev/null | tr -d ' ' | grep -v '^$' || true)
    
    if [[ -n "$tables_to_vacuum" ]]; then
        while IFS= read -r table; do
            if [[ -n "$table" ]]; then
                log "VACUUM na tabela: $table"
                if [[ "$DRY_RUN" == "false" ]]; then
                    PGPASSWORD="$DB_PASSWORD" psql \
                        -h "$DB_HOST" \
                        -p "$DB_PORT" \
                        -U "$DB_USER" \
                        -d "$DB_NAME" \
                        -c "VACUUM ANALYZE $table;" || warning "Falha no VACUUM da tabela $table"
                fi
            fi
        done <<< "$tables_to_vacuum"
    else
        log "Nenhuma tabela necessita VACUUM"
    fi
    
    # ANALYZE em tabelas com muitas mudanças
    log "Executando ANALYZE em tabelas necessárias..."
    
    local analyze_query="
        SELECT tablename 
        FROM pg_stat_user_tables 
        WHERE schemaname = 'public' 
        AND (n_tup_ins + n_tup_upd + n_tup_del) > $ANALYZE_THRESHOLD;
    "
    
    local tables_to_analyze
    tables_to_analyze=$(PGPASSWORD="$DB_PASSWORD" psql \
        -h "$DB_HOST" \
        -p "$DB_PORT" \
        -U "$DB_USER" \
        -d "$DB_NAME" \
        -t -c "$analyze_query" 2>/dev/null | tr -d ' ' | grep -v '^$' || true)
    
    if [[ -n "$tables_to_analyze" ]]; then
        while IFS= read -r table; do
            if [[ -n "$table" ]]; then
                log "ANALYZE na tabela: $table"
                if [[ "$DRY_RUN" == "false" ]]; then
                    PGPASSWORD="$DB_PASSWORD" psql \
                        -h "$DB_HOST" \
                        -p "$DB_PORT" \
                        -U "$DB_USER" \
                        -d "$DB_NAME" \
                        -c "ANALYZE $table;" || warning "Falha no ANALYZE da tabela $table"
                fi
            fi
        done <<< "$tables_to_analyze"
    else
        log "Nenhuma tabela necessita ANALYZE"
    fi
    
    # Obter tamanho do banco
    local db_size
    db_size=$(PGPASSWORD="$DB_PASSWORD" psql \
        -h "$DB_HOST" \
        -p "$DB_PORT" \
        -U "$DB_USER" \
        -d "$DB_NAME" \
        -t -c "SELECT pg_size_pretty(pg_database_size('$DB_NAME'));" 2>/dev/null | tr -d ' ' || echo "unknown")
    
    log "Tamanho do banco de dados: $db_size"
    log "Otimização do banco de dados concluída"
}

# Limpeza do Redis
cleanup_redis() {
    if [[ "$TASKS" != "all" ]] && [[ "$TASKS" != *"redis"* ]]; then
        return 0
    fi
    
    log "=== LIMPEZA DO REDIS ==="
    
    if ! command -v redis-cli >/dev/null 2>&1; then
        warning "redis-cli não encontrado, pulando limpeza do Redis"
        return 0
    fi
    
    local redis_cmd
    if [[ -n "$REDIS_PASSWORD" ]]; then
        redis_cmd="redis-cli -h $REDIS_HOST -p $REDIS_PORT -a $REDIS_PASSWORD"
    else
        redis_cmd="redis-cli -h $REDIS_HOST -p $REDIS_PORT"
    fi
    
    if ! $redis_cmd ping >/dev/null 2>&1; then
        warning "Não foi possível conectar ao Redis"
        return 0
    fi
    
    # Obter informações do Redis
    local redis_info
    redis_info=$($redis_cmd info memory 2>/dev/null || echo "")
    
    if [[ -n "$redis_info" ]]; then
        local used_memory=$(echo "$redis_info" | grep "used_memory_human:" | cut -d: -f2 | tr -d '\r')
        local keys_count=$($redis_cmd dbsize 2>/dev/null || echo "0")
        
        log "Memória utilizada: $used_memory"
        log "Número de chaves: $keys_count"
    fi
    
    # Limpar chaves expiradas
    log "Limpando chaves expiradas..."
    if [[ "$DRY_RUN" == "false" ]]; then
        # Forçar limpeza de chaves expiradas
        for db in {0..15}; do
            $redis_cmd -n $db eval "return redis.call('del', unpack(redis.call('keys', '*')))" 0 >/dev/null 2>&1 || true
        done
    fi
    
    # Limpar chaves de cache antigas (padrão: cache:*)
    log "Limpando cache antigo..."
    local cache_keys
    cache_keys=$($redis_cmd keys "cache:*" 2>/dev/null | wc -l || echo "0")
    
    if [[ "$cache_keys" -gt 0 ]]; then
        log "Encontradas $cache_keys chaves de cache"
        if [[ "$DRY_RUN" == "false" ]]; then
            $redis_cmd eval "local keys = redis.call('keys', 'cache:*'); for i=1,#keys do redis.call('del', keys[i]) end; return #keys" 0 || \
                warning "Falha ao limpar chaves de cache"
        fi
    fi
    
    # Limpar sessões antigas (padrão: session:*)
    log "Limpando sessões antigas..."
    local session_keys
    session_keys=$($redis_cmd keys "session:*" 2>/dev/null | wc -l || echo "0")
    
    if [[ "$session_keys" -gt 0 ]]; then
        log "Encontradas $session_keys chaves de sessão"
        if [[ "$DRY_RUN" == "false" ]]; then
            # Limpar apenas sessões antigas (mais de 7 dias)
            $redis_cmd eval "
                local keys = redis.call('keys', 'session:*')
                local deleted = 0
                for i=1,#keys do
                    local ttl = redis.call('ttl', keys[i])
                    if ttl == -1 or ttl > 604800 then  -- 7 dias
                        redis.call('del', keys[i])
                        deleted = deleted + 1
                    end
                end
                return deleted
            " 0 || warning "Falha ao limpar sessões antigas"
        fi
    fi
    
    log "Limpeza do Redis concluída"
}

# Limpeza de arquivos de cache
cleanup_cache() {
    if [[ "$TASKS" != "all" ]] && [[ "$TASKS" != *"cache"* ]]; then
        return 0
    fi
    
    log "=== LIMPEZA DE CACHE ==="
    
    local cache_dirs=("$CACHE_DIR" "$TEMP_DIR/megaemu" "/tmp/celery" "/var/cache/megaemu")
    
    for dir in "${cache_dirs[@]}"; do
        if [[ -d "$dir" ]]; then
            local initial_size=$(get_dir_size "$dir")
            local initial_count=$(count_files "$dir")
            
            log "Limpando cache em: $dir"
            log "Tamanho inicial: $initial_size ($initial_count arquivos)"
            
            # Remover arquivos antigos
            find "$dir" -type f -mtime +"$CACHE_RETENTION_DAYS" 2>/dev/null | \
                while IFS= read -r file; do
                    if [[ -n "$file" ]]; then
                        debug "Removendo cache: $file"
                        if [[ "$DRY_RUN" == "false" ]]; then
                            rm -f "$file" || warning "Falha ao remover: $file"
                        fi
                    fi
                done
            
            # Remover diretórios vazios
            if [[ "$DRY_RUN" == "false" ]]; then
                find "$dir" -type d -empty -delete 2>/dev/null || true
            fi
            
            local final_size=$(get_dir_size "$dir")
            local final_count=$(count_files "$dir")
            
            log "Tamanho final: $final_size ($final_count arquivos)"
        else
            debug "Diretório de cache não encontrado: $dir"
        fi
    done
    
    log "Limpeza de cache concluída"
}

# Limpeza de arquivos temporários
cleanup_temp_files() {
    if [[ "$TASKS" != "all" ]] && [[ "$TASKS" != *"files"* ]]; then
        return 0
    fi
    
    log "=== LIMPEZA DE ARQUIVOS TEMPORÁRIOS ==="
    
    local temp_dirs=("$TEMP_DIR" "/tmp" "/var/tmp")
    local temp_patterns=("*.tmp" "*.temp" "*.log.old" "core.*" "*.pid")
    
    for dir in "${temp_dirs[@]}"; do
        if [[ -d "$dir" ]]; then
            log "Limpando arquivos temporários em: $dir"
            
            # Remover arquivos temporários antigos
            find "$dir" -type f -mmin +$((TEMP_RETENTION_HOURS * 60)) \( \
                -name "*.tmp" -o \
                -name "*.temp" -o \
                -name "*.log.old" -o \
                -name "core.*" -o \
                -name "*.pid" \) 2>/dev/null | \
                while IFS= read -r file; do
                    if [[ -n "$file" ]]; then
                        debug "Removendo arquivo temporário: $file"
                        if [[ "$DRY_RUN" == "false" ]]; then
                            rm -f "$file" || warning "Falha ao remover: $file"
                        fi
                    fi
                done
        fi
    done
    
    # Limpar arquivos de upload órfãos
    if [[ -d "$UPLOADS_DIR" ]]; then
        log "Limpando uploads órfãos..."
        
        # Encontrar arquivos de upload não referenciados no banco
        # (Esta lógica pode precisar ser adaptada conforme o modelo de dados)
        find "$UPLOADS_DIR" -type f -mtime +"$ORPHAN_RETENTION_DAYS" 2>/dev/null | \
            while IFS= read -r file; do
                if [[ -n "$file" ]]; then
                    # Verificar se arquivo está referenciado no banco
                    local filename=$(basename "$file")
                    local referenced=false
                    
                    if command -v psql >/dev/null 2>&1 && \
                       PGPASSWORD="$DB_PASSWORD" pg_isready -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" >/dev/null 2>&1; then
                        
                        local count
                        count=$(PGPASSWORD="$DB_PASSWORD" psql \
                            -h "$DB_HOST" \
                            -p "$DB_PORT" \
                            -U "$DB_USER" \
                            -d "$DB_NAME" \
                            -t -c "SELECT COUNT(*) FROM roms WHERE file_path LIKE '%$filename%' OR cover_image LIKE '%$filename%';" 2>/dev/null | tr -d ' ' || echo "1")
                        
                        if [[ "$count" -gt 0 ]]; then
                            referenced=true
                        fi
                    fi
                    
                    if [[ "$referenced" == "false" ]]; then
                        debug "Removendo upload órfão: $file"
                        if [[ "$DRY_RUN" == "false" ]]; then
                            rm -f "$file" || warning "Falha ao remover: $file"
                        fi
                    fi
                fi
            done
    fi
    
    log "Limpeza de arquivos temporários concluída"
}

# Limpeza de arquivos órfãos
cleanup_orphans() {
    if [[ "$TASKS" != "all" ]] && [[ "$TASKS" != *"orphans"* ]]; then
        return 0
    fi
    
    log "=== LIMPEZA DE ARQUIVOS ÓRFÃOS ==="
    
    if [[ ! -d "$DATA_DIR" ]]; then
        warning "Diretório de dados não encontrado: $DATA_DIR"
        return 0
    fi
    
    # Encontrar arquivos órfãos (não referenciados no banco)
    log "Procurando arquivos órfãos..."
    
    local orphan_count=0
    local orphan_size=0
    
    find "$DATA_DIR" -type f \( -name "*.zip" -o -name "*.rom" -o -name "*.iso" \) 2>/dev/null | \
        while IFS= read -r file; do
            if [[ -n "$file" ]]; then
                local filename=$(basename "$file")
                local referenced=false
                
                # Verificar se arquivo está referenciado no banco
                if command -v psql >/dev/null 2>&1 && \
                   PGPASSWORD="$DB_PASSWORD" pg_isready -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" >/dev/null 2>&1; then
                    
                    local count
                    count=$(PGPASSWORD="$DB_PASSWORD" psql \
                        -h "$DB_HOST" \
                        -p "$DB_PORT" \
                        -U "$DB_USER" \
                        -d "$DB_NAME" \
                        -t -c "SELECT COUNT(*) FROM roms WHERE file_path LIKE '%$filename%';" 2>/dev/null | tr -d ' ' || echo "1")
                    
                    if [[ "$count" -gt 0 ]]; then
                        referenced=true
                    fi
                fi
                
                # Verificar se arquivo é muito antigo
                if [[ "$referenced" == "false" ]] && \
                   find "$file" -mtime +"$ORPHAN_RETENTION_DAYS" 2>/dev/null | grep -q .; then
                    
                    local file_size=$(stat -c%s "$file" 2>/dev/null || echo "0")
                    orphan_size=$((orphan_size + file_size))
                    orphan_count=$((orphan_count + 1))
                    
                    debug "Arquivo órfão encontrado: $file ($(du -h "$file" | cut -f1))"
                    
                    if [[ "$DRY_RUN" == "false" ]]; then
                        rm -f "$file" || warning "Falha ao remover: $file"
                    fi
                fi
            fi
        done
    
    if [[ "$orphan_count" -gt 0 ]]; then
        local orphan_size_human=$(echo "$orphan_size" | awk '{printf "%.2f MB", $1/1024/1024}')
        log "Encontrados $orphan_count arquivos órfãos ($orphan_size_human)"
    else
        log "Nenhum arquivo órfão encontrado"
    fi
    
    log "Limpeza de arquivos órfãos concluída"
}

# Coleta de estatísticas
collect_stats() {
    if [[ "$TASKS" != "all" ]] && [[ "$TASKS" != *"stats"* ]]; then
        return 0
    fi
    
    log "=== COLETA DE ESTATÍSTICAS ==="
    
    # Estatísticas do sistema
    log "--- Estatísticas do Sistema ---"
    
    # Espaço em disco
    if command -v df >/dev/null 2>&1; then
        log "Espaço em disco:"
        df -h | grep -E '(Filesystem|/dev/)' | head -10
    fi
    
    # Uso de memória
    if [[ -f "/proc/meminfo" ]]; then
        local mem_total=$(grep MemTotal /proc/meminfo | awk '{print $2}')
        local mem_available=$(grep MemAvailable /proc/meminfo | awk '{print $2}')
        local mem_used=$((mem_total - mem_available))
        local mem_percent=$((mem_used * 100 / mem_total))
        
        log "Memória: ${mem_percent}% utilizada"
    fi
    
    # Load average
    if [[ -f "/proc/loadavg" ]]; then
        local load=$(cat /proc/loadavg | cut -d' ' -f1-3)
        log "Load average: $load"
    fi
    
    # Estatísticas dos diretórios
    log "--- Estatísticas dos Diretórios ---"
    
    local dirs=("$APP_DIR" "$DATA_DIR" "$LOGS_DIR" "$CACHE_DIR" "$UPLOADS_DIR")
    for dir in "${dirs[@]}"; do
        if [[ -d "$dir" ]]; then
            local size=$(get_dir_size "$dir")
            local count=$(count_files "$dir")
            log "$dir: $size ($count arquivos)"
        fi
    done
    
    # Estatísticas do banco de dados
    if command -v psql >/dev/null 2>&1 && \
       PGPASSWORD="$DB_PASSWORD" pg_isready -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" >/dev/null 2>&1; then
        
        log "--- Estatísticas do Banco de Dados ---"
        
        # Tamanho do banco
        local db_size
        db_size=$(PGPASSWORD="$DB_PASSWORD" psql \
            -h "$DB_HOST" \
            -p "$DB_PORT" \
            -U "$DB_USER" \
            -d "$DB_NAME" \
            -t -c "SELECT pg_size_pretty(pg_database_size('$DB_NAME'));" 2>/dev/null | tr -d ' ' || echo "unknown")
        
        log "Tamanho do banco: $db_size"
        
        # Número de conexões
        local connections
        connections=$(PGPASSWORD="$DB_PASSWORD" psql \
            -h "$DB_HOST" \
            -p "$DB_PORT" \
            -U "$DB_USER" \
            -d "$DB_NAME" \
            -t -c "SELECT count(*) FROM pg_stat_activity WHERE datname = '$DB_NAME';" 2>/dev/null | tr -d ' ' || echo "0")
        
        log "Conexões ativas: $connections"
        
        # Contagem de registros principais
        local tables=("users" "roms" "games" "systems" "tasks")
        for table in "${tables[@]}"; do
            local count
            count=$(PGPASSWORD="$DB_PASSWORD" psql \
                -h "$DB_HOST" \
                -p "$DB_PORT" \
                -U "$DB_USER" \
                -d "$DB_NAME" \
                -t -c "SELECT count(*) FROM $table;" 2>/dev/null | tr -d ' ' || echo "N/A")
            
            log "Registros em $table: $count"
        done
    fi
    
    # Estatísticas do Redis
    if command -v redis-cli >/dev/null 2>&1; then
        local redis_cmd
        if [[ -n "$REDIS_PASSWORD" ]]; then
            redis_cmd="redis-cli -h $REDIS_HOST -p $REDIS_PORT -a $REDIS_PASSWORD"
        else
            redis_cmd="redis-cli -h $REDIS_HOST -p $REDIS_PORT"
        fi
        
        if $redis_cmd ping >/dev/null 2>&1; then
            log "--- Estatísticas do Redis ---"
            
            local redis_info
            redis_info=$($redis_cmd info memory 2>/dev/null || echo "")
            
            if [[ -n "$redis_info" ]]; then
                local used_memory=$(echo "$redis_info" | grep "used_memory_human:" | cut -d: -f2 | tr -d '\r')
                local keys_count=$($redis_cmd dbsize 2>/dev/null || echo "0")
                
                log "Memória Redis: $used_memory"
                log "Chaves Redis: $keys_count"
            fi
        fi
    fi
    
    log "Coleta de estatísticas concluída"
}

# =============================================================================
# FUNÇÃO PRINCIPAL
# =============================================================================

main() {
    log "=== INICIANDO MANUTENÇÃO DO MEGAEMU MODERN ==="
    log "Tarefas: $TASKS"
    log "Modo: $([ "$DRY_RUN" == "true" ] && echo "Simulação" || echo "Execução")"
    
    # Criar diretório de logs se não existir
    mkdir -p "$(dirname "$MAINTENANCE_LOG")" 2>/dev/null || true
    
    # Verificações iniciais
    check_dependencies
    check_connectivity
    
    # Executar tarefas
    cleanup_logs
    optimize_database
    cleanup_redis
    cleanup_cache
    cleanup_temp_files
    cleanup_orphans
    collect_stats
    
    log "=== MANUTENÇÃO CONCLUÍDA ==="
    
    if [[ "$DRY_RUN" == "true" ]]; then
        success "Simulação de manutenção do MegaEmu Modern concluída"
    else
        success "Manutenção do MegaEmu Modern concluída com sucesso"
    fi
}

# =============================================================================
# PROCESSAMENTO DE ARGUMENTOS
# =============================================================================

parse_arguments() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            -d|--dry-run)
                DRY_RUN=true
                shift
                ;;
            -v|--verbose)
                VERBOSE=true
                shift
                ;;
            -t|--tasks)
                TASKS="$2"
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
                error "Argumento inesperado: $1"
                ;;
        esac
    done
}

# =============================================================================
# TRATAMENTO DE SINAIS
# =============================================================================

# Função de limpeza em caso de interrupção
cleanup_on_exit() {
    log "Manutenção interrompida pelo usuário"
    error "Manutenção cancelada"
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