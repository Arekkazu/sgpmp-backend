# TC-M02-G15 rev2 — RF-33 / RF-34. Segunda evaluacion. No modifica el historico.
# Password via SGPMP_TEST_PASSWORD o CONTRASENA.

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = (Resolve-Path (Join-Path $ScriptDir "..\..\..\..\..")).Path
$TestFile = Join-Path $ScriptDir "test_tc_m02_g15_rev2.py"
$ResultadosDir = Join-Path $ScriptDir "Resultados"
$HtmlPytest = Join-Path $ResultadosDir "TC-M02-G15-rev2-pytest.html"
$TxtLog = Join-Path $ResultadosDir "TC-M02-G15-rev2-pytest.txt"

if (-not (Test-Path -LiteralPath $ResultadosDir)) {
    New-Item -ItemType Directory -Force -Path $ResultadosDir | Out-Null
}

if ([string]::IsNullOrWhiteSpace($env:SGPMP_TEST_PASSWORD) -and [string]::IsNullOrWhiteSpace($env:CONTRASENA)) {
    throw "BLOQUEADO: definir SGPMP_TEST_PASSWORD o CONTRASENA."
}

Set-Location $RepoRoot
$argsPytest = @(
    $TestFile,
    "-v",
    "--tb=short",
    "--html=$HtmlPytest",
    "--self-contained-html"
)

& python -m pytest @argsPytest *>&1 | Tee-Object -FilePath $TxtLog
$code = $LASTEXITCODE

function Protect-Evidence([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path)) { return }
    $raw = [System.IO.File]::ReadAllText($Path)
    $raw = [regex]::Replace($raw, 'eyJ[A-Za-z0-9_\-]+=*\.[A-Za-z0-9_\-]+=*\.[A-Za-z0-9_\-+=/]*', '[REDACTED]')
    $raw = [regex]::Replace($raw, '(?i)Bearer\s+[A-Za-z0-9\-._~+/]+=*', 'Bearer [REDACTED]')
    $pwd = $env:SGPMP_TEST_PASSWORD
    if ([string]::IsNullOrWhiteSpace($pwd)) { $pwd = $env:CONTRASENA }
    if ($pwd) {
        $raw = [regex]::Replace($raw, [regex]::Escape($pwd), '[REDACTED]')
    }
    [System.IO.File]::WriteAllText($Path, $raw)
}

Get-ChildItem -LiteralPath $ResultadosDir -File | ForEach-Object {
    if ($_.Name -notlike "TC-M02-G15-Newman*") {
        Protect-Evidence $_.FullName
    }
}

exit $code
