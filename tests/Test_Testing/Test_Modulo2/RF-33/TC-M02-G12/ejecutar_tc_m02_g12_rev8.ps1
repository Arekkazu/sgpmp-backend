# TC-M02-G12 rev8 RF-33/RF-16.
# Password: SGPMP_TEST_PASSWORD o CONTRASENA (Process, luego User, luego Machine).
# No sobrescribe rev1-rev7. No escribe secretos en el environment JSON.

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$CollectionFile = Join-Path $ScriptDir "tc_m02_g12_rev8.json"
$EnvironmentFile = Join-Path $ScriptDir "environment-g12-rev8.json"
$ResultadosDir = Join-Path $ScriptDir "Resultados"
$HtmlReport = Join-Path $ResultadosDir "TC-M02-G12-rev8-evidencia.html"
$JsonReport = Join-Path $ResultadosDir "TC-M02-G12-rev8.json"
$TxtReport = Join-Path $ResultadosDir "TC-M02-G12-rev8.txt"
$PdfReport = Join-Path $ResultadosDir "TC-M02-G12-rev8-evidencia.pdf"
$BaseUrl = "https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test"
$Correo = "admin@pecuaria.co"

function Get-QaSecret([string]$Name) {
    foreach ($scope in @('Process', 'User', 'Machine')) {
        $v = [Environment]::GetEnvironmentVariable($Name, $scope)
        if (-not [string]::IsNullOrWhiteSpace($v)) { return $v }
    }
    return $null
}

$Pwd = Get-QaSecret 'SGPMP_TEST_PASSWORD'
if ([string]::IsNullOrWhiteSpace($Pwd)) { $Pwd = Get-QaSecret 'CONTRASENA' }

function Write-Log([string]$Message) {
    Write-Host $Message
    Add-Content -LiteralPath $TxtReport -Value $Message -Encoding UTF8
}

function Protect-Evidence([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path)) { return }
    $raw = [System.IO.File]::ReadAllText($Path)
    $raw = [regex]::Replace($raw, 'eyJ[A-Za-z0-9_\-]+=*\.[A-Za-z0-9_\-]+=*\.[A-Za-z0-9_\-+=/]*', '[REDACTED]')
    $raw = [regex]::Replace($raw, '(?i)Bearer\s+[A-Za-z0-9\-._~+/]+=*', 'Bearer [REDACTED]')
    $raw = [regex]::Replace($raw, '(?i)("contrasena"\s*:\s*")[^"]*(")', '${1}[REDACTED]${2}')
    $raw = [regex]::Replace($raw, '(?i)("token"\s*:\s*")[^"]{20,}(")', '${1}[REDACTED]${2}')
    $raw = [regex]::Replace($raw, '(?i)("value"\s*:\s*")Bearer [^"]*(")', '${1}Bearer [REDACTED]${2}')
    $raw = [regex]::Replace($raw, '(?i)refresh_token=[^;\s"]+', 'refresh_token=[REDACTED]')
    $raw = [regex]::Replace($raw, '(?i)refresh_token&#x3D;[^;<"\s]+', 'refresh_token&#x3D;[REDACTED]')
    if ($Pwd) { $raw = [regex]::Replace($raw, [regex]::Escape($Pwd), '[REDACTED]') }
    [System.IO.File]::WriteAllText($Path, $raw)
}

function Export-PdfFromHtml([string]$HtmlPath, [string]$PdfPath) {
    if (-not (Test-Path -LiteralPath $HtmlPath)) { return $false }
    $browser = @(
        "$env:ProgramFiles\Google\Chrome\Application\chrome.exe",
        "${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe",
        "$env:ProgramFiles\Microsoft\Edge\Application\msedge.exe"
    ) | Where-Object { $_ -and (Test-Path -LiteralPath $_) } | Select-Object -First 1
    if (-not $browser) { return $false }
    $uri = (New-Object System.Uri((Resolve-Path -LiteralPath $HtmlPath).Path)).AbsoluteUri
    & $browser --headless --disable-gpu --no-pdf-header-footer --print-to-pdf="$PdfPath" $uri | Out-Null
    return (Test-Path -LiteralPath $PdfPath)
}

if (-not (Get-Command newman -ErrorAction SilentlyContinue)) { throw "Newman no esta en PATH." }
if ([string]::IsNullOrWhiteSpace($Pwd)) { throw "BLOQUEADO: definir SGPMP_TEST_PASSWORD o CONTRASENA (Process/User/Machine)." }
if (-not (Test-Path -LiteralPath $ResultadosDir)) { New-Item -ItemType Directory -Force -Path $ResultadosDir | Out-Null }

Set-Content -LiteralPath $TxtReport -Value "" -Encoding UTF8
Write-Log "TC-M02-G12 rev8 RF-33/RF-16 TEST"
Write-Log "Coleccion: $CollectionFile"
Write-Log "Fecha UTC: $([DateTime]::UtcNow.ToString('o'))"
Write-Log "Ambiente: $BaseUrl"
Write-Log "Usuario: $Correo (password via env, no se registra)."
Write-Log "013 no se reejecuta (APROBADO rev5). 014 solo si GET demuestra min/max 20-40."
Write-Log "No sobrescribe rev1-rev7."
Write-Log ""

$htmlextraOk = $false
try {
    $null = npm list -g newman-reporter-htmlextra 2>$null
    if ($LASTEXITCODE -eq 0) { $htmlextraOk = $true }
} catch { $htmlextraOk = $false }
if (-not $htmlextraOk) {
    Write-Log "Reporter htmlextra no instalado; se usa el reporter html nativo de Newman."
    & newman run $CollectionFile -e $EnvironmentFile --env-var "base_url=$BaseUrl" --env-var "correo=$Correo" --env-var "contrasena=$Pwd" --insecure --reporters "cli,html,json" --reporter-html-export $HtmlReport --reporter-json-export $JsonReport
} else {
    & newman run $CollectionFile -e $EnvironmentFile --env-var "base_url=$BaseUrl" --env-var "correo=$Correo" --env-var "contrasena=$Pwd" --insecure --reporters "cli,htmlextra,json" --reporter-htmlextra-export $HtmlReport --reporter-json-export $JsonReport
}
$code = $LASTEXITCODE
Protect-Evidence $HtmlReport
Protect-Evidence $JsonReport
$pdfOk = Export-PdfFromHtml $HtmlReport $PdfReport
Write-Log "Newman exit code: $code"
Write-Log "HTML: $HtmlReport"
Write-Log "JSON: $JsonReport"
Write-Log "PDF generado: $pdfOk"
if ($pdfOk) { Write-Log "PDF: $PdfReport" }
Protect-Evidence $TxtReport
exit $code
