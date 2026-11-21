# TC-M09-G134 — RF-24 v2.0

RUN decisorio en TEST. TC-M09-265 contrasta las calibraciones oficiales previas por ID, TC-M09-266 comprueba que un nuevo POST no altera calibraciones existentes y TC-M09-267 compara telemetría histórica cerrada mediante API y SELECT de solo lectura.

Requiere Node.js 22, Newman 6, Python con `psycopg2` y `pytest`. Variables de proceso:

```powershell
$env:QA_BASE_URL = 'https://api.inmero.co/back-sigab-test'
$env:QA_ING_EMAIL = '<Ingeniero de Campo>'
$env:QA_ING_PASSWORD = '<contraseña>'
$env:QA_ADMIN_PASSWORD = '<contraseña del Administrador>'
$env:QA_DB_HOST = '<host TEST>'
$env:QA_DB_PORT = '<puerto TEST>'
$env:QA_DB_USER = 'member_qa'
$env:QA_DB_PASSWORD = '<contraseña TEST>'
$env:QA_DB_NAME = 'sgpmp_test'
$env:G134_RUN_ID = 'run-YYYYMMDD-HHMMSS'
node .\run-newman.cjs
```

La BD se usa solo en TC-M09-267 y `test_tc_m09_267.py` ejecuta exclusivamente SELECT con la transacción en modo read-only. Los dos POST de calibración usan al Ingeniero. El Administrador se usa para GET de discovery que el Ingeniero no ve y para leer el historial de telemetría cuando su alcance devuelve vacío. Nunca se guardan secretos, JWT, cookies ni Authorization. No se reenvía un POST ambiguo ni se borran las calibraciones válidas creadas.
