param(
    [Alias("Sufijo")]
    [string]$Suffix = ""
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
if ([string]::IsNullOrEmpty($ScriptDir)) {
    $ScriptDir = $PSScriptRoot
}

$repoRoot = (Resolve-Path (Join-Path $ScriptDir "../../../../..")).Path
[System.Environment]::SetEnvironmentVariable("PYTHONPATH", $repoRoot, "Process")

# Cargar variables de .env.test si existe
$EnvFile = Join-Path $repoRoot ".env.test"
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

$VenvPython = Join-Path $repoRoot ".venv/Scripts/python.exe"
$PythonExe = if (Test-Path $VenvPython) { $VenvPython } else { "python" }

$resultadosDir = Join-Path $ScriptDir "resultados"
New-Item -ItemType Directory -Force -Path $resultadosDir | Out-Null

# Guardas de inmutabilidad
$V1Json = Join-Path $resultadosDir "resultado_TC-M03-G166.json"
$R1Json = Join-Path $resultadosDir "resultado_TC-M03-G166_reintento1.json"

if ([string]::IsNullOrEmpty($Suffix)) {
    Write-Error "Debe especificar -Suffix. Ejemplo: -Suffix '_reintento2'"
    exit 1
}

if (($Suffix -eq "_reintento1") -and (Test-Path $R1Json)) {
    Write-Error "Reintento 1 ya existe. Use un sufijo diferente."
    exit 1
}

# Archivos de salida parametrizados
$reportXml  = Join-Path $resultadosDir "resultado_TC-M03-G166$Suffix.xml"
$reportHtml = Join-Path $resultadosDir "resultado_TC-M03-G166$Suffix.html"
$reportJson = Join-Path $resultadosDir "resultado_TC-M03-G166$Suffix.json"

# Ejecución Pytest
Push-Location $ScriptDir
try {
    & $PythonExe -m pytest `
        --confcutdir="$ScriptDir" `
        "test_tc_m03_g166.py" `
        -p no:cov `
        -v --tb=short `
        "--junitxml=$reportXml" `
        "--html=$reportHtml" `
        --self-contained-html

    $exitPytest = $LASTEXITCODE

    # Generar JSON desde el XML con el conversor parametrizado
    & $PythonExe "generar_json_resultado.py" --suffix "$Suffix"
    $exitConversor = $LASTEXITCODE

    if ($exitConversor -ne 0) {
        exit $exitConversor
    }
    if ($exitPytest -ne 0) {
        exit $exitPytest
    }
    exit 0
} finally {
    Pop-Location
}

