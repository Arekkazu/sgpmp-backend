# Preflight G38 — 2026-10-29 (America/Bogota)

Tipo de prueba intentada: **integración MQTT real + E2E backend TEST**.  
No se publicó en MQTT. No se modificaron umbrales ni BD.

## Destino

| Recurso | Cómo se identificó TEST | Resultado |
|---|---|---|
| Gateway HTTP broker | Hostname `sgpmp-brokertest-…sslip.io` (confirmado 2026-10-25 por Alexander Lozada) | `GET /v1/healthz` → HTTP 200 `{"status":"ok"}` (2026-10-29) |
| Backend API | Hostname `sigab-backendtest-…sslip.io` (`SGPMP-FRONT-END-PWA/.env` `VITE_API_BASE_URL`) | `GET /api-sgpmp-test/health` → HTTP 200 `{"status":"ok"}` |
| Listener MQTT TCP | Requiere `MQTT_HOST` + `MQTT_HOST_PORT` (código G69: `paho.connect(MQTT_HOST, MQTT_PORT)`) | **No comprobado**: variables UNSET. No se inventó el puerto. |
| Firmware en Pi | Tags de `main` | **No hay Pi en este entorno.** Copia local en `_consultas/EDGE-FIRMWARE-SGPMP` está en `main` `a90bb78` (sin clasificador). |

## Firmware (repositorio real)

| Ref | SHA | Clasificador RF-55 |
|---|---|---|
| `main` (copia local HEAD) | `a90bb78ea691cfab8e720aae764ba89d9859a1eb` | Ausente (`reglas/evaluador.py` no existe) |
| `develop` / `v0.4.0-rc.2` | `e618a75f39d7b64bdabae4b3112490aca7ff628b` | Presente (solo en remoto `origin/develop`, no instalado aquí) |

`EDGE_SOURCE=fake` está soportado en `develop` (`Settings.from_env`, default `fake`). En `main` también existe `fake`, pero **sin** evaluación RF-55.

## Variables (presencia; sin valores)

UNSET en proceso, User y Machine, y no hay `.env` / `.env.test` en `sgpmp-backend` ni `edge-agent.env` local:

`DATABASE_URL`, `MQTT_USERNAME`, `MQTT_PASSWORD`, `MQTT_HOST_PORT`, `MQTT_HOST`, `MQTT_DEVICE_USERNAME`, `MQTT_DEVICE_PASSWORD`, `MQTT_TOPIC_PREFIX`, `MQTT_WS_HOST_PORT`, `BACKEND_URL`, `BROKER_SERVICE_TOKEN`, `MQTT_BROKER_URL`, `MQTT_BROKER_TOKEN`, `EDGE_MQTT_HOST`, `EDGE_MQTT_PORT`, `EDGE_MQTT_USERNAME`, `EDGE_MQTT_PASSWORD`, `EDGE_SERIALS`, `EDGE_SOURCE`, `EDGE_IT_API_URL`, `EDGE_IT_API_TOKEN`.

### Puertos (código, no valores de ambiente)

| Variable | Uso | Código |
|---|---|---|
| `MQTT_HOST` + `MQTT_HOST_PORT` | Cliente MQTT QA/paho hacia Mosquitto TEST | `test_tc_m09_g69_protocolo_mqtt_reintento1.py` |
| `EDGE_MQTT_HOST` + `EDGE_MQTT_PORT` | `edge_agent` (default 1883 sin CA, 8883 con CA) | `edge_agent/config.py` en firmware |
| `MQTT_BROKER_URL` | HTTP backend → `POST {url}/v1/commands` | `mqtt_http_adapter.py` |
| `MQTT_WS_HOST_PORT` | WebSocket; no lo usa el clasificador Edge | — |

No se igualó `MQTT_HOST_PORT` a `EDGE_MQTT_PORT`. Sin valores no se abrió TCP.

## Seriales

`EDGE_SERIALS` UNSET. No hay serial de Gateway ni de nodo de laboratorio en este workspace. No se inventaron.

## Decisión

**Detener** publicación de comandos, PATCH de umbrales, inyección de lecturas y pytest de aprobación. Motivo: sin credenciales MQTT, sin seriales de lab, sin agente `e618a75` en ejecución.
