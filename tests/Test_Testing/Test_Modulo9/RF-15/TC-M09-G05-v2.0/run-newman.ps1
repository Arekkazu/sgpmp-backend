# Script de ejecución Newman para TC-M09-G05-v2.0
$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path "..\..\..\..\..").Path
$envTestPath = Join-Path $repoRoot ".env.test"

$adminPwd = ""
$engPwd = ""

if (Test-Path $envTestPath) {
    Get-Content $envTestPath | ForEach-Object {
        if ($_ -match '^TEST_ADMIN_PASSWORD=(.+)$') {
            $adminPwd = $matches[1].Trim()
        }
        if ($_ -match '^TEST_FIELD_ENGINEER_PASSWORD=(.+)$') {
            $engPwd = $matches[1].Trim()
        }
    }
}

if (-not $adminPwd -or -not $engPwd) {
    Write-Error "No se encontraron las contraseñas requeridas en .env.test"
    exit 1
}

$cmd = "newman run tc-m09-g05-v2.0.postman_collection.json --env-var admin_password=""$adminPwd"" --env-var ingeniero_password=""$engPwd"" -r htmlextra --reporter-htmlextra-export resultados\resultado_TC-M09-G05-v2.0.html --reporter-htmlextra-skipSensitiveData --reporter-htmlextra-skipEnvironmentVars --reporter-htmlextra-skipGlobalVars > evidencias\consola_TC-M09-G05-v2.0.txt 2>&1"

cmd.exe /c $cmd
exit $LASTEXITCODE
