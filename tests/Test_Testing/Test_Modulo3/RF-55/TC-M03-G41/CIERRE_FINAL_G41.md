# CIERRE FINAL G41 — Auditoría documental TC-M03-101 / RF-55

Fecha de auditoría: 2026-10-30 (hora local −05:00).  
**No se reejecutó la prueba. No se envió POST ni MQTT de comando. No hay commit ni push.**

---

## 1. Identificación

| Campo | Valor |
|---|---|
| Proyecto | `sgpmp-backend` |
| Rama de trabajo del usuario | `laura` (`d097c33d`) |
| Módulo | 3 |
| Requisito | RF-55 |
| Caso | TC-M03-101 |
| Grupo | G41 |
| Worktree de firmware aislado | `.worktrees/sgpmp-rf55-validation` rama `qa/rf55-validation-e618a75` @ `e618a75` |

---

## 2. Objetivo de TC-M03-101

Definición oficial en `test_tc_m03_g41.py` (`test_tc_m03_101_umbrales_en_caliente`) y `Resultados/TC-M03-101/TC-M03-101_resultado.md`:

> Cambiar umbrales en operación; la **siguiente medición** del nodo usa los umbrales **nuevos** **sin reinicio**.

El pytest de matriz **sigue SKIPPED** (2026-10-25): no hay motor Edge en `src/`. Ese skip **no se modificó** para fabricar un PASS. La ejecución de 2026-10-30 es un **laboratorio funcional autorizado** sobre el Edge real (fuente fake), no un cambio del script pytest.

Diferencia respecto al enunciado histórico: el plan antiguo hablaba de PATCH Dev RF-17; la vía de producto hacia el Edge es `POST /v1/commands` `origen: umbral` (RF-17 sync). No se alteró el caso pytest para ocultar esa diferencia.

---

## 3. Resumen de la ejecución auditada

Corrida `run-2026-10-30-g41-tc101`, t0 formal **2026-10-31T02:37:05Z** (30 oct 21:37 −05:00). PID Edge **9022**. Fuente fake. Umbral 65. Clasificación inicial `precaucion` → posterior `critico` → restauración `precaucion`.

---

## 4. Entorno

| Pieza | Valor en evidencias |
|---|---|
| Host | `RASPBERRY3B` (`snap_preflight.json` `raw_state`) |
| Servicio | `edge-agent` `active` |
| Firmware | `v0.4.0-rc.2` (MQTT / journal) |
| Seriales | `RASPBERRY3B-TEST`, `QA-M03-272-A-088894` |
| Broker POST | `https://sgpmp-brokertest-…sslip.io/v1/commands` |
| MQTT SUB | `sgpmp/<serial>/#` (sesión QA, sin PUB de comando) |

---

## 5. Declaración de laboratorio sintético

**Laboratorio sintético con fuente fake.** `EDGE_FAKE_VARIABLES="Humedad Relativa:%:71:73"` (`RESULTADO_PREPARACION_PREVIA_G41.md`). No es validación de sensor LoRa/DHT.

El único restart de `edge-agent` documentado es el de **preparación previa** (21:18:41 −05:00, PID 798→9022), **antes** del t0 funcional. El journal de la corrida 101 no muestra otro `Starting edge-agent` entre t0 y el cierre.

---

## 6. Resultados iniciales

| Dato | Evidencia | Fragmento |
|---|---|---|
| 72.29 % | `medicion_t0.json` | `"valor": 72.29`, `"tipo_variable": "Humedad Relativa"` |
| `precaucion` | mismo + `mqtt_session.json` evento 02:38:41Z | `"nivel_umbral": "precaucion"`, `version_umbral` original |
| Umbral 65 | `detalle.id_umbral_ambiental` / metadata MQTT | `65` |
| Antes del ACK | captura `02:38:41.383Z` vs ACK `02:38:55.367Z` | MQTT + `ack_aplicacion.json` |

---

## 7. Actualización dinámica

| Dato | Evidencia |
|---|---|
| Payload ensayo 40–65 / 65–70 / 70–98 | `payload_aplicacion.json` versión `2026-10-31T02:38:52.789672+00:00` |
| HTTP 200 `APLICADA` | `http_aplicacion.json` `sent_at` 02:38:52.826Z |
| MQTT command | `mqtt_session.json` 02:38:55.335Z `UMBRAL_AMBIENTAL` id `0834870e…` |
| ACK MQTT OK | `ack_aplicacion.json` / `mqtt_session.json` 02:38:55.367Z |
| Edge `handle_umbral` + persistencia | journal `21:38:55` `Umbral 65 (Humedad Relativa) → OK (guardado)` |
| JSON disco | `snap_despues_apply.json` misma versión y bandas de ensayo, SHA `b29bbc48…` |

HTTP `APLICADA` **no** se usa sola: hay ACK MQTT, journal `guardado` y JSON.

---

## 8. Clasificación posterior

| Dato | Evidencia |
|---|---|
| Captura | `2026-10-31T02:43:41.396Z` (`medicion_posterior.json`) **después** del ACK 02:38:55Z |
| Valor | 71.33 % `Humedad Relativa` |
| Historial | `critico`, id 65 |
| MQTT evento | `evento_posterior_mqtt.json` y `mqtt_session.json` 02:43:41.643Z |
| `version_umbral` | **`2026-10-31T02:38:52.789672+00:00`** (versión de ensayo, no la de octubre 8) |
| `nivel_umbral` | `critico` |

Eso demuestra evaluación **en caliente** con el store actualizado: `evaluar_lote` lee `UmbralStore.todos()` en el mismo proceso (PID 9022). No es un recálculo manual.

---

## 9. Continuidad del proceso

PID **9022** y `NRestarts=0` / `active` en:

- `snap_preflight.json` 02:37:05Z  
- `snap_antes_post.json`  
- `snap_despues_apply.json` 02:38:59Z  
- `snap_final.json` 02:48:50Z  

Heartbeats MQTT del mismo firmware entre apply y post (p. ej. 02:41:13Z). Journal: último `Starting edge-agent` = 21:18:41 (preparación), no durante 21:37–21:48.

**Límite:** no hay un volcado de PID en cada poll de 20 s; la continuidad se infiere de cuatro snapshots, `NRestarts=0`, heartbeats y ausencia de restart en journal. El orquestador abortaba si el PID dejaba de ser 9022 (`ejecutar_tc101.py`).

---

## 10. Restauración

| Campo | Original | Ensayo | Restaurado |
|---|---|---|---|
| `valor_min`/`max` | 40.0 / 98.0 | 40.0 / 98.0 | 40.0 / 98.0 |
| normal | 40–70 | 40–65 | 40–70 |
| precaución | 70–85 | 65–70 | 70–85 |
| crítico | 85–98 | 70–98 | 85–98 |
| `version` | `2026-10-08T21:11:56.393005+00:00` | `2026-10-31T02:38:52.789672+00:00` | `2026-10-31T02:43:52.556363+00:00` |
| SHA-256 JSON | `76c65da5…ecd28c5` | `b29bbc48…f127b5` | `f977b67f…0f8833d` |

SHA final ≠ original: esperado (`version` y `comando_id` nuevos). Negocio restaurado.

Post-restauración: 71.44 % → `precaucion`, `version_umbral` = versión restaurada (`mqtt_session.json` 02:48:41Z, `medicion_restaurada.json`).

ACK restore: `ack_restauracion.json` OK `id_comando=3e43d61a…`. Journal 21:43:53 `Umbral 65 … → OK (guardado)`.

---

## 11. Matriz de 11 criterios (auditoría)

Los números 1–11 siguientes son los de la sección 3 de la solicitud de cierre (trazabilidad documental). Equivalen a los criterios de aprobación de la ejecución.

| # | Exige | Evidencia distinta | Dato comprobable | Auditoría |
|---|---|---|---|---|
| 1 | Medición inicial **anterior** al ACK | `medicion_t0.json` vs `ack_aplicacion.json` | 02:38:41.383Z &lt; 02:38:55.367Z | **PASS** |
| 2 | Clasificación inicial `precaucion` | `medicion_t0.json` **y** MQTT evento t0 (`mqtt_session.json`, `version_umbral` original) | `nivel_umbral: precaucion`, 72.29 % | **PASS** |
| 3 | POST y HTTP | `http_aplicacion.json` (no es el ACK MQTT) | status 200, `APLICADA`, 02:38:52.826Z | **PASS** |
| 4 | ACK MQTT | `ack_aplicacion.json` / `mqtt_session.json` topic `…/status` | `ACK_UMBRAL` `OK` `0834870e…` | **PASS** |
| 5 | Recepción y aplicación Edge | `journal_apply.txt` (no basta HTTP) | `Umbral 65 … → OK (guardado)` 21:38:55 | **PASS** |
| 6 | Store en **memoria** | Evento **posterior** con `version_umbral` de ensayo (`evento_posterior_mqtt.json`). El JSON de disco es el criterio 7. | `version_umbral=2026-10-31T02:38:52.789672+00:00` en evaluación 02:43:41Z, PID 9022 | **PASS** (inferido: no hay dump de RAM; `set()` + evento con esa versión) |
| 7 | Persistencia versión nueva | `snap_despues_apply.json` | `umbral65.version` ensayo, SHA `b29bbc48…` | **PASS** |
| 8 | Medición posterior al ACK | `medicion_posterior.json` timestamp | 02:43:41.396Z &gt; 02:38:55Z | **PASS** |
| 9 | Evento id 65 + versión nueva + `critico` | `evento_posterior_mqtt.json` (no reutilizar solo el historial, que **no** guarda `version_umbral`) | id 65, versión ensayo, `critico`, 71.33 % | **PASS** |
| 10 | PID 9022 sin reinicio en la ventana 101 | cuatro `snap_*.json` + journal sin `Starting` tras 21:18 + heartbeats | MainPID=9022, NRestarts=0 | **PASS** (muestreado, ver §9) |
| 11 | Restauración versión posterior, valores originales, `precaucion` | `snap_final.json` + `ack_restauracion.json` + MQTT 02:48:41Z + `medicion_restaurada.json` | versión restore, bandas 40–70/70–85/85–98, 71.44 % `precaucion`, `version_umbral` restore | **PASS** |

**Veredicto documental:** `APROBADO Y DOCUMENTALMENTE VERIFICADO`

No se usó la misma fila JSON para “probar” HTTP y ACK. El historial local no sustituye al evento MQTT para `version_umbral`.

---

## 12. Rutas de evidencias

Base: `sgpmp-backend/tests/Test_Testing/Test_Modulo3/RF-55/TC-M03-G41/`

- Informe de ejecución: `RESULTADO_EJECUCION_TC_M03_101.md`
- Preparación fake: `RESULTADO_PREPARACION_PREVIA_G41.md`
- Corrida: `Resultados/evidencias/run-2026-10-30-g41-tc101/`
- Caso pytest histórico (SKIPPED): `Resultados/TC-M03-101/TC-M03-101_resultado.md`
- Planes (solo worktree firmware): `.worktrees/sgpmp-rf55-validation/.../PLAN_EJECUCION_FUNCIONAL_RF55.md`, `PLAN_DESBLOQUEO_G41.md`

---

## 13. Limitaciones

- Fuente fake; lecturas 71–73 % sintéticas.
- Pytest TC-M03-101 permanece SKIPPED en matriz automatizada.
- PID no está volcado en cada poll; sí en cuatro hitos y por `NRestarts`.
- Journal de apply/restore incluye el restart de **preparación** (21:18); no ocurrió en la ventana 101.
- SHA final distinto del original.
- `mqtt.stop` es un marcador auxiliar (1 byte); no es evidencia.

---

## 14. Resultado final

| Capa | Resultado |
|---|---|
| Ejecución reportada | APROBADO (laboratorio fake) |
| Auditoría documental de esta fecha | **`APROBADO Y DOCUMENTALMENTE VERIFICADO`** |
| Pytest `test_tc_m03_101_umbrales_en_caliente` | **SKIPPED** (sin cambio) |

---

## 15. Organización documental

Clasificación A/B/C/D en `PROPUESTA_ENTREGA_G41.md`. Originales de evidencia **no** se movieron ni se reescribieron para “mejorar” el PASS. Este cierre y la propuesta son archivos **nuevos**.

---

## 16. Archivos propuestos para `laura`

Lista exacta y hashes: `PROPUESTA_ENTREGA_G41.md` sección C. Destino = mismas rutas bajo `tests/Test_Testing/Test_Modulo3/RF-55/TC-M03-G41/` (hoy untracked, salvo `test_tc_m03_g41.py` y `.gitkeep` ya versionados).

---

## 17. Rama auxiliar

No hay una rama cuyo nombre coincida de forma inequívoca con «Laura» **y** «TESTS». Candidatas observadas (sin asignar archivos por suposición): `origin/test`, `laura-sync-test`, `laura-publish-m03-m04-scripts`, `laura-g38-essential-evidence`. Los auxiliares de firmware permanecen en el worktree `qa/rf55-validation-e618a75`.

---

## 18. Pendientes Git (esperan autorización expresa)

1. `git add` **solo** de la lista C de la propuesta (nunca `git add .`).  
2. Commit en `laura` con mensaje acordado.  
3. Push **solo** si el usuario lo pide aparte (`laura` está ahead 536 / behind 1 respecto a `origin/laura`).  
4. No merge, cherry-pick ni rebase. Conservar cambios de M02, G38, G34/G35, M09, etc.
