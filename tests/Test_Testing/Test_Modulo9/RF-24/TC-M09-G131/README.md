# TC-M09-G131 — RF-24 v2.0

Prueba decisoria en TEST de TC-M09-258, TC-M09-259 y las dos variantes de TC-M09-260. El oráculo de cada petición es **HTTP 4xx y ningún cambio en los IDs ni el total del historial**. No se exige un código o mensaje particular.

Requisitos: Node.js 22 y Newman 6 (`npm install` en la raíz o instalación global). Ejecutar desde esta carpeta con variables de proceso:

```powershell
$env:QA_BASE_URL = 'https://api.inmero.co/back-sigab-test'
$env:QA_EMAIL = '<correo Ingeniero de Campo>'
$env:QA_PASSWORD = '<contraseña>'
$env:G131_RUN_ID = 'run-YYYYMMDD-HHMMSS'
node .\run-newman.cjs
```

Si el Ingeniero recibe `404` en los GET de discovery, proporcionar adicionalmente `QA_ADMIN_PASSWORD`. El runner intenta `admin.dev@gmail.com` y luego `administador.dev@gmail.com` si la primera cuenta no autentica o no puede consultar. El Administrador solo hace GET; nunca ejecuta los POST. Los secretos se mantienen en memoria y no se escriben en los resultados.

El runner valida OpenAPI, identidad, permisos y fixtures antes de enviar POST. Si faltan precondiciones, registra `BLOQUEADO / NO VERIFICABLE` y ejecuta cero POST. Por cada petición inválida consulta el historial inmediatamente antes y después; si aparece una calibración, activa `STOP_ALL` y no envía más POST. No repetir un `RUN_ID`.
