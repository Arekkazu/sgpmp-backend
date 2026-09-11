# CU-08 – Gaps de BD para RF-23 (rangos por tipo de dispositivo, issue #1632)

Continuación del RF-23. Igual que el MVP MQTT (`cu08_gaps_bd_rf23_mqtt.md`),
este gap se gestiona por **Alembic**, no por DDL directo vía MCP postgres. La
fuente de verdad es la migración
`alembic/versions/b1c4a7e9d2f3_rf23_rangos_tipo_dispositivo.py` (sobre el head
`192872fafd40`, la migración RF-16).

## Contexto del issue #1632

El issue pedía tres cosas; **dos ya estaban implementadas** en el MVP del
2026-08-20:

1. Timeout de ACK de 30s → estado `No Confirmado` → HTTP 504. **Ya existía.**
   El timeout de 30s vive en `BROKER-MQTT-SGPMP` (`MQTT_ACK_TIMEOUT_SECONDS`);
   el backend ya consume el veredicto `NO_CONF` y lo mapea a
   `GatewayTimeoutError` (504) en `dispositivo_iot_router.py`.
2. Estado explícito `No Confirmado`. **Ya existía** como `NO_CONF` (entidad,
   `CHECK` de `configuraciones_remotas.estado`, mapeo del router).
3. Rangos de configuración por tipo de dispositivo. **Este era el gap real** y
   es lo que agrega esta entrega.

## Gap de BD y decisión

`modulo9.dispositivos_iot` no tenía columna de tipo, y la validación de
`frecuencia_captura`/`intervalo_transmision` era un mínimo fijo de 1 minuto en
el DTO, sin diferenciación por hardware.

## Migración RF-23 rangos (`b1c4a7e9d2f3`)

1. Tabla `modulo9.tipos_dispositivo_iot`:
   `id_tipo_dispositivo` PK, `nombre` UNIQUE, `frecuencia_captura_min/max`,
   `intervalo_transmision_min/max`, `fecha_creacion`. Dos `CHECK`: cada
   `_min >= 1` y `_max >= _min`.
2. Seed de 3 tipos. **Los rangos son la perilla de calibración** (ilustrativos,
   se ajustan por SQL según hardware real — `# ponytail:` en la migración):
   - `GENERICO`: freq 1..1440, intervalo 1..1440 (replica el mínimo-1 previo).
   - `NODO_BAJO_CONSUMO`: freq 15..1440, intervalo 15..1440.
   - `SENSOR_AMBIENTAL`: freq 5..120, intervalo 5..240.
3. Columna `dispositivos_iot.id_tipo_dispositivo`: se agrega **nullable**, se
   hace **backfill** de todos los dispositivos existentes a `GENERICO`, se pasa
   a **NOT NULL** y se crea la FK. (Decisión NOT NULL + backfill: cada
   dispositivo tiene siempre un tipo con rangos válidos, sin rama de fallback.)

`downgrade()` inverso (drop FK/columna, drop tabla).

## Dónde vive (no en el broker)

Rangos por tipo es responsabilidad del **backend**: el broker
`BROKER-MQTT-SGPMP` no tiene tabla de configuración ni noción de tipo de
dispositivo (es un gateway de protocolo delgado). No se tocó ese repo.

## RBAC

Sin recurso nuevo. Se reutiliza `id_recurso=11` (`dispositivos_iot`):
- Registrar dispositivo con tipo: acción C=1 (ya existente).
- Configurar con validación de rango: acción U=3 (ya existente).
- `GET /configuracion/tipos-dispositivo-iot`: acción R=2 (ya existente; la
  tienen Admin/Prod/Ing).

## Nota sobre la BD `pruebas`

La BD `pruebas` (tests de integración) sigue **sin el schema `modulo9`**
(documentado en `cu08_gaps_bd_rf23_mqtt.md`), así que no hay tests de
integración de módulo 9. La cobertura de esta entrega es **unit tests con
fakes**: `tests/configuration/test_rf23_rangos_tipo_dispositivo.py`.
