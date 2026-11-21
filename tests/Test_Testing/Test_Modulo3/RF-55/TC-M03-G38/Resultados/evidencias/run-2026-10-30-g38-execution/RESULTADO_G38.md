# RESULTADO G38 — consolidación E2, E3 y E5

Fecha de ejecución MQTT: 2026-10-30. Informe de solo lectura. No se reenviaron comandos. No se modificó el Gateway ni `umbrales.json`.

Fuentes: `ANALISIS_ACK_G38.md`, `mqtt_e2e_session.json`, `journal_e2.txt` / `journal_e3.txt` / `journal_e5.txt`, `hash_e*_antes.json` / `hash_e*_despues.json`, `HASH_INICIAL.txt`, `HASH_FINAL.txt`, `payload_e2.json` / `payload_e3.json` / `payload_e5.json`, HTTP `http_e*_response.json`, matriz `test_tc_m03_g38.py`, `TC-M03-095_resultado.md`, `TC-M03-122_resultado.md`, `COMPATIBILIDAD_SENSORES.md`, `PLAN_EJECUCION_ADAPTADO.md`.

E6, E1, E4 y S8 **no** forman parte de esta corrida.

---

## Cómo se aplican PASS y FAIL

Hay **dos capas de criterio**. No se mezclan.

| Capa | Origen | Qué exige | ¿Se puede cerrar con esta corrida? |
|---|---|---|---|
| A. Escenario firmware ACK | `casos_rf55.json` vía `COMPATIBILIDAD_SENSORES.md` y `PLAN_EJECUCION_ADAPTADO.md`: mismos CA, identificador adaptado a umbral **65** / `Humedad Relativa` | `ACK_UMBRAL` ERROR, motivo de `motivo_niveles`, **no** persistir, **no** evento de clasificación por ese comando | Sí, para E2, E3 y E5 |
| B. Caso de matriz pytest | `test_tc_m03_g38.py` | 095: precondición umbral 0 **ya configurado** + **medición válida** → `ERROR_CONFIGURACION` y no división por cero. 122: umbrales OK, severidad ausente **en store**, medición fuera de rango → `severidad_invalida` y crudo RF-62 | **No.** E4 y E6 no corridos. No hay medición ni `ERROR_CONFIGURACION` / `severidad_invalida` en `mqtt_e2e_session.json` |

PASS/FAIL de este informe aplica **solo a la capa A** (lo que se ejecutó). Los IDs TC-M03-095 y TC-M03-122 **no** se marcan PASS ni FAIL.

---

## Resumen

| Escenario | Matriz | Capa A (ACK) | Capa B (TC completo) |
|---|---|---|---|
| E2 | TC-M03-095 | **PASS** | no evaluable (hace falta medición con umbral 0 persistido; E4 no corrido) |
| E3 | TC-M03-095 | **PASS** | no evaluable (igual; E3 no es el CA pytest de “umbral 0 + medición”) |
| E5 | TC-M03-122 | **PASS** | no evaluable (E6 excluido; no hay `severidad_invalida` ni RF-62) |
| E6 | TC-M03-122 | no ejecutado | — |
| E4 | TC-M03-095 | no ejecutado | — |

SHA256 de `/var/lib/sgpmp-edge/umbrales.json` en todas las capturas de hash de esta corrida:

`76c65da537337aefc8a01c1c963ecd168a6fece4560faa4e955307edfecd28c5`

Version umbral 65, antes y después de cada POST:

`2026-10-08T21:11:56.393005+00:00`

---

## Precondiciones comunes (evidencia)

Cumplidas **antes del primer POST** (`hash_e2_antes.json` ts `2026-10-30T21:53:05.753623+00:00`; monitor `mqtt_e2e_session.json`):

| Precondición | Evidencia | ¿OK? |
|---|---|---|
| Monitor CONNECT rc 0 | `mqtt_e2e_session.json` `connect` `2026-10-30T21:48:13.075370+00:00` | sí |
| SUB Gateway `#` Granted QoS 1 | mid 1, `sgpmp/RASPBERRY3B-TEST/#` | sí |
| Gateway `RASPBERRY3B-TEST` | topics command/status/heartbeat | sí |
| Umbral 65, `Humedad Relativa` | `hash_e2_antes.json` | sí |
| Version no nula | `2026-10-08T21:11:56.393005+00:00` | sí |
| Hash = preflight | igual a `HASH_INICIAL.txt` | sí |
| Un POST por escenario | un `command` MQTT por payload E2/E3/E5 | sí |
| No reutilizar `comando_id` de disco | ids nuevos `a1725d6e…`, `2ef6cd39…`, `523e5cea…` (no `6743369e…`) | sí |
| Números JSON (no strings) | payloads MQTT `0.0` / `40.0` / `98.0` | sí |
| `variable` del lab, no snake_case | `Humedad Relativa` | sí |

`hash_e2_antes.json` registra `stderr_len` 27 con `ssh_rc` 0. El hash se obtuvo; el stderr no está volcado en ese JSON.

Heartbeat del Gateway en la misma sesión: `2026-10-30T21:52:58.121518+00:00`, firmware `v0.4.0-rc.2`.

---

## E2 — TC-M03-095

### 1. Precondiciones específicas

Hash y version de umbral 65 coinciden con preflight (`hash_e2_antes.json`). Monitor ya en SUBACK.

### 2. Datos enviados

Archivo: `payload_e2.json`. MQTT `command` `2026-10-30T21:53:09.233588+00:00`:

- `id_comando`: `a1725d6e5d0a4f1891f0a061da2a2da2`
- `emitido_en`: `2026-10-30T21:53:08.339185+00:00`
- `id_umbral_ambiental`: 65
- `variable`: `Humedad Relativa`
- `valor_min` / `valor_max`: 0.0 / 0.0
- tres bandas 0.0–0.0
- `version` del **comando**: `2026-10-07T00:00:00+00:00` (la del payload de ejecución, más antigua que la persistida; el rechazo de rangos ocurre antes del chequeo de versión)

HTTP: `http_e2_response.json` status 200, `estado` `NO_CONF`, `config_version` `null`. El plan adaptado documenta `NO_CONF` como respuesta típica del broker cuando el ACK de dispositivo no llega dentro del timeout HTTP.

### 3. ACK

`sgpmp/RASPBERRY3B-TEST/status` `2026-10-30T21:53:09.252345+00:00`: `ACK_UMBRAL`, `resultado` **ERROR**, mismo `id_comando`, `event_id` `73a8cf3e-49ed-4d4c-beef-e164ab543fd6`.

### 4. Motivo

`valor_min y valor_max deben ser números con valor_min < valor_max`

Coincide con el motivo esperado en `PLAN_EJECUCION_ADAPTADO.md` §4.

### 5. Journal

`journal_e2.txt` (extracto de un solo escenario):

`2026-10-30 16:53:08,413 INFO edge_agent.agent: Umbral 65 (Humedad Relativa) → ERROR (valor_min y valor_max deben ser números con valor_min < valor_max)`

Hora local Pi = `emitido_en` UTC − 5 h. No es un registro inventado.

### 6. Integridad `umbrales.json`

`hash_e2_despues.json`: mismo SHA256 y misma version. `hash_rc` 0. **El JSON de después no trae timestamp ISO.**

En `mqtt_e2e_session.json`, entre el ACK E2 y el command E3 no hay topic `evento`.

### 7. Criterios

| Criterio | ¿Cumple? |
|---|---|
| Capa A: ACK ERROR + motivo min&lt;max + no persistir | **sí → PASS** |
| Capa B: medición válida con umbral 0 persistido → `ERROR_CONFIGURACION` | **no observado** (el umbral 0 no se guardó; no hay entrada de medición) |
| Ausencia de crash del agente | el proceso siguió (ACK E3/E5 posteriores); **no** hay prueba unitaria de “no división por cero” |

**Veredicto E2 (capa A): PASS.**

---

## E3 — TC-M03-095

### 1. Precondiciones

Continuación solo tras E2 ERROR + hash igual. `hash_e3_antes.json` ts `2026-10-30T21:53:47.878179+00:00`: version y hash idénticos, `coincide_preflight` true.

### 2. Datos enviados

`payload_e3.json`. MQTT `command` `2026-10-30T21:53:50.723623+00:00`:

- `id_comando`: `2ef6cd393a3a4dbf9f39c58c463f51ba`
- `emitido_en`: `2026-10-30T21:53:49.937284+00:00`
- umbral 65, `Humedad Relativa`, 40.0–98.0
- `precaucion` 70.0–70.0

HTTP: 200 `NO_CONF` (`http_e3_response.json`).

### 3. ACK

`2026-10-30T21:53:50.784108+00:00`, ERROR, mismo `id_comando`, `event_id` `68e2a60f-f913-4f17-9e2d-854b50c6d262`.

### 4. Motivo

`la banda precaucion debe tener ancho mayor que 0 (70–70)`  
(en JSON MQTT el guion aparece como `\u2013`).

### 5. Journal

`journal_e3.txt` es **acumulado**:

1. Línea E2 `16:53:08,413` (ya registrada).
2. Línea E3: `2026-10-30 16:53:49,984 INFO edge_agent.agent: Umbral 65 (Humedad Relativa) → ERROR (la banda precaucion debe tener ancho mayor que 0 (70–70))`

La línea 2 es la evidencia de E3. La línea 1 no se reinterpreta como un segundo fallo de E3.

### 6. Integridad

`hash_e3_despues.json`: SHA256 y version sin cambio. Sin timestamp ISO en el JSON de después.

### 7. Criterios

Capa A (banda ancho 0 → ACK ERROR, no persistir): **PASS**.  
Capa B pytest 095: E3 no sustituye la medición con umbral 0.

**Veredicto E3 (capa A): PASS.**

---

## E5 — TC-M03-122

### 1. Precondiciones

Tras E3 ERROR + hash igual. `hash_e5_antes.json` ts `2026-10-30T21:54:30.953301+00:00`: coincidencia con preflight.

### 2. Datos enviados

`payload_e5.json`. MQTT `command` `2026-10-30T21:54:33.603314+00:00`:

- `id_comando`: `523e5cea5c0a4b618d44beb21c378523`
- `emitido_en`: `2026-10-30T21:54:32.815294+00:00`
- un solo nivel `normal` 40.0–98.0

HTTP: 200 `NO_CONF` (`http_e5_response.json`).

### 3. ACK

`2026-10-30T21:54:33.900664+00:00`, ERROR, mismo `id_comando`, `event_id` `2374832a-5f85-4fb0-8546-c6c4d9085e61`.

### 4. Motivo

`niveles debe traer normal, precaucion y critico, una vez cada uno`

### 5. Journal

`journal_e5.txt` es **acumulado** (E2 + E3 + E5). Línea de E5:

`2026-10-30 16:54:33,098 INFO edge_agent.agent: Umbral 65 (Humedad Relativa) → ERROR (niveles debe traer normal, precaucion y critico, una vez cada uno)`

### 6. Integridad

`hash_e5_despues.json` y `HASH_FINAL.txt` (texto de cierre ~`2026-10-30T21:55:03Z`): mismo SHA256 y version. Sin dump JSON completo post-POST. Sin timestamp ISO en `hash_e5_despues.json`.

### 7. Criterios

Capa A (solo `normal` → ACK ERROR, no persistir, no inventar CRITICO por este comando): **PASS**.  
Capa B pytest 122 (`severidad_invalida`, crudo RF-62, medición fuera de rango): **no observado**. Eso es E6, excluido.

**Veredicto E5 (capa A): PASS.**

---

## Persistencia umbral 65

No hay evidencia de que E2, E3 o E5 escribieran el umbral 65. Hash y version persistida no cambiaron. La version del comando (`2026-10-07T00:00:00+00:00`) no aparece como version vigente tras los POST.

No hay volcado de memoria del `UmbralStore`. El plan adaptado indica que, sin `set()`, la memoria sigue lo cargado al arranque; esa afirmación de código **no** se verificó con una lectura clasificada ni con reinicio (no autorizado).

---

## Limitaciones de trazabilidad (explícitas)

1. `journal_e3.txt` y `journal_e5.txt` acumulan líneas de escenarios previos; no son cortes exclusivos.
2. `hash_e2_despues.json`, `hash_e3_despues.json`, `hash_e5_despues.json` no incluyen timestamp ISO.
3. No hay `UMBRALES_ORIGINALES.json` recapturado después de cada POST; solo SHA256 + version 65.
4. El ACK MQTT no lleva `id_umbral_ambiental`; el 65 se toma del `command` correlacionado y del journal.
5. HTTP `NO_CONF` no es el ACK del Edge; no se usó como FAIL ni como PASS.
6. `mqtt_e2e_session.json` no contiene mensajes en topic `evento`. Eso apoya “no clasificó por estos comandos” **en la ventana del monitor**, no una prueba de que el clasificador esté ausente para otras variables.
7. Identificador adaptado: contrato firmware usa `temperatura_ambiente` id 7; laboratorio usó 65 / `Humedad Relativa` (autorizado en compatibilidad). El CA de ACK no se reescribió; el nombre de variable del fixture **sí** cambió.
8. Capa B de matriz **sin** PASS/FAIL: faltan medición, E4, E6 y RF-62.

---

## IDs de matriz (cierre)

| ID | Estado de este informe |
|---|---|
| TC-M03-095 | **Sin PASS/FAIL.** E2 y E3 capa A PASS. E4 no ejecutado. CA pytest (`ERROR_CONFIGURACION` + medición) no evidenciado. |
| TC-M03-122 | **Sin PASS/FAIL.** E5 capa A PASS. E6 no ejecutado. CA pytest (`severidad_invalida` + RF-62) no evidenciado. |
| TC-M03-083 | Fuera de esta consolidación (E1/S8 no ejecutados). |

Este cierre no es SKIP-as-pass. Pytest histórico SKIPPED de 2026-10-25 **no** se usa como evidencia de 2026-10-30.
