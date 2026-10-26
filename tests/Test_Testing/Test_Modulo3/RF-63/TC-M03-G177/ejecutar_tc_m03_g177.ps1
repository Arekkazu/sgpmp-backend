$ErrorActionPreference = "Stop"
$env:PYTHONIOENCODING = "utf-8"

$BASE_DEFAULT = "https://api.inmero.co/api-sgpmp-test"

if (-not $env:TEST_ADMIN_PASSWORD) {
    Write-Host "[FATAL] TEST_ADMIN_PASSWORD no esta exportada." -ForegroundColor Red
    exit 2
}

$SANDBOX_SECRET = $env:TEST_SANDBOX_SECRET
if (-not $SANDBOX_SECRET) {
    $SANDBOX_SECRET = "377ab8a5ddc2e5b7f7fb5b58533329eb6ce7f22b99cbd6ad5ffecf3e05b7f8ff"
}

$BASE = if ($env:TEST_BASE_URL) { $env:TEST_BASE_URL } else { $BASE_DEFAULT }

$TC_NAME = "TC-M03-G177"
$RESULTS_DIR = Join-Path $PSScriptRoot "resultados"
if (-not (Test-Path $RESULTS_DIR)) { New-Item -ItemType Directory -Path $RESULTS_DIR | Out-Null }

$HTML_OUT   = Join-Path $RESULTS_DIR ("resultado_" + $TC_NAME + ".html")
$XML_OUT    = Join-Path $RESULTS_DIR ("resultado_" + $TC_NAME + ".xml")
$JSON_OUT   = Join-Path $RESULTS_DIR ("resultado_" + $TC_NAME + ".json")
$COLLECTION = Join-Path $PSScriptRoot "test_tc_m03_g177.json"

Write-Host "=========================================================="
Write-Host (" Ejecutando " + $TC_NAME + " (UNA SOLA VEZ)")
Write-Host (" Base URL: " + $BASE)
Write-Host (" Reportes: " + $RESULTS_DIR)
Write-Host "=========================================================="

$t0 = Get-Date

npx newman run $COLLECTION `
    --env-var "baseUrl=$BASE" `
    --env-var "admin_password=$($env:TEST_ADMIN_PASSWORD)" `
    --env-var "sandbox_secret=$SANDBOX_SECRET" `
    -r cli,htmlextra,junit `
    --reporter-htmlextra-export $HTML_OUT `
    --reporter-junit-export     $XML_OUT

$EXIT_NEWMAN = $LASTEXITCODE
$t1 = Get-Date
$dur = [math]::Round(($t1 - $t0).TotalSeconds, 2)

Write-Host "=========================================================="
Write-Host (" Newman termino en " + $dur + " s con exit_code=" + $EXIT_NEWMAN)
Write-Host "=========================================================="

$CJS = Join-Path $PSScriptRoot "generar_json_resultado.cjs"
if (Test-Path $CJS) {
    Write-Host ("[INFO] Generando JSON de checkpoints desde " + $XML_OUT)
    node $CJS $XML_OUT $JSON_OUT $TC_NAME
    if ($LASTEXITCODE -ne 0) {
        Write-Host ("[WARN] generar_json_resultado.cjs fallo (exit=" + $LASTEXITCODE + ")") -ForegroundColor Yellow
    }
} else {
    Write-Host "[WARN] generar_json_resultado.cjs no existe - no se generara JSON de checkpoints" -ForegroundColor Yellow
}

exit $EXIT_NEWMAN
