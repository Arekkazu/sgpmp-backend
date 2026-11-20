# TC-M07-G057 — Newman (auxiliar). Informe oficial: ejecutar_tc_m07_g57.py
$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$envFile = Join-Path $here "entorno.postman_environment.json"
$required = @(
    "QA_ADMIN_CORREO", "QA_ADMIN_CONTRASENA",
    "QA_AUDITOR_CORREO", "QA_AUDITOR_CONTRASENA",
    "QA_SIN_PERMISO_CORREO", "QA_SIN_PERMISO_CONTRASENA"
)
foreach ($k in $required) {
    if (-not [Environment]::GetEnvironmentVariable($k)) {
        Write-Error "Defina $k antes de Newman."
    }
}
$json = Get-Content $envFile -Raw | ConvertFrom-Json
foreach ($v in $json.values) {
    foreach ($k in $required) {
        if ($v.key -eq $k) { $v.value = [Environment]::GetEnvironmentVariable($k) }
    }
}
$tmp = Join-Path $env:TEMP "tc_m07_g057_env.json"
$json | ConvertTo-Json -Depth 6 | Set-Content -Path $tmp -Encoding utf8
$outDir = Join-Path $here "Resultado"
New-Item -ItemType Directory -Force -Path $outDir | Out-Null
newman run (Join-Path $here "TC-M07-G057.postman_collection.json") -e $tmp --insecure --reporters "cli" 2>&1 |
    Tee-Object -FilePath (Join-Path $outDir "newman_cli_TC-M07-G057.txt")
Remove-Item $tmp -ErrorAction SilentlyContinue
Write-Host "Informe oficial: Resultado/resultado_TC-M07-G057.html"
