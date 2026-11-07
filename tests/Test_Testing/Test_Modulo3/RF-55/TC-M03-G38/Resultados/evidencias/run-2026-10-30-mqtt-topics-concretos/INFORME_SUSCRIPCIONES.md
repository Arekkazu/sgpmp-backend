# MQTT v5 — ACL topics concretos (Gateway y nodo)

Fecha UTC: 2026-10-30. Paho MQTT v5. `client_id` QA `qa-g38-acl-1793369831` (no interfiere con `edge-RASPBERRY3B-TEST`). Usuario `RASPBERRY3B-TEST`. **Sin PUBLISH.** G38 no ejecutado.

## CONNECT

- Host/puerto desde env User → `149.130.169.209:1886`
- **rc 0 Success**, session_present false
- Fin: disconnect **0 Normal disconnection**
- Errores de red: ninguno

## SUBACK por topic (QoS 1 pedido)

Concedida = reason 0/1/2. Rechazada = 135 Not authorized.

| Topic | mid | Resultado |
|---|---|---|
| sgpmp/RASPBERRY3B-TEST/evento | 1 | **Rechazada** (135) |
| sgpmp/RASPBERRY3B-TEST/telemetry | 2 | **Rechazada** (135) |
| sgpmp/RASPBERRY3B-TEST/heartbeat | 3 | **Rechazada** (135) |
| sgpmp/RASPBERRY3B-TEST/status | 4 | **Rechazada** (135) |
| sgpmp/QA-M03-272-A-088894/evento | 5 | **Rechazada** (135) |
| sgpmp/QA-M03-272-A-088894/telemetry | 6 | **Rechazada** (135) |
| sgpmp/QA-M03-272-A-088894/heartbeat | 7 | **Rechazada** (135) |
| sgpmp/QA-M03-272-A-088894/status | 8 | **Rechazada** (135) |

**0/8 concedidas.** Escucha 60 s: **0 mensajes**.

## Lectura ACL

La credencial del Gateway **puede conectar** y, por diseño dynsec, suele **publicar** telemetría/evento/heartbeat/status y **suscribir** `command`. QA intentó **SUB** a topics de subida: el broker responde 135. Encaja con `mosquitto_sub` de Sergio a `sgpmp/<serial>/command`, no a `telemetry`.

Para observar G38 (`evento`/`telemetry`) hace falta un usuario con permiso de **lectura** en esos topics (p. ej. rol de broker/gateway de plataforma), no la credencial del dispositivo.

Raw: `mqtt-session.json` (sin contraseña).
