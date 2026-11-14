# TC-M09-G132 — RF-24 v2.0

RUN decisorio en TEST para precisión de `22.1234` (TC-M09-262) y rechazo de los strings `NaN`, `Infinity` y `-Infinity` (TC-M09-261). Cuatro POST planificados, sin reintentos.

Desde esta carpeta, con Node.js 22 y Newman 6:

```powershell
$env:QA_BASE_URL = 'https://api.inmero.co/back-sigab-test'
$env:QA_EMAIL = '<Ingeniero de Campo>'
$env:QA_PASSWORD = '<contraseña>'
$env:QA_ADMIN_PASSWORD = '<contraseña del Administrador>'
$env:G132_RUN_ID = 'run-YYYYMMDD-HHMMSS'
node .\run-newman.cjs
```

Si el Ingeniero recibe 404 en los GET de discovery, se intenta `admin.dev@gmail.com` y luego `administador.dev@gmail.com`. El Administrador solo hace GET; todos los POST funcionales usan al Ingeniero. Ningún secreto se escribe en el resultado.

El runner valida identidad, permisos, OpenAPI y fixture antes del primer POST. Ejecuta TC-M09-262 primero y compara el valor de la respuesta y del registro recuperado por `id_calibracion` como decimal exacto. Después evalúa TC-M09-261 con HTTP 400, mensaje exacto y comparación de total e IDs PRE/POST. Una persistencia o ambigüedad en una variante inválida activa `STOP_ALL`; la calibración no se borra. Cada RUN_ID es inmutable y no debe reutilizarse.
