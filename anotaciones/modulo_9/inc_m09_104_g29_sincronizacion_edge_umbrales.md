# INC-M09-104-G29 — Umbrales no se propagan al Nodo Edge ni gestionan fallos de sincronización

**RF:** RF-17 (CU03 — Configurar Umbrales y Alertas Ambientales). **Grupo:** TC-M09-G29.
**Casos:** TC-M09-62 (propagación), TC-M09-63 (fallo de sincronización). **Severidad:** Severo.

> **Reevaluación V4 (2026-10-05, issue #493) — el stub se reemplaza por propagación real.**
> QA rechazó TC-M09-62 porque `POST`/`PATCH` seguían inyectando `EdgeSincronizacionStubAdapter`
> (siempre `PENDIENTE`, sin MQTT; censo DEV: 10/10 umbrales `PENDIENTE`, 0 con
> `fecha_ultima_sincronizacion`). Las secciones de abajo describen la primera ronda; lo vigente es
> esta.
>
> **Contrato acordado entre backend y broker** (lado broker: `BROKER-MQTT-SGPMP`, rama
> `feature/rf17-propagacion-umbrales-edge`, contrato para AIoT en `INTEGRACION_DISPOSITIVOS_RF17.md`):
>
> | Pieza | Decisión |
> |---|---|
> | Destino | Los **Gateway Edge** activos (tipo `GATEWAY_EDGE`) de las áreas activas de la especie —las que tienen su `id_especie` o activos biológicos vivos de ella, mismo criterio que #253—: instalados en el área o que atienden un dispositivo activo del área. Es quien evalúa las lecturas en campo (`modulo3.eventos_edge_computing.umbral_*_aplicado`) y lo único que habla MQTT |
> | Resolución | `modulo9.fn_seriales_gateway_edge_por_especie(int)`, `SECURITY DEFINER` (migración `a3c9e5d17b42`): la política de `dispositivos_iot` solo deja leer a Administrador/Ingeniero, pero un Veterinario también edita umbrales |
> | Transporte | `POST /v1/commands` con `origen: "umbral"` por Gateway, en paralelo; el broker publica en el topic `command` ya existente del Edge con `tipo_comando: "UMBRAL_AMBIENTAL"` (sin topics ni ACL nuevos) |
> | Payload | `id_comando`, `emitido_en`, `id_umbral_ambiental`, `version` (= `fecha_actualizacion`), `variable` (nombre de telemetría), `unidad`, `valor_min`, `valor_max`, `niveles[]` |
> | ACK / timeout | `{"tipo_mensaje":"ACK_UMBRAL","resultado":"OK","id_comando":...}` en `status`; 30 s (`MQTT_ACK_TIMEOUT_SECONDS`) |
> | Estado del umbral | todos `APLICADA` → `APLICADA` + `fecha_ultima_sincronizacion`; alguno `NO_CONF` → `NO_CONF` + 500; alguno `PENDIENTE` (Edge desconectado, TC-M09-63) → `PENDIENTE` + 500; sin Gateway o sin broker configurado → `PENDIENTE` (201/200) |
>
> **Tres defectos encontrados en el camino**, todos necesarios para que `APLICADA` llegue a BD:
>
> 1. **El segundo commit perdía la identidad RLS.** `set_config(..., true)` muere en el primer
>    `commit()`, y la política UPDATE de `umbrales_ambientales` filtra la fila sin rol: verificado
>    en `sgpmp_dev` con `member_dev` (sin `BYPASSRLS`), en transacción revertida — **0 filas sin
>    contexto, 1 con rol Veterinario**. Aunque el Edge confirmara, `APLICADA` nunca se habría
>    guardado. Fix: `src/shared/contexto_rls.py` guarda el contexto en `Session.info` y lo vuelve a
>    declarar (sigue siendo local) en cada transacción nueva de la misma sesión. Beneficia también a
>    RF-23 (`ConfigurarRemotamenteUseCase`, mismo patrón de dos commits).
> 2. **La correlación de ACK en el broker era una sola por serial.** Un Edge recibe varios umbrales
>    seguidos (uno por variable) y la segunda espera pisaba a la primera → `NO_CONF` falso. Ahora se
>    indexa por `(serial, id_comando)` y tipo de ACK (cambio en el broker).
> 3. **Editar no reseteaba el estado.** Si la propagación no alcanzaba a persistir, el umbral
>    editado seguía mostrando el `APLICADA` de la versión anterior. `UmbralAmbiental.actualizar()`
>    ahora lo deja `PENDIENTE`.
>
> **Edge (SerBy48/EDGE-FIRMWARE-SGPMP#5):** el `edge_agent` distingue `tipo_comando`, guarda el
> umbral en `umbrales.json` y publica el `ACK_UMBRAL`. Debe instalarse en los Raspberry **antes**
> que este backend y el broker: con el agente anterior cada umbral termina en `NO_CONF` (500) a los 30 s.
> **TC-M09-63** (Edge offline): con sesión persistente Mosquitto sigue listando la conexión del Edge
> caído, así que el Edge publica `{"tipo_mensaje": "DESCONEXION"}` en su `status` (Last Will y antes
> de un cierre ordenado) y el broker no publica: `PENDIENTE` + 500 al instante, y el Edge conserva el
> último umbral guardado. Como el broker no publica, no hay reenvío al reconectar: se propaga en la
> próxima edición (igual que RF-23).
>
> **🔴 Migración `a3c9e5d17b42` requiere DBA** (crea la función; `member_dev` no puede migrar ni
> leer `tipos_dispositivo_iot`, así que solo se validó en modo offline `alembic upgrade --sql`).
> Sin ella, `POST`/`PATCH` fallan al buscar destinos.

## Qué reportó QA

El flujo de `POST`/`PATCH` de umbrales termina en persistencia + auditoría + `201`/`200`, sin
ningún intento de propagar la configuración hacia el Nodo Edge, y sin flujo alterno para cuando
esa propagación falla: no hay estado "Pendiente de Sincronización", no hay ACK/timeout, no hay
manejo de error, no hay forma de consultar qué configuración usa realmente el Edge. Ambos casos
quedan **DESAPROBADOS**.

## Investigación (Paso 0)

**Infraestructura MQTT/Edge existente revisada antes de escribir código:**

- `MqttPort.enviar_configuracion(serial, payload) -> ResultadoEnvioMqtt` (`configuration`,
  usado por RF-23 para configurar un dispositivo IoT individual) — el patrón exacto de
  degradación que necesita este RF (nunca lanza, degrada a `PENDIENTE`), pero atado a **un
  dispositivo por su serial**, no a un umbral por (especie, variable_ambiental).
- `MqttHttpAdapter` (implementación real de `MqttPort`) llama a `BROKER-MQTT-SGPMP` vía
  `POST {base_url}/v1/commands` con `{"serial": ..., ...}` — contrato ya definido para comandos
  a un dispositivo, sin ningún equivalente para "propagar por especie+variable".
- `modulo4.sincronizacion_nodos_edge` — tabla de sincronización, pero específica del motor de
  IA (versión de modelo de predicción por dispositivo), sin relación con umbrales ambientales.
- `NodoEdgePort` (`prediction`) — solo verifica `hay_nodos_activos(tipo_modelo)`, no envía
  configuraciones.
- **No existe en ningún módulo** una relación ya construida de (id_especie,
  id_variable_ambiental) → dispositivos/sensores concretos. M03 (telemetría) tampoco consume
  hoy `umbrales_ambientales` para evaluar lecturas — confirmado buscando en
  `src/telemetry/`, sin resultados.

## Decisión de diseño

**Un solo estado de sincronización por umbral, no por dispositivo destino.** Modelar a qué
sensores/dispositivos concretos les corresponde un umbral requeriría inventar un mapeo
(especie+variable → sensores en fincas con esa especie) que no existe en ningún flujo actual del
sistema — sería adivinar un diseño que ni siquiera el consumidor natural (M03) tiene hoy. RF-17
además describe el estado en singular ("la configuración... queda Pendiente de Sincronización"),
no una lista de dispositivos.

**Adaptador stub, no un adaptador "real".** El contrato de publicación (destino, topic, payload,
confirmación, timeout) para propagar un umbral por especie+variable no existe — inventarlo
significaría adivinar la API de un servicio externo (`BROKER-MQTT-SGPMP`) que no controla este
repositorio. La propia lista de "Acciones requeridas" del incidente pide "definir el mecanismo
de publicación" como tarea aparte, confirmando que ese contrato no está definido todavía por
nadie. Se sigue el patrón ya documentado en `CLAUDE.md` ("Adaptador stub para dependencias
cruzadas"): `EdgeSincronizacionStubAdapter` degrada siempre a `PENDIENTE`, listo para
reemplazarse cuando el equipo de IoT defina el contrato real.

**HTTP 500 cuando el Edge no confirma — tal como lo exige RF-17, literal.** El flujo alterno
"Error de sincronización con el Nodo Edge" de RF-17 es explícito: si la propagación no queda
confirmada, el sistema debe guardar la configuración, marcarla "Pendiente de Sincronización" y
responder `500` con el mensaje del contrato. Una revisión anterior de este mismo fix decidió
apartarse de ese texto por consistencia con `ConfigurarRemotamenteUseCase` (RF-23), que sí trata
el broker caído como éxito — pero RF-23 no tiene ese mismo mandato explícito de HTTP en su propio
documento, así que no hay conflicto real entre RFs, solo entre dos decisiones de diseño posibles.
Ante RF-17 exigiéndolo por escrito, se sigue el texto del requerimiento: `RegistrarUmbralUseCase`
y `EditarUmbralUseCase` primero persisten el umbral y su `estado_sincronizacion` (dos commits,
igual que antes), y **luego** lanzan `InfrastructureError('FALLO_SINCRONIZACION_EDGE', ...)` si el
resultado no fue `APLICADA` — el dato nunca se pierde, solo la respuesta HTTP refleja el fallo de
sincronización tal como pide el RF.

> **Actualización — TC-M09-58-G22 (#459, 2026-09-26): `PENDIENTE` ya no responde 500.**
> El párrafo anterior decía "`500` si el resultado no fue `APLICADA`". Con el stub eso significa
> que **toda** alta o edición válida responde 500 (el stub nunca intenta propagar y devuelve
> siempre `PENDIENTE`), aunque no haya ningún fallo que reportar: QA lo reprodujo en los cuatro
> casos de TC-M09-G22 — el umbral queda guardado y el cliente recibe un error. El flujo alterno
> del RF-17 habla de una propagación que **falla**; "todavía no hay integración" no es eso.
>
> Criterio vigente (`ESTADOS_SINCRONIZACION_SIN_FALLO` en `registrar_umbral_use_case.py`):
>
> | `estado` del puerto | Significado | Respuesta |
> |---|---|---|
> | `APLICADA` | el Edge confirmó | 201 (alta) / 200 (edición) |
> | `PENDIENTE` | no se intentó o quedó encolado (hoy: sin contrato con IoT) | 201 / 200, con `estado_sincronizacion: "PENDIENTE"` en el cuerpo |
> | `NO_CONF` u otro | se intentó y falló (broker caído, timeout, sin ACK) | persiste y responde **500** `FALLO_SINCRONIZACION_EDGE` |
>
> Consecuencia para quien implemente el adaptador real: `EdgeSincronizacionPort` documenta que un
> fallo de comunicación debe devolver `NO_CONF`, **no** `PENDIENTE`; si no, el 500 del RF-17 se
> volvería a ocultar. El 500 se declara ahora en `responses` de `POST` y `PATCH` (OpenAPI).

## Fix

**Dominio:**
- `UmbralAmbiental` gana `estado_sincronizacion` (`PENDIENTE`/`APLICADA`/`NO_CONF`, mismo
  vocabulario que `ConfiguracionRemota`/RF-23), `fecha_ultima_sincronizacion`,
  `motivo_fallo_sincronizacion`, y los métodos `marcar_sincronizado`,
  `marcar_pendiente_sincronizacion`, `marcar_fallo_sincronizacion`.
- Nuevo puerto `EdgeSincronizacionPort.propagar_umbral(id_especie, id_variable_ambiental,
  payload) -> ResultadoEnvioMqtt` (reutiliza el mismo value object que `MqttPort`).
- `EdgeSincronizacionStubAdapter`: implementación stub, siempre `PENDIENTE`.

**Aplicación:** `RegistrarUmbralUseCase` y `EditarUmbralUseCase` llaman a `edge_port.propagar_umbral(...)`
**después** del commit de persistencia + auditoría (mismo patrón post-commit que
`ConfigurarRemotamenteUseCase`), y persisten el resultado en un segundo commit separado vía
`UmbralAmbientalRepository.actualizar_estado_sincronizacion` (no reescribe `niveles` ni
`valor_min`/`valor_max`).

**Infraestructura:**
- `SqlAlchemyUmbralAmbientalRepository`: mapea las 3 columnas nuevas en `guardar`/`actualizar`/
  `_a_entidad`, y agrega `actualizar_estado_sincronizacion`.
- `UmbralAmbientalResponse` expone `estado_sincronizacion`, `fecha_ultima_sincronizacion`,
  `motivo_fallo_sincronizacion` — resuelve el hallazgo puntual de QA ("no existe una vía para
  verificar...").

**Base de datos — migración `424e8d205792` (v5.4.0, sobre head `d014e2cc785d`):** agrega las 3
columnas a `modulo9.umbrales_ambientales` + `CHECK` sobre los 3 valores permitidos.
`estado_sincronizacion` arranca en `PENDIENTE` (`server_default`, también para filas ya
existentes: honesto, nunca hubo intento de sincronización antes de este cambio).

## 🔴 Requiere aprobación de DBA

`member_dev` (la credencial de aplicación) no tiene permiso de lectura sobre `alembic_version`
(`InsufficientPrivilege`), así que la sintaxis se validó primero en modo offline. Se hicieron
**dos rondas** de verificación con una credencial `dba` provista por el usuario, porque entre
ambas `dev` avanzó:

**Ronda 1 (17/09)**, contra head `d014e2cc785d`: `alembic upgrade head` aplicó limpio
(`d014e2cc785d -> 424e8d205792`), columnas y `CHECK` correctos, backfill de 13 filas a
`PENDIENTE`, `alembic downgrade d014e2cc785d` revirtió limpio.

**Ronda 2 (18/09)**, tras mergear `origin/dev`: entre la ronda 1 y esta, se mergeó a `dev` la
migración `1147428cd8fb` (precisión de umbrales, INC-M09-103-G28, de otro desarrollador) sobre
un `down_revision` distinto al de esta rama — dos heads divergentes. Se generó la migración de
reconciliación estándar `58a6bfab5ce6` (`alembic merge`, vacía, no toca ninguna tabla) antes de
poder verificar de nuevo:

| Comprobación | Resultado |
|---|---|
| `alembic heads` tras mergear `dev` | 2 heads (`1147428cd8fb`, `424e8d205792`) — no relacionados, columnas distintas |
| `alembic merge 1147428cd8fb 424e8d205792` | Generó `58a6bfab5ce6`, un solo head |
| `alembic current` (antes) | `1147428cd8fb` |
| `alembic upgrade head` | Aplicó limpio: `424e8d205792` + `58a6bfab5ce6` |
| Columnas creadas | `estado_sincronizacion` (`varchar(20)`, `NOT NULL`, default `'PENDIENTE'`), `fecha_ultima_sincronizacion` (`timestamptz`, nullable), `motivo_fallo_sincronizacion` (`text`, nullable) |
| `CHECK` constraint | `umbrales_ambientales_estado_sincronizacion_check` presente, sobre los 3 valores permitidos |
| Backfill de filas existentes | 13 filas, todas en `PENDIENTE` |
| `valor_min`/`valor_max` (migración del compañero) | Intactos en `NUMERIC(5,2)` antes y después — no se tocaron |
| `alembic downgrade` | Ver nota abajo — requirió un paso adicional |
| `alembic current` (después) | `1147428cd8fb` — BD queda exactamente como antes de la verificación |

**Nota sobre el downgrade:** el primer intento (`alembic downgrade 1147428cd8fb`) solo deshizo
el merge point y dejó la BD en ambos heads (`424e8d205792`, `1147428cd8fb`) — comportamiento
esperado en un mergepoint. El segundo intento apuntó mal al ancestro común
(`alembic downgrade d014e2cc785d`) y **revirtió de más**: además de `424e8d205792`, deshizo
también `1147428cd8fb` y las dos migraciones de RF-49 (`281e99d58ecb`, `1d7d6069da52`) que ya
eran parte legítima de `dev`, ajenas a este cambio. Se detectó de inmediato al revisar
`alembic current` y se corrigió con `alembic upgrade 1147428cd8fb`, que las reaplicó sin tocar
nada de esta rama — verificado después que `valor_min`/`valor_max` seguían en `NUMERIC(5,2)` y
que las 3 columnas de esta migración quedaron eliminadas. Se documenta el error para que quede
claro que un `downgrade` a un revision-id específico en un árbol con merge points debe apuntar
al punto exacto de la rama propia, no al ancestro común de todas las ramas.

Ninguna de las dos rondas reemplaza la aprobación formal del DBA — ambas veces la migración fue
revertida inmediatamente después de confirmar que corre limpio en ambas direcciones. El DBA debe
correr `alembic upgrade head` de forma definitiva antes de mergear.

## Pruebas

- `tests/configuration/test_inc_m09_104_g29_sincronizacion_edge_umbrales.py` (fakes sin BD):
  llamada al edge port con el payload correcto, persistencia de cada estado
  (`PENDIENTE`/`APLICADA`/`NO_CONF`) **antes** de responder, que `NO_CONF` y cualquier estado
  desconocido lanzan `InfrastructureError` (500) tras persistir — no antes —, que `APLICADA` y
  `PENDIENTE` no lanzan nada (#459), que `EditarUmbralUseCase` aplica el mismo criterio, que con
  el stub real el alta válida ya no responde 500, y el estado por defecto de un umbral nuevo.
- Mientras el contrato real del broker no exista, `EdgeSincronizacionStubAdapter` siempre
  devuelve `PENDIENTE`: las altas y ediciones responden 201/200 con `estado_sincronizacion:
  "PENDIENTE"` y el 500 solo aparecerá cuando un adaptador real reporte `NO_CONF`.

## Fuera de alcance

- **El contrato real de publicación hacia el broker MQTT para umbrales** (destino, topic,
  payload, ACK/timeout) — pendiente de definición con el equipo de IoT, tal como pide la propia
  lista de acciones requeridas del incidente. `EdgeSincronizacionStubAdapter` queda listo para
  reemplazarse cuando ese contrato exista.
- **Resolver qué dispositivos/sensores concretos reciben un umbral** — no hay ninguna relación
  ya modelada en el sistema para esto; construirla ahora sería adivinar un diseño de datos que
  ni el consumidor natural (M03) tiene todavía.
- **Consultar la configuración efectiva aplicada en el Edge en tiempo real** — el campo
  `estado_sincronizacion` refleja el resultado del último intento de propagación (mismo patrón
  que `ConfiguracionRemota.estado`), no una consulta en vivo al dispositivo; no existe ningún
  mecanismo de "consultar estado" en `MqttPort` ni en el broker real para replicar ese patrón.
