# TC-M09-G139 — límite de observaciones VISION

G139 se ejecuta en TEST. La primera puerta es el contrato `/openapi.json`: debe publicar una operación VISION formal antes de preparar ventanas, N, cámara o línea base. La telemetría común con `apto_para_ia=true` no se toma como vector de comportamiento VISION sin un vínculo formal.

Desde esta carpeta:

```powershell
$env:QA_BASE_URL = 'https://api.inmero.co/back-sigab-test'
$env:G139_RUN_ID = 'run-YYYYMMDD-HHMMSS'
python .\test_tc_m09_g139.py --run
```

El script ejecuta la colección con Newman, consulta el OpenAPI de TEST, y usa Pytest para confirmar que el contrato no cambió durante el preflight. Si la operación VISION no existe, registra TC-282 y TC-283 como **BLOQUEADOS / NO VERIFICABLES**, con cero POST VISION y sin SQL ni fixtures. El GET de Newman es una ejecución real y se resume en `newman.html`; Pytest deja `pytest.xml`.

Si aparece una operación candidata VISION, el script se detiene antes de cualquier POST. Para continuar se debe comprobar la fuente formal de observaciones, N, el vínculo cámara/área y la superficie de línea base que exige el paquete. No existe lógica que invente esos datos ni que escriba en BD.

Cada RUN_ID es único. Los resultados se consolidan en `RESULTADOS/<RUN_ID>/` como `evidencia.json`, `newman.html`, `pytest.xml` y `TC-M09-G139_resultado.md`.
