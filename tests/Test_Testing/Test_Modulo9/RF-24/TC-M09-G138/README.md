# TC-M09-G138 — validaciones VISION de RF-24

G138 comienza con el contrato desplegado en TEST. La colección ejecuta mediante Newman un `GET /openapi.json`. El runner inspecciona rutas, operaciones y esquemas para encontrar una calibración formal VISION. Un POST de calibración SENSOR no sustituye esa operación.

Desde esta carpeta:

```powershell
$env:QA_BASE_URL = 'https://api.inmero.co/back-sigab-test'
$env:G138_RUN_ID = 'run-YYYYMMDD-HHMMSS'
node .\run-newman.cjs
```

Si VISION no está publicada, la matriz exige **RECHAZADO** para TC-278, 279, 280 y 281. En ese caso el runner guarda la consulta OpenAPI, los cuatro resultados y una incidencia consolidada. No hace login, POST VISION, setup, consultas SQL ni cambios de BD.

Si se publica VISION, el runner se detiene antes de cualquier escritura: primero deben verificarse por API las cuatro precondiciones, la fuente formal del paradigma de TC-280 y la superficie de línea base. No se crea un fixture por haber encontrado solamente una ruta.

Los artefactos del RUN son `evidencia.json`, `newman.html` y `TC-M09-G138_resultado.md`. El informe explica cada caso en prosa y conserva solo los datos técnicos que fundamentan la decisión; el JSON guarda el detalle de la búsqueda contractual.
