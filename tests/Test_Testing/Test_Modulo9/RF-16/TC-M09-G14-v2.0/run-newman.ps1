# Script de ejecución Newman para TC-M09-G14-v2.0
$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path "..\..\..\..\..").Path
$envTestPath = Join-Path $repoRoot ".env.test"

$adminPwd = ""

if (Test-Path $envTestPath) {
    Get-Content $envTestPath | ForEach-Object {
        if ($_ -match '^TEST_ADMIN_PASSWORD=(.+)$') {
            $adminPwd = $matches[1].Trim()
        }
    }
}

if (-not $adminPwd) {
    Write-Error "No se encontró TEST_ADMIN_PASSWORD en .env.test"
    exit 1
}

$cmd = "newman run tc-m09-g14-v2.0.postman_collection.json --env-var admin_password=""$adminPwd"" -r htmlextra --reporter-htmlextra-export resultados\resultado_TC-M09-G14-v2.0.html --reporter-htmlextra-skipSensitiveData --reporter-htmlextra-skipEnvironmentVars --reporter-htmlextra-skipGlobalVars > evidencias\consola_TC-M09-G14-v2.0.txt 2>&1"

cmd.exe /c $cmd
exit $LASTEXITCODE
