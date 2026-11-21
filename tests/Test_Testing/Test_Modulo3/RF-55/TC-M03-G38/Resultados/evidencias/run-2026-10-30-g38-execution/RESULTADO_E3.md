# RESULTADO E3 — TC-M03-G38

Fecha UTC: 2026-10-30. Un solo `POST /v1/commands` con `payload_e3.json`. Continuación autorizada porque E2 produjo ACK `ERROR` y hash idéntico. Sin repetición. Sin PUBLISH MQTT de comando. Sin PATCH. Sin reinicio. Bearer vía `Get-Credential` (`MQTT_BROKER_TOKEN`); no impreso ni persistido. E6 no se ejecutó.

## Veredicto

**EJECUTADO — ACK ERROR, umbral no persistido.**

El Edge rechazó la banda `precaucion` de ancho 0 (70–70). Hash y versión del umbral 65 sin cambio.

## Condiciones previas (tras E2)

| Dato | Valor |
|---|---|
| Version en Pi | `2026-10-08T21:11:56.393005+00:00` |
| SHA256 | `76c65da537337aefc8a01c1c963ecd168a6fece4560faa4e955307edfecd28c5` |
| Coincide preflight | sí (`hash_e3_antes.json`) |

## Envío

- Endpoint: `https://sgpmp-brokertest-zyytic-0f1138-149-130-169-209.sslip.io/v1/commands`
- Payload: `payload_e3.json` (HR 40–98, precaución 70–70)
- Marca UTC de envío: `2026-10-30T21:53:47`

## HTTP

- Status: `200`
- `estado`: `NO_CONF`
- `config_version`: `null`
- Archivo: `http_e3_response.json`

## ACK MQTT

- Topic: `sgpmp/RASPBERRY3B-TEST/status`
- `tipo_mensaje`: `ACK_UMBRAL`
- `resultado`: `ERROR`
- `id_comando`: `2ef6cd393a3a4dbf9f39c58c463f51ba`
- `motivo`: `la banda precaucion debe tener ancho mayor que 0 (70–70)`
- `event_id`: `68e2a60f-f913-4f17-9e2d-854b50c6d262`
- ts monitor: `2026-10-30T21:53:50.784108+00:00`
- Archivo: `ack_e3.json`

## Journal (Edge)

```
2026-10-30 16:53:49,984 INFO edge_agent.agent: Umbral 65 (Humedad Relativa) → ERROR (la banda precaucion debe tener ancho mayor que 0 (70–70))
```

Archivo: `journal_e3.txt` (incluye también la línea de E2, journalctl acumulado).

## Hash y versión después

SHA256 `76c65da537337aefc8a01c1c963ecd168a6fece4560faa4e955307edfecd28c5`. Version `2026-10-08T21:11:56.393005+00:00`. Igual a preflight. `hash_e3_despues.json`.

Se continuó a E5 según procedimiento.
