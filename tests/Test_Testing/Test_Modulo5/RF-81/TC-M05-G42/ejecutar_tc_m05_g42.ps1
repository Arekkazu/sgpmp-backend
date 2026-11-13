# | Fecha      | Nombre                   | Que se hizo                                                           |
# |------------|--------------------------|-----------------------------------------------------------------------|
# | 2026-11-07 | Juan Sebastian Gutierrez | Runner PowerShell TC-M05-G42 (RF-81, filtros y paginacion)            |
# | 12/11/2026 | Juan Sebastian Gutierrez | Reintento 1: --reintento N, sin copia a resultados/, escaneo exit 4   |
param(
    [int]$Reintento = 0
)

$ErrorActionPreference = 'Stop'

# Rutas relativas
$tcDir       = $PSScriptRoot
$repo        = (Resolve-Path -LiteralPath (Join-Path $tcDir '..\..\..\..\..')).Path
$prueba      = Join-Path $tcDir 'test_tc_m05_g42.py'
$envFile     = Join-Path $repo '.env.test'
$resDir      = Join-Path $tcDir 'resultados'
$rf76Dir     = Join-Path $repo 'tests\Test_Testing\Test_Modulo5\RF-76'
$rf77Dir     = Join-Path $repo 'tests\Test_Testing\Test_Modulo5\RF-77'
$rf80Dir     = Join-Path $repo 'tests\Test_Testing\Test_Modulo5\RF-80'

$g38Script   = Join-Path $rf80Dir 'TC-M05-G38\test_tc_m05_g38.py'
$g37Script   = Join-Path $rf80Dir 'TC-M05-G37\test_tc_m05_g37.py'
$g25Script   = Join-Path $rf77Dir 'TC-M05-G25\test_tc_m05_g25.py'
$g24Script   = Join-Path $rf77Dir 'TC-M05-G24\test_tc_m05_g24.py'
$g21Script   = Join-Path $rf77Dir 'TC-M05-G21\test_tc_m05_g21.py'
$g19Script   = Join-Path $rf76Dir 'TC-M05-G19\test_tc_m05_g19.py'
$g17Script   = Join-Path $rf76Dir 'TC-M05-G17\test_tc_m05_g17.py'
$g16Script   = Join-Path $rf76Dir 'TC-M05-G16\test_tc_m05_g16.py'
$g15Script   = Join-Path $rf76Dir 'TC-M05-G15\test_tc_m05_g15.py'
$g14Script   = Join-Path $rf76Dir 'TC-M05-G14\test_tc_m05_g14.py'

Write-Host "=== TC-M05-G42 (RF-81): Filtros, Paginacion y Limites (Reintento=$Reintento) ===" -ForegroundColor Cyan

# 1. Cargar .env.test en memoria
if (-not (Test-Path -LiteralPath $envFile)) {
    Write-Error "PRECONDICION_FALLIDA: no existe $envFile"
    exit 2
}
Get-Content -LiteralPath $envFile | ForEach-Object {
    $linea = $_.Trim()
    if ($linea -and -not $linea.StartsWith('#') -and $linea.Contains('=')) {
        $idx = $linea.IndexOf('=')
        $k = $linea.Substring(0, $idx).Trim()
        $v = $linea.Substring($idx + 1).Trim().Trim('"').Trim("'")
        [Environment]::SetEnvironmentVariable($k, $v, 'Process')
    }
}

# 2. Hashes iniciales de suites previas y de resultados/
$shaG42Script = (Get-FileHash -LiteralPath $prueba -Algorithm SHA256).Hash
$shaG42Runner = (Get-FileHash -LiteralPath $PSCommandPath -Algorithm SHA256).Hash
$shaG38 = (Get-FileHash -LiteralPath $g38Script -Algorithm SHA256).Hash
$shaG37 = (Get-FileHash -LiteralPath $g37Script -Algorithm SHA256).Hash
$shaG25 = (Get-FileHash -LiteralPath $g25Script -Algorithm SHA256).Hash
$shaG24 = (Get-FileHash -LiteralPath $g24Script -Algorithm SHA256).Hash
$shaG21 = (Get-FileHash -LiteralPath $g21Script -Algorithm SHA256).Hash
$shaG19 = (Get-FileHash -LiteralPath $g19Script -Algorithm SHA256).Hash
$shaG17 = (Get-FileHash -LiteralPath $g17Script -Algorithm SHA256).Hash
$shaG16 = (Get-FileHash -LiteralPath $g16Script -Algorithm SHA256).Hash
$shaG15 = (Get-FileHash -LiteralPath $g15Script -Algorithm SHA256).Hash
$shaG14 = (Get-FileHash -LiteralPath $g14Script -Algorithm SHA256).Hash

$hashesResInicio = @{}
if (Test-Path -LiteralPath $resDir) {
    Get-ChildItem -LiteralPath $resDir -File | ForEach-Object {
        $hashesResInicio[$_.Name] = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash
    }
}

Write-Host "Integridad inicial verificada. G42 Script: $shaG42Script" -ForegroundColor Gray

# 3. Directorio de staging
$timestamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$staging   = Join-Path $tcDir "evidencias\run-$timestamp"
New-Item -ItemType Directory -Path $staging -Force | Out-Null
$env:TEST_EVIDENCE_DIR = $staging

$sufijo = if ($Reintento -gt 0) { "_reintento$Reintento" } else { '' }
$reporteHtml = Join-Path $staging "resultado_TC-M05-G42$sufijo.html"
$reporteXml  = Join-Path $staging "resultado_TC-M05-G42$sufijo.xml"
$consoleLog  = Join-Path $staging "console_execution.log"

# 4. Ejecutar pytest
$pyExe = Join-Path $repo '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pyExe)) { $pyExe = 'python' }

Write-Host "Ejecutando Pytest contra TEST_BASE_URL=$($env:TEST_BASE_URL)..." -ForegroundColor Yellow
$pytestArgs = @(
    '-m', 'pytest',
    '-p', 'no:randomly',
    '--tb=short',
    "--html=$reporteHtml",
    '--self-contained-html',
    "--junitxml=$reporteXml",
    $prueba
)

$tInicio = Get-Date
& $pyExe $pytestArgs 2>&1 | Tee-Object -FilePath $consoleLog
$codigo = $LASTEXITCODE
$duracion = [math]::Round(((Get-Date) - $tInicio).TotalSeconds, 2)
Write-Host "Pytest finalizado en ${duracion}s con exit code=$codigo" -ForegroundColor Cyan

# 5. Generar artefactos derivados
Write-Host "Generando artefactos derivados..." -ForegroundColor Yellow
$genScript = Join-Path $tcDir 'generar_artefactos_run_g42.py'
& $pyExe $genScript `
    --staging $staging `
    --reintento $Reintento `
    --sha-g42-script $shaG42Script `
    --sha-g42-runner $shaG42Runner `
    --sha-g38-script $shaG38 `
    --sha-g37-script $shaG37 `
    --sha-g25-script $shaG25 `
    --sha-g24-script $shaG24 `
    --sha-g21-script $shaG21 `
    --sha-g19-script $shaG19 `
    --sha-g17-script $shaG17 `
    --sha-g16-script $shaG16 `
    --sha-g15-script $shaG15 `
    --sha-g14-script $shaG14
if ($LASTEXITCODE -ne 0) {
    Write-Error "Fallo generar_artefactos_run_g42.py (exit=$LASTEXITCODE)"
    exit $LASTEXITCODE
}

# 6. Escaneo de secretos en staging (solo reporta, exit 4 si hay hallazgos)
Write-Host "Escaneando secretos en staging..." -ForegroundColor Yellow
$criterios = @()
$varsSecretos = @(
    @{ Nombre = 'TEST_ADMIN_PASSWORD'; Valor = $env:TEST_ADMIN_PASSWORD; Cola20 = $true },
    @{ Nombre = 'TEST_SANDBOX_SECRET'; Valor = $env:TEST_SANDBOX_SECRET; Cola20 = $true },
    @{ Nombre = 'TEST_ADMIN_EMAIL';    Valor = $env:TEST_ADMIN_EMAIL;    Cola20 = $false },
    @{ Nombre = 'TEST_PRODUCTOR_EMAIL';Valor = $env:TEST_PRODUCTOR_EMAIL;Cola20 = $false },
    @{ Nombre = 'TEST_INGENIERO_EMAIL';Valor = $env:TEST_INGENIERO_EMAIL;Cola20 = $false }
)
foreach ($item in $varsSecretos) {
    $val = $item.Valor
    if ([string]::IsNullOrEmpty($val)) {
        Write-Host "  [OMITIDO] $($item.Nombre) vacio en entorno" -ForegroundColor DarkGray
        continue
    }
    $criterios += @{ Etiqueta = $item.Nombre; Regex = [regex]::Escape($val); Longitud = $val.Length }
    if ($item.Cola20 -and $val.Length -ge 20) {
        $cola = $val.Substring($val.Length - 20)
        $criterios += @{ Etiqueta = "$($item.Nombre)_ultimos20"; Regex = [regex]::Escape($cola); Longitud = $cola.Length }
    }
}
$jwtPrefijo = 'ey' + 'J'
$criterios += @{ Etiqueta = 'JWT_PREFIJO'; Regex = ($jwtPrefijo + '[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}'); Longitud = $jwtPrefijo.Length }

Write-Host "Patrones buscados (etiqueta : longitud):" -ForegroundColor Gray
foreach ($crit in $criterios) {
    Write-Host "  - $($crit.Etiqueta) : len=$($crit.Longitud)" -ForegroundColor Gray
}

$hallazgos = 0
Get-ChildItem -LiteralPath $staging -File | ForEach-Object {
    $archivoActual = $_.FullName
    $contenido = Get-Content -LiteralPath $archivoActual -Raw -Encoding UTF8
    foreach ($crit in $criterios) {
        if ($contenido -match $crit.Regex) {
            Write-Host "ALERTA SECRETO en $($_.Name) (criterio: $($crit.Etiqueta), len=$($crit.Longitud))" -ForegroundColor Red
            $hallazgos++
        }
    }
}
Write-Host "Escaneo de secretos finalizado: $hallazgos hallazgos." -ForegroundColor $(if ($hallazgos -eq 0) { 'Green' } else { 'Red' })
if ($hallazgos -gt 0) {
    exit 4
}

# 7. Validar integridad de suites previas y de resultados/ (nunca copia a resultados/)
$shaPostG38 = (Get-FileHash -LiteralPath $g38Script -Algorithm SHA256).Hash
$shaPostG37 = (Get-FileHash -LiteralPath $g37Script -Algorithm SHA256).Hash
$shaPostG25 = (Get-FileHash -LiteralPath $g25Script -Algorithm SHA256).Hash
$shaPostG24 = (Get-FileHash -LiteralPath $g24Script -Algorithm SHA256).Hash
$shaPostG21 = (Get-FileHash -LiteralPath $g21Script -Algorithm SHA256).Hash
$shaPostG19 = (Get-FileHash -LiteralPath $g19Script -Algorithm SHA256).Hash
$shaPostG17 = (Get-FileHash -LiteralPath $g17Script -Algorithm SHA256).Hash
$shaPostG16 = (Get-FileHash -LiteralPath $g16Script -Algorithm SHA256).Hash
$shaPostG15 = (Get-FileHash -LiteralPath $g15Script -Algorithm SHA256).Hash
$shaPostG14 = (Get-FileHash -LiteralPath $g14Script -Algorithm SHA256).Hash

if ($shaPostG38 -ne $shaG38 -or $shaPostG37 -ne $shaG37 -or $shaPostG25 -ne $shaG25 -or $shaPostG24 -ne $shaG24 -or $shaPostG21 -ne $shaG21 -or $shaPostG19 -ne $shaG19 -or $shaPostG17 -ne $shaG17 -or $shaPostG16 -ne $shaG16 -or $shaPostG15 -ne $shaG15 -or $shaPostG14 -ne $shaG14) {
    Write-Error "CORRUPCION: hashes de suites previas modificados durante TC-M05-G42!"
    exit 3
}

$hashesResFin = @{}
if (Test-Path -LiteralPath $resDir) {
    Get-ChildItem -LiteralPath $resDir -File | ForEach-Object {
        $hashesResFin[$_.Name] = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash
    }
}
$resIntacto = ($hashesResInicio.Count -eq $hashesResFin.Count)
if ($resIntacto) {
    foreach ($k in $hashesResInicio.Keys) {
        if ($hashesResFin[$k] -ne $hashesResInicio[$k]) { $resIntacto = $false; break }
    }
}
if (-not $resIntacto) {
    Write-Error "CORRUPCION: resultados/ fue modificado durante la ejecucion!"
    exit 5
}
Write-Host "Confirmado: resultados/ intacto (SHA-256 sin cambios). Staging: $staging" -ForegroundColor Green

exit $codigo
