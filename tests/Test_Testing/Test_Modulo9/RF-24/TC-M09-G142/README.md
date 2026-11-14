# TC-M09-G142 — integración automática M02 → VISION

El objetivo es comprobar dos disparadores de M02: registrar un lote poblacional y cerrar su ciclo. La ausencia de una ruta **manual** VISION no bloquea por sí sola estos casos: la integración podría ser interna. Antes de un POST M02 se necesita identificar una fuente formal de observaciones VISION, su vínculo con cámara/área, N y una superficie verificable de línea base.

Desde esta carpeta en PowerShell:

```powershell
$env:QA_BASE_URL = 'https://api.inmero.co/back-sigab-test'
$env:TEST_DB_HOST = '<host TEST>'
$env:TEST_DB_PORT = '<puerto TEST>'
$env:TEST_DB_NAME = '<base TEST>'
$env:TEST_DB_USER = '<usuario read-only>'
$env:TEST_DB_PASSWORD = '<contraseña>'
$env:G142_RUN_ID = 'run-YYYYMMDD-HHMMSS'
python -B .\test_tc_m09_g142.py --run
```

El script usa Newman para consultar `/openapi.json` y validar las rutas M02. Luego ejecuta **solo SELECT** de `information_schema` en una conexión TEST con `default_transaction_read_only=on`; Pytest revalida las precondiciones observadas. Si no hay fuente formal de vectores VISION, marca TC-288 y TC-289 como **BLOQUEADOS / NO VERIFICABLES**. No registra ni cierra activos, no envía POST manual VISION y no modifica BD.

`RESULTADOS/<RUN_ID>/` contiene `evidencia.json`, `newman.html`, `pytest.xml` y `TC-M09-G142_resultado.md`. El informe explica por caso qué evento se esperaba y qué impidió ejecutarlo, sin presentar la ausencia de un POST como un fallo de integración.
