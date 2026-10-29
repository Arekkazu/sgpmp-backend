# 36 — Auditoría de snapshot y restore TC-M09-179 rev12

**G94:** pendiente (no se cambia). Cypress **no** se ejecutó. Sin PATCH/POST/PUT/DELETE a TEST, sin commit.

**Veredicto de preparación:** **LISTA PARA EJECUCIÓN CONTROLADA**, condicionada a autorización explícita de escritura en finca 1. No bloqueada por contrato ni por el arnés.

---

## 1. Fuentes inspeccionadas

- Spec/config rev12; `35_preparacion_rev12.md`; `34_plan_cierre_brechas.md`; `33_auditoria_documental_final.md`
- Spec histórico `tc_m09_g94_179_rev4_test.cy.js` y `G94-rev4-179-snapshot-identidad.json`
- Contrato: `identidad_visual_router.py` PATCH Form; `ActualizarIdentidadVisualDTO`; `actualizar_identidad_visual_use_case.py`; `IdentidadVisual.actualizar`; `IdentidadVisualResponse`; curls CU-06 Flujo C (412, logo omitido se conserva)

---

## 2. Hallazgos — snapshot

| Pregunta | Hallazgo |
|---|---|
| Endpoint original | `GET /configuracion/identidad-visual/1` (admin, recurso 23). Tema: `GET /configuracion/personalizacion/tema` (productor, 24). |
| Campos GET | Contrato: `id_identidad_visual`, `id_finca`, `id_usuario`, `logo_path`, `primary_color`, `secondary_color`, `org_display_name`, `version`, `fecha_creacion`, `accesibilidad` (derivado, no se restaura). |
| Campos PATCH | Form **obligatorios**: `primary_color`, `secondary_color`, `org_display_name`, `version`. `logo` archivo opcional. |
| Snapshot previo | Rev12 capturaba primary/secondary/org/version/logo_path (como rev4). **No** persistía `id_finca` ni validaba secondary/org contra el DTO. |
| Riesgo de pérdida | `logo_path`: el use case pasa `logo_path=None` si no hay archivo; `actualizar()` **no** pisa el logo. Omitir `logo` es correcto; **no** enviar archivo vacío. `id_usuario` **sí** cambia al admin que PATCHea (no está en el DTO; residual). `accesibilidad` se recalcula. `version` incrementa. |
| Secretos | GET identidad no trae JWT. Login bodies no se escriben. |

**Defecto corregido:** el snapshot ahora exige hex de secondary, org 1–50 chars, `id_finca===1` y persiste el cuerpo de restore en `G94-rev12-179-paquete-recuperacion.json` **antes** de cualquier PATCH.

---

## 3. Hallazgos — restauración por escenario

| # | Escenario | ¿Garantizado? |
|---|---|---|
| 1 | `it` PASS | Sí: `after()` restore con login fresco + GET de verificación. Mocha FAIL si GET ≠ snapshot. |
| 2 | Aserción tras PATCH 200 | Sí: `patchedId`/`patchedTema` se marcan tras HTTP de escritura; `after` corre. |
| 3 | Falla login productor UI | Sí para **no empeorar**: no hay snapshot de tema ni PATCH. Identidad no se toca. Restore omitido. |
| 4 | Error Cypress recuperable (expect, timeout) | Sí: `after`/`afterEach` suelen ejecutarse. |
| 5 | Restore PATCH 401 | Sí como **fallo visible**: `pendiente`, no se reusa JWT SPA, no reintento, `expect` en `after`. Archivo `RESTORE-PENDIENTE.json`. |
| 6 | Otro HTTP (412, 403, 500) | Igual: un intento, `pendiente`, sin bucle. 412 = `CONFLICTO_CONCURRENCIA` en contrato. |
| 7 | Proceso/Cypress abortado | **No.** Hooks no corren. Riesgo residual → `RECUPERACION_MANUAL.md`. |
| 8 | Restore HTTP 200 y estado ≠ snapshot | **Antes no:** solo se comparaba `primary_color`. **Ahora:** primary, secondary, org, `logo_path`; `pendiente` + `expect`. |

**Defecto corregido:** si el PATCH de estímulo se **envía** pero el `.then` no marca 200 (`escrituraIdentidadIniciada` / `escrituraTemaIniciada`), el `after` igual intenta restore (evita el hueco “respuesta perdida / expect de status”).

El preflight sigue siendo **solo GET + login**. No puede probar el permiso U de PATCH sin escribir.

---

## 4. Correcciones realizadas (solo rev12 local)

- Snapshot: campos del contrato + validación DTO; paquete de recuperación antes de PATCH.
- Restore si hubo **intento de escritura**, no solo HTTP 200.
- GET final compara colores, org y logo.
- `RESTORE-PENDIENTE.json` si no coincide.
- `RECUPERACION_MANUAL.md` (sin secretos).
- `NO_EJECUTADO.md` conservado (sigue sin ejecución).

**No modificado:** RLS, producto, evidencias rev4/rev11/178-rev4, estado G94.

---

## 5. Archivos modificados / creados

| Archivo | Acción |
|---|---|
| `sgpmp-backend/tests/.../TC-M09-G94/tc_m09_g94_179_rev12_test.cy.js` | Fortalecido |
| `.../Resultados/179-rev12/RECUPERACION_MANUAL.md` | Creado |
| `.../Resultados/179-rev12/NO_EJECUTADO.md` | Conservado; nota a recuperación |
| `analisis_TC-M09-G94/36_auditoria_restore_rev12.md` | Este informe |
| `cypress.config.179.rev12.cjs` | Sin cambio de rutas (`Resultados/179-rev12/`) |

---

## 6. Validaciones estáticas

- `node --check` spec + config: **exit 0**.
- Rutas: `specPattern` → `tc_m09_g94_179_rev12_test.cy.js`; `reportDir` → `Resultados/179-rev12`; `trashAssetsBeforeRuns: false`.
- PATCH identidad: `form: true`, mismos cuatro campos que el router. Sin `logo`.
- Restore tema: JSON `{ theme_mode }` como `guardar_tema_dto.py`.
- Sin `npx cypress run`. Sin peticiones a TEST en esta fase.

---

## 7. Procedimiento de recuperación (interrupción abrupta)

Resumen (detalle en `Resultados/179-rev12/RECUPERACION_MANUAL.md`):

1. Leer `paquete-recuperacion.json` / snapshot. Si no existen, no escribir.
2. Login fresco admin → GET identidad 1. Un PATCH form con snapshot y **version del GET vigente**. Omitir logo. GET de comprobación.
3. Login fresco productor → GET tema. Un PATCH `{ theme_mode }` del snapshot si diverge.
4. 401/412: parar. No bucle. No `/tema/global`. No otras fincas.

---

## 8. Riesgos residuales

1. Kill/crash de Cypress o de la máquina: hooks no corren.
2. Preflight no demuestra permiso de **escritura** (U) ni un PATCH de restore.
3. `id_usuario` de la fila de identidad pasa a ser el admin restaurador (comportamiento del use case, no del DTO).
4. 412 por edición concurrente de la finca 1: un intento y fallo visible.
5. Restore de tema con valores snapshot cuando el PATCH de estímulo no llegó a aplicarse: posible incremento de `version` de identidad o reescritura de tema al mismo valor (escritura extra benigna respecto al baseline).
6. El oráculo de marca (`#757575`) no se revalida hasta la corrida autorizada.

---

## 9. Veredicto

**LISTA PARA EJECUCIÓN CONTROLADA.** Es **seguro solicitar autorización** de una corrida TEST, con ventana acordada y el procedimiento de recuperación a mano. No es seguro afirmar que G94 queda aprobado tras esa corrida hasta ver Mocha (incluido `after`) y los JSON de restore.

Comando (no ejecutado):

```
npx cypress run --config-file tests/Test_Testing/Test_Modulo9/RF-27/TC-M09-G94/cypress.config.179.rev12.cjs
```
