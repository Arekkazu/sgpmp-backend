# TC-M09-G85 rev2 TEST. Password: SGPMP_TEST_PASSWORD o CONTRASENA.
$ErrorActionPreference = "Stop"
Set-Location "C:\Users\ll529\OneDrive\Documentos\integrador\sgpmp-backend"
$out = "tests\Test_Testing\Test_Modulo9\RF-26\TC-M09-G85\Resultados"
New-Item -ItemType Directory -Force -Path $out | Out-Null
python -m pytest "tests\Test_Testing\Test_Modulo9\RF-26\TC-M09-G85\test_tc_m09_g85_rev2.py" --noconftest -q --tb=short
$pass = $env:SGPMP_TEST_PASSWORD
if (-not $pass) { $pass = $env:CONTRASENA }
if ($pass) {
  npx cypress run --config-file "tests/Test_Testing/Test_Modulo9/RF-26/TC-M09-G85/cypress.config.rev2.cjs" --env "correo=admin@pecuaria.co,contrasena=$pass"
}
