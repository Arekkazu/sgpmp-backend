# MQTT v5 — monitor `sgpmp_gateway_test`

Fecha UTC: 2026-10-30. Paho MQTT v5. `client_id` QA `qa-g38-mon-1793371003`. **Sin PUBLISH.** G38 no ejecutado.

## User env (SET, sin valores)

| Variable | Estado |
|---|---|
| MQTT_HOST | SET (conservado) |
| MQTT_HOST_PORT | SET (conservado) |
| MQTT_USERNAME | SET → `sgpmp_gateway_test` |
| MQTT_PASSWORD | SET, longitud 32 (cuadro Windows) |
| MQTT_TOPIC_PREFIX | SET (conservado) |

## CONNECT

- `149.130.169.209:1886`
- **rc 135 Not authorized**
- session_present: false
- Luego disconnect 128 Unspecified error
- **No SUBSCRIBE** (sin sesión)

## Topics previstos (no enviados)

| Topic | SUBACK |
|---|---|
| sgpmp/RASPBERRY3B-TEST/# | no enviado |
| sgpmp/QA-M03-272-A-088894/# | no enviado |

Escucha 60 s: **0 mensajes.** Heartbeats: **no observados.**

## Lectura

La sesión de **dispositivo** `RASPBERRY3B-TEST` (clave 32) sí dio CONNECT 0. Con **`sgpmp_gateway_test`** y otra clave de 32 caracteres el broker **rechaza** CONNECT. Confirmar con Sergio/Danna la contraseña **específica** de `sgpmp_gateway_test` (no reutilizar la del serial).

Raw: `mqtt-session.json` (sin contraseña).
