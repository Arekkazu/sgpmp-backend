# TC-M02-G15 rev4 — reevaluacion completa TEST. No modifica rev2/rev3 ni historico.
# Password via SGPMP_TEST_PASSWORD o CONTRASENA.

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = (Resolve-Path (Join-Path $ScriptDir "..\..\..\..\..")).Path
$TestFile = Join-Path $ScriptDir "test_tc_m02_g15_rev4.py"
$CollectionFile = Join-Path $ScriptDir "tc_m02_g15_rev4.json"
$EnvironmentFile = Join-Path $ScriptDir "environment-g15-rev4.json"
$ResultadosDir = Join-Path $ScriptDir "Resultados"
$HtmlPytest = Join-Path $ResultadosDir "TC-M02-G15-rev4-pytest.html"
$TxtLog = Join-Path $ResultadosDir "TC-M02-G15-rev4-pytest.txt"
$HtmlNewman = Join-Path $ResultadosDir "TC-M02-G15-rev4-Newman.html"
$JsonNewman = Join-Path $ResultadosDir "TC-M02-G15-rev4-Newman.json"
$TxtNewman = Join-Path $ResultadosDir "TC-M02-G15-rev4-Newman.txt"
$BaseUrl = "https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test"
$Pwd = $env:SGPMP_TEST_PASSWORD
if ([string]::IsNullOrWhiteSpace($Pwd)) { $Pwd = $env:CONTRASENA }

function Protect-Evidence([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path)) { return }
    $raw = [System.IO.File]::ReadAllText($Path)
    $raw = [regex]::Replace($raw, 'eyJ[A-Za-z0-9_\-]+=*\.[A-Za-z0-9_\-]+=*\.[A-Za-z0-9_\-+=/]*', '[REDACTED]')
    $raw = [regex]::Replace($raw, '(?i)Bearer\s+[A-Za-z0-9\-._~+/]+=*', 'Bearer [REDACTED]')
    $raw = [regex]::Replace($raw, '(?i)("contrasena"\s*:\s*")[^"]*(")', '${1}[REDACTED]${2}')
    $raw = [regex]::Replace($raw, '(?i)("token"\s*:\s*")[^"]{20,}(")', '${1}[REDACTED]${2}')
    $raw = [regex]::Replace($raw, '(?i)("value"\s*:\s*")Bearer [^"]*(")', '${1}Bearer [REDACTED]${2}')
    $raw = [regex]::Replace($raw, '(?i)refresh_token=[^;\s"]+', 'refresh_token=[REDACTED]')
    if ($Pwd) { $raw = [regex]::Replace($raw, [regex]::Escape($Pwd), '[REDACTED]') }
    foreach ($name in @('SGPMP_TEST_PASSWORD','CONTRASENA','SGPMP_INGENIERO_PASSWORD','ENGINEER_PASSWORD')) {
        $p2 = [Environment]::GetEnvironmentVariable($name, 'Process')
        if ([string]::IsNullOrWhiteSpace($p2)) { $p2 = [Environment]::GetEnvironmentVariable($name, 'User') }
        if ($p2) { $raw = [regex]::Replace($raw, [regex]::Escape($p2), '[REDACTED]') }
    }
    [System.IO.File]::WriteAllText($Path, $raw)
}

if ([string]::IsNullOrWhiteSpace($Pwd)) { throw "BLOQUEADO: definir SGPMP_TEST_PASSWORD o CONTRASENA." }
if (-not (Test-Path -LiteralPath $ResultadosDir)) { New-Item -ItemType Directory -Force -Path $ResultadosDir | Out-Null }

Set-Location $RepoRoot
& python -m pytest $TestFile -v --tb=short --html=$HtmlPytest --self-contained-html *>&1 | Tee-Object -FilePath $TxtLog
$codePytest = $LASTEXITCODE

Get-ChildItem -LiteralPath $ResultadosDir -File | Where-Object { $_.Name -like "*rev4*" } | ForEach-Object {
    Protect-Evidence $_.FullName
}

if ((Get-Command newman -ErrorAction SilentlyContinue) -and (Test-Path -LiteralPath $CollectionFile)) {
    Set-Content -LiteralPath $TxtNewman -Value "TC-M02-G15 rev4 Newman GET-only (sin PATCH BOLA repetido)." -Encoding UTF8
    & newman run $CollectionFile -e $EnvironmentFile --env-var "base_url=$BaseUrl" --env-var "contrasena=$Pwd" --insecure --reporters "cli,htmlextra,json" --reporter-htmlextra-export $HtmlNewman --reporter-json-export $JsonNewman
    Add-Content -LiteralPath $TxtNewman -Value "Newman exit: $LASTEXITCODE" -Encoding UTF8
    Protect-Evidence $HtmlNewman
    Protect-Evidence $JsonNewman
    Protect-Evidence $TxtNewman
}

Protect-Evidence $TxtLog
Protect-Evidence $HtmlPytest
exit $codePytest
