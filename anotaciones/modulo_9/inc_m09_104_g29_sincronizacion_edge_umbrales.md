# INC-M09-104-G29 — Umbrales no se propagan al Nodo Edge ni gestionan fallos de sincronización

**RF:** RF-17 (CU03 — Configurar Umbrales y Alertas Ambientales). **Grupo:** TC-M09-G29.
**Casos:** TC-M09-62 (propagación), TC-M09-63 (fallo de sincronización). **Severidad:** Severo.

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

**Nunca HTTP 500 por fallo de sincronización — decisión explícita del usuario.** RF-17 describe
literalmente un `500` para este escenario, pero el mismo problema (broker MQTT externo caído o
sin ACK) ya está resuelto en este backend para RF-23 (`ConfigurarRemotamenteUseCase`), donde el
resultado `PENDIENTE`/`NO_CONF` **nunca** es un error del cliente — la petición sí tuvo éxito
(la configuración quedó guardada), solo la aplicación en el dispositivo queda pendiente. Se
prioriza consistencia entre dos flujos que resuelven exactamente el mismo problema técnico sobre
seguir literalmente un RF que no conocía ese patrón ya establecido en el código.

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

Esta migración **no se pudo verificar contra una base real**: `member_dev` (la única credencial
disponible en este entorno) no tiene permiso de lectura sobre `alembic_version`
(`InsufficientPrivilege`), así que ni `alembic upgrade head` ni `alembic current` pudieron
ejecutarse contra `sgpmp_dev`. Se validó únicamente la sintaxis generando el SQL en modo offline
(`alembic upgrade ... --sql`, sin tocar ninguna base):

```sql
ALTER TABLE modulo9.umbrales_ambientales ADD COLUMN estado_sincronizacion VARCHAR(20) DEFAULT 'PENDIENTE'::character varying NOT NULL;
ALTER TABLE modulo9.umbrales_ambientales ADD COLUMN fecha_ultima_sincronizacion TIMESTAMP WITH TIME ZONE;
ALTER TABLE modulo9.umbrales_ambientales ADD COLUMN motivo_fallo_sincronizacion TEXT;
ALTER TABLE modulo9.umbrales_ambientales ADD CONSTRAINT umbrales_ambientales_estado_sincronizacion_check CHECK (estado_sincronizacion IN ('PENDIENTE', 'APLICADA', 'NO_CONF'));
```

El `downgrade()` es simétrico (genera el `DROP` inverso exacto, verificado igual en modo
offline). El DBA debe correr `alembic upgrade head` con una credencial con permisos DDL antes de
mergear, y confirmar el resultado contra `sgpmp_dev`/`sgpmp_test` reales.

## Pruebas

- `tests/configuration/test_inc_m09_104_g29_sincronizacion_edge_umbrales.py` (nuevo, 10 casos,
  fakes sin BD): llamada al edge port con el payload correcto, persistencia de cada estado
  (`PENDIENTE`/`APLICADA`/`NO_CONF`), confirmación de que ningún resultado del edge port lanza
  excepción ni produce 500, que el umbral queda guardado antes del intento de propagación, que
  `EditarUmbralUseCase` también re-propaga, que el stub siempre degrada a `PENDIENTE`, y el
  estado por defecto de un umbral recién creado.
- Suite completa `tests/configuration -m "not integration"`: 246 passed (236 previos + 10
  nuevos).
- Suite completa `tests -m "not integration"`: 697 passed, mismos 2 fallos preexistentes en
  `test_registrar_transferencia_use_case.py` (no relacionados, ya documentados en el repo).

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
