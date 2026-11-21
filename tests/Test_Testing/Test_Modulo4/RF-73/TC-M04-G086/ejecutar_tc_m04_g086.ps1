# ejecutar_tc_m04_g086.ps1 - Runner Pytest para TC-M04-G086
param(
    [string]$Suffix = ""
)

$ErrorActionPreference = "Stop"

$RepoRoot = "c:\Users\Juansegutt\Integrador\sgpmp-backend"
$TC       = "tests\Test_Testing\Test_Modulo4\RF-73\TC-M04-G086"
$ResultDir = Join-Path $RepoRoot "$TC\resultados"

# 0. Guarda de protección para V1 (D-08 / RN-R05-EXT)
$V1Json = Join-Path $ResultDir "resultado_TC-M04-G086.json"
if ([string]::IsNullOrEmpty($Suffix) -and (Test-Path $V1Json)) {
    Write-Host "ADVERTENCIA: $V1Json (V1) ya existe. Para no sobreescribir V1 en reintentos, use -Suffix '_reintento1'." -ForegroundColor Yellow
    Write-Host "Ejecución cancelada para proteger V1. Pase -Suffix explícitamente." -ForegroundColor Red
    exit 1
}

# 1. Cargar .env.test
$EnvFile = Join-Path $RepoRoot ".env.test"
if (Test-Path $EnvFile) {
    Get-Content $EnvFile | ForEach-Object {
        if ($_ -match '^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.+)$') {
            $name  = $matches[1]
            $value = $matches[2].Trim('"').Trim("'")
            [Environment]::SetEnvironmentVariable($name, $value, "Process")
        }
    }
}

# 2. Validar TEST_DATABASE_URL
$TestDb = $env:TEST_DATABASE_URL
if (-not $TestDb -or -not $TestDb.StartsWith("postgresql://")) {
    Write-Host "ERROR: TEST_DATABASE_URL debe empezar con postgresql:// (recibido: '$TestDb')" -ForegroundColor Red
    exit 2
}

# 3. PYTHONPATH
$env:PYTHONPATH = "."

# 4. Result dir
if (-not (Test-Path $ResultDir)) {
    New-Item -ItemType Directory -Path $ResultDir -Force | Out-Null
}

# 5. pytest con junit
$JunitXml = Join-Path $ResultDir "_raw_pytest$Suffix.xml"
Push-Location $RepoRoot
try {
    .\.venv\Scripts\pytest.exe $TC -v --junitxml="$JunitXml" --tb=short
    $ExitPytest = $LASTEXITCODE
}
finally {
    Pop-Location
}

# 6. Consolidar
$FinalJson = Join-Path $ResultDir "resultado_TC-M04-G086$Suffix.json"
.\.venv\Scripts\python.exe (Join-Path $RepoRoot "$TC\consolidar_resultados.py") $JunitXml $FinalJson

# 7. Reporte
Write-Host ""
Write-Host "=== RESUMEN TC-M04-G086 ===" -ForegroundColor Cyan
if (Test-Path $FinalJson) {
    Get-Content $FinalJson | ConvertFrom-Json | ConvertTo-Json -Depth 5
}
Write-Host "EXIT_PYTEST=$ExitPytest"
Write-Host "RESULT_JSON=$FinalJson"
exit 0
