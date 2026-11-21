$ErrorActionPreference = "Stop"
if (-not (Get-Command newman -ErrorAction SilentlyContinue)) {
    Write-Output "Newman no está instalado. La ejecución con evidencia la hace ejecutar_tc_m06_g115.py."
    exit 2
}
if (-not $env:QA_PRODUCTOR_CORREO -or -not $env:QA_CONTRASENA -or -not $env:QA_ID_ACTIVO) {
    Write-Output "Defina QA_PRODUCTOR_CORREO, QA_CONTRASENA y QA_ID_ACTIVO."
    exit 2
}
newman run "$PSScriptRoot\TC-M06-G115.postman_collection.json" `
    --env-var "correo_productor=$env:QA_PRODUCTOR_CORREO" `
    --env-var "contrasena=$env:QA_CONTRASENA" `
    --env-var "id_activo=$env:QA_ID_ACTIVO" `
    --reporters cli
