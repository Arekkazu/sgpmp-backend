# ejecutar_tc_m04_g087.ps1 - Runner Pytest para TC-M04-G087
param(
    [string]$Suffix = ""
)

$ErrorActionPreference = "Stop"

$RepoRoot  = "c:\Users\Juansegutt\Integrador\sgpmp-backend"
$TC        = "tests\Test_Testing\Test_Modulo4\RF-73\TC-M04-G087"
$ResultDir = Join-Path $RepoRoot "$TC\resultados"

# Guarda de protección V1 (R5 / RN-R05-EXT)
$V1Json = Join-Path $ResultDir "resultado_TC-M04-G087.json"
if ([string]::IsNullOrEmpty($Suffix) -and (Test-Path $V1Json)) {
    Write-Host "V1 existente. Use -Suffix '_reintentoN'." -ForegroundColor Yellow
    exit 1
}

# Cargar .env.test
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

$TestDb = $env:TEST_DATABASE_URL
if (-not $TestDb -or -not $TestDb.StartsWith("postgresql://")) {
    Write-Host "ERROR: TEST_DATABASE_URL debe empezar con postgresql:// (recibido: '$TestDb')" -ForegroundColor Red
    exit 2
}

$env:PYTHONPATH = "."

if (-not (Test-Path $ResultDir)) {
    New-Item -ItemType Directory -Path $ResultDir -Force | Out-Null
}

$JunitXml = Join-Path $ResultDir "_raw_pytest$Suffix.xml"
$HtmlReport = Join-Path $ResultDir "resultado_TC-M04-G087$Suffix.html"
Push-Location $RepoRoot
try {
    .\.venv\Scripts\pytest.exe $TC -v --junitxml="$JunitXml" --html="$HtmlReport" --self-contained-html --tb=short
    $ExitPytest = $LASTEXITCODE
}
finally {
    Pop-Location
}

$FinalJson = Join-Path $ResultDir "resultado_TC-M04-G087$Suffix.json"
.\.venv\Scripts\python.exe (Join-Path $RepoRoot "$TC\consolidar_resultados.py") $JunitXml $FinalJson

Write-Host ""
Write-Host "=== RESUMEN TC-M04-G087 ===" -ForegroundColor Cyan
if (Test-Path $FinalJson) {
    Get-Content $FinalJson | ConvertFrom-Json | ConvertTo-Json -Depth 5
}
Write-Host "EXIT_PYTEST=$ExitPytest"
Write-Host "RESULT_JSON=$FinalJson"

# FIX OBS-M04-G086-02: propagar exit code de pytest
exit $ExitPytest
