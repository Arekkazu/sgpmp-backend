# PROPUESTA DE ENTREGA G41 — espera autorización del usuario

**No se hizo commit, push, merge, cherry-pick, rebase ni `git add`.**

---

## A. Rama principal de destino

`sgpmp-backend`, rama **`laura`**, HEAD `d097c33d`.  
Tracking: `origin/laura` (**ahead 536, behind 1**). El behind 1 es un riesgo de integración ajeno a G41; no se resuelve en esta propuesta.

Los archivos oficiales **ya están** en el working tree de `laura` (untracked). Destino = misma ruta. No hace falta copiar a otra carpeta salvo que el usuario lo pida.

---

## B. Rama auxiliar «Laura / TESTS»

Inspección (`git branch -a` en `sgpmp-backend`):

| Nombre exacto | ¿Coincide con «Laura» y «TESTS»? |
|---|---|
| `laura` | Solo Laura |
| `laura-sync-test` | Laura + test (worktree `.worktrees/sgpmp-laura-sync-test`, mismo commit `d097c33d`) |
| `laura-g38-essential-evidence` | Laura + G38, no TESTS |
| `laura-publish-m03-m04-scripts` | Laura + scripts M03/M04 |
| `origin/test` | TESTS, no Laura |
| `test` (local) | TESTS, no Laura |

**No hay un nombre inequívoco «Laura TESTS».** No se asignan archivos a una rama por suposición. Los auxiliares de firmware se conservan en el worktree `qa/rf55-validation-e618a75`.

---

## C. Tabla de archivos para `laura` (paquete oficial)

Prefijo origen y destino (relativo a `sgpmp-backend/`):

`tests/Test_Testing/Test_Modulo3/RF-55/TC-M03-G41/`

Hashes SHA-256 calculados sobre los archivos reales (PowerShell `Get-FileHash`). Tamaño en bytes.

| Origen (= destino) | Descripción | Justificación | Criterios | Bytes | SHA-256 |
|---|---|---|---|---:|---|
| `RESULTADO_EJECUCION_TC_M03_101.md` | Informe de la corrida funcional | Relato oficial, alcance fake | todos (síntesis) | 7230 | `e6624940992d6c8f63b8f6d4cd4dcee7d379d191e4d5f9bb6935be4c2f7eae93` |
| `RESULTADO_PREPARACION_PREVIA_G41.md` | Fake + PID 9022 + un restart previo | Trazabilidad de la fuente sintética | 10 (contexto PID), fake | 7002 | `b04526423c1df4b43be2a4f893a05717e598646711f6ff5a19c6cf15cdc45fe0` |
| `CIERRE_FINAL_G41.md` | Auditoría de cierre | Matriz documental 11 criterios | todos | 10836 | `7a67209ae1c134782f33cc728647551100003421a8d6921d02bffd4e675f045d` |
| `PROPUESTA_ENTREGA_G41.md` | Esta propuesta | Entrega Git | n/a | (recalcular tras guardar) | El SHA-256 de *este* archivo cambia al editarlo; verificar con `Get-FileHash` en el momento del `git add` |
| `Resultados/evidencias/run-2026-10-30-g41-tc101/medicion_t0.json` | Historial t0 | Medición inicial | 1, 2 | 490 | `09fd07716fb670db8b26eb421c8bcd72f197b4a4dc7a4547c5d68cf960a11a49` |
| `…/medicion_posterior.json` | Historial post-ACK | Medición posterior | 8 | 486 | `4a92c6ea7d4ae07596fbd570ff3f6de7f56a15cef32bb50ae7be2e15bae42f2a` |
| `…/medicion_restaurada.json` | Historial post-restore | Restauración observada | 11 | 491 | `ba6dfbd06523760a19abed23e773482229e50a0924f71c1a4adee5e706e1cc15` |
| `…/evento_posterior_mqtt.json` | Evento MQTT crítico | id 65 + versión ensayo + critico | 6, 9 | 989 | `dee2d3f8e4a766d7ab28653090d08463342eae3b5e4a74b9b2d5a862fe15161b` |
| `…/http_aplicacion.json` | POST apply | HTTP (no ACK) | 3 | 420 | `c50a295de3f9d72973667d5895729e9482f289ef539781e2d7d6eedd77baa5af` |
| `…/http_restauracion.json` | POST restore | HTTP restore | 11 | 420 | `44cf4d9006044e01efefea0e178265135b8ee8044397215ad67ea065d5d29617` |
| `…/ack_aplicacion.json` | ACK MQTT apply | Distinto de HTTP | 4 | 287 | `71b0c05a885e5331bef613ed97c8346cdb74a3e196ccde703318d6f7cd0473a2` |
| `…/ack_restauracion.json` | ACK MQTT restore | Restauración | 11 | 287 | `2280a70192f458ce47d885280ed14863616be810ea4f21f3453d1f1a484c53e9` |
| `…/payload_aplicacion.json` | Cuerpo umbral ensayo | Sin secretos | 3, 7 | 576 | `fdc3808dee9d8b06abd7286a0e29cdf4dc722d8c03bbc6e6493590b9ea203b10` |
| `…/payload_restauracion.json` | Cuerpo restore | Bandas originales | 11 | 576 | `014dc60b5a531f281e59fda35289e7f8ae8b583b4c11caf7856ab1ce109197cd` |
| `…/snap_preflight.json` | PID/SHA/umbral t0 | Continuidad + original | 7, 10 | 4489 | `1653211a3c5b8821f80a88bb2a2fb6c65bb762343e8ff959321ed0de525c8b02` |
| `…/snap_antes_post.json` | PID antes POST | Continuidad | 10 | 5636 | `23eea046ef45a87a4a51e01605a9b711e786e9a1762f1e050856811ff7b97b8d` |
| `…/snap_despues_apply.json` | JSON persistido ensayo | Disco ≠ RAM | 7 | 5639 | `ce9448f5be668fe01b633fff03e9be051c28d671642ca730aa4a7ee20ff53747` |
| `…/snap_final.json` | PID final + restore | 10, 11 | 7351 | `8954ae009b8d86650eeb675b6cf7d380a3fea282063fc8aab9ef7a2b9f2ae1aa` |
| `…/journal_apply.txt` | Log Edge apply | Aplicación firmware | 5 | 1154 | `9923d997e98f49411ab22a8b2611a33016aefcdb107bb07f3e9736dd73cc70b9` |
| `…/journal_restore.txt` | Log Edge restore | Segundo `OK (guardado)` | 5, 11 | 1249 | `9109fa483cc8c1d1d0119c488abcb7479a1d42623047f56f2d59a6ef46f64d37` |
| `…/mqtt_session.json` | SUB completo | Cadena command/ACK/eventos/heartbeats | 1,2,4,6,9,10,11 | 18169 | `d70f725884e434d5e9bdadd738a8a477a406d22cf13760e81e7879db76954f24` |
| `…/log_orquestador.json` | Criterios máquina | Trazabilidad orquestador | síntesis | 6846 | `98f50fe6483104305e85754ac5bade00d95c054ef822d94ee05a3a5d5c2dba2e` |
| `automatizacion_tc101/ejecutar_tc101.py` | Orquestador (secretos solo stdin) | Reproducibilidad autorizada | n/a | 30080 | `d92998bd84c60667fbb1c4cb858ad5d9b30cc051db98c79ad4820c43809c5424` |
| `automatizacion_tc101/ejecutar_tc101.ps1` | Get-Credential wrapper | Sin secretos persistidos | n/a | 1527 | `61e0240019d785755c8985743649cb850ea9e6d122e1530e34e58040d4a139e0` |

`test_tc_m03_g41.py` y `.gitkeep` **ya están** en `laura`; no se reañaden ni se modifican.

Revisión de secretos en el paquete C: no hay `Authorization`, contraseñas ni tokens. Sí hay IP/host de broker TEST (ya públicos en G38).

---

## D. Archivos auxiliares (no subir en el primer commit de aprobación)

| Archivo | Rama propuesta | Motivo | Riesgo |
|---|---|---|---|
| `run-…/hist_poll_t0.json`, `hist_poll_post.json`, `hist_poll_restore.json` | ninguna (quedar untracked o worktree) | Volcados intermedios redundantes con `medicion_*.json` | Ruido en revisión |
| `run-…/mqtt.stop` | no subir | Semáforo interno (1 byte) | Ninguno útil |
| `automatizacion_etapa1/**` y `Resultados/evidencias/run-2026-10-31-g41-etapa1*` | no asignar a rama inventada | Dry-run etapa 1; **no** aprueban 101 | Confundir DRY_RUN con APROBADO |
| `Resultados/evidencias/AUDITORIA_*.md`, `DIAGNOSTICO_*.md`, `INVESTIGACION_*.md`, `ANALISIS_RECUPERACION_RF55.md`, `CORRECCIONES_*.md` | opcional `laura` en un segundo commit de “bitácora G41” | Apoyo técnico | Volumen |
| `Resultados/TC-M03-101/**`, `PLAN_TC-M03-101_NO_EJECUTADO.md`, pytest G41 2026-10-25 | opcional `laura` (histórico SKIPPED) | No borrar; no es la corrida 30 oct | Confusión de fechas |
| Worktree firmware: `PLAN_*.md`, `preparar_fake_g41*`, `verificar_fake_g41*`, `lectura_umbral65*`, `diagnostico_ssh*`, tests `test_umbral_store_todos.py`, `test_store_evaluador_rf55.py` | **solo** `qa/rf55-validation-e618a75` | Firmware/QA aislado | No mezclar con `laura` |
| `preparar_fake_g41_remoto.txt`, `verificar_fake_g41_remoto.txt`, `ssh_diagnostico_remoto.txt` | no `laura` | Logs remotos; revisar si algún futuro dump trae secretos | Posible dato de infra |

---

## E. Conservar sin mover (D y ajenos)

- Todo G38 (`TC-M03-G38/`, worktree `laura-g38-essential-evidence`).  
- G34, G35, G36, G57, M09, `tests/integration/*` modificados, `mochawesome-report/`.  
- `src/` firmware, Raspberry, `.env`.  
- Cambios staged/unstaged de M02 en `laura`.

---

## F. Estado Git antes de incorporar (inspección)

**`sgpmp-backend` / `laura`:** untracked G41 (informes + Resultados + automatizacion_*), más muchos untracked ajenos (M09, RF-54, G38 STOP files, etc.) y modified M02. **Prohibido `git add .`.**

**`.worktrees/sgpmp-rf55-validation` / `qa/rf55-validation-e618a75`:** untracked `raspberry/tests/test_store_evaluador_rf55.py`, `test_umbral_store_todos.py`, `tests/` (G41 planes y scripts de Pi).

**`.worktrees/sgpmp-g38-essential`:** `laura-g38-essential-evidence` — no tocar.

**`.worktrees/sgpmp-laura-sync-test`:** `laura-sync-test` @ mismo `d097c33d` — no tocar.

---

## G. Operaciones **después** de autorización expresa (no ejecutadas)

1. En `sgpmp-backend`, permanecer en `laura`.  
2. `git add` **solo** las rutas de la tabla C (más `CIERRE_FINAL_G41.md` y este archivo).  
3. `git status` para confirmar que no entra G38/M09/M02.  
4. Commit con mensaje del estilo: documentar aprobación de laboratorio TC-M03-101 G41 (fuente fake).  
5. Push únicamente con una segunda autorización (`ahead 536` / `behind 1`).

---

## H. Confirmación

- Commit: **no**.  
- Push: **no**.  
- Staging: **no**.  
- Merge / cherry-pick / rebase / cambio de rama: **no**.  
- Raspberry / POST / MQTT comando / re-run 101: **no**.
