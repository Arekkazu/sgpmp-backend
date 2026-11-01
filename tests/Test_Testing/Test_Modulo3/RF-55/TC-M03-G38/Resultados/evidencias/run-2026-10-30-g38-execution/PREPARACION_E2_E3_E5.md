# Preparación consecutiva E2 → E3 → E5 (sin POST)

Fecha: 2026-10-30. Payloads **no modificados**. E6 fuera. BD y Edge no se tocan.

Revisión: `PREPARACION_E2.md`, `COMPROBACION_FINAL_E2.md` (umbral 65 y hash coincidían; monitor de comprobación ya cerrado; E2 pendiente de Bearer).

## Canal (igual para los tres)

| Pieza | Valor |
|---|---|
| Broker | TEST `https://sgpmp-brokertest-zyytic-0f1138-149-130-169-209.sslip.io/v1/commands` |
| Método | un `POST /v1/commands` **por** escenario |
| Gateway | `RASPBERRY3B-TEST` |
| Auth | **solo** `MQTT_BROKER_TOKEN` (cuadro `Get-Credential`). **Prohibido** `BROKER_SERVICE_TOKEN` |
| MQTT PUB | no |

## Payloads conservados

| Escenario | Archivo | Defecto |
|---|---|---|
| E2 | `payload_e2.json` | min=max=0 |
| E3 | `payload_e3.json` | precaución 70–70 |
| E5 | `payload_e5.json` | solo `normal` |

Los tres: `origen=umbral`, serial Gateway, id 65, `Humedad Relativa`, `version` `2026-10-07T00:00:00+00:00`.

## Orden cuando haya Bearer TEST verificado

1. Abrir monitor (`_mqtt_e2_monitor.py`) a `sgpmp/RASPBERRY3B-TEST/#` y `sgpmp/QA-M03-272-A-088894/#`; esperar Granted QoS 1; **dejarlo vivo**.
2. Antes de **cada** POST: `sudo -u sgpmp-edge cat` + `sha256sum`; version 65 y hash = preflight (`2026-10-08T21:11:56.393005+00:00` / `76c65da537337aefc8a01c1c963ecd168a6fece4560faa4e955307edfecd28c5`). Si no, **parar**.
3. Un POST (`_comando_umbral.py enviar e2` luego e3 luego e5). **No repetir** si timeout o `NO_CONF`.
4. Tras cada uno: ACK en `…/status` esperado `ERROR`; journal; hash. Si ACK `OK`, HTTP `APLICADA` o hash distinto: **parar** (no restaurar, no E3/E5 siguientes, no E6).
5. `PENDIENTE` HTTP ≠ prueba ejecutada.

Script de comprobación (0 POST): `ejecutar_g38_e2_e3_e5.ps1`. `-Enviar` **no** dispara envíos automáticos si el Bearer no está autorizado en el proceso.

## Estado ahora

`MQTT_BROKER_TOKEN` no verificado para TEST (ausente en el proceso). **Ningún POST.** E2, E3 y E5 quedan **preparados y pendientes**.
