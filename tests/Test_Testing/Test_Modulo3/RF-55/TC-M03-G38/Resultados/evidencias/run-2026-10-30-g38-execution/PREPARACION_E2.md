# Preparación E2 (sin envío) — 2026-10-30 tarde

Revisión de `RESULTADO_E2.md`: el POST de la mañana **no se envió** porque el token no estaba en la Pi. Este documento deja el canal listo **sin** repetir esa búsqueda y **sin** publicar.

## Conservado

`payload_e2.json` (sin cambios): `origen=umbral`, `serial=RASPBERRY3B-TEST`, id 65, `Humedad Relativa`, `version` de comando `2026-10-07T00:00:00+00:00` (anterior a la de disco).

## Canal fijado

| Pieza | Valor |
|---|---|
| Broker | TEST `https://sgpmp-brokertest-zyytic-0f1138-149-130-169-209.sslip.io/v1/commands` |
| Método | **solo** `POST /v1/commands` |
| Gateway | `RASPBERRY3B-TEST` |
| MQTT directo | no |
| PATCH umbrales / BD | no |
| E3, E5, E6 | no |

El script aborta si el payload no es ese serial, origen `umbral`, id 65 y nombre `Humedad Relativa`.

## Credencial renovada

No se lee `/etc/sgpmp` ni `.env`. No se reutilizan secretos del chat.

Cuando se autorice el envío:

```powershell
.\ejecutar_e2.ps1 -Enviar
```

Cuadro Windows `Get-Credential` (usuario `MQTT_BROKER_TOKEN`, el Bearer va en la contraseña). Pasa por tubería a Python, se usa en `Authorization` y se anula en memoria. No hay `Set-Content`, historial de argumentos ni `print` del valor.

Sin `-Enviar` el script **solo comprueba** destino y payload.

## Qué falta para ejecutar E2

1. Autorización explícita de **un** POST (esta preparación no la sustituye).
2. El Bearer **renovado** en el cuadro seguro (no está en este repo ni en env Windows).
3. Monitor MQTT abierto **durante** el POST (`_mqtt_e2_monitor.py` + `sgpmp_gateway_test` de User env, no el token del broker).
4. Reconfirmar versión/hash del umbral 65 **en el momento del envío** (lectura `sudo -u sgpmp-edge cat`, no grep de tokens).

No se ejecutó E2 ni ningún otro escenario.
