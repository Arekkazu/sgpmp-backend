# | Fecha      | Nombre     | Que se hizo                                                    |
# |------------|------------|----------------------------------------------------------------|
# | 2026-10-23 | QA Team    | Runner inicial Newman para TC-M03-G170                         |
# | 2026-10-30 | Juansegutt | Actualizar nombres a _reintento1 e integrar consolidación JSON |

$env:BROKER_TOKEN = "6558230ae103c2adc04d0656a1b72c71b2340c9eeb378ca7b2bea637099d8fa4"
$scriptDir = "tests\Test_Testing\Test_Modulo3\RF-62\TC-M03-G170"

# Cargar .env.test desde root o relativo
$envPath = ".env.test"
if (-not (Test-Path $envPath)) {
    $envPath = Join-Path $scriptDir "..\..\..\..\..\.env.test"
}

if (Test-Path $envPath) {
    Get-Content $envPath | ForEach-Object {
        $line = $_.Trim()
        if ($line -and -not $line.StartsWith("#") -and $line.Contains("=")) {
            $parts = $line.Split("=", 2)
            [System.Environment]::SetEnvironmentVariable($parts[0].Trim(), $parts[1].Trim(), "Process")
        }
    }
}

$runId = "test-g170-sensor91-" + [System.Guid]::NewGuid().ToString().Substring(0,8)
$resultadosDir = Join-Path $scriptDir "resultados"
$evidenciasDir = Join-Path $scriptDir "evidencias"
if (-not (Test-Path $resultadosDir)) { New-Item -ItemType Directory -Path $resultadosDir -Force | Out-Null }
if (-not (Test-Path $evidenciasDir)) { New-Item -ItemType Directory -Path $evidenciasDir -Force | Out-Null }

$reportHtml = Join-Path $resultadosDir "resultado_TC-M03-G170_reintento1.html"
$rawJson    = Join-Path $resultadosDir "resultado_TC-M03-G170_reintento1.raw.json"
$reportJson = Join-Path $resultadosDir "resultado_TC-M03-G170_reintento1.json"
$consoleLog = Join-Path $evidenciasDir "console_run_reintento1.log"

Write-Host "Ejecutando TC-M03-G170 Reintento 1 con run_id: $runId y secret length: $($env:TEST_SANDBOX_SECRET.Length)"

npx -y newman run (Join-Path $scriptDir "test_tc_m03_g170.json") `
  --env-var baseUrl="https://www.api.inmero.co/api-sgpmp-test" `
  --env-var run_id="$runId" `
  --env-var sandbox_secret="$env:TEST_SANDBOX_SECRET" `
  --env-var admin_password="$env:TEST_ADMIN_PASSWORD" `
  --env-var broker_token="$env:BROKER_TOKEN" `
  -r cli,htmlextra,json `
  --reporter-htmlextra-export $reportHtml `
  --reporter-htmlextra-title "TC-M03-G170 Reintento 1 - Sensor preexistente (RF-62)" `
  --reporter-htmlextra-omitRequestBodies `
  --reporter-htmlextra-omitHeaders `
  --reporter-json-export $rawJson `
  2>&1 | Tee-Object -FilePath $consoleLog

if (Test-Path $rawJson) {
    node (Join-Path $scriptDir "consolidar-resultados.cjs") --input $rawJson --output $reportJson
    Remove-Item $rawJson -Force -ErrorAction SilentlyContinue
}
