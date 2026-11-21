# TC-M09-G133 — RF-24 v2.0

RUN decisorio en TEST de autenticación, sesión cerrada y permiso del Administrador. Se planifican tres POST de calibración y un DELETE de sesión, sin reintentos funcionales.

Desde esta carpeta, con Node.js 22 y Newman 6:

```powershell
$env:QA_BASE_URL = 'https://api.inmero.co/back-sigab-test'
$env:QA_ING_EMAIL = '<Ingeniero de Campo>'
$env:QA_ING_PASSWORD = '<contraseña>'
$env:QA_ADMIN_PASSWORD = '<contraseña del Administrador>'
$env:G133_RUN_ID = 'run-YYYYMMDD-HHMMSS'
node .\run-newman.cjs
```

El runner intenta `admin.dev@gmail.com` y luego `administador.dev@gmail.com`, comprueba identidad y permisos, valida el fixture por GET y ejecuta TC-M09-264 primero. Después prueba TC-M09-263 sin cabecera `Authorization`; por último, inicia una sesión nueva del Ingeniero, la cierra con `DELETE /sesiones/` y reutiliza exactamente su token para el POST. Tokens, contraseñas, cookies y cabeceras de autorización permanecen solo en memoria. Los historiales PRE/POST se comparan por total e IDs. Una persistencia inesperada en una variante de seguridad activa `STOP_ALL`.
