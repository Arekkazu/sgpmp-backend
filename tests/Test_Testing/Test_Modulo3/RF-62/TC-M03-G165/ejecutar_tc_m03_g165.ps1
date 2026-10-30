param(
    [string]$Sufijo = "_reintento1"
)

$ErrorActionPreference = "Continue"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = (Resolve-Path (Join-Path $ScriptDir "../../../../..")).Path
[System.Environment]::SetEnvironmentVariable("PYTHONPATH", $RepoRoot, "Process")

# Cargar variables de .env.test si existe
$EnvFile = Join-Path $RepoRoot ".env.test"
if (Test-Path $EnvFile) {
    Get-Content $EnvFile | ForEach-Object {
        $line = $_.Trim()
        if ($line -and -not $line.StartsWith("#") -and $line.Contains("=")) {
            $parts = $line.Split("=", 2)
            $key = $parts[0].Trim()
            $val = $parts[1].Trim()
            [System.Environment]::SetEnvironmentVariable($key, $val, "Process")
        }
    }
}

$VenvPython = Join-Path $RepoRoot ".venv/Scripts/python.exe"
$PythonExe = if (Test-Path $VenvPython) { $VenvPython } else { "python" }

$FechaHoy = Get-Date -Format "yyyyMMdd"
$EvidenciasDir = Join-Path $ScriptDir "evidencias/run-$FechaHoy"
New-Item -ItemType Directory -Force -Path $EvidenciasDir | Out-Null

Push-Location $ScriptDir
try {
    $XmlA = "resultados/resultado_TC-M03-G165${Sufijo}_A.xml"
    $HtmlA = "resultados/resultado_TC-M03-G165${Sufijo}_A.html"
    $LogA = Join-Path $EvidenciasDir "console${Sufijo}_A.log"

    $XmlB = "resultados/resultado_TC-M03-G165${Sufijo}_B.xml"
    $HtmlB = "resultados/resultado_TC-M03-G165${Sufijo}_B.html"
    $LogB = Join-Path $EvidenciasDir "console${Sufijo}_B.log"

    $XmlC = "resultados/resultado_TC-M03-G165${Sufijo}_C.xml"
    $HtmlC = "resultados/resultado_TC-M03-G165${Sufijo}_C.html"
    $LogC = Join-Path $EvidenciasDir "console${Sufijo}_C.log"

    Write-Host "=== Run A: TestEscenarioBase (17 tests) ==="
    $swA = [System.Diagnostics.Stopwatch]::StartNew()
    & $PythonExe -m pytest "test_tc_m03_g165.py::TestEscenarioBase" -v -s `
        "--junitxml=$XmlA" `
        "--html=$HtmlA" `
        --self-contained-html 2>&1 | Tee-Object -FilePath $LogA
    $exitA = $LASTEXITCODE
    $swA.Stop()
    Write-Host "RUN_A_DURATION_SEC=$([math]::Round($swA.Elapsed.TotalSeconds, 2)) EXIT=$exitA"

    Write-Host "=== Run B: TestEscenario318a + TestEscenario318b (18 tests) ==="
    $swB = [System.Diagnostics.Stopwatch]::StartNew()
    & $PythonExe -m pytest "test_tc_m03_g165.py::TestEscenario318a" "test_tc_m03_g165.py::TestEscenario318b" -v -s `
        "--junitxml=$XmlB" `
        "--html=$HtmlB" `
        --self-contained-html 2>&1 | Tee-Object -FilePath $LogB
    $exitB = $LASTEXITCODE
    $swB.Stop()
    Write-Host "RUN_B_DURATION_SEC=$([math]::Round($swB.Elapsed.TotalSeconds, 2)) EXIT=$exitB"

    Write-Host "=== Run C: TestEscenario318c + TestEscenario320 (17 tests) ==="
    $swC = [System.Diagnostics.Stopwatch]::StartNew()
    & $PythonExe -m pytest "test_tc_m03_g165.py::TestEscenario318c" "test_tc_m03_g165.py::TestEscenario320" -v -s `
        "--junitxml=$XmlC" `
        "--html=$HtmlC" `
        --self-contained-html 2>&1 | Tee-Object -FilePath $LogC
    $exitC = $LASTEXITCODE
    $swC.Stop()
    Write-Host "RUN_C_DURATION_SEC=$([math]::Round($swC.Elapsed.TotalSeconds, 2)) EXIT=$exitC"

    Write-Host "=== Consolidando 3 XMLs en un único JSON y HTML ==="
    node consolidar-resultados.cjs --sufijo $Sufijo --xmls "$XmlA,$XmlB,$XmlC"
    $exitConsolidar = $LASTEXITCODE

    # Mover parciales A/B/C a evidencias para mantener resultados/ limpio para el scanner
    foreach ($parcial in @($XmlA, $HtmlA, $XmlB, $HtmlB, $XmlC, $HtmlC)) {
        if (Test-Path $parcial) {
            Move-Item -Path $parcial -Destination $EvidenciasDir -Force
        }
    }

    if ($exitConsolidar -ne 0) {
        exit $exitConsolidar
    }
    if ($exitA -ne 0 -or $exitB -ne 0 -or $exitC -ne 0) {
        exit 1
    }
    exit 0
} finally {
    Pop-Location
}
