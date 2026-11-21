$ErrorActionPreference = "Stop"
Set-Location "c:\Users\Juansegutt\Integrador\sgpmp-backend"
$env:PYTHONPATH = "."
$env:TEST_BASE_URL = "https://www.api.inmero.co/api-sgpmp-test"
$env:ENABLE_TEST_SANDBOX = "true"
$env:TEST_SANDBOX_SECRET = "377ab8a5ddc2e5b7f7fb5b58533329eb6ce7f22b99cbd6ad5ffecf3e05b7f8ff"
$env:TEST_ADMIN_EMAIL = "administador.dev@gmail.com"
if (-not $env:TEST_ADMIN_PASSWORD) {
    Write-Error "TEST_ADMIN_PASSWORD no definida en el entorno"
    exit 1
}
$env:SECRET_KEY = "test-secret-key-1234567890123456"
$inicio = Get-Date
.\.venv\Scripts\python.exe -m pytest `
  --confcutdir=tests/Test_Testing/Test_Modulo3/RF-62/TC-M03-G166 `
  tests/Test_Testing/Test_Modulo3/RF-62/TC-M03-G166/test_tc_m03_g166.py `
  -k "test_tc309_r4_clasificacion_apto" `
  -v -x --tb=short --durations=10 `
  --html=/tmp/smoke_TC-M03-G166.html --self-contained-html `
  --junitxml=/tmp/smoke_TC-M03-G166.xml
$fin = Get-Date
Write-Host "DURACION_SEG: $((New-TimeSpan -Start $inicio -End $fin).TotalSeconds)"
Write-Host "EXIT_CODE: $LASTEXITCODE"
