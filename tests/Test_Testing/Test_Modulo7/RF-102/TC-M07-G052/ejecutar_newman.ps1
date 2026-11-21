# TC-M07-G052 — runner Newman (opcional). Preferir ejecutar_tc_m07_g52.py para el informe HTML oficial.
# Requiere variables de entorno QA_ADMIN_CORREO / QA_ADMIN_CONTRASENA (no hardcodear).
$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$envFile = Join-Path $here "entorno.postman_environment.json"

if (-not $env:QA_ADMIN_CORREO -or -not $env:QA_ADMIN_CONTRASENA) {
    Write-Error "Defina QA_ADMIN_CORREO y QA_ADMIN_CONTRASENA antes de Newman."
}

# Inyecta solo nombres presentes; Newman lee el environment JSON (rellenar valores en memoria).
$json = Get-Content $envFile -Raw | ConvertFrom-Json
foreach ($v in $json.values) {
    if ($v.key -eq "QA_ADMIN_CORREO") { $v.value = $env:QA_ADMIN_CORREO }
    if ($v.key -eq "QA_ADMIN_CONTRASENA") { $v.value = $env:QA_ADMIN_CONTRASENA }
}
$tmp = Join-Path $env:TEMP "tc_m07_g052_env.json"
$json | ConvertTo-Json -Depth 6 | Set-Content -Path $tmp -Encoding utf8

$outDir = Join-Path $here "Resultado"
New-Item -ItemType Directory -Force -Path $outDir | Out-Null

newman run (Join-Path $here "TC-M07-G052.postman_collection.json") `
  -e $tmp `
  --reporters cli,htmlextra `
  --reporter-htmlextra-export (Join-Path $outDir "newman_TC-M07-G052.html")

Remove-Item $tmp -ErrorAction SilentlyContinue
Write-Host "Informe oficial del caso: Resultado/resultado_TC-M07-G52.html (generado por ejecutar_tc_m07_g52.py)"
