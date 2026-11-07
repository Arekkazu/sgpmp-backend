# MQTT suscripción solo lectura — 2026-10-30

Objetivo: CONNECT + SUBACK QoS 1 a `sgpmp/+/evento|telemetry|heartbeat|status` contra `149.130.169.209:1886`. Sin publish.

## Variables (SET/UNSET)

| Variable | Proceso | HKCU User | Machine |
|---|---|---|---|
| MQTT_HOST | UNSET | UNSET | UNSET |
| MQTT_HOST_PORT | UNSET | UNSET | UNSET |
| MQTT_USERNAME | UNSET | UNSET | UNSET |
| MQTT_PASSWORD | UNSET | UNSET | UNSET |
| MQTT_TOPIC_PREFIX | UNSET | UNSET | UNSET |

## Resultado

**No se abrió sesión MQTT.** Las credenciales no están en el entorno de este proceso ni en las variables de usuario persistentes. No hay CONNECT, SUBACK ni mensajes. No se ejecutó G38.

Broker TCP TEST conocido de diagnósticos previos: `149.130.169.209:1886` (no reautenticado en esta corrida).
