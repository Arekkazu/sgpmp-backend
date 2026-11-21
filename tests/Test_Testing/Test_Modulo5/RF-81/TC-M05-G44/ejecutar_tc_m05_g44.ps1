# | Fecha      | Nombre                   | Que se hizo                                                           |
# |------------|--------------------------|-----------------------------------------------------------------------|
# | 2026-11-07 | Juan Sebastian Gutierrez | Runner PowerShell TC-M05-G44 (RF-81, exportacion del historial)       |
param(
    [int]$Reintento = 0
)

$ErrorActionPreference = 'Stop'

# Rutas relativas
$tcDir       = $PSScriptRoot
$repo        = (Resolve-Path -LiteralPath (Join-Path $tcDir '..\..\..\..\..')).Path
$prueba      = Join-Path $tcDir 'test_tc_m05_g44.py'
$envFile     = Join-Path $repo '.env.test'
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

Write-Host "=== TC-M05-G44 (RF-81): Exportacion del Historial ===" -ForegroundColor Cyan

# 1. Cargar .env.test
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

# 2. Hashes iniciales de suites previas
$shaG44Script = (Get-FileHash -LiteralPath $prueba -Algorithm SHA256).Hash
$shaG44Runner = (Get-FileHash -LiteralPath $PSCommandPath -Algorithm SHA256).Hash
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

Write-Host "Integridad inicial verificada. G44 Script: $shaG44Script" -ForegroundColor Gray

# 3. Directorio de staging
$timestamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$staging   = Join-Path $tcDir "evidencias\run-$timestamp"
New-Item -ItemType Directory -Path $staging -Force | Out-Null
$env:TEST_EVIDENCE_DIR = $staging

$sufijo = if ($Reintento -gt 0) { "_reintento$Reintento" } else { '' }
$reporteHtml = Join-Path $staging "resultado_TC-M05-G44$sufijo.html"
$reporteXml  = Join-Path $staging "resultado_TC-M05-G44$sufijo.xml"
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

& $pyExe $pytestArgs 2>&1 | Tee-Object -FilePath $consoleLog
$codigo = $LASTEXITCODE

# 5. Generar artefactos derivados
Write-Host "Generando artefactos derivados..." -ForegroundColor Yellow
$genScript = Join-Path $tcDir 'generar_artefactos_run_g44.py'
& $pyExe $genScript `
    --staging $staging `
    --sha-g44-script $shaG44Script `
    --sha-g44-runner $shaG44Runner `
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

# 6. Escaneo de secretos en staging
Write-Host "Escaneando secretos en staging..." -ForegroundColor Yellow
$patronesSecretos = @()
if ($env:TEST_ADMIN_PASSWORD)   { $patronesSecretos += [regex]::Escape($env:TEST_ADMIN_PASSWORD) }
if ($env:TEST_SANDBOX_SECRET)   { $patronesSecretos += [regex]::Escape($env:TEST_SANDBOX_SECRET) }
if ($env:TEST_ADMIN_PASSWORD -and $env:TEST_ADMIN_PASSWORD.Length -gt 20) {
    $patronesSecretos += [regex]::Escape($env:TEST_ADMIN_PASSWORD.Substring($env:TEST_ADMIN_PASSWORD.Length - 20))
}
if ($env:TEST_SANDBOX_SECRET -and $env:TEST_SANDBOX_SECRET.Length -gt 20) {
    $patronesSecretos += [regex]::Escape($env:TEST_SANDBOX_SECRET.Substring($env:TEST_SANDBOX_SECRET.Length - 20))
}
$patronesSecretos += 'eyJ[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}'
if ($env:TEST_ADMIN_EMAIL) { $patronesSecretos += [regex]::Escape($env:TEST_ADMIN_EMAIL) }

$hallazgos = 0
Get-ChildItem -LiteralPath $staging -File | ForEach-Object {
    $archivoActual = $_.FullName
    $contenido = Get-Content -LiteralPath $archivoActual -Raw -Encoding UTF8
    foreach ($pat in $patronesSecretos) {
        if ($pat -and ($contenido -match $pat)) {
            Write-Host "ALERTA SECRETO en $archivoActual (patron: $pat)" -ForegroundColor Red
            $hallazgos++
        }
    }
}
Write-Host "Escaneo de secretos finalizado: $hallazgos hallazgos." -ForegroundColor $(if ($hallazgos -eq 0) { 'Green' } else { 'Red' })

# 7. Validar integridad de suites previas post-corrida
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
    Write-Error "CORRUPCION: hashes de suites previas modificados durante TC-M05-G44!"
    exit 3
}

# 8. Promocion a resultados/ (si escaneo limpio y archivos existen)
$htmlFinal = Join-Path $staging "resultado_TC-M05-G44$sufijo.html"
$jsonFinal = Join-Path $staging "resultado_TC-M05-G44$sufijo.json"

if ($hallazgos -eq 0 -and (Test-Path -LiteralPath $htmlFinal) -and (Test-Path -LiteralPath $jsonFinal)) {
    Write-Host "Promoviendo reporte oficial a resultados/..." -ForegroundColor Green
    Copy-Item -LiteralPath $htmlFinal -Destination (Join-Path $tcDir "resultados\resultado_TC-M05-G44.html") -Force
    Copy-Item -LiteralPath $jsonFinal -Destination (Join-Path $tcDir "resultados\resultado_TC-M05-G44.json") -Force
    Write-Host "Promocion oficial completada en resultados/." -ForegroundColor Green
    Get-ChildItem -LiteralPath (Join-Path $tcDir 'resultados') | Select-Object Name, Length, @{Name="SHA256";Expression={(Get-FileHash $_.FullName -Algorithm SHA256).Hash}} | Format-Table -AutoSize
} else {
    Write-Host "No se promueve a resultados/ (secretos=$hallazgos)." -ForegroundColor Yellow
}

exit $codigo

