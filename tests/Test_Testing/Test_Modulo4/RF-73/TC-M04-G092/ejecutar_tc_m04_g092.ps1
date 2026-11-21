# ejecutar_tc_m04_g092.ps1 - Runner Pytest para TC-M04-G092
# Uso:
#   powershell -File tests\Test_Testing\Test_Modulo4\RF-73\TC-M04-G092\ejecutar_tc_m04_g092.ps1
#   powershell -File tests\Test_Testing\Test_Modulo4\RF-73\TC-M04-G092\ejecutar_tc_m04_g092.ps1 -Suffix "_reintento2"
param(
    [string]$Suffix = ""
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not $ScriptDir) {
    $ScriptDir = (Get-Location).Path
}
$RepoRoot = (Resolve-Path (Join-Path $ScriptDir "..\..\..\..\..")).Path
$TC = "tests\Test_Testing\Test_Modulo4\RF-73\TC-M04-G092"
$ResultDir = Join-Path $RepoRoot "$TC\resultados"

if (-not (Test-Path $ResultDir)) {
    New-Item -ItemType Directory -Path $ResultDir -Force | Out-Null
}

# Guarda V1: impedir sobreescritura accidental de la linea base V1
$V1Json = Join-Path $ResultDir "resultado_TC-M04-G092.json"
if ([string]::IsNullOrEmpty($Suffix) -and (Test-Path $V1Json)) {
    Write-Host "ERROR: V1 existente ($V1Json). Use -Suffix '_reintentoN'." -ForegroundColor Yellow
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

$JunitXml = Join-Path $ResultDir "_raw_pytest$Suffix.xml"
$HtmlReport = Join-Path $ResultDir "resultado_TC-M04-G092$Suffix.html"
$FinalJson = Join-Path $ResultDir "resultado_TC-M04-G092$Suffix.json"

Push-Location $RepoRoot
try {
    .\.venv\Scripts\pytest.exe $TC -v --junitxml="$JunitXml" --html="$HtmlReport" --self-contained-html --tb=short
    $ExitPytest = $LASTEXITCODE
}
finally {
    Pop-Location
}

$ConsolidadorPy = Join-Path $ScriptDir "consolidar_resultados.py"
.\.venv\Scripts\python.exe $ConsolidadorPy $JunitXml $FinalJson

Write-Host ""
Write-Host "=== RESUMEN TC-M04-G092 ===" -ForegroundColor Cyan
if (Test-Path $FinalJson) {
    Get-Content $FinalJson | ConvertFrom-Json | ConvertTo-Json -Depth 5
}
Write-Host "EXIT_PYTEST=$ExitPytest"
Write-Host "RESULT_JSON=$FinalJson"
Write-Host "RESULT_HTML=$HtmlReport"

# Propagar exit code de pytest
exit $ExitPytest
