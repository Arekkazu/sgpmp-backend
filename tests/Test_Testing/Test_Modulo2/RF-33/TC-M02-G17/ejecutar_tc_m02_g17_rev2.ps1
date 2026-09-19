# TC-M02-G17 rev2 RF-33/RF-16. Segunda evaluacion TEST. No modifica historico.
# Password via SGPMP_TEST_PASSWORD o CONTRASENA.

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$CollectionFile = Join-Path $ScriptDir "tc_m02_g17_rev2.json"
$EnvironmentFile = Join-Path $ScriptDir "environment-g17-rev2.json"
$ResultadosDir = Join-Path $ScriptDir "Resultados"
$HtmlReport = Join-Path $ResultadosDir "TC-M02-G17-rev2-Newman.html"
$JsonReport = Join-Path $ResultadosDir "TC-M02-G17-rev2.json"
$TxtReport = Join-Path $ResultadosDir "TC-M02-G17-rev2-ejecucion.txt"
$BaseUrl = "https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test"
$Correo = "admin@pecuaria.co"
$Pwd = $env:SGPMP_TEST_PASSWORD
if ([string]::IsNullOrWhiteSpace($Pwd)) { $Pwd = $env:CONTRASENA }

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
    $raw = [regex]::Replace($raw, '(?i)("token"\s*:\s*")[^"]{8,}(")', '${1}[REDACTED]${2}')
    $raw = [regex]::Replace($raw, '(?i)("value"\s*:\s*")Bearer [^"]*(")', '${1}Bearer [REDACTED]${2}')
    if ($Pwd) { $raw = [regex]::Replace($raw, [regex]::Escape($Pwd), '[REDACTED]') }
    [System.IO.File]::WriteAllText($Path, $raw)
}

if (-not (Get-Command newman -ErrorAction SilentlyContinue)) { throw "Newman no esta en PATH." }
if ([string]::IsNullOrWhiteSpace($Pwd)) { throw "BLOQUEADO: definir SGPMP_TEST_PASSWORD o CONTRASENA." }
if (-not (Test-Path -LiteralPath $ResultadosDir)) { New-Item -ItemType Directory -Force -Path $ResultadosDir | Out-Null }

Set-Content -LiteralPath $TxtReport -Value "" -Encoding UTF8
Write-Log "TC-M02-G17 rev2 RF-33 / RF-16 TEST - INC-M02-47-G17"
Write-Log "Coleccion: $CollectionFile"
Write-Log "Fecha UTC: $([DateTime]::UtcNow.ToString('o'))"
Write-Log "Historico: solo .gitkeep en esta carpeta; Newman v1 no esta en el workspace."
Write-Log "No se modifica RF-16 ni codigo productivo."
Write-Log ""

& newman run $CollectionFile -e $EnvironmentFile --env-var "base_url=$BaseUrl" --env-var "correo=$Correo" --env-var "contrasena=$Pwd" --insecure --reporters "cli,htmlextra,json" --reporter-htmlextra-export $HtmlReport --reporter-json-export $JsonReport --color off
$code = $LASTEXITCODE
Protect-Evidence $HtmlReport
Protect-Evidence $JsonReport
Write-Log "Newman exit code: $code"
Write-Log "HTML: $HtmlReport"
Write-Log "JSON: $JsonReport"
Protect-Evidence $TxtReport
exit $code
