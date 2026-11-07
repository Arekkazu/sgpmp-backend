# Comprobación final E2 — 2026-10-30 (tarde)

**Sin `-Enviar`. Sin POST. Sin E3/E5/E6.** Token de broker no pedido ni leído.

## Procedimiento

`PREPARACION_E2.md` + `ejecutar_e2.ps1` (sin switch): broker TEST, `POST /v1/commands`, serial `RASPBERRY3B-TEST`, payload `payload_e2.json`. Salida: `Sin -Enviar: no hay POST ni cuadro de credencial.`

Entrada segura: `Get-Credential` **solo** si se usa `-Enviar`. El Bearer no está en env Windows (`MQTT_BROKER_TOKEN` UNSET). No se recuperaron secretos del chat ni de `/etc/sgpmp`.

## Monitor MQTT (sesión de comprobación)

`mqtt_prep_final_session.json`, 2026-10-30T21:30:10Z, usuario de monitorización (no el Bearer HTTP):

| Topic | SUBACK |
|---|---|
| `sgpmp/RASPBERRY3B-TEST/#` | Granted QoS 1 |
| `sgpmp/QA-M03-272-A-088894/#` | Granted QoS 1 |

CONNECT rc 0. Esa sesión **ya cerró** (timeout 60 s). Para el POST real hay que abrir otra igual **antes** de `-Enviar`.

## Umbral 65 vs preflight

`reconfirm_umbral65.json` (SSH `sudo -S -u sgpmp-edge cat` + `sha256sum`; sin PTY):

| Campo | Preflight | Ahora | ¿Igual? |
|---|---|---|---|
| version | `2026-10-08T21:11:56.393005+00:00` | igual | sí |
| variable | `Humedad Relativa` | igual | sí |
| SHA256 | `76c65da537337aefc8a01c1c963ecd168a6fece4560faa4e955307edfecd28c5` | igual | sí |

No aplica detenerse por divergencia.

## Estado de E2

**PENDIENTE** de Bearer renovado y autorizado para TEST, más un monitor vivo en el momento del único POST.
