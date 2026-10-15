# TC-M09-G137 — RF-24 VISION, Flujo F

El primer control es el contrato publicado en TEST. La colección Postman consulta `/openapi.json` mediante Newman; el runner identifica una operación VISION por su ruta, descripción o body formal. Si no existe, aplica el oráculo del paquete: TC-275 y TC-276 bloqueados, TC-277 rechazado. No utiliza el endpoint SENSOR como sustituto.

Desde esta carpeta:

```powershell
$env:QA_BASE_URL = 'https://api.inmero.co/back-sigab-test'
$env:G137_RUN_ID = 'run-YYYYMMDD-HHMMSS'
node .\run-newman.cjs
```

El RUN conserva en un único `evidencia.json` el estado Git previo, el resumen y hash del OpenAPI, las decisiones y la incidencia. `newman.html` muestra la ejecución del GET contractual. El informe explica cada caso en prosa y remite al JSON para datos extensos. Ninguna contraseña ni token se usa en esta rama de ejecución.

Pytest/SELECT de línea base, login y fixtures se omiten si TEST no publica VISION, porque las fases siguientes quedan cerradas por el primer preflight. Si aparece una operación VISION, el runner se detiene antes de cualquier POST para incorporar la verificación de precondiciones exigida por el paquete; no ejecuta una calibración basándose solo en la existencia de una ruta.
