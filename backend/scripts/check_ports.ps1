# check_ports.ps1 - Script de Auto-Diagnóstico de Portas para MegaEmu Modern

# Descrição: Verifica se as portas configuradas estão disponíveis, com logs detalhados e verificações de erro.
# Não remove ou simplifica verificações existentes; adiciona diagnósticos granulares.

# Portas a verificar (baseado em docker-compose.yml e frontend)
$ports = @(
    5432,  # Postgres
    6379,  # Redis
    8000,  # Backend
    5555,  # Flower (opcional)
    9090,  # Prometheus (opcional)
    3001,  # Grafana (mapeado para 3000 no container)
    3000   # Frontend React (executado no host)
)

# Log inicial
Write-Output "[INFO] Iniciando verificação de portas em $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
Write-Output "[INFO] Portas configuradas: $($ports -join ', ')"

# Verificação de permissões (mantendo robustez)
if (-not ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Output "[WARNING] Executando sem privilégios de administrador. Algumas verificações podem falhar."
}

# Obter conexões listening
$listening = Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue
if ($null -eq $listening) {
    Write-Output "[ERROR] Falha ao obter conexões TCP. Verifique permissões ou NetTCPConnection."
    exit 1
}
Write-Output "[INFO] Total de portas listening detectadas: $($listening.Count)"

# Verificar cada porta com detalhes
foreach ($port in $ports) {
    Write-Output "[DEBUG] Verificando porta $port..."
    $inUse = $listening | Where-Object { $_.LocalPort -eq $port }
    if ($inUse) {
        $processId = $inUse.OwningProcess
        $process = Get-Process -Id $processId -ErrorAction SilentlyContinue
        $processName = if ($process) { $process.ProcessName } else { "Desconhecido (PID: $processId)" }
        Write-Output "[ERROR] Porta $port em uso por processo: $processName (PID: $processId)"
        Write-Output "[DEBUG] Endereço local: $($inUse.LocalAddress)"
    } else {
        Write-Output "[OK] Porta $port disponível."
    }
}

# Log final
Write-Output "[INFO] Verificação concluída em $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
Write-Output "[ADVICE] Se houver conflitos, pare os processos ou altere as portas em .env/docker-compose."

# Saúde check: Verificar se houve erros
$errors = $Error.Count
if ($errors -gt 0) {
    Write-Output "[ERROR] Ocorreram $errors erros durante a execução. Consulte logs acima."
    exit 1
}
exit 0