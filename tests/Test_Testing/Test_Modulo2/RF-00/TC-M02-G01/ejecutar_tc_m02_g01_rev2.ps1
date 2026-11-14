# TC-M02-G01 rev2 - segunda evaluacion QA (RF-00, Modulo 02)
# TEST. Password via $env:SGPMP_TEST_PASSWORD o $env:CONTRASENA. No se escribe en JSON.

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$CollectionFile = Join-Path $ScriptDir "tc_m02_g01_rev2.json"
$EnvironmentFile = Join-Path $ScriptDir "environment-g01-rev2.json"
$ResultadosDir = Join-Path $ScriptDir "Resultados"

$BaseUrl = "https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test"
$AdminEmail = "admin@pecuaria.co"
$AdminPassword = $env:SGPMP_TEST_PASSWORD
if ([string]::IsNullOrWhiteSpace($AdminPassword)) {
    $AdminPassword = $env:CONTRASENA
}

$HtmlReport = Join-Path $ResultadosDir "TC-M02-G01-rev2-Newman.html"
$JsonReport = Join-Path $ResultadosDir "TC-M02-G01-rev2-Newman.json"
$TxtReport = Join-Path $ResultadosDir "TC-M02-G01-rev2-ejecucion.txt"

function Write-Log([string]$Message) {
    Write-Host $Message
    Add-Content -LiteralPath $TxtReport -Value $Message -Encoding UTF8
}

function Protect-Evidence([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path)) { return }
    $raw = [System.IO.File]::ReadAllText($Path)
    $raw = [regex]::Replace($raw, 'eyJ[A-Za-z0-9_\-]+=*\.[A-Za-z0-9_\-]+=*\.[A-Za-z0-9_\-+=/]*', '[REDACTED_JWT]')
    $raw = [regex]::Replace($raw, '(?i)Bearer\s+[A-Za-z0-9\-._~+/]+=*', 'Bearer [REDACTED]')
    $raw = [regex]::Replace($raw, '(?i)("contrasena"\s*:\s*")[^"]*(")', '${1}[REDACTED]${2}')
    $raw = [regex]::Replace($raw, "(?i)('contrasena'\s*:\s*')[^']*(')", '${1}[REDACTED]${2}')
    $raw = [regex]::Replace($raw, '(?i)("token"\s*:\s*")[^"]{20,}(")', '${1}[REDACTED]${2}')
    $raw = [regex]::Replace($raw, '(?i)("value"\s*:\s*")Bearer [^"]*(")', '${1}Bearer [REDACTED]${2}')
    if ($AdminPassword) {
        $escaped = [regex]::Escape($AdminPassword)
        $raw = [regex]::Replace($raw, $escaped, '[REDACTED]')
    }
    [System.IO.File]::WriteAllText($Path, $raw)
}

if (-not (Test-Path -LiteralPath $CollectionFile)) {
    throw "No existe la coleccion: $CollectionFile"
}
if (-not (Get-Command newman -ErrorAction SilentlyContinue)) {
    throw "Newman no esta instalado o no esta en PATH."
}
if ([string]::IsNullOrWhiteSpace($AdminPassword)) {
    throw "BLOQUEADO: definir SGPMP_TEST_PASSWORD o CONTRASENA en el entorno. No se hardcodea en el runner."
}

if (-not (Test-Path -LiteralPath $ResultadosDir)) {
    New-Item -ItemType Directory -Force -Path $ResultadosDir | Out-Null
}

Set-Content -LiteralPath $TxtReport -Value "" -Encoding UTF8

Write-Log "============================================================"
Write-Log " TC-M02-G01 rev2 - RF-00 PRUEBAS GENERALES MODULO 02"
Write-Log " Ambiente: TEST"
Write-Log " Base URL: $BaseUrl"
Write-Log " Coleccion: $CollectionFile"
Write-Log " Runner: $($MyInvocation.MyCommand.Path)"
Write-Log " Fecha UTC: $([DateTime]::UtcNow.ToString('o'))"
Write-Log " Login: un intento. Password via env-var (no en JSON)."
Write-Log "============================================================"
Write-Log ""

$NewmanArguments = @(
    "run",
    $CollectionFile,
    "-e", $EnvironmentFile,
    "--env-var", "baseUrl=$BaseUrl",
    "--env-var", "correo=$AdminEmail",
    "--env-var", "contrasena=$AdminPassword",
    "--insecure",
    "--reporters", "cli,htmlextra,json",
    "--reporter-htmlextra-export", $HtmlReport,
    "--reporter-json-export", $JsonReport
)

& newman @NewmanArguments
$NewmanExitCode = $LASTEXITCODE

Protect-Evidence $HtmlReport
Protect-Evidence $JsonReport
Protect-Evidence $TxtReport

Write-Log ""
Write-Log "Newman exit code: $NewmanExitCode"
Write-Log "HTML: $HtmlReport"
Write-Log "JSON: $JsonReport"
Write-Log ""
Write-Log "Auditoria de creacion: registrada por el caso de uso segun revision de codigo, pero no verificable mediante API publica disponible."
Write-Log "Disponibilidad intermodular no verificada directamente en esta ejecucion; el catalogo devuelve la especie activa."
Write-Log "Desactivar no elimina ni libera el nombre (unicidad sobre todas las filas)."
Write-Log ""

exit $NewmanExitCode
