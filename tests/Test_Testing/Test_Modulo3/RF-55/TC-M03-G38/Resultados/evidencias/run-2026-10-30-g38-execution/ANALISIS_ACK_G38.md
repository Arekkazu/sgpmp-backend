# Análisis ACK G38 — E2, E3 y E5

Fuente primaria: `mqtt_e2e_session.json` (monitor Paho, CONNECT rc 0, SUB `sgpmp/RASPBERRY3B-TEST/#` y `sgpmp/QA-M03-272-A-088894/#`, Granted QoS 1).

Análisis de solo lectura. No se reenviaron comandos. No se modificó Edge, base de datos ni configuración.

Este documento **no** declara PASS/FAIL de casos de matriz (TC-M03-083 / 095 / 122). Describe lo observado en laboratorio.

## 1. Tres comandos y tres ACK

En la sesión hay **exactamente tres** mensajes en `sgpmp/RASPBERRY3B-TEST/command` (`tipo_comando`: `UMBRAL_AMBIENTAL`) y **exactamente tres** `ACK_UMBRAL` en `sgpmp/RASPBERRY3B-TEST/status`. No hay un cuarto comando ni un ACK `OK`.

El serial del topic es el gateway `RASPBERRY3B-TEST`. Los tres comandos llevan `id_umbral_ambiental`: **65** y `variable`: `Humedad Relativa`. Los ACK **no** incluyen el id de umbral; la correlación es por `id_comando`.

## 2. Correlación comando ↔ ACK

Criterios usados, en orden:

1. Igualdad de `id_comando` (único, suficiente).
2. Orden temporal: cada ACK llega **menos de 1 s** después del `command` correspondiente en el monitor.
3. Coincidencia del payload MQTT con `payload_e2.json` / `payload_e3.json` / `payload_e5.json` (rangos y bandas).
4. Journal `edge_agent.agent` con el mismo motivo y umbral 65, en hora local Pi (UTC−5).

| Escenario | `id_comando` | `emitido_en` (payload command) | Monitor `command` | Monitor `ACK_UMBRAL` | Δ monitor | `event_id` ACK |
|---|---|---|---|---|---|---|
| E2 | `a1725d6e5d0a4f1891f0a061da2a2da2` | `2026-10-30T21:53:08.339185+00:00` | `21:53:09.233588+00:00` | `21:53:09.252345+00:00` | ~19 ms | `73a8cf3e-49ed-4d4c-beef-e164ab543fd6` |
| E3 | `2ef6cd393a3a4dbf9f39c58c463f51ba` | `2026-10-30T21:53:49.937284+00:00` | `21:53:50.723623+00:00` | `21:53:50.784108+00:00` | ~60 ms | `68e2a60f-f913-4f17-9e2d-854b50c6d262` |
| E5 | `523e5cea5c0a4b618d44beb21c378523` | `2026-10-30T21:54:32.815294+00:00` | `21:54:33.603314+00:00` | `21:54:33.900664+00:00` | ~297 ms | `2374832a-5f85-4fb0-8546-c6c4d9085e61` |

No hay cruce de `id_comando`: cada ACK cita el id del comando inmediatamente anterior.

Payload MQTT vs archivo enviado:

- **E2** `command`: `valor_min`/`valor_max` 0.0, tres bandas 0–0 → igual a `payload_e2.json`.
- **E3** `command`: 40–98, `precaucion` 70–70 → igual a `payload_e3.json`.
- **E5** `command`: 40–98, un solo nivel `normal` → igual a `payload_e5.json`.

Version en los tres comandos MQTT: `2026-10-07T00:00:00+00:00` (la del payload HTTP, no la version persistida en Pi).

## 3. Tabla de resultados

| Campo | E2 | E3 | E5 |
|---|---|---|---|
| Gateway | `RASPBERRY3B-TEST` | `RASPBERRY3B-TEST` | `RASPBERRY3B-TEST` |
| Topic command | `sgpmp/RASPBERRY3B-TEST/command` | igual | igual |
| Topic ACK | `sgpmp/RASPBERRY3B-TEST/status` | igual | igual |
| `id_umbral_ambiental` (en command) | 65 | 65 | 65 |
| Variable (en command) | `Humedad Relativa` | `Humedad Relativa` | `Humedad Relativa` |
| ACK `id_umbral` | **ausente en el ACK** | **ausente en el ACK** | **ausente en el ACK** |
| ACK `resultado` | **ERROR** | **ERROR** | **ERROR** |
| ACK `OK` | no | no | no |
| Motivo ACK | `valor_min y valor_max deben ser números con valor_min < valor_max` | `la banda precaucion debe tener ancho mayor que 0 (70–70)` | `niveles debe traer normal, precaucion y critico, una vez cada uno` |
| HTTP broker | 200, `estado`: `NO_CONF`, `config_version`: `null` | igual | igual |
| Journal línea propia | sí, `journal_e2.txt` | sí, segunda línea de `journal_e3.txt` | sí, tercera línea de `journal_e5.txt` |
| Hash antes | `76c65da…d28c5` (`hash_e2_antes.json`) | `76c65da…d28c5` (`hash_e3_antes.json`) | `76c65da…d28c5` (`hash_e5_antes.json`) |
| Hash después | `76c65da…d28c5` (`hash_e2_despues.json`) | `76c65da…d28c5` (`hash_e3_despues.json`) | `76c65da…d28c5` (`hash_e5_despues.json`) |
| Version umbral 65 antes | `2026-10-08T21:11:56.393005+00:00` | igual | igual |
| Version umbral 65 después | `2026-10-08T21:11:56.393005+00:00` | igual | igual |
| Persistencia observada | no (hash y version iguales) | no | no |

SHA256 completo, idéntico en todas las capturas de esta corrida:

`76c65da537337aefc8a01c1c963ecd168a6fece4560faa4e955307edfecd28c5`

Coincide con `HASH_INICIAL.txt` (preflight ~`2026-10-30T16:11:50Z`) y `HASH_FINAL.txt` (postcheck E5 ~`2026-10-30T21:55:03Z`).

## 4. Journal edge-agent

Hora del journal: **local Pi**, coherente con UTC−5 respecto a `emitido_en` / monitor.

| Escenario | Archivo | Línea atribuible | ¿Suficiente? |
|---|---|---|---|
| E2 | `journal_e2.txt` | `2026-10-30 16:53:08,413 … Umbral 65 (Humedad Relativa) → ERROR (valor_min y valor_max deben ser números con valor_min < valor_max)` | sí (extracto de un solo escenario) |
| E3 | `journal_e3.txt` | `2026-10-30 16:53:49,984 … → ERROR (la banda precaucion debe tener ancho mayor que 0 (70–70))` | sí; el archivo **también** repite la línea de E2 (journalctl acumulado, no un extracto exclusivo) |
| E5 | `journal_e5.txt` | `2026-10-30 16:54:33,098 … → ERROR (niveles debe traer normal, precaucion y critico, una vez cada uno)` | sí; el archivo **también** incluye E2 y E3 |

No falta la línea de journal de ningún escenario ejecutado. Lo que sí hay que leer con cuidado: `journal_e3.txt` y `journal_e5.txt` no son cortes “solo este POST”; son ventanas que acumulan líneas previas de la misma corrida.

Los motivos del journal coinciden **literalmente** con el campo `motivo` de cada ACK (en E3 el ACK JSON escapa el guion como `\u2013`; el journal muestra `70–70`).

## 5. Hashes `umbrales.json`

Capturas presentes (ninguna faltante para E2/E3/E5):

| Momento | Archivo | SHA256 | Version umbral 65 | `ssh_rc` / `hash_rc` |
|---|---|---|---|---|
| Preflight | `HASH_INICIAL.txt` | `76c65da…d28c5` | no está en ese txt | captura previa |
| Antes E2 | `hash_e2_antes.json` | `76c65da…d28c5` | `2026-10-08T21:11:56.393005+00:00` | `ssh_rc` 0; `stderr_len` 27 (stderr no vacío; el hash se obtuvo con rc 0) |
| Después E2 | `hash_e2_despues.json` | `76c65da…d28c5` | misma | `hash_rc` 0; **sin timestamp ISO** en el JSON |
| Antes E3 | `hash_e3_antes.json` | `76c65da…d28c5` | misma | `ssh_rc` 0 |
| Después E3 | `hash_e3_despues.json` | `76c65da…d28c5` | misma | `hash_rc` 0; **sin timestamp ISO** |
| Antes E5 | `hash_e5_antes.json` | `76c65da…d28c5` | misma | `ssh_rc` 0 |
| Después E5 | `hash_e5_despues.json` | `76c65da…d28c5` | misma | `hash_rc` 0; **sin timestamp ISO** |
| Cierre | `HASH_FINAL.txt` | `76c65da…d28c5` | misma | texto de postcheck E5 |

Limitación: los JSON `hash_e*_despues.json` no guardan el instante de captura; la secuencia se infiere del orquestador (postcheck inmediatamente después del ACK) y de `HASH_FINAL.txt`. No hay un dump completo de `umbrales.json` posterior a cada POST en esta carpeta de ejecución (el contenido original está en el preflight `UMBRALES_ORIGINALES.json`, fuera de este análisis de ACK).

## 6. Persistencia del umbral 65

Evidencia **contra** persistencia de los comandos E2/E3/E5:

- ACK `resultado` = `ERROR` en los tres `id_comando`.
- Journal: `→ ERROR (…)` para umbral 65, sin línea de aplicación / set en estos extractos.
- SHA256 de `/var/lib/sgpmp-edge/umbrales.json` **igual** antes y después de cada escenario y respecto al preflight.
- Version del umbral 65 **igual** (`2026-10-08T21:11:56.393005+00:00`), distinta de la version **del comando** (`2026-10-07T00:00:00+00:00`). Si el Edge hubiera aplicado el payload, la version persistida habría tenido que cambiar a la del comando o a un valor nuevo; no ocurrió.

HTTP `NO_CONF` / `config_version: null` **no** se usa aquí como prueba de no persistencia: es el timeout de confirmación del broker. La prueba de rechazo es MQTT ACK + journal + hash.

No hay evidencia de escritura del umbral 65 con los rangos 0–0, 70–70 o “solo normal”.

## 7. Lo que este análisis no cubre

- E6, E1, E4, S8: no hay command/ACK de esos escenarios en `mqtt_e2e_session.json`.
- PASS/FAIL de matriz QA: no se declara. Hace falta el criterio formal de cada TC (IDs de matriz, variable nominal vs 65, RF-55.2 vs RF-17) además de estas evidencias de ACK.
- Recat de `umbrales.json` completo tras cada POST: no está en los `hash_*_despues.json`.
- El ACK no lleva `id_umbral_ambiental`; la identificación del umbral 65 en el ACK se apoya en el command correlacionado y en el journal (`Umbral 65`).
