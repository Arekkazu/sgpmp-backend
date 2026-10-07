# TC-M09-G141 — reemplazo de línea base vigente VISION

G141 se decide en TEST. TC-M09-287 solo puede ejecutar su segundo POST cuando existe una operación VISION publicada, una L1 vigente verificable del par área/especie y una ventana posterior W2 con observaciones VISION aptas suficientes. El caso **no** exige que L1 permanezca almacenada como historial; exige que deje de ser la vigente.

Desde esta carpeta:

```powershell
$env:QA_BASE_URL = 'https://api.inmero.co/back-sigab-test'
$env:G141_RUN_ID = 'run-YYYYMMDD-HHMMSS'
python -B .\test_tc_m09_287.py --run
```

El script ejecuta con Newman la consulta contractual `GET /openapi.json`, verifica por Pytest que el contrato no cambió durante el preflight y revisa el resultado oficial previo de TC-M09-275. Si VISION no se publica o TC-275 no dejó una L1 verificable, G141 queda **BLOQUEADO / NO VERIFICABLE**. No se crea L1 de forma oculta, no se envía POST VISION ni se escribe en BD.

Los resultados se consolidan en `RESULTADOS/<RUN_ID>/`: `evidencia.json`, `newman.html`, `pytest.xml` si se ejecutó Pytest realmente, y `TC-M09-G141_resultado.md`. El informe explica qué se pudo observar y qué sigue pendiente de prueba.
