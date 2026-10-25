# TC-M02-G15 rev5 — solo 031. No modifica rev4 ni backend.
$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = (Resolve-Path (Join-Path $ScriptDir "..\..\..\..\..")).Path
$TestFile = Join-Path $ScriptDir "test_tc_m02_g15_rev5.py"
$CollectionFile = Join-Path $ScriptDir "tc_m02_g15_rev5.json"
$EnvironmentFile = Join-Path $ScriptDir "environment-g15-rev5.json"
$ResultadosDir = Join-Path $ScriptDir "Resultados"
$HtmlPytest = Join-Path $ResultadosDir "TC-M02-G15-rev5-pytest.html"
$TxtLog = Join-Path $ResultadosDir "TC-M02-G15-rev5-pytest.txt"
$HtmlNewman = Join-Path $ResultadosDir "TC-M02-G15-rev5-Newman.html"
$JsonNewman = Join-Path $ResultadosDir "TC-M02-G15-rev5-Newman.json"
$TxtNewman = Join-Path $ResultadosDir "TC-M02-G15-rev5-Newman.txt"
$BaseUrl = "https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test"
$IngPwd = $env:SGPMP_INGENIERO_PASSWORD
if ([string]::IsNullOrWhiteSpace($IngPwd)) { $IngPwd = $env:ENGINEER_PASSWORD }
$AdminPwd = $env:SGPMP_TEST_PASSWORD
if ([string]::IsNullOrWhiteSpace($AdminPwd)) { $AdminPwd = $env:CONTRASENA }

function Protect-Evidence([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path)) { return }
    $raw = [System.IO.File]::ReadAllText($Path)
    $raw = [regex]::Replace($raw, 'eyJ[A-Za-z0-9_\-]+=*\.[A-Za-z0-9_\-]+=*\.[A-Za-z0-9_\-+=/]*', '[REDACTED]')
    $raw = [regex]::Replace($raw, '(?i)Bearer\s+[A-Za-z0-9\-._~+/]+=*', 'Bearer [REDACTED]')
    $raw = [regex]::Replace($raw, '(?i)("contrasena"\s*:\s*")[^"]*(")', '${1}[REDACTED]${2}')
    $raw = [regex]::Replace($raw, '(?i)("token"\s*:\s*")[^"]{20,}(")', '${1}[REDACTED]${2}')
    $raw = [regex]::Replace($raw, '(?i)("value"\s*:\s*")Bearer [^"]*(")', '${1}Bearer [REDACTED]${2}')
    if ($IngPwd) { $raw = [regex]::Replace($raw, [regex]::Escape($IngPwd), '[REDACTED]') }
    if ($AdminPwd) { $raw = [regex]::Replace($raw, [regex]::Escape($AdminPwd), '[REDACTED]') }
    foreach ($name in @('SGPMP_TEST_PASSWORD','CONTRASENA','SGPMP_INGENIERO_PASSWORD','ENGINEER_PASSWORD')) {
        $p2 = [Environment]::GetEnvironmentVariable($name, 'Process')
        if ([string]::IsNullOrWhiteSpace($p2)) { $p2 = [Environment]::GetEnvironmentVariable($name, 'User') }
        if ($p2) { $raw = [regex]::Replace($raw, [regex]::Escape($p2), '[REDACTED]') }
    }
    [System.IO.File]::WriteAllText($Path, $raw)
}

if ([string]::IsNullOrWhiteSpace($IngPwd)) { throw "BLOQUEADO: definir SGPMP_INGENIERO_PASSWORD o ENGINEER_PASSWORD." }
if (-not (Test-Path -LiteralPath $ResultadosDir)) { New-Item -ItemType Directory -Force -Path $ResultadosDir | Out-Null }

Set-Location $RepoRoot
& python -m pytest $TestFile -v --tb=short --html=$HtmlPytest --self-contained-html *>&1 | Tee-Object -FilePath $TxtLog
$codePytest = $LASTEXITCODE

Set-Content -LiteralPath $TxtNewman -Value @"
TC-M02-G15 rev5 Newman NO ejecutado contra TEST.
Motivo: TC-M02-031 permite un solo intento de login por usuario (ingeniero, luego alt solo si 401).
El veredicto vive en pytest. Coleccion tc_m02_g15_rev5.json queda como artefacto, sin segundo login.
"@ -Encoding UTF8
Protect-Evidence $TxtNewman
Get-ChildItem -LiteralPath $ResultadosDir -File | Where-Object { $_.Name -like "*rev5*" } | ForEach-Object {
    Protect-Evidence $_.FullName
}
exit $codePytest
