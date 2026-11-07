# RESULTADO E2 — TC-M03-095 / G38

Fecha UTC: 2026-10-30. Un solo `POST /v1/commands` con `payload_e2.json`. Sin repetición. Sin PUBLISH MQTT de comando. Sin PATCH. Sin reinicio. Bearer vía `Get-Credential` (`MQTT_BROKER_TOKEN`); no impreso ni persistido. E6 no se ejecutó.

## Veredicto

**EJECUTADO — ACK ERROR, umbral no persistido.**

El Edge rechazó el comando por `valor_min` / `valor_max` iguales (0 y 0). El SHA256 de `/var/lib/sgpmp-edge/umbrales.json` y la versión del umbral 65 permanecieron iguales al preflight. El broker HTTP devolvió `NO_CONF` (timeout de confirmación al broker); la confirmación concluyente es el `ACK_UMBRAL` MQTT en `status`, no el campo HTTP `estado`.

No es APROBADO de configuración aplicada. No es ACK `OK`. No es `APLICADA`.

## Condiciones previas (coinciden con preflight)

| Dato | Valor |
|---|---|
| Gateway | `RASPBERRY3B-TEST` |
| Umbral | ID 65, `Humedad Relativa` |
| Version en Pi | `2026-10-08T21:11:56.393005+00:00` |
| SHA256 | `76c65da537337aefc8a01c1c963ecd168a6fece4560faa4e955307edfecd28c5` |
| Version en payload | `2026-10-07T00:00:00+00:00` (intencional, más antigua) |
| Monitor Paho | activo (`mqtt_e2e_session.json`) |

## Envío

- Endpoint: `https://sgpmp-brokertest-zyytic-0f1138-149-130-169-209.sslip.io/v1/commands`
- Payload: `payload_e2.json` (tres bandas 0–0, `valor_min`=`valor_max`=0)
- Marca UTC de envío: `2026-10-30T21:53:05`

## HTTP

- Status: `200`
- `estado`: `NO_CONF`
- `mensaje`: El comando fue enviado pero el dispositivo no confirmó la recepción a tiempo.
- `config_version`: `null`
- Archivo: `http_e2_response.json`

El HTTP `NO_CONF` no se interpretó como ausencia de ACK: el monitor ya tenía SUB y el ACK MQTT llegó ~4 s después del POST (el broker espera más tiempo al dispositivo para marcar `APLICADA`).

## ACK MQTT

- Topic: `sgpmp/RASPBERRY3B-TEST/status`
- `tipo_mensaje`: `ACK_UMBRAL`
- `resultado`: `ERROR`
- `id_comando`: `a1725d6e5d0a4f1891f0a061da2a2da2`
- `motivo`: `valor_min y valor_max deben ser números con valor_min < valor_max`
- `event_id`: `73a8cf3e-49ed-4d4c-beef-e164ab543fd6`
- ts monitor: `2026-10-30T21:53:09.252345+00:00`
- Archivo: `ack_e2.json`

## Journal (Edge)

```
2026-10-30 16:53:08,413 INFO edge_agent.agent: Umbral 65 (Humedad Relativa) → ERROR (valor_min y valor_max deben ser números con valor_min < valor_max)
```

Hora local Pi (UTC−5). Archivo: `journal_e2.txt`.

## Hash y versión después

| Campo | Después de E2 |
|---|---|
| SHA256 | `76c65da537337aefc8a01c1c963ecd168a6fece4560faa4e955307edfecd28c5` |
| Version umbral 65 | `2026-10-08T21:11:56.393005+00:00` |
| Igual a preflight | sí |

Archivos: `hash_e2_antes.json`, `hash_e2_despues.json`.

## Paradas

Ninguna de las paradas obligatorias se activó (no hubo ACK `OK`, no `APLICADA`, hash intacto, versión no nula, ACK ERROR concluyente, autenticación HTTP 200).

Se continuó a E3 según procedimiento.
