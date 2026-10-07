# TC-M09-G74-v2.0 — RF-24 v2.0

Prueba API reutilizable de `TC-M09-141-v2.0`: registro de una calibración en modalidad
`SENSOR` ejecutada por el **Ingeniero de Campo**, con reconfirmación del fixture
dispositivo–sensor–área y del rango técnico por GET, historial PRE, un **único** POST
oficial y reconciliación del registro en el historial POST por `id_calibracion`.

- **Requisito:** RF-24 v2.0
- **Caso de uso:** CU05 — Gestionar Dispositivos IoT, Flujo D
- **Ambiente decisorio:** TEST
- **Informe de cada corrida:** `RESULTADOS/<RUN_ID>/TC-M09-G74_resultado.md`

Esta carpeta es independiente de `../TC-M09-G74/`, que conserva sin cambios la prueba
histórica de `TC-M09-141` y sus resultados previos. No modificar esa carpeta desde aquí.

## Fixture del caso

```text
id_sensor            = 6         (TEMPERATURA)
id_dispositivo_iot   = 3         (IOT-ALE01-HLA-003, activo)
id_infraestructura   = 3         (área asociada al sensor)
valor_referencia     = 22.5000   (interior al rango 0.0000 – 45.0000)
modo_calibracion     = SENSOR
observaciones        = QA TC-M09-141-v2.0
fecha_calibracion    = ISO-8601 generada en cada ejecución
```

Los IDs llegan como entrada pero **la colección los reconfirma por GET antes del POST**:
no se asumen válidos por haber funcionado antes.

Nota de fixture: el `id_infraestructura` propio del dispositivo 3 es `1`. El `3` del caso
corresponde al área **asociada al sensor 6**, que es lo que se valida. La colección no
exige que el área del dispositivo coincida con `area_id`.

## Credenciales

Solo por variables de proceso. Nunca en archivos, colección, reportes ni Git.

```powershell
$env:QA_BASE_URL="https://api.inmero.co/back-sigab-test"
$env:TEST_FIELD_ENGINEER_EMAIL="ingeniero@pecuaria.co"
$env:TEST_FIELD_ENGINEER_PASSWORD="<secreto>"

# Administrador auxiliar: SOLO lectura del fixture (ver más abajo).
$env:TEST_ADMIN_EMAIL="administador.dev@gmail.com"
$env:TEST_ADMIN_PASSWORD="<secreto>"
```

### Por qué hay un Administrador auxiliar

En TEST el Ingeniero **no tiene dispositivos en su alcance**: `GET
/configuracion/dispositivos-iot` devuelve `total 0` (incluso con `solo_activos=false`, que
es el valor por defecto). En consecuencia, para ese actor:

```text
GET /configuracion/dispositivos-iot/3        -> 404 DISPOSITIVO_NO_ENCONTRADO
GET /configuracion/sensores/6/asociaciones   -> 404 SENSOR_NO_ENCONTRADO
```

mientras que `GET /configuracion/dispositivos-iot/3/sensores` y el historial de
calibraciones del sensor 6 sí responden 200 para el Ingeniero.

Por eso **únicamente esos dos GET de reconfirmación** (detalle de dispositivo RF-21 e
historial de asociaciones RF-22) se ejecutan con una sesión de Administrador de solo
lectura. El login, los permisos, el historial PRE, el **POST de calibración** y el
historial POST se ejecutan siempre con el Ingeniero. El Administrador nunca ejecuta la
escritura funcional del caso.

## Ejecución

```powershell
$env:G74_RUN_ID="run-YYYYMMDD-HHMMSS"
node .\run-newman.cjs
```

Opcionales (con estos valores por defecto):

```powershell
$env:G74_DEVICE_ID="3"
$env:G74_SENSOR_ID="6"
$env:G74_AREA_ID="3"
$env:G74_SENSOR_CATEGORY="TEMPERATURA"
$env:G74_REFERENCE_VALUE="22.5000"
```

Re-sanitizar un HTML ya generado (no cuenta como segunda ejecución):

```powershell
node .\run-newman.cjs --sanitize-html .\RESULTADOS\<RUN_ID>\newman\newman-TC-M09-141-v2.0.html
```

## Reglas que la automatización hace cumplir

- **Un solo POST por RUN.** No hay reintentos. Si el POST falla o se interrumpe, la
  reconciliación es el GET del historial, nunca un segundo envío.
- **El RUN no se sobrescribe:** el runner aborta si la carpeta del `RUN_ID` ya existe, y
  exige el formato `run-YYYYMMDD-HHMMSS`.
- **Éxito = cualquier 2xx.** No se exige `201`.
- **`total_POST == total_PRE + 1` no es oráculo** (puede haber calibraciones concurrentes
  de otros testers). El oráculo es: el `id_calibracion` no estaba en PRE, sí está en POST
  y conserva los seis valores funcionales.
- **Decimales** se comparan por valor (`22.5` ≡ `22.50` ≡ `22.5000`) y **fechas** por
  instante temporal, no por representación textual.
- `observaciones` es exactamente `QA TC-M09-141-v2.0`: no se le concatena el `RUN_ID`.
- El identificador del sensor se lee como `id_sensor` o `id_sensores`, según lo que
  exponga TEST.
- Secretos y `Authorization` se redactan del HTML antes de conservarlo como evidencia.

## Artefactos por corrida

```text
TC-M09-G74-v2.0/
├── README.md
├── TC-M09-G74-v2.0.postman_collection.json
├── run-newman.cjs
└── RESULTADOS/<RUN_ID>/
    ├── newman/newman-TC-M09-141-v2.0.html   reporte sanitizado
    ├── TC-M09-141-v2.0.json                 artefacto con fixture, oráculo y assertions
    ├── evidencia/
    │   ├── historial_pre.json
    │   ├── request_calibracion.json         body funcional, Authorization redactado
    │   ├── response_calibracion.json
    │   └── historial_post.json
    └── TC-M09-G74_resultado.md              informe del caso
```
