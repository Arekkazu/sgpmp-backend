# TC-M02-G16 rev2. No modifica rev1 ni backend.
$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = (Resolve-Path (Join-Path $ScriptDir "..\..\..\..\..")).Path
$TestFile = Join-Path $ScriptDir "test_tc_m02_g16_rev2.py"
$CollectionFile = Join-Path $ScriptDir "tc_m02_g16_rev2.json"
$EnvironmentFile = Join-Path $ScriptDir "environment-g16-rev2.json"
$ResultadosDir = Join-Path $ScriptDir "Resultados"
$HtmlPytest = Join-Path $ResultadosDir "TC-M02-G16-rev2-pytest.html"
$TxtLog = Join-Path $ResultadosDir "TC-M02-G16-rev2-pytest.txt"
$HtmlNewman = Join-Path $ResultadosDir "TC-M02-G16-rev2-Newman.html"
$JsonNewman = Join-Path $ResultadosDir "TC-M02-G16-rev2-Newman.json"
$K6Note = Join-Path $ResultadosDir "TC-M02-G16-rev2-k6-omitido.txt"
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
    if ($Pwd) { $raw = [regex]::Replace($raw, [regex]::Escape($Pwd), '[REDACTED]') }
    [System.IO.File]::WriteAllText($Path, $raw)
}

if ([string]::IsNullOrWhiteSpace($Pwd)) { throw "BLOQUEADO: SGPMP_TEST_PASSWORD o CONTRASENA." }
if (-not (Test-Path -LiteralPath $ResultadosDir)) { New-Item -ItemType Directory -Force -Path $ResultadosDir | Out-Null }

Set-Location $RepoRoot
& python -m pytest $TestFile -v --tb=short --html=$HtmlPytest --self-contained-html *>&1 | Tee-Object -FilePath $TxtLog
$codePytest = $LASTEXITCODE

# No se lanza k6 aqui: duplicaria 101 altas. Script k6 rev2 queda como artefacto.
"k6 no ejecutado (no en PATH o se evita doble rafaga). 032 = pytest 101 POST validos + PATCH /estado." |
    Set-Content -LiteralPath $K6Note -Encoding utf8

if ((Get-Command newman -ErrorAction SilentlyContinue) -and (Test-Path -LiteralPath $CollectionFile)) {
    & newman run $CollectionFile -e $EnvironmentFile --env-var "base_url=$BaseUrl" --env-var "contrasena=$Pwd" --insecure --reporters "cli,htmlextra,json" --reporter-htmlextra-export $HtmlNewman --reporter-json-export $JsonNewman
    Protect-Evidence $HtmlNewman
    Protect-Evidence $JsonNewman
}

Get-ChildItem -LiteralPath $ResultadosDir -File | Where-Object { $_.Name -like "*rev2*" } | ForEach-Object {
    Protect-Evidence $_.FullName
}
exit $codePytest
