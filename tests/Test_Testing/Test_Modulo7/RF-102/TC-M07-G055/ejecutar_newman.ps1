# TC-M07-G055 — Newman (auxiliar). Informe oficial: ejecutar_tc_m07_g55.py
$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$envFile = Join-Path $here "entorno.postman_environment.json"
if (-not $env:QA_ADMIN_CORREO -or -not $env:QA_ADMIN_CONTRASENA) {
    Write-Error "Defina QA_ADMIN_CORREO y QA_ADMIN_CONTRASENA antes de Newman."
}
$json = Get-Content $envFile -Raw | ConvertFrom-Json
foreach ($v in $json.values) {
    if ($v.key -eq "QA_ADMIN_CORREO") { $v.value = $env:QA_ADMIN_CORREO }
    if ($v.key -eq "QA_ADMIN_CONTRASENA") { $v.value = $env:QA_ADMIN_CONTRASENA }
}
$tmp = Join-Path $env:TEMP "tc_m07_g055_env.json"
$json | ConvertTo-Json -Depth 6 | Set-Content -Path $tmp -Encoding utf8
$outDir = Join-Path $here "Resultado"
New-Item -ItemType Directory -Force -Path $outDir | Out-Null
newman run (Join-Path $here "TC-M07-G055.postman_collection.json") -e $tmp --insecure --reporters "cli" 2>&1 |
    Tee-Object -FilePath (Join-Path $outDir "newman_cli_TC-M07-G055.txt")
Remove-Item $tmp -ErrorAction SilentlyContinue
Write-Host "Informe oficial: Resultado/resultado_TC-M07-G055.html"
