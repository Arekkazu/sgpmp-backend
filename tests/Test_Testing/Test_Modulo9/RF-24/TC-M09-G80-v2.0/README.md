# TC-M09-G80-v2.0 — RF-24 v2.0

Auditoría RF-10 de una calibración SENSOR exitosa.

- **Requisito:** RF-24 v2.0
- **Caso de uso:** CU05 — Gestionar Dispositivos IoT, Flujo D
- **Caso:** TC-M09-151-v2.0
- **Tipo:** Auditoría — capa API
- **Ambiente decisorio:** TEST
- **Informe de cada corrida:** `RESULTADOS/<RUN_ID>/TC-M09-G80-v2.0_resultado.md`

Hay que demostrar que una calibración `SENSOR` exitosa queda registrada en el historial
inmutable de RF-10, consultable con `GET /auditoria/`, y que el evento se correlaciona con la
calibración realmente creada:

```text
Ingeniero -> calibración SENSOR exitosa -> id_calibracion real -> ventana temporal real
-> Administrador consulta RF-10 -> evento correlacionado
-> mismo Ingeniero, mismo sensor, mismo dispositivo, mismo valor
```

El nombre del informe lleva el identificador del grupo. **No** se abrevia a `F80` ni a ninguna
otra variante.

## Aislamiento de carpetas

Esta carpeta es la única autorizada. La histórica `../TC-M09-G80/` es de **solo lectura**: no se
edita, no recibe resultados y no se usa como directorio de trabajo. `run-newman.cjs` aborta si
se ejecuta desde cualquier carpeta que no se llame exactamente `TC-M09-G80-v2.0`.

De la automatización histórica **no** se hereda nada hardcodeado: URL `sslip.io`,
`admin@pecuaria.co`, `id_usuario` fijo, ventana de septiembre de 2026 ni referencias a la
calibración de G74. Todo se descubre en cada corrida: `id_usuario` del Ingeniero, fixture,
`id_calibracion`, hora real del POST, ventana de auditoría y Administrador efectivo.

## Credenciales

Solo por variables de proceso. Nunca en archivos, colección, evidencias ni informe.

```powershell
$env:QA_BASE_URL="https://api.inmero.co/back-sigab-test"
$env:QA_ING_EMAIL="ingeniero@pecuaria.co"
$env:QA_ING_PASSWORD="<secreto>"

# El Administrador SOLO consulta auditoría y GET de fixture.
$env:QA_ADMIN_PRIMARY="admin.dev@gmail.com"
$env:QA_ADMIN_SECONDARY="administador.dev@gmail.com"
$env:QA_ADMIN_PASSWORD="<secreto>"
```

Reparto de actores, que es parte del caso: **el Ingeniero ejecuta la calibración y el
Administrador consulta RF-10.** El Administrador nunca crea la calibración. El runner intenta el
administrador primario una vez y, si no autentica, el secundario una vez; no prueba otras
contraseñas y registra cuál quedó en uso.

El Administrador también cubre los GET de fixture que el Ingeniero no puede leer: en TEST su
listado de dispositivos responde HTTP 200 con una lista vacía por alcance de finca, de modo que
el detalle de dispositivo y las asociaciones le devuelven 404.

## Ejecución

```powershell
$env:G80_RUN_ID="run-YYYYMMDD-HHMMSS"
node .\run-newman.cjs
```

Opcionales (fixture preferido, con estos valores por defecto):

```powershell
$env:G80_SENSOR_ID="6"
$env:G80_DEVICE_ID="3"
$env:G80_AREA_ID="3"
$env:G80_CATEGORY="TEMPERATURA"
$env:G80_VALOR="22.5000"
```

## Reglas que la automatización hace cumplir

- **Presupuesto: 1 POST de calibración.** No hay segundo POST automático. Si queda ambiguo, se
  reconcilia con el GET del historial y no se reenvía. Los logins no cuentan como escritura
  funcional.
- **La calibración se genera en el RUN.** No se reutiliza ningún `id_calibracion`, fecha ni
  ventana de una corrida anterior: el objetivo es correlacionar un evento generado ahora.
- **Ventana construida con los tiempos reales:** fecha persistida de la calibración ±1 minuto,
  conservando también `t_request_before` y `t_response_after`. Nunca fechas fijas.
- **Correlación estricta contra falsos positivos.** Un evento solo cuenta si pertenece al
  Ingeniero, cae dentro de la ventana y contiene **simultáneamente** sensor, dispositivo y
  valor. Un login, una consulta de perfil o cualquier otro evento del mismo usuario en la
  ventana **no** satisface el caso. Esto importa de verdad: los dígitos del sensor y del
  dispositivo pueden aparecer por coincidencia dentro de una dirección IP del `detalle`, así que
  exigir los tres datos a la vez es lo que evita aprobar por error.
- **Paginación completa.** Si `total` excede la página, el runner recorre las siguientes con la
  misma `fecha_hasta`; no se concluye ausencia de evento mirando solo la primera.
- **RF-10 es el oráculo, no la auditoría interna de M09.** Una fila en
  `modulo9.auditorias_calibraciones` no aprueba el caso si falta el registro correlacionable en
  `/auditoria/`. El diagnóstico de base es secundario y de solo lectura; si no hay acceso
  autorizado, queda como NO DISPONIBLE.
- **El catálogo de tipos de evento es hallazgo de preflight,** no cierre del caso: aunque no
  publique un tipo para calibración exitosa, se ejecuta la calibración y se verifica
  empíricamente `/auditoria/`.
- **El RUN no se sobrescribe:** el runner aborta si la carpeta del `RUN_ID` ya existe.
- `observaciones` es exactamente `QA TC-M09-151-v2.0`.
- Secretos sanitizados del HTML y de `evidencia.json`; la revisión queda registrada dentro del
  propio `evidencia.json`.

## Si el fixture oficial deja de ser válido

No se modifica la base, no se crea sensor, no se asocia área y no se activa nada para hacer
pasar la prueba. Se busca por GET un fixture semánticamente equivalente (preferible TEMPERATURA,
valor interior del rango) y toda la correlación usa los IDs y el valor efectivos. Si no existe
ninguno, el resultado es BLOQUEADO / NO VERIFICABLE por precondición funcional no disponible.

## Artefactos por corrida

Pocos archivos, consolidados:

```text
RESULTADOS/<RUN_ID>/
├── evidencia.json                  git, OpenAPI, catálogo de tipos de evento, actores,
│                                   fixture, historial PRE/POST, request/response de la
│                                   calibración, id_calibracion, timestamps, ventana RF-10,
│                                   consulta, eventos, correlación, diagnóstico y seguridad
├── newman.html                     reporte sanitizado
└── TC-M09-G80-v2.0_resultado.md    informe del caso
```
