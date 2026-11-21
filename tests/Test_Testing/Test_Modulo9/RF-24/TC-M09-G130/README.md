# TC-M09-G130 — RF-24 v2.0

Rechazo de referencias a hardware inexistente en el registro de calibración.

- **Requisito:** RF-24 v2.0
- **Caso de uso:** CU05 — Gestionar Dispositivos IoT, Flujo D
- **Casos:** TC-M09-256 y TC-M09-257
- **Tipo:** Validación — capa API
- **Ambiente decisorio:** TEST (**esta prueba no es local**)
- **Informe de cada corrida:** `RESULTADOS/<RUN_ID>/TC-M09-G130_resultado.md`

| Caso | Escenario | Esperado |
|---|---|---|
| TC-M09-256 | dispositivo inexistente en el body, sensor real en la ruta | HTTP 404 + mensaje común del RF, sin persistencia |
| TC-M09-257 | sensor inexistente en la ruta, dispositivo real en el body | HTTP 404 + mensaje común del RF, historial del sensor en `total 0` |

Mensaje exigido en ambos:

```text
Error de referencia: El sensor o dispositivo especificado no existe. No se puede registrar una calibración sobre un hardware inexistente.
```

Es el mensaje **común** de referencia. Un mensaje específico por entidad, como
`No existe un dispositivo IoT con ID 999999.` o `No existe un sensor con ID 999999.`, **no es
PASS** aunque el código HTTP sea 404.

Como es un caso nuevo, vive directamente en su carpeta oficial `TC-M09-G130/`: sin sufijo
`-v2.0`, sin `EvaluacionV2` y sin reutilizar ninguna carpeta histórica. El informe lleva el
identificador del grupo y no se abrevia a `F130`.

## Credenciales

Solo por variables de proceso. Nunca en archivos, colección, evidencias ni informe.

```powershell
$env:QA_BASE_URL="https://api.inmero.co/back-sigab-test"
$env:QA_ING_EMAIL="ingeniero@pecuaria.co"
$env:QA_ING_PASSWORD="<secreto>"

# Administrador: SOLO GET de precondición.
$env:QA_ADMIN_PRIMARY="admin.dev@gmail.com"
$env:QA_ADMIN_SECONDARY="administador.dev@gmail.com"
$env:QA_ADMIN_PASSWORD="<secreto>"
```

Los **dos POST** del caso los ejecuta el Ingeniero de Campo. El `id_usuario` se descubre
dinámicamente, no se hardcodea.

### Por qué hace falta el Administrador

Para acreditar que un ID de dispositivo **no existe**. Para el Ingeniero, incluso un dispositivo
real responde 404 por alcance de finca, de modo que su 404 no distinguiría "no existe" de "fuera
de mi alcance". El Administrador ve todos los dispositivos, así que su 404 sí acredita
inexistencia. También cubre los GET de fixture que el Ingeniero no puede leer.

## Ejecución

```powershell
$env:G130_RUN_ID="run-YYYYMMDD-HHMMSS"
node .\run-newman.cjs
```

Opcionales (con estos valores por defecto):

```powershell
$env:G130_SENSOR_ID="6"
$env:G130_DEVICE_ID="3"
$env:G130_AREA_ID="3"
$env:G130_CATEGORY="TEMPERATURA"
$env:G130_VALOR="22.5000"
$env:G130_IDS_INEXISTENTES="999999,999998,888888"
```

## Reglas que la automatización hace cumplir

- **Presupuesto: 2 POST**, uno por caso. No hay reintentos: si un POST queda ambiguo, se
  reconcilia con el GET del historial y no se reenvía.
- **Los IDs inexistentes se verifican por GET antes de los POST**, no se asumen. El dispositivo
  se acredita con el Administrador (404) y el sensor por su historial (`total 0`, `items []`). Si
  ninguno de los candidatos resulta inexistente, el runner aborta: no se crean ni se eliminan
  datos para conseguirlo.
- **Una sola invalidez intencional por caso.** En TC-256 el sensor de la ruta es real y válido; en
  TC-257 el dispositivo del body es real y válido. Así el rechazo es atribuible a la referencia
  inexistente y no a otra causa.
- **Mensaje comparado de forma exacta** contra el texto común del RF. No se adapta al backend ni
  se reinterpreta después de ver la respuesta.
- **Cero persistencia:** en TC-256 se comparan total e IDs del historial del sensor real antes y
  después; en TC-257 se comprueba que el historial del sensor inexistente sigue en `total 0`.
- **STOP_ALL:** si TC-256 llegara a persistir una calibración que debía rechazarse, el RUN se
  detiene (`postman.setNextRequest(null)`) y TC-257 no se ejecuta, para no seguir enviando POST
  sin entender la contaminación.
- **El RUN no se sobrescribe:** el runner aborta si la carpeta del `RUN_ID` ya existe, y exige el
  formato `run-YYYYMMDD-HHMMSS`.
- **Incidencia consolidada** cuando ambos casos fallan por la misma manifestación; si las causas
  difieren, el runner marca el responsable como `Por determinar` en lugar de consolidar a ciegas.
- `observaciones` exactas: `QA TC-M09-256` y `QA TC-M09-257`.
- Secretos sanitizados del HTML y de `evidencia.json`; la revisión queda registrada dentro del
  propio `evidencia.json`.

## Si el fixture real deja de ser válido

No se crea fixture. Se descubre por GET un equivalente (dispositivo activo, sensor activo del
dispositivo, asociación vigente y valor dentro del rango) y el informe declara los IDs efectivos.
Si no existe ninguno, el resultado es BLOQUEADO / NO VERIFICABLE por precondición funcional no
disponible, explicando la causa.

## Artefactos por corrida

Pocos archivos, consolidados:

```text
RESULTADOS/<RUN_ID>/
├── evidencia.json              git, OpenAPI, actor, fixture, IDs inexistentes con su
│                               verificación, PRE/request/response/POST de cada caso,
│                               oráculos, presupuesto de POST, incidencia y seguridad
├── newman.html                 reporte sanitizado
└── TC-M09-G130_resultado.md    informe del grupo
```
