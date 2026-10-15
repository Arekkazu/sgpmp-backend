# TC-M09-G88 rev2 TEST Cypress. Password: SGPMP_TEST_PASSWORD o CONTRASENA via --env.
$ErrorActionPreference = "Stop"
Set-Location "C:\Users\ll529\OneDrive\Documentos\integrador\sgpmp-backend"
$pass = $env:SGPMP_TEST_PASSWORD
if (-not $pass) { $pass = $env:CONTRASENA }
if (-not $pass) { throw "BLOQUEADO: definir SGPMP_TEST_PASSWORD o CONTRASENA" }
npx cypress run --config-file "tests/Test_Testing/Test_Modulo9/RF-26/TC-M09-G88/cypress.config.rev2.cjs" --env "correo=admin@pecuaria.co,contrasena=$pass"
