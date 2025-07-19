#!/bin/bash

# =============================================================================
# SCRIPT DE HEALTH CHECK - MEGAEMU MODERN
# =============================================================================
# Script para verificar a saúde do sistema MegaEmu Modern
# Monitora serviços, conectividade, recursos e métricas de performance

set -euo pipefail

# =============================================================================
# CONFIGURAÇÕES
# =============================================================================

# URLs e endpoints
API_BASE_URL="${API_BASE_URL:-http://localhost:8000}"
HEALTH_ENDPOINT="${HEALTH_ENDPOINT:-/health}"
METRICS_ENDPOINT="${METRICS_ENDPOINT:-/metrics}"
READINESS_ENDPOINT="${READINESS_ENDPOINT:-/ready}"

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

# Configurações de limites
CPU_THRESHOLD="${CPU_THRESHOLD:-80}"
MEMORY_THRESHOLD="${MEMORY_THRESHOLD:-85}"
DISK_THRESHOLD="${DISK_THRESHOLD:-90}"
LOAD_THRESHOLD="${LOAD_THRESHOLD:-2.0}"
RESPONSE_TIME_THRESHOLD="${RESPONSE_TIME_THRESHOLD:-5000}"

# Configurações de timeout
HTTP_TIMEOUT="${HTTP_TIMEOUT:-10}"
DB_TIMEOUT="${DB_TIMEOUT:-5}"
REDIS_TIMEOUT="${REDIS_TIMEOUT:-3}"

# Configurações de notificação
WEBHOOK_URL="${HEALTH_WEBHOOK_URL:-}"
EMAIL_TO="${HEALTH_EMAIL_TO:-}"
SLACK_WEBHOOK="${SLACK_WEBHOOK_URL:-}"

# Configurações de saída
OUTPUT_FORMAT="${OUTPUT_FORMAT:-text}"
VERBOSE=false
QUIET=false
CHECKS="all"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")

# Variáveis de estado
OVERALL_STATUS="healthy"
FAILED_CHECKS=()
WARNING_CHECKS=()
CHECK_RESULTS=()

# =============================================================================
# FUNÇÕES AUXILIARES
# =============================================================================

# Função de log
log() {
    if [[ "$QUIET" != "true" ]]; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
    fi
}

# Função de debug
debug() {
    if [[ "$VERBOSE" == "true" ]]; then
        log "DEBUG: $1"
    fi
}

# Função de erro
error() {
    log "ERROR: $1"
    OVERALL_STATUS="unhealthy"
    FAILED_CHECKS+=("$1")
}

# Função de aviso
warning() {
    log "WARNING: $1"
    if [[ "$OVERALL_STATUS" == "healthy" ]]; then
        OVERALL_STATUS="degraded"
    fi
    WARNING_CHECKS+=("$1")
}

# Função de sucesso
success() {
    debug "SUCCESS: $1"
}

# Função para mostrar ajuda
show_help() {
    cat << EOF
Uso: $0 [OPÇÕES]

OPÇÕES:
    -v, --verbose            Saída detalhada
    -q, --quiet              Saída silenciosa (apenas erros)
    -f, --format FORMAT      Formato de saída (text, json, prometheus)
    -c, --checks LISTA       Verificações a executar (all,api,db,redis,system,services)
    -t, --timeout SEGUNDOS   Timeout para verificações HTTP (padrão: 10)
    -h, --help               Mostrar esta ajuda

VERIFICAÇÕES:
    all      - Todas as verificações (padrão)
    api      - API e endpoints HTTP
    db       - Banco de dados PostgreSQL
    redis    - Cache Redis
    system   - Recursos do sistema
    services - Serviços externos
    celery   - Workers Celery

FORMATOS DE SAÍDA:
    text       - Texto legível (padrão)
    json       - JSON estruturado
    prometheus - Métricas Prometheus

EXEMPLOS:
    $0                           # Verificação completa
    $0 -v -f json                # Saída JSON detalhada
    $0 -c api,db                 # Apenas API e banco
    $0 -q -f prometheus          # Métricas silenciosas

CÓDIGOS DE SAÍDA:
    0 - Sistema saudável
    1 - Sistema degradado (avisos)
    2 - Sistema não saudável (erros)
    3 - Erro de execução
EOF
}

# Função para enviar notificações
send_notification() {
    local status="$1"
    local message="$2"
    local details="${3:-}"
    
    # Webhook genérico
    if [[ -n "$WEBHOOK_URL" ]]; then
        curl -s -X POST "$WEBHOOK_URL" \
            -H "Content-Type: application/json" \
            -d "{
                \"event\": \"health_check\",
                \"status\": \"$status\",
                \"message\": \"$message\",
                \"details\": \"$details\",
                \"timestamp\": \"$(date -Iseconds)\",
                \"checks\": \"$CHECKS\",
                \"failed_checks\": [$(printf '\"%s\",' "${FAILED_CHECKS[@]}" | sed 's/,$//')]],
                \"warning_checks\": [$(printf '\"%s\",' "${WARNING_CHECKS[@]}" | sed 's/,$//')]]
            }" || debug "Failed to send webhook notification"
    fi
    
    # Slack
    if [[ -n "$SLACK_WEBHOOK" ]]; then
        local color="good"
        case "$status" in
            "unhealthy") color="danger" ;;
            "degraded") color="warning" ;;
        esac
        
        curl -s -X POST "$SLACK_WEBHOOK" \
            -H "Content-Type: application/json" \
            -d "{
                \"attachments\": [{
                    \"color\": \"$color\",
                    \"title\": \"MegaEmu Health Check\",
                    \"text\": \"$message\",
                    \"fields\": [
                        {\"title\": \"Status\", \"value\": \"$status\", \"short\": true},
                        {\"title\": \"Timestamp\", \"value\": \"$(date)\", \"short\": true}
                    ]
                }]
            }" || debug "Failed to send Slack notification"
    fi
    
    # Email
    if [[ -n "$EMAIL_TO" ]] && command -v mail >/dev/null 2>&1; then
        echo -e "$message\n\n$details" | \
            mail -s "MegaEmu Health Check - $status" "$EMAIL_TO" || \
            debug "Failed to send email notification"
    fi
}

# Função para medir tempo de resposta
measure_response_time() {
    local url="$1"
    local timeout="${2:-$HTTP_TIMEOUT}"
    
    local start_time=$(date +%s%3N)
    
    if curl -s -f -m "$timeout" "$url" >/dev/null 2>&1; then
        local end_time=$(date +%s%3N)
        echo $((end_time - start_time))
        return 0
    else
        echo "-1"
        return 1
    fi
}

# Função para verificar porta
check_port() {
    local host="$1"
    local port="$2"
    local timeout="${3:-3}"
    
    if command -v nc >/dev/null 2>&1; then
        nc -z -w"$timeout" "$host" "$port" 2>/dev/null
    elif command -v telnet >/dev/null 2>&1; then
        timeout "$timeout" telnet "$host" "$port" </dev/null >/dev/null 2>&1
    else
        # Fallback usando /dev/tcp (bash built-in)
        timeout "$timeout" bash -c "exec 3<>/dev/tcp/$host/$port" 2>/dev/null
    fi
}

# Função para adicionar resultado
add_result() {
    local check="$1"
    local status="$2"
    local message="$3"
    local value="${4:-}"
    local unit="${5:-}"
    
    CHECK_RESULTS+=("$check|$status|$message|$value|$unit")
}

# =============================================================================
# VERIFICAÇÕES DE SAÚDE
# =============================================================================

# Verificação da API
check_api() {
    if [[ "$CHECKS" != "all" ]] && [[ "$CHECKS" != *"api"* ]]; then
        return 0
    fi
    
    log "Verificando API..."
    
    # Health endpoint
    local health_url="${API_BASE_URL}${HEALTH_ENDPOINT}"
    local response_time
    
    response_time=$(measure_response_time "$health_url")
    
    if [[ "$response_time" -eq -1 ]]; then
        error "API não está respondendo: $health_url"
        add_result "api_health" "critical" "API não responde" "0" "ms"
    else
        if [[ "$response_time" -gt "$RESPONSE_TIME_THRESHOLD" ]]; then
            warning "API respondendo lentamente: ${response_time}ms"
            add_result "api_health" "warning" "Resposta lenta" "$response_time" "ms"
        else
            success "API respondendo normalmente: ${response_time}ms"
            add_result "api_health" "ok" "API saudável" "$response_time" "ms"
        fi
    fi
    
    # Readiness endpoint
    local readiness_url="${API_BASE_URL}${READINESS_ENDPOINT}"
    response_time=$(measure_response_time "$readiness_url")
    
    if [[ "$response_time" -eq -1 ]]; then
        warning "Endpoint de readiness não está respondendo"
        add_result "api_readiness" "warning" "Readiness não responde" "0" "ms"
    else
        success "Endpoint de readiness OK: ${response_time}ms"
        add_result "api_readiness" "ok" "Readiness OK" "$response_time" "ms"
    fi
    
    # Metrics endpoint
    local metrics_url="${API_BASE_URL}${METRICS_ENDPOINT}"
    response_time=$(measure_response_time "$metrics_url")
    
    if [[ "$response_time" -eq -1 ]]; then
        warning "Endpoint de métricas não está respondendo"
        add_result "api_metrics" "warning" "Métricas não respondem" "0" "ms"
    else
        success "Endpoint de métricas OK: ${response_time}ms"
        add_result "api_metrics" "ok" "Métricas OK" "$response_time" "ms"
    fi
}

# Verificação do PostgreSQL
check_database() {
    if [[ "$CHECKS" != "all" ]] && [[ "$CHECKS" != *"db"* ]]; then
        return 0
    fi
    
    log "Verificando PostgreSQL..."
    
    if ! command -v psql >/dev/null 2>&1; then
        warning "psql não encontrado, pulando verificação do banco"
        add_result "db_client" "warning" "Cliente não encontrado" "0" ""
        return 0
    fi
    
    # Verificar conectividade
    if ! check_port "$DB_HOST" "$DB_PORT" "$DB_TIMEOUT"; then
        error "PostgreSQL não está acessível em $DB_HOST:$DB_PORT"
        add_result "db_connectivity" "critical" "Porta não acessível" "0" ""
        return 1
    fi
    
    # Verificar autenticação e consulta simples
    local start_time=$(date +%s%3N)
    
    if PGPASSWORD="$DB_PASSWORD" psql \
        -h "$DB_HOST" \
        -p "$DB_PORT" \
        -U "$DB_USER" \
        -d "$DB_NAME" \
        -c "SELECT 1;" >/dev/null 2>&1; then
        
        local end_time=$(date +%s%3N)
        local query_time=$((end_time - start_time))
        
        success "PostgreSQL conectado e respondendo: ${query_time}ms"
        add_result "db_query" "ok" "Consulta bem-sucedida" "$query_time" "ms"
    else
        error "Falha na autenticação ou consulta ao PostgreSQL"
        add_result "db_query" "critical" "Falha na consulta" "0" "ms"
        return 1
    fi
    
    # Verificar estatísticas do banco
    local db_size
    db_size=$(PGPASSWORD="$DB_PASSWORD" psql \
        -h "$DB_HOST" \
        -p "$DB_PORT" \
        -U "$DB_USER" \
        -d "$DB_NAME" \
        -t -c "SELECT pg_database_size('$DB_NAME');" 2>/dev/null | tr -d ' ' || echo "0")
    
    local connections
    connections=$(PGPASSWORD="$DB_PASSWORD" psql \
        -h "$DB_HOST" \
        -p "$DB_PORT" \
        -U "$DB_USER" \
        -d "$DB_NAME" \
        -t -c "SELECT count(*) FROM pg_stat_activity WHERE datname = '$DB_NAME';" 2>/dev/null | tr -d ' ' || echo "0")
    
    debug "Tamanho do banco: $db_size bytes"
    debug "Conexões ativas: $connections"
    
    add_result "db_size" "info" "Tamanho do banco" "$db_size" "bytes"
    add_result "db_connections" "info" "Conexões ativas" "$connections" "count"
    
    # Verificar locks
    local locks
    locks=$(PGPASSWORD="$DB_PASSWORD" psql \
        -h "$DB_HOST" \
        -p "$DB_PORT" \
        -U "$DB_USER" \
        -d "$DB_NAME" \
        -t -c "SELECT count(*) FROM pg_locks WHERE NOT granted;" 2>/dev/null | tr -d ' ' || echo "0")
    
    if [[ "$locks" -gt 0 ]]; then
        warning "$locks locks não concedidos detectados"
        add_result "db_locks" "warning" "Locks pendentes" "$locks" "count"
    else
        add_result "db_locks" "ok" "Sem locks pendentes" "$locks" "count"
    fi
}

# Verificação do Redis
check_redis() {
    if [[ "$CHECKS" != "all" ]] && [[ "$CHECKS" != *"redis"* ]]; then
        return 0
    fi
    
    log "Verificando Redis..."
    
    if ! command -v redis-cli >/dev/null 2>&1; then
        warning "redis-cli não encontrado, pulando verificação do Redis"
        add_result "redis_client" "warning" "Cliente não encontrado" "0" ""
        return 0
    fi
    
    # Verificar conectividade
    if ! check_port "$REDIS_HOST" "$REDIS_PORT" "$REDIS_TIMEOUT"; then
        error "Redis não está acessível em $REDIS_HOST:$REDIS_PORT"
        add_result "redis_connectivity" "critical" "Porta não acessível" "0" ""
        return 1
    fi
    
    # Configurar comando Redis
    local redis_cmd
    if [[ -n "$REDIS_PASSWORD" ]]; then
        redis_cmd="redis-cli -h $REDIS_HOST -p $REDIS_PORT -a $REDIS_PASSWORD"
    else
        redis_cmd="redis-cli -h $REDIS_HOST -p $REDIS_PORT"
    fi
    
    # Verificar ping
    local start_time=$(date +%s%3N)
    
    if $redis_cmd ping >/dev/null 2>&1; then
        local end_time=$(date +%s%3N)
        local ping_time=$((end_time - start_time))
        
        success "Redis respondendo ao ping: ${ping_time}ms"
        add_result "redis_ping" "ok" "Ping bem-sucedido" "$ping_time" "ms"
    else
        error "Redis não está respondendo ao ping"
        add_result "redis_ping" "critical" "Ping falhou" "0" "ms"
        return 1
    fi
    
    # Verificar informações do Redis
    local redis_info
    redis_info=$($redis_cmd info memory 2>/dev/null || echo "")
    
    if [[ -n "$redis_info" ]]; then
        local used_memory_bytes=$(echo "$redis_info" | grep "used_memory:" | cut -d: -f2 | tr -d '\r')
        local max_memory_bytes=$(echo "$redis_info" | grep "maxmemory:" | cut -d: -f2 | tr -d '\r')
        local keys_count=$($redis_cmd dbsize 2>/dev/null || echo "0")
        
        debug "Memória utilizada: $used_memory_bytes bytes"
        debug "Memória máxima: $max_memory_bytes bytes"
        debug "Número de chaves: $keys_count"
        
        add_result "redis_memory" "info" "Memória utilizada" "$used_memory_bytes" "bytes"
        add_result "redis_keys" "info" "Número de chaves" "$keys_count" "count"
        
        # Verificar uso de memória
        if [[ "$max_memory_bytes" -gt 0 ]] && [[ "$used_memory_bytes" -gt 0 ]]; then
            local memory_percent=$((used_memory_bytes * 100 / max_memory_bytes))
            
            if [[ "$memory_percent" -gt 90 ]]; then
                warning "Uso de memória Redis alto: ${memory_percent}%"
                add_result "redis_memory_usage" "warning" "Memória alta" "$memory_percent" "%"
            else
                add_result "redis_memory_usage" "ok" "Memória normal" "$memory_percent" "%"
            fi
        fi
    fi
}

# Verificação do sistema
check_system() {
    if [[ "$CHECKS" != "all" ]] && [[ "$CHECKS" != *"system"* ]]; then
        return 0
    fi
    
    log "Verificando recursos do sistema..."
    
    # CPU
    if [[ -f "/proc/loadavg" ]]; then
        local load_1min=$(cat /proc/loadavg | cut -d' ' -f1)
        local cpu_cores=$(nproc 2>/dev/null || echo "1")
        local load_percent=$(echo "$load_1min * 100 / $cpu_cores" | bc -l 2>/dev/null | cut -d. -f1 || echo "0")
        
        debug "Load average (1min): $load_1min"
        debug "CPU cores: $cpu_cores"
        debug "Load percentage: $load_percent%"
        
        add_result "system_load" "info" "Load average" "$load_1min" "load"
        
        if [[ "$load_percent" -gt "$CPU_THRESHOLD" ]]; then
            warning "Load do sistema alto: ${load_percent}%"
            add_result "system_load_percent" "warning" "Load alto" "$load_percent" "%"
        else
            add_result "system_load_percent" "ok" "Load normal" "$load_percent" "%"
        fi
    fi
    
    # Memória
    if [[ -f "/proc/meminfo" ]]; then
        local mem_total=$(grep MemTotal /proc/meminfo | awk '{print $2}')
        local mem_available=$(grep MemAvailable /proc/meminfo | awk '{print $2}')
        local mem_used=$((mem_total - mem_available))
        local mem_percent=$((mem_used * 100 / mem_total))
        
        debug "Memória total: $mem_total KB"
        debug "Memória disponível: $mem_available KB"
        debug "Memória utilizada: ${mem_percent}%"
        
        add_result "system_memory_total" "info" "Memória total" "$mem_total" "KB"
        add_result "system_memory_used" "info" "Memória utilizada" "$mem_used" "KB"
        
        if [[ "$mem_percent" -gt "$MEMORY_THRESHOLD" ]]; then
            warning "Uso de memória alto: ${mem_percent}%"
            add_result "system_memory_percent" "warning" "Memória alta" "$mem_percent" "%"
        else
            add_result "system_memory_percent" "ok" "Memória normal" "$mem_percent" "%"
        fi
    fi
    
    # Espaço em disco
    if command -v df >/dev/null 2>&1; then
        local disk_usage
        disk_usage=$(df / | tail -1 | awk '{print $5}' | sed 's/%//')
        
        debug "Uso do disco raiz: ${disk_usage}%"
        
        add_result "system_disk_usage" "info" "Uso do disco" "$disk_usage" "%"
        
        if [[ "$disk_usage" -gt "$DISK_THRESHOLD" ]]; then
            warning "Uso de disco alto: ${disk_usage}%"
            add_result "system_disk_status" "warning" "Disco cheio" "$disk_usage" "%"
        else
            add_result "system_disk_status" "ok" "Disco normal" "$disk_usage" "%"
        fi
    fi
    
    # Processos
    local process_count
    process_count=$(ps aux | wc -l)
    
    debug "Número de processos: $process_count"
    add_result "system_processes" "info" "Processos ativos" "$process_count" "count"
}

# Verificação dos serviços
check_services() {
    if [[ "$CHECKS" != "all" ]] && [[ "$CHECKS" != *"services"* ]]; then
        return 0
    fi
    
    log "Verificando serviços..."
    
    # Verificar se o processo da aplicação está rodando
    local app_processes
    app_processes=$(pgrep -f "uvicorn\|gunicorn\|python.*main" | wc -l)
    
    if [[ "$app_processes" -gt 0 ]]; then
        success "Processo da aplicação rodando ($app_processes processos)"
        add_result "service_app" "ok" "Aplicação rodando" "$app_processes" "count"
    else
        error "Processo da aplicação não encontrado"
        add_result "service_app" "critical" "Aplicação parada" "0" "count"
    fi
    
    # Verificar Docker (se disponível)
    if command -v docker >/dev/null 2>&1; then
        local docker_containers
        docker_containers=$(docker ps --filter "name=megaemu" --format "table {{.Names}}" | tail -n +2 | wc -l 2>/dev/null || echo "0")
        
        debug "Containers Docker: $docker_containers"
        add_result "service_docker" "info" "Containers ativos" "$docker_containers" "count"
    fi
}

# Verificação do Celery
check_celery() {
    if [[ "$CHECKS" != "all" ]] && [[ "$CHECKS" != *"celery"* ]]; then
        return 0
    fi
    
    log "Verificando Celery..."
    
    # Verificar workers Celery
    local celery_processes
    celery_processes=$(pgrep -f "celery.*worker" | wc -l)
    
    if [[ "$celery_processes" -gt 0 ]]; then
        success "Workers Celery rodando ($celery_processes workers)"
        add_result "celery_workers" "ok" "Workers ativos" "$celery_processes" "count"
    else
        warning "Nenhum worker Celery encontrado"
        add_result "celery_workers" "warning" "Workers parados" "0" "count"
    fi
    
    # Verificar beat Celery
    local beat_processes
    beat_processes=$(pgrep -f "celery.*beat" | wc -l)
    
    if [[ "$beat_processes" -gt 0 ]]; then
        success "Celery Beat rodando"
        add_result "celery_beat" "ok" "Beat ativo" "$beat_processes" "count"
    else
        warning "Celery Beat não encontrado"
        add_result "celery_beat" "warning" "Beat parado" "0" "count"
    fi
}

# =============================================================================
# FUNÇÕES DE SAÍDA
# =============================================================================

# Saída em texto
output_text() {
    echo
    echo "=== MEGAEMU HEALTH CHECK REPORT ==="
    echo "Timestamp: $(date)"
    echo "Overall Status: $OVERALL_STATUS"
    echo
    
    if [[ ${#FAILED_CHECKS[@]} -gt 0 ]]; then
        echo "FAILED CHECKS:"
        for check in "${FAILED_CHECKS[@]}"; do
            echo "  ❌ $check"
        done
        echo
    fi
    
    if [[ ${#WARNING_CHECKS[@]} -gt 0 ]]; then
        echo "WARNING CHECKS:"
        for check in "${WARNING_CHECKS[@]}"; do
            echo "  ⚠️  $check"
        done
        echo
    fi
    
    if [[ "$VERBOSE" == "true" ]]; then
        echo "DETAILED RESULTS:"
        for result in "${CHECK_RESULTS[@]}"; do
            IFS='|' read -r check status message value unit <<< "$result"
            local icon=""
            case "$status" in
                "ok") icon="✅" ;;
                "warning") icon="⚠️" ;;
                "critical") icon="❌" ;;
                "info") icon="ℹ️" ;;
            esac
            
            if [[ -n "$value" ]] && [[ -n "$unit" ]]; then
                echo "  $icon $check: $message ($value $unit)"
            else
                echo "  $icon $check: $message"
            fi
        done
    fi
}

# Saída em JSON
output_json() {
    local failed_json="[]"
    local warning_json="[]"
    local results_json="[]"
    
    # Construir array de falhas
    if [[ ${#FAILED_CHECKS[@]} -gt 0 ]]; then
        failed_json="[$(printf '"%s",' "${FAILED_CHECKS[@]}" | sed 's/,$//')]]"
    fi
    
    # Construir array de avisos
    if [[ ${#WARNING_CHECKS[@]} -gt 0 ]]; then
        warning_json="[$(printf '"%s",' "${WARNING_CHECKS[@]}" | sed 's/,$//')]]"
    fi
    
    # Construir array de resultados
    if [[ ${#CHECK_RESULTS[@]} -gt 0 ]]; then
        local result_items=()
        for result in "${CHECK_RESULTS[@]}"; do
            IFS='|' read -r check status message value unit <<< "$result"
            result_items+=("{
        \"check\": \"$check\",
        \"status\": \"$status\",
        \"message\": \"$message\",
        \"value\": \"$value\",
        \"unit\": \"$unit\"
      }")
        done
        results_json="[$(IFS=','; echo "${result_items[*]}")]]"
    fi
    
    cat << EOF
{
  "timestamp": "$(date -Iseconds)",
  "overall_status": "$OVERALL_STATUS",
  "checks_requested": "$CHECKS",
  "failed_checks": $failed_json,
  "warning_checks": $warning_json,
  "results": $results_json
}
EOF
}

# Saída em formato Prometheus
output_prometheus() {
    echo "# HELP megaemu_health_status Overall health status (0=unhealthy, 1=degraded, 2=healthy)"
    echo "# TYPE megaemu_health_status gauge"
    
    local status_value=2
    case "$OVERALL_STATUS" in
        "unhealthy") status_value=0 ;;
        "degraded") status_value=1 ;;
        "healthy") status_value=2 ;;
    esac
    
    echo "megaemu_health_status $status_value"
    echo
    
    # Métricas detalhadas
    for result in "${CHECK_RESULTS[@]}"; do
        IFS='|' read -r check status message value unit <<< "$result"
        
        if [[ -n "$value" ]] && [[ "$value" != "0" ]] && [[ "$unit" != "" ]]; then
            local metric_name="megaemu_${check}"
            echo "# HELP $metric_name $message"
            echo "# TYPE $metric_name gauge"
            echo "$metric_name{status=\"$status\",unit=\"$unit\"} $value"
            echo
        fi
        
        # Status como métrica binária
        local status_metric="megaemu_${check}_status"
        local status_value=1
        case "$status" in
            "critical") status_value=0 ;;
            "warning") status_value=0.5 ;;
            "ok"|"info") status_value=1 ;;
        esac
        
        echo "# HELP $status_metric Status of $check (0=critical, 0.5=warning, 1=ok)"
        echo "# TYPE $status_metric gauge"
        echo "$status_metric{check=\"$check\"} $status_value"
        echo
    done
}

# =============================================================================
# FUNÇÃO PRINCIPAL
# =============================================================================

main() {
    debug "Iniciando health check do MegaEmu Modern"
    debug "Verificações: $CHECKS"
    debug "Formato de saída: $OUTPUT_FORMAT"
    
    # Executar verificações
    check_api
    check_database
    check_redis
    check_system
    check_services
    check_celery
    
    # Gerar saída
    case "$OUTPUT_FORMAT" in
        "json")
            output_json
            ;;
        "prometheus")
            output_prometheus
            ;;
        *)
            output_text
            ;;
    esac
    
    # Enviar notificações se necessário
    if [[ "$OVERALL_STATUS" != "healthy" ]]; then
        local details=""
        if [[ ${#FAILED_CHECKS[@]} -gt 0 ]]; then
            details+="Failed: $(IFS=', '; echo "${FAILED_CHECKS[*]}")\n"
        fi
        if [[ ${#WARNING_CHECKS[@]} -gt 0 ]]; then
            details+="Warnings: $(IFS=', '; echo "${WARNING_CHECKS[*]}")"
        fi
        
        send_notification "$OVERALL_STATUS" "MegaEmu health check failed" "$details"
    fi
    
    # Código de saída
    case "$OVERALL_STATUS" in
        "healthy") exit 0 ;;
        "degraded") exit 1 ;;
        "unhealthy") exit 2 ;;
    esac
}

# =============================================================================
# PROCESSAMENTO DE ARGUMENTOS
# =============================================================================

parse_arguments() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            -v|--verbose)
                VERBOSE=true
                shift
                ;;
            -q|--quiet)
                QUIET=true
                shift
                ;;
            -f|--format)
                OUTPUT_FORMAT="$2"
                shift 2
                ;;
            -c|--checks)
                CHECKS="$2"
                shift 2
                ;;
            -t|--timeout)
                HTTP_TIMEOUT="$2"
                shift 2
                ;;
            -h|--help)
                show_help
                exit 0
                ;;
            -*)
                echo "Opção desconhecida: $1" >&2
                exit 3
                ;;
            *)
                echo "Argumento inesperado: $1" >&2
                exit 3
                ;;
        esac
    done
    
    # Validar formato de saída
    case "$OUTPUT_FORMAT" in
        "text"|"json"|"prometheus")
            ;;
        *)
            echo "Formato de saída inválido: $OUTPUT_FORMAT" >&2
            exit 3
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