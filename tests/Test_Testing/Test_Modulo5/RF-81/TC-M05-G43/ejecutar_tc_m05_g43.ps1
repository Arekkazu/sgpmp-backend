<#
Runner oficial de TC-M05-G43 (RF-81 / RF-80).
Uso:
  powershell -ExecutionPolicy Bypass -File "tests\Test_Testing\Test_Modulo5\RF-81\TC-M05-G43\ejecutar_tc_m05_g43.ps1" -Reintento 1

HISTORIAL DE CAMBIOS:
| Fecha      | Autor                    | Cambio |
|------------|--------------------------|--------|
| 2026-11-07 | Equipo QA                | Version inicial del runner oficial. |
| 12/11/2026 | Juan Sebastian Gutierrez | Reintento 1: soporte -Reintento, proteccion de resultados/, ASCII sin BOM y escaneo completo de secretos. |
| 12/11/2026 | Juan Sebastian Gutierrez | Correccion de la raiz del repo (5 niveles) |
| 12/11/2026 | Juan Sebastian Gutierrez | C4: verificacion SHA-256 de las 10 suites previas (G14..G38) y exclusion explicita del staging nuevo. |
| 12/11/2026 | Juan Sebastian Gutierrez | F2: escaneo de secretos antes de integridad, exclusion de ARCHIVADO_NO_OFICIAL.txt y detalle de SHA en integridad. |
#>

param(
    [int]$Reintento = 0
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = (Resolve-Path (Join-Path $ScriptDir "..\..\..\..\..")).Path
$EnvPath = Join-Path $RepoRoot ".env.test"

if (-not (Test-Path $EnvPath)) {
    Write-Error "No existe .env.test en $EnvPath"
    exit 2
}

$EnvMap = @{}
foreach ($line in (Get-Content -Path $EnvPath -Encoding UTF8)) {
    $trim = $line.Trim()
    if (-not $trim -or $trim.StartsWith("#")) { continue }
    $idx = $trim.IndexOf("=")
    if ($idx -lt 1) { continue }
    $k = $trim.Substring(0, $idx).Trim()
    $v = $trim.Substring($idx + 1).Trim().Trim('"').Trim("'")
    $EnvMap[$k] = $v
}

function Get-HashesSnapshot {
    param([string]$DirPath)
    $snap = @{}
    if (Test-Path $DirPath) {
        Get-ChildItem -Path $DirPath -File -Recurse | Sort-Object FullName | ForEach-Object {
            $snap[$_.FullName] = (Get-FileHash -Path $_.FullName -Algorithm SHA256).Hash
        }
    }
    return $snap
}

$ResultadosDir = Join-Path $ScriptDir "resultados"
$EvidenciasRoot = Join-Path $ScriptDir "evidencias"
$SnapResultadosAntes = Get-HashesSnapshot -DirPath $ResultadosDir
$SnapEvidenciasRaw = Get-HashesSnapshot -DirPath $EvidenciasRoot
$SnapEvidenciasAntes = @{}
foreach ($k in $SnapEvidenciasRaw.Keys) {
    if ($k.EndsWith("ARCHIVADO_NO_OFICIAL.txt")) { continue }
    $SnapEvidenciasAntes[$k] = $SnapEvidenciasRaw[$k]
}

$Mod5Dir = Join-Path $RepoRoot "tests\Test_Testing\Test_Modulo5"
$PrevSuiteScripts = @(
    (Join-Path $Mod5Dir "RF-76\TC-M05-G14\test_tc_m05_g14.py"),
    (Join-Path $Mod5Dir "RF-76\TC-M05-G15\test_tc_m05_g15.py"),
    (Join-Path $Mod5Dir "RF-76\TC-M05-G16\test_tc_m05_g16.py"),
    (Join-Path $Mod5Dir "RF-76\TC-M05-G17\test_tc_m05_g17.py"),
    (Join-Path $Mod5Dir "RF-76\TC-M05-G19\test_tc_m05_g19.py"),
    (Join-Path $Mod5Dir "RF-77\TC-M05-G21\test_tc_m05_g21.py"),
    (Join-Path $Mod5Dir "RF-77\TC-M05-G24\test_tc_m05_g24.py"),
    (Join-Path $Mod5Dir "RF-77\TC-M05-G25\test_tc_m05_g25.py"),
    (Join-Path $Mod5Dir "RF-80\TC-M05-G37\test_tc_m05_g37.py"),
    (Join-Path $Mod5Dir "RF-80\TC-M05-G38\test_tc_m05_g38.py")
)
$SnapPrevSuitesAntes = @{}
foreach ($sp in $PrevSuiteScripts) {
    if (-not (Test-Path $sp)) {
        Write-Error "No existe script de suite previa: $sp"
        exit 3
    }
    $SnapPrevSuitesAntes[$sp] = (Get-FileHash -Path $sp -Algorithm SHA256).Hash
}

$Stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$EvDir = Join-Path $EvidenciasRoot "run-$Stamp"
New-Item -ItemType Directory -Path $EvDir -Force | Out-Null

$Suf = if ($Reintento -gt 0) { "_reintento$Reintento" } else { "" }
$JunitXml = Join-Path $EvDir "pytest_TC-M05-G43$Suf.xml"
$PytestLog = Join-Path $EvDir "pytest_TC-M05-G43$Suf.log"

$env:TEST_EVIDENCE_DIR = $EvDir
$env:PYTHONIOENCODING = "utf-8"

$PythonExe = "python"
$VenvPy = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (Test-Path $VenvPy) {
    $PythonExe = $VenvPy
}

$TestFile = Join-Path $ScriptDir "test_tc_m05_g43.py"
$PytestArgs = @(
    "-m", "pytest",
    $TestFile,
    "-v",
    "--tb=short",
    "--junitxml=$JunitXml"
)

Write-Host "[TC-M05-G43] Staging: $EvDir"
Write-Host "[TC-M05-G43] Ejecutando pytest (--tb=short)..."

$PrevPref = $ErrorActionPreference
$ErrorActionPreference = "Continue"
& $PythonExe @PytestArgs 2>&1 | Tee-Object -FilePath $PytestLog | Out-Null
$PytestExit = $LASTEXITCODE
$ErrorActionPreference = $PrevPref

Write-Host "[TC-M05-G43] pytest exit code: $PytestExit"

$GenScript = Join-Path $ScriptDir "generar_artefactos_run_g43.py"
$GenArgs = @(
    $GenScript,
    "--evidence-dir", $EvDir,
    "--junit", $JunitXml,
    "--reintento", "$Reintento"
)
& $PythonExe @GenArgs
$GenExit = $LASTEXITCODE
if ($GenExit -ne 0) {
    Write-Error "Fallo generar_artefactos_run_g43.py (exit $GenExit)"
    exit $GenExit
}

# (b) Escaneo de secretos sobre todos los artefactos del staging (siempre se ejecuta y reporta)
$SecretVars = @(
    "TEST_ADMIN_PASSWORD",
    "TEST_FIELD_ENGINEER_PASSWORD",
    "TEST_PRODUCER_PASSWORD",
    "TEST_VET_PASSWORD",
    "TEST_SANDBOX_SECRET"
)
$EmailVars = @(
    "TEST_ADMIN_EMAIL",
    "TEST_FIELD_ENGINEER_EMAIL",
    "TEST_PRODUCER_EMAIL",
    "TEST_VET_EMAIL"
)

$Patterns = @()
foreach ($sv in $SecretVars) {
    $val = $EnvMap[$sv]
    if ([string]::IsNullOrEmpty($val)) {
        Write-Host "[SCAN] Variable vacia omitida: $sv"
        continue
    }
    $Patterns += @{ Name = $sv; Value = $val }
    $tail = if ($val.Length -gt 20) { $val.Substring($val.Length - 20) } else { $val }
    $Patterns += @{ Name = "${sv}_TAIL20"; Value = $tail }
}
foreach ($ev in $EmailVars) {
    $val = $EnvMap[$ev]
    if ([string]::IsNullOrEmpty($val)) {
        Write-Host "[SCAN] Variable vacia omitida: $ev"
        continue
    }
    $Patterns += @{ Name = $ev; Value = $val }
}
$JwtPrefix = "ey" + "J"
$Patterns += @{ Name = "JWT_PREFIX"; Value = $JwtPrefix }

$Findings = @()
$StagingFiles = Get-ChildItem -Path $EvDir -File -Recurse
foreach ($f in $StagingFiles) {
    $content = Get-Content -Path $f.FullName -Raw -Encoding UTF8
    if ([string]::IsNullOrEmpty($content)) { continue }
    foreach ($p in $Patterns) {
        if ($content.Contains($p.Value)) {
            $Findings += "$($f.Name)::$($p.Name) (len=$($p.Value.Length))"
        }
    }
}

$ScanExit = 0
if ($Findings.Count -gt 0) {
    Write-Host "[SCAN] HALLAZGOS DE SECRETOS EN STAGING:"
    foreach ($hit in $Findings) {
        Write-Host "  - $hit"
    }
    $ScanExit = 4
} else {
    Write-Host "[SCAN] 0 hallazgos en $($StagingFiles.Count) archivos de staging."
}

# (c) Verificaciones de integridad (resultados/, evidencias/ previas excluyendo staging nuevo y ARCHIVADO_NO_OFICIAL.txt, y 10 suites previas)
$IntegrityExit = 0
$SnapResultadosDespues = Get-HashesSnapshot -DirPath $ResultadosDir
if ($SnapResultadosAntes.Count -ne $SnapResultadosDespues.Count) {
    Write-Host "[INTEGRIDAD] ERROR: cambio cantidad de archivos en resultados/ (antes=$($SnapResultadosAntes.Count), despues=$($SnapResultadosDespues.Count))"
    $IntegrityExit = 3
}
foreach ($k in $SnapResultadosAntes.Keys) {
    if ($SnapResultadosDespues[$k] -ne $SnapResultadosAntes[$k]) {
        Write-Host "[INTEGRIDAD] ERROR en resultados/: $k | esperado=$($SnapResultadosAntes[$k]) | actual=$($SnapResultadosDespues[$k])"
        $IntegrityExit = 3
    }
}
foreach ($k in $SnapEvidenciasAntes.Keys) {
    if ($k.StartsWith($EvDir) -or $k.EndsWith("ARCHIVADO_NO_OFICIAL.txt")) { continue }
    $hNow = if (Test-Path $k) { (Get-FileHash -Path $k -Algorithm SHA256).Hash } else { "NO_EXISTE" }
    if ($hNow -ne $SnapEvidenciasAntes[$k]) {
        Write-Host "[INTEGRIDAD] ERROR en evidencia previa: $k | esperado=$($SnapEvidenciasAntes[$k]) | actual=$hNow"
        $IntegrityExit = 3
    }
}
$SnapEvidenciasDespues = Get-HashesSnapshot -DirPath $EvidenciasRoot
$PrevCountDespues = ($SnapEvidenciasDespues.Keys | Where-Object { -not $_.StartsWith($EvDir) -and -not $_.EndsWith("ARCHIVADO_NO_OFICIAL.txt") }).Count
if ($PrevCountDespues -ne $SnapEvidenciasAntes.Count) {
    Write-Host "[INTEGRIDAD] ERROR: cambio cantidad de archivos en corridas previas de evidencias/ (antes=$($SnapEvidenciasAntes.Count), despues=$PrevCountDespues)"
    $IntegrityExit = 3
}
foreach ($sp in $PrevSuiteScripts) {
    $hSuiteNow = if (Test-Path $sp) { (Get-FileHash -Path $sp -Algorithm SHA256).Hash } else { "NO_EXISTE" }
    if ($hSuiteNow -ne $SnapPrevSuitesAntes[$sp]) {
        Write-Host "[INTEGRIDAD] ERROR en suite previa: $sp | esperado=$($SnapPrevSuitesAntes[$sp]) | actual=$hSuiteNow"
        $IntegrityExit = 3
    }
}
if ($IntegrityExit -eq 0) {
    Write-Host "[INTEGRIDAD] OK: resultados/, evidencias/ previas y 10 suites previas sin cambios."
}

Write-Host "[TC-M05-G43] Finalizado. Staging: $EvDir"
if ($ScanExit -ne 0) { exit $ScanExit }
if ($IntegrityExit -ne 0) { exit $IntegrityExit }
exit $PytestExit
