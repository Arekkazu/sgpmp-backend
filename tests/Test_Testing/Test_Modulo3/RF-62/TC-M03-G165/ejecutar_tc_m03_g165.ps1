param(
    [Alias("Sufijo")]
    [string]$Suffix = ""
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

$resultadosDir = Join-Path $ScriptDir "resultados"
New-Item -ItemType Directory -Force -Path $resultadosDir | Out-Null

# Guarda de inmutabilidad: V1 y Reintento 1 no deben sobrescribirse
$V1Json = Join-Path $resultadosDir "resultado_TC-M03-G165.json"
$R1Json = Join-Path $resultadosDir "resultado_TC-M03-G165_reintento1.json"

if ([string]::IsNullOrEmpty($Suffix)) {
    Write-Error "Debe especificar -Suffix. Ejemplo: -Suffix '_reintento2'"
    exit 1
}

if (($Suffix -eq "_reintento1") -and (Test-Path $R1Json)) {
    Write-Error "Reintento 1 ya existe. Use un sufijo diferente (ej: _reintento2)."
    exit 1
}

# Si el sufijo es nuevo, verificar que V1 y R1 existan (integridad del histórico)
if (-not (Test-Path $V1Json)) {
    Write-Warning "V1 no encontrado. ¿Se ejecutó alguna vez este caso?"
}

$reportXml  = Join-Path $resultadosDir "resultado_TC-M03-G165$Suffix.xml"
$reportHtml = Join-Path $resultadosDir "resultado_TC-M03-G165$Suffix.html"
$reportJson = Join-Path $resultadosDir "resultado_TC-M03-G165$Suffix.json"

Push-Location $ScriptDir
try {
    $XmlA = Join-Path $resultadosDir "resultado_TC-M03-G165${Suffix}_A.xml"
    $HtmlA = Join-Path $resultadosDir "resultado_TC-M03-G165${Suffix}_A.html"
    $LogA = Join-Path $EvidenciasDir "console${Suffix}_A.log"

    $XmlB = Join-Path $resultadosDir "resultado_TC-M03-G165${Suffix}_B.xml"
    $HtmlB = Join-Path $resultadosDir "resultado_TC-M03-G165${Suffix}_B.html"
    $LogB = Join-Path $EvidenciasDir "console${Suffix}_B.log"

    $XmlC = Join-Path $resultadosDir "resultado_TC-M03-G165${Suffix}_C.xml"
    $HtmlC = Join-Path $resultadosDir "resultado_TC-M03-G165${Suffix}_C.html"
    $LogC = Join-Path $EvidenciasDir "console${Suffix}_C.log"

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
    node consolidar-resultados.cjs --sufijo $Suffix --xmls "$XmlA,$XmlB,$XmlC"
    $exitConsolidar = $LASTEXITCODE

    # Consolidar JUnit XML unificado
    if ((Test-Path $XmlA) -and (Test-Path $XmlB) -and (Test-Path $XmlC)) {
        $xmlContentA = Get-Content $XmlA -Raw
        $xmlContentB = Get-Content $XmlB -Raw
        $xmlContentC = Get-Content $XmlC -Raw
        $testcases = @()
        foreach ($content in @($xmlContentA, $xmlContentB, $xmlContentC)) {
            $matches = [regex]::Matches($content, '<testcase[\s\S]*?<\/testcase>|<testcase[^\/>]*\/>')
            foreach ($m in $matches) {
                $testcases += $m.Value
            }
        }
        $totalTests = $testcases.Count
        $totalFails = ($testcases | Where-Object { $_ -match '<failure|<error' }).Count
        $combinedXml = "<?xml version=""1.0"" encoding=""utf-8""?><testsuites name=""pytest tests""><testsuite name=""pytest"" errors=""0"" failures=""$totalFails"" skipped=""0"" tests=""$totalTests"">$($testcases -join '')</testsuite></testsuites>"
        [System.IO.File]::WriteAllText($reportXml, $combinedXml, [System.Text.Encoding]::UTF8)
        Write-Host "Generado XML: $reportXml"
    }

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
