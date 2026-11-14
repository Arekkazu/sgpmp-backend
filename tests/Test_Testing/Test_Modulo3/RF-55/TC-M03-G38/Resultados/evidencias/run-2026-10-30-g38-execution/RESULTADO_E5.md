# RESULTADO E5 — TC-M03-G38

Fecha UTC: 2026-10-30. Un solo `POST /v1/commands` con `payload_e5.json`. Continuación autorizada porque E3 produjo ACK `ERROR` y hash idéntico. Sin repetición. Sin PUBLISH MQTT de comando. Sin PATCH. Sin reinicio. Bearer vía `Get-Credential` (`MQTT_BROKER_TOKEN`); no impreso ni persistido. **E6 no se ejecutó.**

## Veredicto

**EJECUTADO — ACK ERROR, umbral no persistido.**

El Edge rechazó el comando porque `niveles` traía solo `normal` (faltan `precaucion` y `critico`). Hash y versión del umbral 65 sin cambio.

## Condiciones previas (tras E3)

| Dato | Valor |
|---|---|
| Version en Pi | `2026-10-08T21:11:56.393005+00:00` |
| SHA256 | `76c65da537337aefc8a01c1c963ecd168a6fece4560faa4e955307edfecd28c5` |
| Coincide preflight | sí (`hash_e5_antes.json`) |

## Envío

- Endpoint: `https://sgpmp-brokertest-zyytic-0f1138-149-130-169-209.sslip.io/v1/commands`
- Payload: `payload_e5.json` (solo nivel `normal` 40–98)
- Marca UTC de envío: `2026-10-30T21:54:30`

## HTTP

- Status: `200`
- `estado`: `NO_CONF`
- `config_version`: `null`
- Archivo: `http_e5_response.json`

## ACK MQTT

- Topic: `sgpmp/RASPBERRY3B-TEST/status`
- `tipo_mensaje`: `ACK_UMBRAL`
- `resultado`: `ERROR`
- `id_comando`: `523e5cea5c0a4b618d44beb21c378523`
- `motivo`: `niveles debe traer normal, precaucion y critico, una vez cada uno`
- `event_id`: `2374832a-5f85-4fb0-8546-c6c4d9085e61`
- ts monitor: `2026-10-30T21:54:33.900664+00:00`
- Archivo: `ack_e5.json`

## Journal (Edge)

```
2026-10-30 16:54:33,098 INFO edge_agent.agent: Umbral 65 (Humedad Relativa) → ERROR (niveles debe traer normal, precaucion y critico, una vez cada uno)
```

Archivo: `journal_e5.txt` (incluye líneas de E2 y E3).

## Hash y versión después

SHA256 `76c65da537337aefc8a01c1c963ecd168a6fece4560faa4e955307edfecd28c5`. Version `2026-10-08T21:11:56.393005+00:00`. Igual a preflight. `hash_e5_despues.json`, `HASH_FINAL.txt`.

No se restauró `umbrales.json` porque no hubo cambio. No se reinició el Edge.
