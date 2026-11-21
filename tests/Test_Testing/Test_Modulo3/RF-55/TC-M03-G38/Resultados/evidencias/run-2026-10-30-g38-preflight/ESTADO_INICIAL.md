# Estado inicial — G38 preflight 2026-10-30

Solo lectura. No se publicó MQTT. No se enviaron comandos. No se modificó la Raspberry. No se escribió en BD. No se ejecutaron E1–E6 ni S8. No se sobrescribieron evidencias anteriores.

## Raspberry (SSH `sgpmp@100.96.29.65`)

| Campo | Valor observado |
|---|---|
| hostname | `RASPBERRY3B` |
| `edge-agent` | `active` (systemctl, usuario sgpmp) |
| `/var/lib/sgpmp-edge/` | `Permission denied` como `sgpmp` (preflight anterior) |
| `umbrales.json` | **leído** 2026-10-30T15:28:28Z (ver abajo) |
| `config.json` | no leído (fuera de este comando) |
| MQTT TCP | dos sesiones ESTAB `192.168.40.5` → `149.130.169.209:1886` |
| Journal (grep `Comando\|ACK`, sin sudo) | última línea de comando: `2026-10-29 13:25:32` `Comando QA-M03-272-A-088894 → OK (aplicado)`; RF-55.2 activo en arranques 04:27, 13:21 y 17:51 del 29 |
| Comandos el 2026-10-30 | no aparecen en ese grep |

`/etc/sgpmp/edge-agent.env` no se leyó (root 600, histórico).

## Lectura `umbrales.json` (Sergio, solo lectura)

| Campo | Valor |
|---|---|
| Fecha UTC | **2026-10-30T15:28:28+00:00** |
| Host | `100.96.29.65` (`RASPBERRY3B`) |
| SSH | `sgpmp` (cuadro Windows `Get-Credential`; contraseña no persistida) |
| Comando | `sudo -u sgpmp-edge cat /var/lib/sgpmp-edge/umbrales.json` |
| Método que funcionó | `sudo -n -u sgpmp-edge cat` (NOPASSWD; no hizo falta `-S`) |
| Exit code | **0** |
| Archivo | **existe y es legible** como usuario `sgpmp-edge` |
| Copia local | `UMBRALES_ORIGINALES.json` (contenido exacto del cat + newline final). El original en la Pi **no se modificó**. |
| JSON válido | **sí** (`json.loads`, objeto/`dict`) |
| Tamaño copia | 1387 bytes |

Umbrales vigentes en disco (2):

| id_umbral_ambiental | variable | unidad | valor_min | valor_max | bandas (normal / precaución / crítico) | version | comando_id |
|---|---|---|---|---|---|---|---|
| 65 | Humedad Relativa | % | 40.0 | 98.0 | 40–70 / 70–85 / 85–98 | 2026-10-08T21:11:56.393005+00:00 | `6743369e531944bea216d5511a4a554c` |
| 48 | pH del agua | pH | 5.6 | 8.4 | 5.6–6.53 / 6.53–7.46 / 7.46–8.4 | 2026-10-08T21:16:43.262342+00:00 | `7b899854cb97456991a732f4e22a7171` |

No hay umbral de `temperatura_ambiente`, `frecuencia_respiratoria` ni `humedad_suelo` en este archivo. No se interpretó si los nombres con espacio coinciden con el catálogo RF-17.

Meta de la lectura: `UMBRALES_LECTURA_META.json`.

## MQTT monitor (`sgpmp_gateway_test`, v5)

Preflight 14:56–14:57 UTC (`mqtt_60s.json`): CONNECT **rc 0**, SUBACK Granted QoS 1 a `sgpmp/RASPBERRY3B-TEST/#` y `sgpmp/QA-M03-272-A-088894/#`, **0 mensajes** en 60 s.

Corrida anterior conservada `run-2026-10-30-mqtt-monitor-retry` (14:47–14:48 UTC): mismos SUB concedidos, **2 HEARTBEAT** (gateway y nodo), firmware `v0.4.0-rc.2`, buffer INACTIVO, `sensores_operativos`: `rf55_2`. Sin `status`, `telemetry` ni `evento` en 60 s.

Conclusión: el cliente de monitorización **conecta y la ACL concede** los `#`. Esta ventana de 60 s no coincidió con un heartbeat. No se observó ningún `ACK_UMBRAL` ni `ERROR_CONFIGURACION` en ninguna de las dos ventanas.

## Backend TEST

`GET https://www.api.inmero.co/api-sgpmp-test/health` → 200. Umbrales y catálogo de variables → 401 sin JWT.

## Interferencia

No hay evidencia de comandos Edge el 30-oct en el journal accesible. Hay **dos** sockets MQTT establecidos desde la Pi (el agente y un segundo cliente no identificado). No se enumeraron otros tests activos en el broker.

## Seriales

- Gateway: `RASPBERRY3B-TEST`
- Nodo: `QA-M03-272-A-088894`
