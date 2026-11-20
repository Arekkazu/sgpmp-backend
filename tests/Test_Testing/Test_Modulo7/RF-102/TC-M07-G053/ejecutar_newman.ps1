# TC-M07-G053 — runner Newman (opcional). Preferir ejecutar_tc_m07_g53.py para el informe HTML oficial.
# Requiere variables de entorno QA_ADMIN_CORREO / QA_ADMIN_CONTRASENA (no hardcodear).
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
$tmp = Join-Path $env:TEMP "tc_m07_g053_env.json"
$json | ConvertTo-Json -Depth 6 | Set-Content -Path $tmp -Encoding utf8

$outDir = Join-Path $here "Resultado"
New-Item -ItemType Directory -Force -Path $outDir | Out-Null

# --insecure: entorno TEST con cadena TLS que Node/Newman no confía en este host (Python urllib sí valida vía sistema).
newman run (Join-Path $here "TC-M07-G053.postman_collection.json") `
  -e $tmp `
  --insecure `
  --reporters "cli" `
  2>&1 | Tee-Object -FilePath (Join-Path $outDir "newman_cli_TC-M07-G053.txt")
# Nota: el informe oficial HTML lo genera ejecutar_tc_m07_g53.py; Newman es evidencia auxiliar.

Remove-Item $tmp -ErrorAction SilentlyContinue
Write-Host "Informe oficial del caso: Resultado/resultado_TC-M07-G053.html (generado por ejecutar_tc_m07_g53.py)"
