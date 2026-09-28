# TC-M09-175 rev1 TEST. No sobrescribe G91 historico ni 173-174 rev1.
# Password 175: SGPMP_175_PASSWORD. Admin GET global: SGPMP_TEST_PASSWORD o CONTRASENA.

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$CollectionFile = Join-Path $ScriptDir "tc_m09_175_rev1.json"
$EnvironmentFile = Join-Path $ScriptDir "environment-175-rev1.json"
$ResultadosDir = Join-Path $ScriptDir "Resultados"
$HtmlReport = Join-Path $ResultadosDir "TC-M09-175-rev1-evidencia.html"
$JsonReport = Join-Path $ResultadosDir "TC-M09-175-rev1.json"
$TxtReport = Join-Path $ResultadosDir "TC-M09-175-rev1.txt"
$BaseUrl = "https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test"
$Correo175 = "cm09175.qa@sgpmp-test.com"
$Pwd175 = $env:SGPMP_175_PASSWORD
$CorreoAdmin = "admin@pecuaria.co"
$PwdAdmin = $env:SGPMP_TEST_PASSWORD
if ([string]::IsNullOrWhiteSpace($PwdAdmin)) { $PwdAdmin = $env:CONTRASENA }

function Write-Log([string]$Message) {
    Write-Host $Message
    Add-Content -LiteralPath $TxtReport -Value $Message -Encoding UTF8
}

function Protect-Evidence([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path)) { return }
    $raw = [System.IO.File]::ReadAllText($Path)
    $raw = [regex]::Replace($raw, 'eyJ[A-Za-z0-9_\-]+=*\.[A-Za-z0-9_\-]+=*\.[A-Za-z0-9_\-+=/]*', '[REDACTED]')
    $raw = [regex]::Replace($raw, '(?i)Bearer\s+[A-Za-z0-9\-._~+/]+=*', 'Bearer [REDACTED]')
    $raw = [regex]::Replace($raw, '(?i)("contrasena[^"]*"\s*:\s*")[^"]*(")', '${1}[REDACTED]${2}')
    $raw = [regex]::Replace($raw, '(?i)("token"\s*:\s*")[^"]{20,}(")', '${1}[REDACTED]${2}')
    $raw = [regex]::Replace($raw, '(?i)("value"\s*:\s*")Bearer [^"]*(")', '${1}Bearer [REDACTED]${2}')
    $raw = [regex]::Replace($raw, '(?i)refresh_token=[^;\s"]+', 'refresh_token=[REDACTED]')
    $raw = [regex]::Replace($raw, '(?i)refresh_token&#x3D;[^;<"\s]+', 'refresh_token&#x3D;[REDACTED]')
    foreach ($secret in @($Pwd175, $PwdAdmin)) {
        if ($secret) { $raw = [regex]::Replace($raw, [regex]::Escape($secret), '[REDACTED]') }
    }
    [System.IO.File]::WriteAllText($Path, $raw)
}

if (-not (Get-Command newman -ErrorAction SilentlyContinue)) { throw "Newman no esta en PATH." }
if ([string]::IsNullOrWhiteSpace($Pwd175)) { throw "BLOQUEADO: definir SGPMP_175_PASSWORD." }
if ([string]::IsNullOrWhiteSpace($PwdAdmin)) { throw "BLOQUEADO: definir SGPMP_TEST_PASSWORD o CONTRASENA para GET global admin." }
if (-not (Test-Path -LiteralPath $ResultadosDir)) { New-Item -ItemType Directory -Force -Path $ResultadosDir | Out-Null }

Set-Content -LiteralPath $TxtReport -Value "" -Encoding UTF8
Write-Log "TC-M09-175 rev1 TEST RF-27"
Write-Log "Coleccion: $CollectionFile"
Write-Log "Fecha UTC: $([DateTime]::UtcNow.ToString('o'))"
Write-Log "Ambiente: $BaseUrl"
Write-Log "Usuario 175: $Correo175 (id esperado 120). Password via env."
Write-Log "No PATCH. No DELETE. No DML."
Write-Log ""

& newman run $CollectionFile -e $EnvironmentFile --env-var "base_url=$BaseUrl" --env-var "correo_175=$Correo175" --env-var "contrasena_175=$Pwd175" --env-var "correo_admin=$CorreoAdmin" --env-var "contrasena_admin=$PwdAdmin" --insecure --reporters "cli,htmlextra,json" --reporter-htmlextra-export $HtmlReport --reporter-json-export $JsonReport
$code = $LASTEXITCODE
Protect-Evidence $HtmlReport
Protect-Evidence $JsonReport
Write-Log "Newman exit code: $code"
Write-Log "HTML: $HtmlReport"
Write-Log "JSON: $JsonReport"
Protect-Evidence $TxtReport
exit $code
