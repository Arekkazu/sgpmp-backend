# Comprobación pre-E2 (solo lectura) — 2026-10-30

**No se envió POST /v1/commands. No hay PUBLISH MQTT. E6 no ejecutado. Token de broker no usado ni guardado.**

## 1. Umbral 65

| Campo | Valor leído |
|---|---|
| id_umbral_ambiental | 65 |
| variable | `Humedad Relativa` |
| **version** | **`2026-10-08T21:11:56.393005+00:00`** |
| unidad | % |
| valor_min / valor_max | 40.0 / 98.0 |
| comando_id | `6743369e531944bea216d5511a4a554c` |

`version` **no es null**, está presente y es ISO-8601 con zona. **No se detiene** por el criterio de version. Sí se **detiene** aquí porque falta autorización explícita para publicar E2.

Método: SSH `sgpmp@100.96.29.65`, `sudo -S -u sgpmp-edge` (NOPASSWD/`-n` respondió *password is required*). Un eco de PTY se redactó en la evidencia; no hay token ni contraseña en los JSON de payload.

## 2. Hash inicial

```
76c65da537337aefc8a01c1c963ecd168a6fece4560faa4e955307edfecd28c5  /var/lib/sgpmp-edge/umbrales.json
```

El intento `sudo -n | sha256sum` produjo el hash de cadena vacía (`e3b0c442…`) y **se descarta**.

## 3. Monitor MQTT

No había un proceso Paho persistente de la sesión anterior. Se abrió **una sesión nueva** (v5, `sgpmp_gateway_test`, ~12 s, **sin PUBLISH**):

| Comprobación | Resultado |
|---|---|
| CONNECT | rc **0** Success |
| `sgpmp/RASPBERRY3B-TEST/#` | SUBACK **Granted QoS 1** (mid 1) |
| `sgpmp/QA-M03-272-A-088894/#` | SUBACK **Granted QoS 1** (mid 2) |
| Mensajes en 12 s | 0 |

El usuario de monitorización **sigue autorizado**. Las suscripciones de esta comprobación se cerraron al disconnect (normal). Para E2 hará falta un monitor **abierto durante el POST**.

## 4. Payloads preparados (no enviados)

`version` en los tres: **`2026-10-07T00:00:00+00:00`** (anterior a `2026-10-08T21:11:56.393005+00:00`).

- `payload_e2.json` — min=max=0
- `payload_e3.json` — precaución 70–70
- `payload_e5.json` — solo `normal`

`id_comando` lo asignará el broker. No se reutiliza el `comando_id` almacenado.

## 5. Parada

Esperando autorización para **un** POST de E2. No se invocó `/v1/commands`.
