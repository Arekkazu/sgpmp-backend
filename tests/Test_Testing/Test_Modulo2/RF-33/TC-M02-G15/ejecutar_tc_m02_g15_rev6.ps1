# TC-M02-G15 rev6 — reevaluacion completa TEST. No modifica rev1-rev5 ni producto.
# Password admin/productor: SGPMP_TEST_PASSWORD o CONTRASENA.
# Ingeniero: SGPMP_INGENIERO_PASSWORD, ENGINEER_PASSWORD o el mismo secreto TEST.

$ErrorActionPreference = "Continue"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = (Resolve-Path (Join-Path $ScriptDir "..\..\..\..\..")).Path
$TestFile = Join-Path $ScriptDir "test_tc_m02_g15_rev6.py"
$ResultadosDir = Join-Path $ScriptDir "Resultados"
$HtmlPytest = Join-Path $ResultadosDir "TC-M02-G15-rev6-pytest.html"
$TxtLog = Join-Path $ResultadosDir "TC-M02-G15-rev6-pytest.txt"
$PdfReport = Join-Path $ResultadosDir "TC-M02-G15-rev6-evidencia.pdf"
$HtmlEvid = Join-Path $ResultadosDir "TC-M02-G15-rev6-evidencia.html"
$Pwd = $env:SGPMP_TEST_PASSWORD
if ([string]::IsNullOrWhiteSpace($Pwd)) { $Pwd = $env:CONTRASENA }
$IngPwd = $env:SGPMP_INGENIERO_PASSWORD
if ([string]::IsNullOrWhiteSpace($IngPwd)) { $IngPwd = $env:ENGINEER_PASSWORD }

function Protect-Evidence([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path)) { return }
    $raw = [System.IO.File]::ReadAllText($Path)
    $raw = [regex]::Replace($raw, 'eyJ[A-Za-z0-9_\-]+=*\.[A-Za-z0-9_\-]+=*\.[A-Za-z0-9_\-+=/]*', '[REDACTED]')
    $raw = [regex]::Replace($raw, '(?i)Bearer\s+[A-Za-z0-9\-._~+/]+=*', 'Bearer [REDACTED]')
    $raw = [regex]::Replace($raw, '(?i)("contrasena"\s*:\s*")[^"]*(")', '${1}[REDACTED]${2}')
    $raw = [regex]::Replace($raw, '(?i)("token"\s*:\s*")[^"]{20,}(")', '${1}[REDACTED]${2}')
    $raw = [regex]::Replace($raw, '(?i)("value"\s*:\s*")Bearer [^"]*(")', '${1}Bearer [REDACTED]${2}')
    if ($Pwd) { $raw = [regex]::Replace($raw, [regex]::Escape($Pwd), '[REDACTED]') }
    if ($IngPwd) { $raw = [regex]::Replace($raw, [regex]::Escape($IngPwd), '[REDACTED]') }
    [System.IO.File]::WriteAllText($Path, $raw)
}

if ([string]::IsNullOrWhiteSpace($Pwd)) { throw "BLOQUEADO: definir SGPMP_TEST_PASSWORD o CONTRASENA." }
if (-not (Test-Path -LiteralPath $ResultadosDir)) { New-Item -ItemType Directory -Force -Path $ResultadosDir | Out-Null }

Set-Location $RepoRoot
& python -m pytest $TestFile -v --tb=short --noconftest --html=$HtmlPytest --self-contained-html *>&1 | Tee-Object -FilePath $TxtLog
$codePytest = $LASTEXITCODE

Get-ChildItem -LiteralPath $ResultadosDir -File | Where-Object { $_.Name -like "*rev6*" } | ForEach-Object {
    Protect-Evidence $_.FullName
}

$chrome = "$env:ProgramFiles\Google\Chrome\Application\chrome.exe"
if ((Test-Path -LiteralPath $chrome) -and (Test-Path -LiteralPath $HtmlEvid)) {
    $uri = (New-Object System.Uri((Resolve-Path -LiteralPath $HtmlEvid).Path)).AbsoluteUri
    & $chrome --headless --disable-gpu --no-pdf-header-footer --print-to-pdf="$PdfReport" $uri | Out-Null
}

exit $codePytest
