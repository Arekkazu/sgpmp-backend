# TC-M03-G36 — RF-55.1. No modifica src/. No Newman (no hay endpoint de clasificacion Edge).
$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = (Resolve-Path (Join-Path $ScriptDir "..\..\..\..\..")).Path
$TestFile = Join-Path $ScriptDir "test_tc_m03_g36.py"
$ResultadosDir = Join-Path $ScriptDir "Resultados"
$HtmlPytest = Join-Path $ResultadosDir "TC-M03-G36-pytest.html"
$TxtLog = Join-Path $ResultadosDir "TC-M03-G36-pytest.txt"

if (-not (Test-Path -LiteralPath $ResultadosDir)) {
    New-Item -ItemType Directory -Force -Path $ResultadosDir | Out-Null
}

Set-Location $RepoRoot
$env:PYTHONPATH = $RepoRoot
& python -m pytest $TestFile -v --tb=short --html=$HtmlPytest --self-contained-html *>&1 | Tee-Object -FilePath $TxtLog
$codePytest = $LASTEXITCODE
exit $codePytest
