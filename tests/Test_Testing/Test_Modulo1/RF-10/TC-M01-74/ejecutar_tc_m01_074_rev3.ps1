# TC-M01-074 rev3 TEST. No sobrescribe rev1/rev2. No CDP.
$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = (Resolve-Path (Join-Path $ScriptDir "..\..\..\..\..")).Path
$Config = Join-Path $ScriptDir "cypress.config.rev3.cjs"
$Spec = Join-Path $ScriptDir "tc_m01_074_rev3.cy.js"
$ResultadosDir = Join-Path $ScriptDir "Resultados"
$TxtLog = Join-Path $ResultadosDir "TC-M01-074_rev3_ejecucion.txt"
$Pwd = $env:SGPMP_TEST_PASSWORD
if ([string]::IsNullOrWhiteSpace($Pwd)) { $Pwd = $env:CONTRASENA }
$Correo = "admin@pecuaria.co"
if (-not [string]::IsNullOrWhiteSpace($env:SGPMP_TEST_CORREO)) { $Correo = $env:SGPMP_TEST_CORREO }

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

if ([string]::IsNullOrWhiteSpace($Pwd)) { throw "BLOQUEADO: definir SGPMP_TEST_PASSWORD o CONTRASENA." }
if (-not (Test-Path -LiteralPath $ResultadosDir)) { New-Item -ItemType Directory -Force -Path $ResultadosDir | Out-Null }

Set-Location $RepoRoot
npx cypress run --config-file $Config --spec $Spec --env "correo=$Correo,contrasena=$Pwd" --browser chrome
$code = $LASTEXITCODE
Get-ChildItem -LiteralPath $ResultadosDir -File | Where-Object { $_.Name -like "*rev3*" } | ForEach-Object { Protect-Evidence $_.FullName }
exit $code
