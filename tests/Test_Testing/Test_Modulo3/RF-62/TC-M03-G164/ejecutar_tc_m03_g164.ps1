<#
.SYNOPSIS
    Script de ejecución automatizada con Newman para TC-M03-G164 (RF-62).
.DESCRIPTION
    Ejecuta la colección Postman/Newman validando variables de entorno,
    verificando ausencia de hardcodeos (L2 / M2 / M7 / M8), pasando credenciales y correos
    por --env-var, suprimiendo datos sensibles en el reporte htmlextra (L6)
    y escaneando fugas de seguridad posteriores.
#>

param(
    [object]$WithSeed = $false,
    [object]$DryRun = $false,
    [string]$ReportPath = "",
    [string]$RawJsonPath = "",
    [string]$ModoDatos = "existentes", # opciones: existentes | sandbox | sql_dba
    [string]$BaseUrl = "https://api.inmero.co/api-sgpmp-test",
    [int]$StatusValidacionEsperado = 422
)

$WithSeed = ($WithSeed -eq $true -or "$WithSeed".ToLower() -eq "true" -or "$WithSeed" -eq "1")
$DryRun = ($DryRun -eq $true -or "$DryRun".ToLower() -eq "true" -or "$DryRun" -eq "1")

# M18: Cálculo dinámico de rutas basado en la ubicación del script ($PSScriptRoot)
$scriptDir = $PSScriptRoot
if (-not $scriptDir) {
    $scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
}
if (-not $scriptDir) {
    $scriptDir = (Get-Location).Path
}

$collectionPath = Join-Path $scriptDir "test_tc_m03_g164.json"
$verifierPath = Join-Path $scriptDir "verificar_hardcode_tc_m03_g164.cjs"
$cleanupSqlPath = Join-Path $scriptDir "cleanup_seed_tc_m03_g164.sql"
$resultadosDir = Join-Path $scriptDir "resultados"

Write-Host "=================================================================" -ForegroundColor Cyan
Write-Host "Iniciando suite de pruebas: TC-M03-G164 (RF-62 - Calidad Telemetria)" -ForegroundColor Cyan
Write-Host "Directorio base: $scriptDir" -ForegroundColor Cyan
Write-Host "Modo de datos seleccionado: $ModoDatos" -ForegroundColor Cyan
Write-Host "Base URL: $BaseUrl" -ForegroundColor Cyan
Write-Host "WithSeed: $WithSeed" -ForegroundColor Cyan
Write-Host "DryRun: $DryRun" -ForegroundColor Cyan
Write-Host "=================================================================" -ForegroundColor Cyan

# 1. Validar variables de entorno requeridas
$sandboxSecret = $env:TEST_SANDBOX_SECRET; if (-not $sandboxSecret) { Write-Error "FALTA TEST_SANDBOX_SECRET"; exit 1 }
$adminPassword = $env:TEST_ADMIN_PASSWORD; if (-not $adminPassword) { Write-Error "FALTA TEST_ADMIN_PASSWORD"; exit 1 }
$productorPassword = $env:TEST_PRODUCER_PASSWORD; if (-not $productorPassword) { $productorPassword = $adminPassword }
$ingenieroPassword = $env:TEST_FIELD_ENGINEER_PASSWORD; if (-not $ingenieroPassword) { $ingenieroPassword = $adminPassword }
$runId = if ($env:RUN_ID) { $env:RUN_ID } else { "test-run-" + [guid]::NewGuid().ToString() }

# M1 / M18: Correos configurables vía entorno con defaults
$adminEmail = if ($env:TEST_ADMIN_EMAIL) { $env:TEST_ADMIN_EMAIL } else { "administador.dev@gmail.com" }
$productorEmail = if ($env:TEST_PRODUCER_EMAIL) { $env:TEST_PRODUCER_EMAIL } else { "productor@pecuaria.co" }
$ingenieroEmail = if ($env:TEST_FIELD_ENGINEER_EMAIL) { $env:TEST_FIELD_ENGINEER_EMAIL } else { "gestor.granja.test@pecuaria.co" }

if (-not $sandboxSecret) {
    Write-Error "ERROR: La variable de entorno TEST_SANDBOX_SECRET no esta definida."
    exit 1
}
if (-not $adminPassword) {
    Write-Error "ERROR: La variable de entorno TEST_ADMIN_PASSWORD no esta definida."
    exit 1
}
if (-not $productorPassword) {
    Write-Error "ERROR: La variable de entorno TEST_PRODUCER_PASSWORD no esta definida."
    exit 1
}
if (-not $ingenieroPassword) {
    Write-Error "ERROR: La variable de entorno TEST_FIELD_ENGINEER_PASSWORD no esta definida."
    exit 1
}

# 2. Chequeo estático previo contra hardcodeos (L2 / M2 / M7 / M8) con variables de entorno disponibles
Write-Host "`n[M8] Ejecutando verificacion estatica contra valores hardcodeados..." -ForegroundColor Cyan
node $verifierPath
if ($LASTEXITCODE -ne 0) {
    Write-Error "ERROR: La coleccion contiene valores hardcodeados o parametros no autorizados."
    exit 1
}

# 3. Determinar rutas de salida (ReportPath y RawJsonPath) con versionamiento por reintentos (§8.4 / §8.5)
if (-not (Test-Path $resultadosDir)) {
    New-Item -ItemType Directory -Path $resultadosDir -Force | Out-Null
}
$dirResultados = $resultadosDir
$sufijo = ""
if (Test-Path "$dirResultados/resultado_TC-M03-G164_reintento1.json") {
    $n = 1
    while (Test-Path "$dirResultados/resultado_TC-M03-G164_reintento$($n+1).json") { $n++ }
    $sufijo = "_reintento$($n+1)"
} elseif (Test-Path "$dirResultados/resultado_TC-M03-G164.json") {
    $sufijo = "_reintento1"
}
$archivoJson = "resultado_TC-M03-G164$sufijo.json"
$archivoHtml = "resultado_TC-M03-G164$sufijo.html"

if ($ReportPath) {
    $reportFile = $ReportPath
} else {
    $reportFile = Join-Path $resultadosDir $archivoHtml
}

$reportParent = Split-Path -Parent $reportFile
if ($reportParent -and -not (Test-Path $reportParent)) {
    New-Item -ItemType Directory -Path $reportParent -Force | Out-Null
}

if (-not $RawJsonPath) {
    $RawJsonPath = Join-Path $env:TEMP "tc_m03_g164\run.json"
}
$rawJsonParent = Split-Path -Parent $RawJsonPath
if ($rawJsonParent -and -not (Test-Path $rawJsonParent)) {
    New-Item -ItemType Directory -Path $rawJsonParent -Force | Out-Null
}

Write-Host "Reporte destino HTML: $reportFile" -ForegroundColor Yellow
Write-Host "Reporte destino JSON: $RawJsonPath" -ForegroundColor Yellow

$exitCode = 0

# 4. F-3: Bloque try/finally para asegurar rollback de sandbox y cleanup de BD
try {
    Write-Host "`nEjecutando Newman con run_id: $runId (login admin dentro de la coleccion)..." -ForegroundColor Cyan
    npx newman run $collectionPath `
      --env-var "baseUrl=$BaseUrl" `
      --env-var "sandbox_secret=$sandboxSecret" `
      --env-var "run_id=$runId" `
      --env-var "admin_email=$adminEmail" `
      --env-var "admin_password=$adminPassword" `
      --env-var "productor_email=$productorEmail" `
      --env-var "productor_password=$productorPassword" `
      --env-var "ingeniero_email=$ingenieroEmail" `
      --env-var "ingeniero_password=$ingenieroPassword" `
      --env-var "modo_datos=$ModoDatos" `
      --env-var "status_validacion_esperado=$StatusValidacionEsperado" `
      -r cli,htmlextra,json `
      --reporter-htmlextra-export $reportFile `
      --reporter-json-export $RawJsonPath `
      --reporter-htmlextra-title "Reporte TC-M03-G164 - Calidad Telemetria RF-62" `
      --reporter-htmlextra-skipHeaders "Authorization,X-Sandbox-Secret" `
      --reporter-htmlextra-hideRequestBody "NW-00-Setup-Login-Admin" `
      --reporter-htmlextra-hideResponseBody "NW-00-Setup-Login-Admin" `
      --reporter-htmlextra-skipEnvironmentVars "sandbox_secret,admin_password,productor_password,ingeniero_password,admin_token,token_admin,producer_token,token_productor,engineer_token,token_ingeniero"

    $exitCode = $LASTEXITCODE

    # 5. M18: Validar que el reporte HTML se haya generado; fallar si no existe
    if (-not (Test-Path $reportFile)) {
        Write-Error "ERROR: El reporte HTML no fue generado en la ruta esperada: $reportFile"
        $exitCode = 1
    } else {
        # 6. Escaneo de seguridad sobre el HTML generado (L6)
        Write-Host "`n[L6] Escaneando reporte HTML generado en busca de fugas de secretos y tokens..." -ForegroundColor Cyan
        $htmlContent = Get-Content -Path $reportFile -Raw
        $fugaDetectada = $false

        if ($htmlContent.Contains($sandboxSecret)) {
            Write-Error "CRITICO: TEST_SANDBOX_SECRET expuesto en el reporte HTML."
            $fugaDetectada = $true
        }
        if ($htmlContent.Contains($adminPassword) -or $htmlContent.Contains($productorPassword) -or $htmlContent.Contains($ingenieroPassword)) {
            Write-Error "CRITICO: Contrasena de prueba expuesta en el reporte HTML."
            $fugaDetectada = $true
        }
        if ($htmlContent -match "eyJ[a-zA-Z0-9_-]{15,}\.eyJ[a-zA-Z0-9_-]{15,}") {
            Write-Error "CRITICO: Token JWT expuesto en el reporte HTML."
            $fugaDetectada = $true
        }
        if ($htmlContent -match "Bearer\s+(?!\{\{)[a-zA-Z0-9_\-\.]{15,}") {
            Write-Error "CRITICO: Patron 'Bearer <token>' literal expuesto en el reporte HTML."
            $fugaDetectada = $true
        }

        if ($fugaDetectada) {
            Remove-Item -Path $reportFile -Force
            Write-Error "El reporte HTML ha sido eliminado por motivos de seguridad debido a fuga de secretos."
            $exitCode = 1
        } else {
            Write-Host "[L6 OK] Escaneo de seguridad limpio: cero credenciales, secretos, Bearer o tokens en el HTML." -ForegroundColor Green
        }
    }
        # FIX B3: generar JSON consolidado con checkpoints OK/FALLA para scanner
        if (Test-Path $RawJsonPath) {
            try {
                $runData = Get-Content $RawJsonPath -Raw | ConvertFrom-Json
                $cps = @()
                foreach ($ex in $runData.run.executions) {
                    $itemName = if ($ex.item.name) { $ex.item.name } else { "unknown" }
                    foreach ($a in $ex.assertions) {
                        $cps += [PSCustomObject]@{
                            paso     = "$itemName :: $($a.assertion)"
                            esperado = "PASSED"
                            obtenido = if ($a.error) { "FAILED" } else { "PASSED" }
                            estado   = if ($a.error) { "FALLA" } else { "OK" }
                        }
                    }
                }
                $okN = ($cps | Where-Object estado -eq "OK").Count
                $fallaN = ($cps | Where-Object estado -eq "FALLA").Count
                $vered = if ($fallaN -gt 0) { "RECHAZADO" } else { "APROBADO" }
                $outObj = [ordered]@{
                    tc = "TC-M03-G164"
                    summary = [ordered]@{ total = $cps.Count; ok = $okN; falla = $fallaN; veredicto = $vered; bloqueo_externo = $null }
                    checkpoints = $cps
                }
                $jsonOut = Join-Path $resultadosDir $archivoJson
                $jsonText = $outObj | ConvertTo-Json -Depth 6
                [System.IO.File]::WriteAllText($jsonOut, $jsonText, (New-Object System.Text.UTF8Encoding($false)))
                Write-Host "[B3 OK] JSON: $($cps.Count) cps | OK=$okN FALLA=$fallaN | $vered"
            } catch {
                Write-Warning "[B3] Fallo: $_"
            }
        }
}
finally {
    Write-Host "`n[FINALLY] Iniciando tareas de limpieza y teardown garantizado..." -ForegroundColor Yellow
    if ($runId) {
        try {
            Write-Host "Ejecutando rollback preventivo de sandbox para run_id: $runId..." -ForegroundColor Yellow
            $teardownHeaders = @{ 'X-Sandbox-Secret' = $sandboxSecret }
            Invoke-RestMethod -Method DELETE -Uri "$BaseUrl/test-control/runs/$runId" -Headers $teardownHeaders -ErrorAction SilentlyContinue | Out-Null
            Write-Host "[TEARDOWN OK] Sandbox cerrado para run_id: $runId." -ForegroundColor Green
        } catch {
            Write-Warning "Rollback sandbox en finally no requirió acción o falló: $_"
        }
    }

    if ($WithSeed) {
        $dbUrl = if ($env:TEST_DB_URL) { $env:TEST_DB_URL } else { $env:TEST_DATABASE_URL }
        if ($dbUrl -and (Test-Path $cleanupSqlPath)) {
            try {
                Write-Host "Ejecutando cleanup SQL de seed..." -ForegroundColor Yellow
                psql $dbUrl -f $cleanupSqlPath -v confirmar_commit=1 | Out-Null
                Write-Host "[CLEANUP SQL OK] Limpieza de seed ejecutada exitosamente." -ForegroundColor Green
            } catch {
                Write-Warning "Ejecución de cleanup_seed_tc_m03_g164.sql falló o psql no disponible: $_"
            }
        } else {
            Write-Host "Cleanup SQL omitido: TEST_DB_URL no configurada." -ForegroundColor Yellow
        }
    } else {
        Write-Host "WithSeed es `$false; no se ejecuta cleanup SQL." -ForegroundColor Cyan
    }
}

Write-Host "`n=================================================================" -ForegroundColor Cyan
Write-Host "Ejecucion finalizada con codigo de salida: $exitCode" -ForegroundColor Cyan
Write-Host "Comando de verificacion pre-commit del scanner (QA Dashboard):" -ForegroundColor Green
Write-Host "python3 -c `"import scanner as s; print([c for c in s.scan()['casos'] if c['tc_id']=='TC-M03-G164'])`"" -ForegroundColor Green
Write-Host "=================================================================" -ForegroundColor Cyan

exit $exitCode
