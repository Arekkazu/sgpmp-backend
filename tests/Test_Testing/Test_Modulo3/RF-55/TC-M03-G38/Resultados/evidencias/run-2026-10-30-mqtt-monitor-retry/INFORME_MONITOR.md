# MQTT v5 — monitor `sgpmp_gateway_test` (reintento)

Fecha UTC: 2026-10-30. Paho MQTT v5. `client_id` QA `qa-g38-mon-retry-1793371642`. **Sin PUBLISH.** G38 no ejecutado.

## User env

| Variable | Estado |
|---|---|
| MQTT_HOST | SET (`149.130.169.209`) |
| MQTT_HOST_PORT | SET (`1886`) |
| MQTT_USERNAME | SET (`sgpmp_gateway_test`) |
| MQTT_PASSWORD | SET, longitud **24** (cuadro Windows; no copiada) |
| MQTT_TOPIC_PREFIX | SET (`sgpmp`) |

## CONNECT

**rc 0 Success.** session_present false. Cierre: **0 Normal disconnection.**

## Suscripciones QoS 1

| Topic | mid | SUBACK |
|---|---|---|
| sgpmp/RASPBERRY3B-TEST/# | 1 | **Concedida** Granted QoS 1 |
| sgpmp/QA-M03-272-A-088894/# | 2 | **Concedida** Granted QoS 1 |

## Mensajes (60 s)

| UTC | Topic | tipo |
|---|---|---|
| 2026-10-30T14:47:25.453521+00:00 (campo fecha_registro) | sgpmp/RASPBERRY3B-TEST/heartbeat | HEARTBEAT |
| 2026-10-30T14:48:02.363847+00:00 | sgpmp/QA-M03-272-A-088894/heartbeat | HEARTBEAT |

**2 mensajes.** Firmware en ambos: `v0.4.0-rc.2`. Buffer INACTIVO, 0 pendientes. `sensores_operativos`: `rf55_2` operativo. Reloj sincronizado.

No hubo `evento` ni `telemetry` ni `status` en esta ventana (heartbeat ~300 s). El monitor **sí** lee el tráfico de ambos seriales.

Raw: `mqtt-session.json` (sin contraseña).
