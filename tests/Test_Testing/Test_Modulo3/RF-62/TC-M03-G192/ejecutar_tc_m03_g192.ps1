# Runner PowerShell para TC-M03-G192 (Calidad Visión RFC-011 - BLOQUEADO POR ENDPOINT NO IMPLEMENTADO)
param(
    [string]$BaseUrl = "https://api.inmero.co/back-sigab-test"
)

$CurrentDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ResultadosDir = Join-Path $CurrentDir "resultados"

if (-not (Test-Path $ResultadosDir)) {
    New-Item -ItemType Directory -Path $ResultadosDir -Force | Out-Null
}

$Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$RunDir = Join-Path $CurrentDir "RESULTADOS/run-$Timestamp"
New-Item -ItemType Directory -Path $RunDir -Force | Out-Null

Write-Host "==========================================================" -ForegroundColor Magenta
Write-Host "  EJECUTANDO RUNNER TC-M03-G192 (RFC-011 Calidad Vision)" -ForegroundColor Magenta
Write-Host "==========================================================" -ForegroundColor Magenta

Write-Host "[BLOQUEADO] Endpoint para evaluación de calidad de observaciones de visión computacional NO IMPLEMENTADO." -ForegroundColor Red
Write-Host "  - OpenAPI y backend solo exponen evaluación de telemetría escalar (POST /iot/calidad/{id_telemetria}/evaluar en calidad_router.py:105)." -ForegroundColor Yellow
Write-Host "  - No existe /iot/calidad/vision/{id}/evaluar ni caso de uso asociado a RFC-011 en backend TEST." -ForegroundColor Yellow
Write-Host "  - Subcasos TC-369 a TC-373 marcados como BLOQUEADOS con motivo explícito." -ForegroundColor Yellow
Write-Host "`nReporte detallado disponible en: resultados/resultado_TC-M03-G192.html" -ForegroundColor Cyan

Copy-Item (Join-Path $ResultadosDir "resultado_TC-M03-G192.html") (Join-Path $RunDir "resultado_TC-M03-G192.html") -Force -ErrorAction SilentlyContinue

Write-Host "`nConsultando estado en qa-dashboard scanner..." -ForegroundColor Yellow
$DashboardDir = Join-Path $CurrentDir "../../../qa-dashboard"
if (Test-Path $DashboardDir) {
    Push-Location $DashboardDir
    try {
        python3 -c "import scanner as s; print([c for c in s.scan()['casos'] if c['tc_id']=='TC-M03-G192'])"
    } catch {
        Write-Warning "No se pudo ejecutar scanner: $_"
    }
    Pop-Location
}

exit 0
