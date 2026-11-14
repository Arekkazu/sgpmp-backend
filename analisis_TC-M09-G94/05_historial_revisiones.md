# 05 — Historial de revisiones TC-M09-G94

Solo revisiones con artefactos en el repositorio. No se inventan corridas.

Ruta base: `sgpmp-backend/tests/Test_Testing/Test_Modulo9/RF-27/TC-M09-G94/`

---

## Tabla

| Revisión | Resultado funcional | Resultado del hook de restauración | Evidencia automática | Declaración manual | Veredicto registrado | Observaciones |
|---|---|---|---|---|---|---|
| **rev1** (DEV, 2026-09-14) | 178: no se midió contraste (falló GET contexto). 179: Cypress pending, sin PATCH | Restauración 179 “no aplicó” (no hubo cambio) | Cypress: 2 registered, 0 pass, 1 fail, 1 pending (`G94-rev1-dev-ejecucion.txt`). Spec `tc_m09_g94.cy.js` | Acta en el mismo txt | 178 FAIL; 179 pending | Login dashboard sí; contexto 401. Entorno DEV, no TEST |
| **rev2** (TEST) | 178: axe 0 violaciones (12 nodos). 179: API `color_ajustado` sí; UI `--brand-500` **no** cambió (`#1A6B3C`) | 179: restore identidad 200 según acta; no hay JSON Mocha de hook 401 | `G94-rev2-178-axe.json`; `G94-rev2-test-ejecucion.txt`; spec `tc_m09_g94_rev2_test.cy.js` | Acta: 178 APROBADO; 179 RECHAZADO | 178 APROBADO; 179 RECHAZADO | Admin finca **34**; CSS no aplicó variante. NAV ratio 1.15 marcado no aplicable |
| **rev3** (TEST, 179) | Incompleto: `data-theme` no llegó a `light` a tiempo / null | Restore vía Python citado en acta (no el after Cypress como protagonista del fail) | Spec `tc_m09_g94_179_rev3_test.cy.js`; `G94-rev3-179-ejecucion.txt` | Acta de timing | No hay PASS 179 | Carrera CSS vs visita |
| **rev4** (TEST, 179, 2026-09-25T07:19Z) | Variante CSS `--brand-500=#757575`, `data-theme=light`. API ratio 1 / `cumple_aa` false | `after all`: PATCH tema **401** vs 200. Acta: restore API **posterior** identidad `#1A6B3C` y `theme_mode=2` | `TC-M09-G94_179_rev4_test.json` (0 pass / 1 fail); `G94-rev4-179-css-despues.json`; `G94-rev4-179-axe.json` (1 violación) | `G94-rev4-179-ejecucion.txt` clasifica 179 **APROBADO** (“el fail de Mocha es el hook”) | **Automático: FAIL.** **Acta: APROBADO.** **Grupo G94: RECHAZADO** (antecedente del líder, alineado al automático) | Discrepancia acta vs Mocha. Axe 1 violación no asertada |

No hay artefactos de rev5+ de G94 en el árbol inspeccionado.

---

## Por qué rev4 quedó rechazada (grupo)

El líder no dejó que el acta textual anulara el fail automático. Eso coincide con:

1. `stats.failures === 1`, `passes === 0`.
2. Mensaje explícito de hook `after all`.
3. Criterio de integridad: restore 200 forma parte de la ejecución controlada; un 401 deja el procedimiento incompleto **aunque** la variante se hubiera visto.

Además, aunque se ignorara el hook, axe 1 violación impediría afirmar AA de la UI resultante. El acta **no** usa esa violación como RECHAZADO; usa APROBADO. El rechazo institucional del grupo se sostiene sobre el **reporte automático**, no sobre axe.

**Confirmado:** el antecedente del líder es consistente con `TC-M09-G94_179_rev4_test.json`.

---

## Discrepancias abiertas o resueltas

| Discrepancia | Fuentes | Resolución |
|---|---|---|
| Acta rev4 APROBADO vs Mocha FAIL | `G94-rev4-179-ejecucion.txt` vs JSON | **Resuelta para el veredicto de grupo:** prevalece el automático (RECHAZADO). El acta documenta la variante, no el PASS del runner |
| “La aserción de variante pasó” vs `state: failed` del `it` | JSON `code` vs `err` | **Resuelta:** Cypress atribuye el fail del hook al test. Los `writeFile` de CSS/axe existen; no hay `pass: true` |
| Restore 401 vs restore posterior OK | JSON vs acta | **Parcialmente abierta:** el hook falló (**confirmado**); el restore posterior es **narrativa**. Estado TEST actual **no verificable** aquí |
| Matriz “Playwright / Cypress-axe” vs repo solo Cypress | enunciado vs `TC-M09-G94/*.cy.js` | **Resuelta:** la implementación es Cypress + axe-core. Playwright no aparece |
| 178 APROBADO vs grupo RECHAZADO | rev2 vs G94 | **Resuelta:** el grupo exige 178+179; 179 no tiene PASS automático |
| 401 “¿bug de producto?” vs nota `401_no_es_bug` | hook vs `anotaciones/modulo_9/tc_m09_g94_contexto_401_no_es_bug.md` | **Abierta en el detalle del code:** clase TOKEN_REVOCADO **inferida**; body G94 ausente |

---

## Matriz de evidencias por revisión (archivos)

### rev1

- `Resultados/G94-rev1-dev-ejecucion.txt`

### rev2

- `Resultados/G94-rev2-test-ejecucion.txt`
- `Resultados/G94-rev2-178-axe.json`
- `Resultados/G94-rev2-178-axe-aplicables.json`
- Spec: `tc_m09_g94_rev2_test.cy.js`

### rev3

- `Resultados/G94-rev3-179-ejecucion.txt`
- Spec: `tc_m09_g94_179_rev3_test.cy.js`

### rev4

- `Resultados/TC-M09-G94_179_rev4_test.json` (+ `.html`, `.xml` si existen junto al JSON)
- `Resultados/G94-rev4-179-ejecucion.txt`
- `Resultados/G94-rev4-179-axe.json`
- `Resultados/G94-rev4-179-css-despues.json`
- Spec: `tc_m09_g94_179_rev4_test.cy.js`
- Config: `cypress.config.179.rev4.cjs`

### Contexto de 401 (no es acta de veredicto)

- `sgpmp-backend/anotaciones/modulo_9/tc_m09_g94_contexto_401_no_es_bug.md`
- Analogía: `tests/Test_Testing/Test_Modulo9/RF-28/TC-M09-G95/Resultados/G95-rev2-test-restauracion.txt`

---

## Cierre documental 2026-10-10 (no sustituye las filas históricas)

Las filas de rev1–rev4 y el veredicto **RECHAZADO** de este archivo **siguen siendo el registro de aquel corte**. Artefactos rev5–rev12 existen en informes `08`–`44` y en `Resultados/`; no se reescriben aquí.

| Corte vigente | Resultado funcional | Restauración | Veredicto de grupo |
|---|---|---|---|
| 178-rev4 + 179-rev11 + **179-rev12 corrida final** | 178 PASS (axe 0, sidebar 6.47). 179-rev11 PASS (`#249453` dark). 179-rev12 PASS (`#757575` light) | 179-rev12 GET final = snapshot; sin `RESTORE-PENDIENTE.json`. Corridas 38 y 42 de rev12 **FAIL** (arnés); historial conservado | **APROBADO** — `45_cierre_final_G94.md` |

Discrepancia «178 APROBADO vs grupo RECHAZADO» de la tabla anterior queda **cerrada** por 179-rev11 y 179-rev12 PASS automáticos, no por el acta Mocha-fail de 179-rev4.
