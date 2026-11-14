

$Root = (Get-Location).Path
$TestDir = Join-Path $Root "tests\Test_Testing\Test_Modulo2\RF-34\TC-M02-G19"
$Collection = Join-Path $TestDir "tc_m02_g19.json"
$Resultados = Join-Path $TestDir "Resultados"

$BaseUrl = "https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test"
$LoginUrl = "$BaseUrl/sesiones/"
$ActivoId = "181"
$FechaReferencia = "2026-09-09T20:45:00Z"

Write-Host ""
Write-Host "============================================================"
Write-Host " TC-M02-G19 - RF-34"
Write-Host " Fecha, defecto, integridad y auditoria"
Write-Host "============================================================"
Write-Host ""

if (-not (Test-Path $Collection)) {
    throw "No se encontro la collection: $Collection"
}

New-Item -ItemType Directory -Force -Path $Resultados | Out-Null

Write-Host "[1/4] Comprobando login Productor..."
$loginBody = @{
    correo_electronico = "productor@pecuaria.co"
    contrasena = "Test1234!"
} | ConvertTo-Json

try {
    $loginResponse = Invoke-RestMethod `
        -Uri $LoginUrl `
        -Method Post `
        -ContentType "application/json" `
        -Body $loginBody

    if ([string]::IsNullOrWhiteSpace($loginResponse.token)) {
        throw "Login respondio sin token."
    }

    Write-Host "Login correcto."
}
catch {
    Write-Host "ERROR en login: $($_.Exception.Message)" -ForegroundColor Red
    throw
}

Write-Host ""
Write-Host "[2/4] Validando collection..."
$null = Get-Content -Raw $Collection | ConvertFrom-Json
Write-Host "Collection encontrada."

Write-Host ""
Write-Host "[3/4] Generando environment..."

$Environment = @{
    id = "tc-m02-g19-rf34-environment"
    name = "TC-M02-G19 - RF-34 - TEST"
    values = @(
        @{ key = "baseUrl"; value = $BaseUrl; enabled = $true; type = "default" },
        @{ key = "activoActivoId"; value = $ActivoId; enabled = $true; type = "default" },
        @{ key = "fechaReferencia"; value = $FechaReferencia; enabled = $true; type = "default" },
        @{ key = "historicoEncontrado"; value = "false"; enabled = $true; type = "default" },
        @{ key = "inconsistenciaEncontrada"; value = "false"; enabled = $true; type = "default" },
        @{ key = "token"; value = ""; enabled = $true; type = "default" }
    )
    _postman_variable_scope = "environment"
} | ConvertTo-Json -Depth 10

$EnvironmentFile = Join-Path $TestDir "environment-g19.json"
Set-Content -Path $EnvironmentFile -Value $Environment -Encoding UTF8

Write-Host "Environment creado correctamente."
Write-Host ""
Write-Host "Activo para consulta ACTIVA/defaulto : $ActivoId"
Write-Host "Fecha de referencia                  : $FechaReferencia"
Write-Host "Historial cerrado previo             : False"
Write-Host "Inconsistencia preparada              : False"

Write-Host ""
Write-Host "[4/4] Ejecutando Newman..."
Write-Host ""

$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$HtmlReport = Join-Path $Resultados "TC-M02-G19-Newman-$stamp.html"
$JsonReport = Join-Path $Resultados "TC-M02-G19-Newman-$stamp.json"

& newman run $Collection `
    -e $EnvironmentFile `
    --reporters "cli,htmlextra,json" `
    --reporter-htmlextra-export $HtmlReport `
    --reporter-json-export $JsonReport

$exitCode = $LASTEXITCODE

Write-Host ""
Write-Host "============================================================"
Write-Host " Newman finalizo con codigo: $exitCode"
Write-Host "============================================================"
Write-Host ""
Write-Host "HTML:"
Write-Host $HtmlReport
Write-Host ""
Write-Host "JSON:"
Write-Host $JsonReport

exit $exitCode
