# TC-M02-G16 — primera evaluacion RF-33 TEST.
# Password via SGPMP_TEST_PASSWORD o CONTRASENA. No modifica backend ni otros casos.

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = (Resolve-Path (Join-Path $ScriptDir "..\..\..\..\..")).Path
$TestFile = Join-Path $ScriptDir "test_tc_m02_g16.py"
$K6File = Join-Path $ScriptDir "tc_m02_g16_rate_limit.js"
$ResultadosDir = Join-Path $ScriptDir "Resultados"
$HtmlPytest = Join-Path $ResultadosDir "TC-M02-G16-pytest.html"
$TxtLog = Join-Path $ResultadosDir "TC-M02-G16-pytest.txt"
$K6Out = Join-Path $ResultadosDir "TC-M02-G16-k6.json"

if (-not (Test-Path -LiteralPath $ResultadosDir)) {
    New-Item -ItemType Directory -Force -Path $ResultadosDir | Out-Null
}
if ([string]::IsNullOrWhiteSpace($env:SGPMP_TEST_PASSWORD) -and [string]::IsNullOrWhiteSpace($env:CONTRASENA)) {
    throw "BLOQUEADO: definir SGPMP_TEST_PASSWORD o CONTRASENA."
}

Set-Location $RepoRoot
& python -m pytest $TestFile -v --tb=short --html=$HtmlPytest --self-contained-html *>&1 | Tee-Object -FilePath $TxtLog
$code = $LASTEXITCODE

$k6 = Get-Command k6 -ErrorAction SilentlyContinue
if ($k6) {
    $tokenHint = "usar SGPMP_TEST_PASSWORD dentro de k6; no se imprime"
    & k6 run --insecure-skip-tls-verify --summary-export=$K6Out $K6File
} else {
    "k6 NO INSTALADO. TC-M02-032 se cubrio con rafaga controlada en pytest (101 POST invalidos). ZAP no ejecutado." |
        Set-Content -LiteralPath (Join-Path $ResultadosDir "TC-M02-G16-k6-omitido.txt") -Encoding utf8
}

function Protect-Evidence([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path)) { return }
    $raw = [System.IO.File]::ReadAllText($Path)
    $raw = [regex]::Replace($raw, 'eyJ[A-Za-z0-9_\-]+=*\.[A-Za-z0-9_\-]+=*\.[A-Za-z0-9_\-+=/]*', '[REDACTED]')
    $raw = [regex]::Replace($raw, '(?i)Bearer\s+[A-Za-z0-9\-._~+/]+=*', 'Bearer [REDACTED]')
    foreach ($name in @('SGPMP_TEST_PASSWORD','CONTRASENA')) {
        $pwd = [Environment]::GetEnvironmentVariable($name, 'Process')
        if ([string]::IsNullOrWhiteSpace($pwd)) {
            $pwd = [Environment]::GetEnvironmentVariable($name, 'User')
        }
        if ($pwd) { $raw = [regex]::Replace($raw, [regex]::Escape($pwd), '[REDACTED]') }
    }
    [System.IO.File]::WriteAllText($Path, $raw)
}

Get-ChildItem -LiteralPath $ResultadosDir -File | ForEach-Object { Protect-Evidence $_.FullName }
exit $code
