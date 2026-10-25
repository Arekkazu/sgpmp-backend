$ErrorActionPreference = "Stop"
$env:PYTHONIOENCODING = "utf-8"

# 1. TEST_ADMIN_PASSWORD (check existente)
if (-not $env:TEST_ADMIN_PASSWORD) {
    Write-Host "[FATAL] TEST_ADMIN_PASSWORD no esta exportada." -ForegroundColor Red
    exit 2
}

# 2. TEST_DATABASE_URL y TEST_SANDBOX_SECRET desde .env.test
$envFile = Join-Path $PSScriptRoot "..\..\..\..\..\.env.test"
if (Test-Path $envFile) {
    if (-not $env:TEST_DATABASE_URL) {
        $line = Get-Content $envFile | Where-Object { $_ -match '^TEST_DATABASE_URL=' } | Select-Object -First 1
        if ($line) {
            $env:TEST_DATABASE_URL = ($line -replace '^TEST_DATABASE_URL=', '').Trim()
            Write-Host "[INFO] TEST_DATABASE_URL cargado desde .env.test"
        }
    }
    if (-not $env:TEST_SANDBOX_SECRET) {
        $secLine = Get-Content $envFile | Where-Object { $_ -match '^TEST_SANDBOX_SECRET=' } | Select-Object -First 1
        if ($secLine) {
            $env:TEST_SANDBOX_SECRET = ($secLine -replace '^TEST_SANDBOX_SECRET=', '').Trim()
        }
    }
}

if (-not $env:TEST_SANDBOX_SECRET) {
    $env:TEST_SANDBOX_SECRET = "377ab8a5ddc2e5b7f7fb5b58533329eb6ce7f22b99cbd6ad5ffecf3e05b7f8ff"
}

if (-not $env:TEST_DATABASE_URL) {
    Write-Host "[FATAL] TEST_DATABASE_URL no esta exportada y no se encontro en .env.test." -ForegroundColor Red
    Write-Host "        Exportala manualmente o verifica el archivo .env.test" -ForegroundColor Red
    exit 2
}

if ($env:TEST_DATABASE_URL -match '^sqlite:') {
    Write-Host "[FATAL] TEST_DATABASE_URL apunta a SQLite. Debe apuntar a Postgres TEST." -ForegroundColor Red
    exit 3
}

# Mostrar URL con password enmascarado
$urlSafe = $env:TEST_DATABASE_URL -replace ':[^:@/]+@', ':****@'
Write-Host ("[INFO] TEST_DATABASE_URL = " + $urlSafe)

# 3. Ejecutar pytest
$TC_NAME = "TC-M03-G191"
$RESULTS_DIR = Join-Path $PSScriptRoot "resultados"
if (-not (Test-Path $RESULTS_DIR)) { New-Item -ItemType Directory -Path $RESULTS_DIR | Out-Null }

$HTML_OUT = Join-Path $RESULTS_DIR ("resultado_" + $TC_NAME + ".html")
$XML_OUT  = Join-Path $RESULTS_DIR ("resultado_" + $TC_NAME + ".xml")
$JSON_OUT = Join-Path $RESULTS_DIR ("resultado_" + $TC_NAME + ".json")

Write-Host "=========================================================="
Write-Host (" Ejecutando " + $TC_NAME + " (Pytest + Postgres TEST)")
Write-Host "=========================================================="

$t0 = Get-Date

& ".\.venv\Scripts\python.exe" -m pytest `
    (Join-Path $PSScriptRoot "test_tc_m03_g191.py") `
    --html=$HTML_OUT `
    --self-contained-html `
    --junitxml=$XML_OUT `
    -v

$EXIT_PYTEST = $LASTEXITCODE
$t1 = Get-Date
$dur = [math]::Round(($t1 - $t0).TotalSeconds, 2)

Write-Host "=========================================================="
Write-Host (" Pytest termino en " + $dur + " s con exit_code=" + $EXIT_PYTEST)
Write-Host "=========================================================="

$CJS = Join-Path $PSScriptRoot "generar_json_resultado.cjs"
if (Test-Path $CJS) {
    node $CJS $XML_OUT $JSON_OUT $TC_NAME
}

exit $EXIT_PYTEST
