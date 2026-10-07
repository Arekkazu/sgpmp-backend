# TC-M09-G135 — rechazos de calibración y auditoría RF-10

Ejecuta en TEST seis intentos de calibración SENSOR rechazados con Newman. Después de cada POST, el runner consulta el historial de calibraciones y `/auditoria/` para decidir el caso. No modifica cuentas, dispositivos, backend ni BD.

En PowerShell, establezca las credenciales **solo en variables del proceso** y ejecute desde esta carpeta:

```powershell
$env:QA_BASE_URL = 'https://api.inmero.co/back-sigab-test'
$env:QA_ING_EMAIL = 'ingeniero@pecuaria.co'
$env:QA_ING_PASSWORD = '<contraseña>'
$env:QA_ADMIN_PASSWORD = '<contraseña>'
$env:QA_PRODUCTOR_EMAIL = 'm2m.nuevo@ejemplo.com'
$env:QA_PRODUCTOR_PASSWORD = '<contraseña>'
$env:G135_RUN_ID = 'run-YYYYMMDD-HHMMSS'
node .\run-newman.cjs
```

`node .\run-newman.cjs --preflight` realiza únicamente GET y login para revisar actores, acceso y fixtures antes del RUN. El Administrador se prueba en orden `admin.dev@gmail.com`, `administador.dev@gmail.com`; se utiliza para RF-10 y para discovery de dispositivos, sensores, asociaciones o áreas solo tras un 404 del Ingeniero. Los POST usan el actor de cada caso. Un RUN_ID existente nunca se sobrescribe. No hay reintentos de POST. Si un rechazo persiste una calibración, se detienen los demás.

Los resultados quedan en `RESULTADOS/<RUN_ID>/` en tres archivos: `evidencia.json`, `newman.html` y `TC-M09-G135_resultado.md`. Las contraseñas, JWT y cabeceras de autorización no se incluyen. Un caso aprueba únicamente si obtiene el código esperado, no crea calibración y cuenta con un evento RF-10 completo y correlacionado.
