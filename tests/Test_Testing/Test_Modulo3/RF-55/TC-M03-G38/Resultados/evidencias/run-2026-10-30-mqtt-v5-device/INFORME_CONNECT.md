# MQTT v5 TEST — credencial de dispositivo RASPBERRY3B-TEST

Fecha UTC: 2026-10-30. Cliente paho MQTT **v5**. Solo CONNECT + (si hubiera sesión) SUB QoS 1. **Sin PUBLISH.** G38 no ejecutado.

## Variables User (SET/UNSET)

| Variable | User | Comprobado |
|---|---|---|
| MQTT_HOST | SET | valor esperado 149.130.169.209 |
| MQTT_HOST_PORT | SET | 1886 |
| MQTT_USERNAME | SET | RASPBERRY3B-TEST |
| MQTT_PASSWORD | SET | rotada vía cuadro Windows; no copiada |
| MQTT_TOPIC_PREFIX | SET | sgpmp |

## CONNECT

- Broker: `149.130.169.209:1886`
- **rc 135** (`0x87`) **Not authorized**
- session_present: false
- TCP/CONNACK: el broker respondió; **rechazó** usuario/contraseña (o política de autorización)
- Tras el rechazo: disconnect 128 Unspecified error. Un reintento del cliente, mismo 135.

## SUBSCRIBE (no enviados)

| Topic | Resultado |
|---|---|
| sgpmp/+/evento | no enviado (sin sesión) |
| sgpmp/+/telemetry | no enviado |
| sgpmp/+/heartbeat | no enviado |
| sgpmp/+/status | no enviado |

## Mensajes

0 en 60 s.

## Conclusión

Autenticación **sigue fallando** con la credencial de dispositivo en User. No es el usuario `sgpmp_gateway_test` de la corrida anterior (carpeta `run-2026-10-30-mqtt-sub-readonly`, no modificada).

Siguiente: confirmar con Sergio que la contraseña rotada está activa en dynsec TEST y que el usuario MQTT es exactamente `RASPBERRY3B-TEST` (el edge-agent usa `client_id` `edge-RASPBERRY3B-TEST`; esta prueba usó un `client_id` QA distinto, lo habitual).

Raw: `mqtt-sub-session.json` (sin contraseña).
