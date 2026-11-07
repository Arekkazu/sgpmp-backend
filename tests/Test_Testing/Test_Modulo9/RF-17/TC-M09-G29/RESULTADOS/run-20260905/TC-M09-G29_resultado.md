# TC-M09-G29 — RF-17: Propagación de umbrales por MQTT/Edge

**Resultado del grupo: BLOQUEADO.** Se evaluaron exclusivamente los casos
originales `TC-M09-62` y `TC-M09-63`. La fase obligatoria de viabilidad se
realizó antes de cualquier llamada mutante y no permitió establecer una cadena
real y observable **Servidor → MQTT → Edge** en TEST.

| Caso original | Objetivo | Intentos de escritura | Resultado | Categoría | Equipo responsable | Acción |
|---|---|---:|---|---|---|---|
| TC-M09-62 | Propagar una configuración válida de umbral y confirmar recepción, ACK y aplicación reales en Edge. | 0/2 | **BLOCKED — MQTT_TEST_INFRASTRUCTURE_NOT_AVAILABLE** (`MQTT_CLIENT_MISSING` como bloqueo adicional). | `INFRAESTRUC` — infraestructura/sistema externo TEST; y trazabilidad funcional pendiente. | **AIoT e Implementación.** Desarrollo solo si AIoT confirma que RF-17 debe incluir la integración. | **REPORTAR A AIoT E IMPLEMENTACIÓN.** Si AIoT confirma la obligación funcional de RF-17, **REPORTAR A DESARROLLO**. |
| TC-M09-63 | Conservar la configuración anterior de Edge cuando este está offline y registrar la sincronización pendiente. | 0/2 | **BLOCKED — NO EXISTE MECANISMO SEGURO/AUTORIZADO PARA INDUCIR EDGE OFFLINE**. | `INFRAESTRUC` — entorno TEST sin Edge observable ni control QA de indisponibilidad. | **AIoT e Implementación.** | **REPORTAR A AIoT E IMPLEMENTACIÓN.** |

No se hizo reintento porque no se realizó un primer `POST`/`PATCH`. Tampoco se
generó un reporte Newman: emitir una publicación, ACK o log de Edge sin esos
componentes sería una simulación, expresamente excluida del caso.

## MQTT / EDGE

La API TEST estuvo disponible por `GET`: `/health` y `/openapi.json` devolvieron
`200`. El contrato publicado contiene los endpoints de RF-17
`/configuracion/umbrales` (POST/GET),
`/configuracion/umbrales/{id_umbral_ambiental}` (PATCH) y la desactivación. No
declara una operación MQTT o Edge asociada a esos umbrales.

El código local en la rama evaluada confirma ese límite de trazabilidad:

- `src/configuration/application/use_cases/umbrales/registrar_umbral_use_case.py`
  persiste el umbral, niveles y auditoría; `editar_umbral_use_case.py` hace lo
  mismo para la actualización. Una búsqueda con límites de palabra no encontró
  `mqtt`, `broker`, `edge`, `sincronización` ni `ack` en ambos casos de uso ni
  en `umbral_router.py`.
- `MqttHttpAdapter` y `ConfigurarRemotamenteUseCase` son de **RF-23** y solo se
  crean desde `POST /configuracion/dispositivos-iot/{id}/configurar`. Allí el
  backend llama por HTTP al servicio `BROKER-MQTT-SGPMP`; el caso no es parte
  del flujo de umbrales RF-17.
- `.env.test` y `.env.dev` no declaran `MQTT_BROKER_URL` ni
  `MQTT_BROKER_TOKEN`. La única referencia es `.env.example`, con
  `http://localhost:8001` y token vacío para RF-23, por lo que no constituye
  un broker TEST. `docker-compose.test.yml` tampoco declara esas variables.
  No se sondearon puertos ni se adivinó una URL.
- No están disponibles `mosquitto_sub`, `mosquitto_pub`, `mqtt`, MQTT Explorer,
  `paho-mqtt`, `gmqtt`, `asyncio-mqtt` ni el paquete Node `mqtt`. No se instaló
  ninguno.
- El único adaptador de nodo revisado es `NodoEdgeStubAdapter`, descrito por el
  código como stub temporal y devuelve disponibilidad sin consultar un Edge
  real. No se encontró un registro de conexión, log de recepción/ACK ni control
  QA de desconexión. En TEST, el `GET` sin autenticación al inventario de
  dispositivos respondió `401`; `GET /iot/eventos-edge` respondió `405` con
  `Allow: POST`. Ninguno aporta presencia, conexión o aplicación observable de
  un Edge.

Por ello no existe evidencia admisible de broker accesible, Edge TEST conectado,
recepción MQTT, ACK ni aplicación efectiva. `TC-M09-63` tampoco cuenta con un
Edge naturalmente offline identificado ni con un control QA que permita
desconectarlo sin detener servicios, cambiar red o modificar infraestructura.

La evidencia estructurada y sin secretos está en
[viabilidad-mqtt-edge.json](viabilidad-mqtt-edge.json).

## Entorno y alcance

- Backend local: rama `qa/juan-esteban-m09`, SHA
  `adc3932b9f0293a76ebec7e89ed877274791b6a1`.
- Frontend local: rama `qa/juan-esteban-m09`, SHA
  `966621df4e2c6a1f2c9233ea5ebefbb9e3bc2f56`.
- API TEST: `https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test`.
- Se emplearon solo lecturas de archivos, búsquedas de código y `GET` a TEST.
  No se autenticó ningún usuario porque no era necesario para identificar los
  bloqueos y no se inició un flujo de configuración.

## Clasificación, responsables y acción requerida

No se observó un fallo de producto en ejecución: no hubo configuración creada,
publicación MQTT ni sincronización que pudiera fallar. Por tanto, este reporte
no debe abrir un defecto de Desarrollo por el estado actual del grupo. Sí debe
escalarse cada bloqueo al equipo que puede resolverlo:

| Hallazgo verificable | Clasificación | Equipo responsable | Acción concreta |
|---|---|---|---|
| No hay broker MQTT TEST, endpoint documentado, credenciales de proceso ni Edge real observable con ACK/aplicación. | `INFRAESTRUC` — Infraestructura / Sistema Externo TEST. | **AIoT e Implementación.** | **REPORTAR A AIoT E IMPLEMENTACIÓN** para provisionar y documentar broker, identidad de Edge, conectividad y una vía observable de ACK/aplicación. |
| No existe un mecanismo QA oficial para dejar un Edge de TEST offline sin alterar servicios, red o infraestructura. | `INFRAESTRUC` — control de escenario en TEST no disponible. | **AIoT e Implementación.** | **REPORTAR A AIoT E IMPLEMENTACIÓN** para habilitar un Edge de pruebas naturalmente desconectado o un control QA documentado, reversible y autorizado. |
| No hay cliente MQTT aprobado disponible en el puesto/entorno TEST y el caso prohíbe instalarlo durante la ejecución. | Bloqueo de capacidad de prueba; no es defecto funcional. | **Implementación.** | **REPORTAR A IMPLEMENTACIÓN** para preaprovisionar un cliente MQTT compatible o un script de pruebas ya aprobado, sin instalarlo dentro del caso. |
| RF-17 no publica umbrales hacia MQTT en el contrato ni en los casos de uso; la única integración hallada pertenece a RF-23. | Discrepancia de trazabilidad y alcance de la integración IoT. | **AIoT.** | **REPORTAR A AIoT** para confirmar si TC-M09-G29 pertenece a RF-17 o debe reasignarse a RF-23. Si AIoT confirma que RF-17 exige esta propagación, entonces crear defecto `FLUJO` y **REPORTAR A DESARROLLO** para implementar y documentar la integración. |

La automatización no tiene un fallo que corregir y no debe sustituir los
componentes faltantes por mocks, logs manuales, datos inventados ni cambios de
infraestructura. G29 puede reanudarse cuando AIoT e Implementación confirmen
las precondiciones y AIoT haya resuelto el alcance RF-17/RF-23.

## Seguridad y restricciones cumplidas

- No se almacenaron contraseñas, tokens, cookies ni cabeceras de autorización.
- No se ejecutaron `POST`, `PATCH`, `PUT`, `DELETE`, `INSERT`, `UPDATE`,
  operaciones mutantes de base de datos, publicación/suscripción MQTT,
  instalación de dependencias, Docker, cambios de red ni cambios de
  infraestructura.
- No se modificó código funcional ni se tocaron G22–G28. No se inició G30.
- Todos los archivos creados por esta ejecución están dentro de
  `sgpmp-backend/tests/Test_Testing/Test_Modulo9/RF-17/TC-M09-G29/`.

## Git final

Ambos repositorios continúan en `qa/juan-esteban-m09`; sus SHA permanecen
`adc3932b9f0293a76ebec7e89ed877274791b6a1` (backend) y
`966621df4e2c6a1f2c9233ea5ebefbb9e3bc2f56` (frontend). En ambos,
`git diff --stat` quedó vacío. Se preservaron los artefactos untracked
preexistentes G24–G27 en backend y G22/G28 en frontend. El único archivo G29
ya versionado era `NOTA_BLOQUEO.md`; los nuevos artefactos QA de este run son
los enumerados en [git-final.json](git-final.json). No hubo commit, push,
merge ni cambio de rama.

La ejecución se detiene aquí para revisión humana.
