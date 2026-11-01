# RESULTADO — Ejecución funcional TC-M03-101 (G41 / RF-55)

**Laboratorio sintético con fuente fake.** No es validación de un sensor ambiental real LoRa/DHT.

**Veredicto TC-M03-101: `APROBADO`**

Host: `RASPBERRY3B`. Usuario SSH: `sgpmp`. Servicio: `edge-agent`. PID: **9022** de t0 a cierre. `NRestarts=0`. `EDGE_SOURCE=fake`. Variable: `Humedad Relativa` (`%`).

Evidencias crudas (no se sobrescribieron informes previos):  
`tests/Test_Testing/Test_Modulo3/RF-55/TC-M03-G41/Resultados/evidencias/run-2026-10-30-g41-tc101/`

---

## Resumen ejecutivo

Con el proceso **9022** vivo se capturó una medición ~72 % clasificada **`precaucion`** contra el umbral 65 original. Se envió `POST /v1/commands` (`origen: umbral`) con bandas que colocan ~72 % en **`critico`**. El broker respondió HTTP **200 APLICADA**. MQTT entregó `ACK_UMBRAL` **OK**. El journal registró `Umbral 65 (Humedad Relativa) → OK (guardado)`. El JSON persistió la versión nueva. La **siguiente** medición (71.33 %) salió **`critico`**, con `id_umbral_ambiental=65` y `version_umbral` igual a la aplicada. Se restauraron las bandas originales con versión **posterior** (no se reutilizó la de 2026-10-08). Una medición posterior a la restauración volvió a **`precaucion`**. El PID no cambió. No se reinició Edge ni se tocó `/etc/sgpmp/edge-agent.env`.

---

## t0 y continuidad

| Campo | Valor |
|---|---|
| t0 formal | 2026-10-31 **02:37:05Z** (30 oct **21:37:05 −05:00**) |
| PID | **9022** (preflight, antes POST, después apply, final) |
| `ActiveState` | `active` |
| `NRestarts` | `0` |
| SHA umbrales en t0 | `76c65da537337aefc8a01c1c963ecd168a6fece4560faa4e955307edfecd28c5` |
| Umbral 65 en t0 | `Humedad Relativa`, 40–98, bandas 40–70 / 70–85 / 85–98, versión `2026-10-08T21:11:56.393005+00:00` |

Monitor MQTT SUB iniciado **antes** del POST, topics `sgpmp/RASPBERRY3B-TEST/#` y `sgpmp/QA-M03-272-A-088894/#`. Sin PUB de comando desde el cliente QA.

---

## Medición inicial (antes del ACK de aplicación)

| Campo | Valor |
|---|---|
| Captura | `2026-10-31T02:38:41.383Z` (historial id 8; también id 7 en `RASPBERRY3B-TEST` = 71.4 %) |
| Serial (fila usada) | `QA-M03-272-A-088894` |
| Variable | `Humedad Relativa` |
| Valor | **72.29** `%` |
| Clasificación | `DESVIACION_SIMPLE` / `MODERADO` / **`precaucion`** |
| Umbral | **65** |
| vs ACK apply | captura **02:38:41Z** &lt; ACK **02:38:55Z** |

---

## Actualización

Contrato real inspeccionado: `POST {broker}/v1/commands`, cuerpo `UmbralCommandRequest` (`origen`, `serial`, `id_umbral_ambiental`, `version` ISO con zona, `variable`, `unidad`, `valor_min`/`valor_max`, `niveles[]`). El broker añade `tipo_comando: UMBRAL_AMBIENTAL` y publica en `sgpmp/<serial>/command`. Firmware: `handle_umbral` → `motivo_niveles` → `UmbralStore.set` (disco + RAM).

Bandas de ensayo (validadas localmente: contiguas, ancho &gt; 0, cubren 40–98; 72 % → `critico`):

| Banda | Ensayo | Original / restaurado |
|---|---|---|
| normal | 40–65 | 40–70 |
| precaución | 65–70 | 70–85 |
| crítico | 70–98 | 85–98 |

`valor_min`/`valor_max` se mantuvieron en 40.0 / 98.0.

| Paso | Hora UTC | Resultado |
|---|---|---|
| POST apply | 02:38:52.826Z | HTTP **200**, `estado=APLICADA` (token redactado) |
| MQTT command | ~02:38:55Z | `sgpmp/RASPBERRY3B-TEST/command` `UMBRAL_AMBIENTAL` |
| ACK MQTT | 02:38:55.367Z | `ACK_UMBRAL` **OK**, `id_comando=0834870e2b9443bcb2ccf09902705b86` |
| Journal | 21:38:55 −05:00 | `Umbral 65 (Humedad Relativa) → OK (guardado)` |
| JSON | versión `2026-10-31T02:38:52.789672+00:00`, `comando_id` = mismo id |
| SHA apply | `b29bbc48d2024d5bf3ce380e76f8b5304f54949a5325cff4771f078d37f127b5` |
| PID | **9022** |

Payload: `run-2026-10-30-g41-tc101/payload_aplicacion.json`. HTTP: `http_aplicacion.json`.

---

## Medición posterior al ACK (criterio decisivo)

| Campo | Valor |
|---|---|
| Captura | `2026-10-31T02:43:41.396Z` (**después** del ACK 02:38:55Z) |
| Valor | **71.33** `%` (`Humedad Relativa`) |
| Historial | id 9, `DESVIACION_SIMPLE` / `CRITICO` / **`critico`**, umbral **65** |
| MQTT evento | `sgpmp/QA-M03-272-A-088894/evento` a 02:43:41.643Z |
| `version_umbral` | **`2026-10-31T02:38:52.789672+00:00`** (versión aplicada) |
| `id_umbral_ambiental` | **65** |
| `nivel_umbral` | **`critico`** |
| Firmware | `v0.4.0-rc.2` |
| PID | **9022** |

Cambio observado: **`precaucion` → `critico`**. No es un evento anterior al ACK ni un cálculo manual.

---

## Restauración

| Campo | Valor |
|---|---|
| POST restore | HTTP **200 APLICADA**, versión **`2026-10-31T02:43:52.556363+00:00`** (&gt; versión de ensayo; **no** es la de 8 oct) |
| ACK MQTT | 02:43:54.191Z, `ACK_UMBRAL` **OK**, `id_comando=3e43d61a1a664f29988f5e98e371be7d` |
| JSON | 40–98; bandas 40–70 / 70–85 / 85–98; `variable=Humedad Relativa` |
| SHA final | `f977b67f25cb8cb59c1d4fb79a593f61ff1d5bd984a042af433b0d1710f8833d` |
| vs SHA original | **Distinto** (versión y `comando_id` nuevos). Valores de negocio restaurados. |

Medición post-restauración (misma ventana): `2026-10-31T02:48:41.193Z`, 71.44 %, **`precaucion`**, umbral 65. Confirma que las bandas restauradas rigen en caliente.

PID final **9022**. Servicio `active`. `NRestarts=0`.

---

## Versiones

| Etapa | `version` |
|---|---|
| Original | `2026-10-08T21:11:56.393005+00:00` |
| Aplicada (ensayo) | `2026-10-31T02:38:52.789672+00:00` |
| Restaurada | `2026-10-31T02:43:52.556363+00:00` |

---

## Criterios PASS/FAIL

| # | Criterio | Resultado |
|---|---|---|
| 1 | Medición inicial con clasificación anterior (`precaucion`, id 65) | **PASS** |
| 2 | Actualización válida del umbral 65 | **PASS** |
| 3 | ACK y recepción efectiva por Edge | **PASS** |
| 4 | Nueva versión en memoria (`set` + evento con esa versión) | **PASS** |
| 5 | Persistencia JSON | **PASS** |
| 6 | Medición posterior al ACK | **PASS** |
| 7 | Evento con valor, ID 65, versión nueva y clasificación distinta | **PASS** |
| 8 | Mismo PID 9022 | **PASS** |
| 9 | Restauración con versión posterior | **PASS** |
| 10 | Valores originales restaurados | **PASS** |
| 11 | Servicio activo sin reinicio | **PASS** |

---

## Limitaciones

- Fuente **fake** (`Humedad Relativa:%:71:73`). Las lecturas 71–73 no provienen de DHT/LoRa.
- Cadencia observada ~5 min entre capturas de esta corrida (el env declara `EDGE_FRECUENCIA_CAPTURA_MIN=10`; no se cambió el env).
- El historial local no guarda `version_umbral`; esa prueba está en MQTT `metadata_edge`.
- SHA final ≠ original: esperado por versión/`comando_id`.
- No se usó `--live` del esqueleto de etapa 1. El POST fue el mecanismo G38 (`Get-Credential` + `POST /v1/commands`). Sin commits, merges, push ni cambios a G38.

---

## Estado persistente

- Etapa 1: CERRADA  
- Validación local: COMPLETADA  
- RF-55 integrado: CONFIRMADA  
- **TC-M03-101: APROBADO** (laboratorio sintético fake)  
- Umbral 65: valores de negocio originales, versión de restauración 2026-10-31  
- `--live` etapa1: no habilitado  
- G38: sin alteraciones  
