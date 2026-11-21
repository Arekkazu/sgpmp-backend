# MQTT v5 TEST — reintento con clave de 32 caracteres

Fecha UTC: 2026-10-30. Paho MQTT v5. `client_id` QA `qa-g38-v5-retry-1793369661` (no es `edge-RASPBERRY3B-TEST`). **Sin PUBLISH.** G38 no ejecutado.

## Variables (SET, sin valores)

| Variable | Proceso |
|---|---|
| MQTT_HOST | SET |
| MQTT_HOST_PORT | SET |
| MQTT_USERNAME | SET (`RASPBERRY3B-TEST`) |
| MQTT_PASSWORD | SET (longitud 32) |
| MQTT_TOPIC_PREFIX | SET |

## CONNECT

- Broker `149.130.169.209:1886`
- **rc 0 Success**
- session_present: false
- Disconnect al final: **0 Normal disconnection**

La clave de 32 caracteres **autoriza** la sesión. El 135 anterior era la contraseña incompleta.

## SUBSCRIBE QoS 1 (por topic)

| Topic | mid | SUBACK |
|---|---|---|
| sgpmp/+/evento | 1 | **135 Not authorized** |
| sgpmp/+/telemetry | 2 | **135 Not authorized** |
| sgpmp/+/heartbeat | 3 | **135 Not authorized** |
| sgpmp/+/status | 4 | **135 Not authorized** |

ACL de credencial **por Gateway**: no cubre el comodín `+` (otros seriales). Sergio se suscribe a `sgpmp/<serial>/…` del propio Edge.

Escucha 60 s: **0 mensajes** (SUB no concedido).

## Siguiente (cuando se autorice)

Suscribir **solo** seriales del lab, p. ej.:

- `sgpmp/RASPBERRY3B-TEST/{evento,telemetry,heartbeat,status,command}`
- `sgpmp/QA-M03-272-A-088894/{evento,telemetry,heartbeat,status}` si la ACL del Gateway lo permite.

Raw: `mqtt-sub-session.json` (sin contraseña).
