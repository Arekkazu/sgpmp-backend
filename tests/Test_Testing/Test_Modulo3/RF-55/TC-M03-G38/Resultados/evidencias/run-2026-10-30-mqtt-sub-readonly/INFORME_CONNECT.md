# MQTT TEST — CONNECT y suscripción solo lectura

Fecha (UTC): 2026-10-30. Cliente: `paho-mqtt` 2.x, MQTT v3.1.1, mismo patrón que G69 (`username_pw_set` + `connect`). **Sin PUBLISH.** No se ejecutó G38.

## Variables

Leídas desde ámbito User hacia el proceso. Informe SET/UNSET, sin valores:

| Variable | Durante la corrida |
|---|---|
| MQTT_HOST | SET |
| MQTT_HOST_PORT | SET |
| MQTT_USERNAME | SET |
| MQTT_PASSWORD | SET |
| MQTT_TOPIC_PREFIX | SET |

Destino usado (no secreto): host `149.130.169.209`, puerto `1886`, prefijo `sgpmp`.

## CONNECT

- **Código:** `135` (`0x87`)
- **Motivo del broker:** `Not authorized`
- **session_present:** false
- TCP al broker **sí** (el CONNACK llegó). Fallo de **autenticación/autorización**, no de red.

El cliente reintentó varias veces y siempre recibió el mismo CONNACK 135, luego disconnect `128` Unspecified error. **No hay SUBACK.** **0 mensajes.**

## SUBSCRIBE (no enviados)

Patrones previstos QoS 1 (no se enviaron porque CONNECT no fue aceptado):

- `sgpmp/+/evento`
- `sgpmp/+/telemetry`
- `sgpmp/+/heartbeat`
- `sgpmp/+/status`

## Mensajes

Ninguno.

## Conclusión

**Bloqueado en CONNECT.** Credenciales User presentes pero el broker TEST **rechaza** la sesión (`Not authorized`). No se publica, no se cambia umbral, no G38.

Posibles causas (sin probar más): contraseña User distinta de la de Mosquitto TEST; usuario sin permiso en dynsec; mezcla con DEV. Revalidar `MQTT_PASSWORD` con Danna (prompt seguro, no chat).

Raw: `mqtt-sub-session.json` (sin contraseña).
