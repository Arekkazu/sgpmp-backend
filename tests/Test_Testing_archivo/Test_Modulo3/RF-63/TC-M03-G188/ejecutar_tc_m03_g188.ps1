# Runner PowerShell para TC-M03-G188 (Resiliencia - BLOQUEADO POR INFRAESTRUCTURA)
param(
    [string]$BaseUrl = "https://api.inmero.co/back-sigab-test"
)

$CurrentDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ResultadosDir = Join-Path $CurrentDir "resultados"

if (-not (Test-Path $ResultadosDir)) {
    New-Item -ItemType Directory -Path $ResultadosDir -Force | Out-Null
}

Write-Host "==========================================================" -ForegroundColor Magenta
Write-Host "  EJECUTANDO RUNNER TC-M03-G188 (Resiliencia y Continuidad)" -ForegroundColor Magenta
Write-Host "==========================================================" -ForegroundColor Magenta

Write-Host "[BLOQUEADO] Requiere infraestructura de laboratorio (docker-compose.test.yml + toxiproxy). No ejecutable contra TEST desplegado." -ForegroundColor Red
Write-Host "  - TC-M03-357: Caida de servicio/DB de auditoria (requiere detener PostgreSQL/proceso)." -ForegroundColor Yellow
Write-Host "  - TC-M03-358: Caida del broker MQTT (requiere orquestador de contenedores)." -ForegroundColor Yellow
Write-Host "  - TC-M03-359: Desconexion de nodo Edge >=2h (incompatible con timeout de sandbox 180s)." -ForegroundColor Yellow
Write-Host "`nReporte detallado de diseno disponible en: resultados/resultado_TC-M03-G188.html" -ForegroundColor Cyan

Write-Host "`nConsultando estado en qa-dashboard scanner..." -ForegroundColor Yellow
$DashboardDir = Join-Path $CurrentDir "../../../qa-dashboard"
if (Test-Path $DashboardDir) {
    Push-Location $DashboardDir
    try {
        python3 -c "import scanner as s; print([c for c in s.scan()['casos'] if c['tc_id']=='TC-M03-G188'])"
    } catch {
        Write-Warning "No se pudo ejecutar scanner: $_"
    }
    Pop-Location
}

exit 0
