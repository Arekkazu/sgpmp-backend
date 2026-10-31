# RESULTADO — Preparación previa autorizada G41

Fecha local (Raspberry): **2026-10-30**. Host: `RASPBERRY3B`. Usuario SSH: `sgpmp`. Servicio: `edge-agent`.

**Veredicto: `PREPARACION_COMPLETADA`**

Hay mediciones sintéticas con el nombre exacto `Humedad Relativa`. El agente las procesó, coincidieron con el umbral **65** y el servicio quedó activo. **No se inició TC-M03-101.** **No se actualizó el umbral 65.** **No se restauró el entorno.** `--live` permanece deshabilitado.

---

## Acciones autorizadas (únicas)

1. Editar **solo** `EDGE_FAKE_VARIABLES` en `/etc/sgpmp/edge-agent.env`.
2. Un único `systemctl restart edge-agent` **antes** del t0 formal de TC-M03-101.

No se envió `POST` al backend, no se publicó comando MQTT, no se escribió `/var/lib/sgpmp-edge/umbrales.json` ni `/var/lib/sgpmp/umbrales.json`, no se cambió LoRa, no se modificó código fuente, no hubo segundo restart.

Credenciales: Windows `Get-Credential` → stdin cifrado SSH (paramiko) → `sudo -S` por stdin. No se guardaron secretos en archivos ni en este informe.

---

## Formato de `EDGE_FAKE_VARIABLES`

Código (`raspberry/edge_agent/config.py`, `_parse_fake_variables`): cada ítem es **cuatro** campos separados por `:`:

`nombre:unidad:min:max`

Varios ítems se separan con `;`. Si `len(parts) != 4` se lanza `ConfigError`.

| Propuesta | Resultado |
|---|---|
| `%:71:73` | **Inválido** (3 campos). No se escribió. |
| `Humedad Relativa:%:71:73` | **Válido**. Nombre exacto, unidad `%`, rango 71–73. |

El nombre se copia a `FakeVariable.nombre` y `FakeLoraSource.read()` lo pone en `Reading.variable` sin normalizar. El evaluador compara `umbral.variable == reading.variable` de forma exacta.

Systemd `EnvironmentFile`: el valor con espacios va **entre comillas** en el archivo. El proceso ve el valor **sin** esas comillas.

La variable se lee **al iniciar el proceso** (`Settings.from_env` / `EnvironmentFile=`). Un cambio en el `.env` no aplica en caliente; por eso el único restart autorizado.

---

## Configuración de la variable (secretos omitidos)

| Momento | `EDGE_FAKE_VARIABLES` | Otras claves observadas (valores no secretos) |
|---|---|---|
| Antes | **ausente** (no había línea activa) | `EDGE_SOURCE=fake`; `EDGE_FRECUENCIA_CAPTURA_MIN=10`; `EDGE_SERIALS=RASPBERRY3B-TEST,QA-M03-272-A-088894`; `EDGE_LORA_VARIABLES=1=temperatura_ambiente:C;2=humedad_relativa:%` (sin uso con fuente fake) |
| Después | `"Humedad Relativa:%:71:73"` en el archivo | Las mismas claves, sin cambio de valor |

En `/proc/<pid>/environ` del PID nuevo:

`EDGE_FAKE_VARIABLES=Humedad Relativa:%:71:73`

`PATCH_OK False` = no había línea activa previa; se **añadió** al final. No se reescribieron las demás variables.

---

## Respaldo

| Campo | Valor |
|---|---|
| Ruta | `/etc/sgpmp/edge-agent.env.bak-g41-20261030` |
| Método | `cp -a` (conserva propietario y modo) |
| `stat` del respaldo | `root:root:600` |

No se copió el respaldo fuera de la Raspberry (contiene secretos MQTT).

---

## Reinicio (único)

| Campo | Valor |
|---|---|
| PID anterior | **798** (activo desde 2026-10-29 17:51, diagnóstico G41) |
| Hora del stop | 2026-10-30 **21:18:39** −05:00 (journal: desconexión MQTT / `edge_agent detenido`) |
| Hora de arranque | 2026-10-30 **21:18:41** −05:00 (`Started edge-agent.service`; firmware `v0.4.0-rc.2`) |
| PID nuevo | **9022** |
| `ActiveState` post | `active` (reconfirmado 21:21:03 −05:00, mismo PID 9022) |
| `NRestarts` | **0** antes y **0** después |

`NRestarts=0` es el comportamiento esperado de un `systemctl restart` **manual**: systemd incrementa ese contador en reinicios por fallo (`Restart=`), no en un restart pedido por el operador.

No se ejecutó un segundo restart.

---

## Lecturas sintéticas y procesamiento

`FakeLoraSource.read()` produce un `Reading` por variable configurada. Tras el arranque, `next_capture=now` dispara la primera captura de inmediato (no espera los 10 min de `EDGE_FRECUENCIA_CAPTURA_MIN`).

Historial local (`/var/lib/sgpmp-edge/historial.db`), 2 filas nuevas en `2026-10-31T02:18:41.209802+00:00` (= 21:18:41 −05:00):

| id | serial | clasificación | severidad | variables | ruta / estado | detalle |
|---|---|---|---|---|---|---|
| 1 | `RASPBERRY3B-TEST` | `DESVIACION_SIMPLE` | `MODERADO` | `Humedad Relativa` = **71.44** `%` | `DIRECTA` / `ENVIADO` | `nivel_umbral`: `precaucion`; `id_umbral_ambiental`: **65** |
| 2 | `QA-M03-272-A-088894` | `DESVIACION_SIMPLE` | `MODERADO` | `Humedad Relativa` = **72.61** `%` | `DIRECTA` / `ENVIADO` | igual |

Outbox (`buffer.db`) conservaba telemetría pendiente de intervalo de transmisión, con el mismo nombre y valores:

- `{"variable": "Humedad Relativa", "valor_crudo": 71.44, "unidad": "%", ...}`
- `{"variable": "Humedad Relativa", "valor_crudo": 72.61, "unidad": "%", ...}`

Nombre exacto confirmado en historial, outbox y umbral 65.

---

## Umbral 65 (solo lectura)

| Campo | Antes | Después |
|---|---|---|
| SHA256 `/var/lib/sgpmp-edge/umbrales.json` | `76c65da537337aefc8a01c1c963ecd168a6fece4560faa4e955307edfecd28c5` | **idéntico** |
| `variable` | `Humedad Relativa` | `Humedad Relativa` |
| `version` | `2026-10-08T21:11:56.393005+00:00` | sin cambio |

El evaluador **sí** resolvió el umbral 65 contra esas lecturas (`id_umbral_ambiental: 65` en `detalle` del historial). No se envió ningún comando de actualización.

---

## Confirmaciones de no-acción

- Sin `POST /v1/commands` ni publicación MQTT de comando.
- Sin escritura en `umbrales.json` (hash estable; mtime del archivo 8 oct).
- Sin cambio LoRa / `EDGE_SOURCE` (sigue `fake`).
- Sin cambio de código, rama, commit, merge ni worktree.
- Sin TC-M03-101 y sin `--live`.
- Sin restauración del `.env` (queda pendiente de autorización expresa).

---

## Limitaciones

- El journal a INFO no imprime cada captura; la evidencia de medición está en SQLite (historial + outbox), no en líneas `FakeLoraSource`.
- `EDGE_LORA_VARIABLES` sigue usando `humedad_relativa`; **no se tocó**. Con `EDGE_SOURCE=fake` no alimenta `read()`.
- Valores 71.44 / 72.61 caen en banda de precaución del umbral 65; eso es coherente con el rango sintético 71–73, no es una actualización de umbral.
- El respaldo permanece en la Raspberry; restaurar exige autorización posterior.
- `NRestarts` no sirve como contador de restarts manuales; el PID 798 → 9022 y el journal sí.

---

## Estado persistente (recordatorio)

- Etapa 1: **CERRADA**
- Validación local: **COMPLETADA**
- RF-55 integrado: **CONFIRMADA**
- TC-M03-101: **NO APROBADO** / **NO EJECUTADO**
- Etapa 2 funcional: **NO EJECUTADA**
- `--live`: **DESHABILITADO**

El agente (PID **9022**) está listo para un t0 de TC-M03-101 **solo si** llega autorización expresa de ejecución funcional. Hasta entonces no se actualiza el umbral 65 y no se restaura el `.env`.
