# 01 — Diagnóstico ejecutivo TC-M09-G94

**Caso:** TC-M09-G94 (TC-M09-178 + TC-M09-179)  
**Requerimiento:** RF-27  
**Caso de uso:** CU-06 — Personalizar Interfaz del Sistema  
**Rama analizada:** `sgpmp-backend` HEAD / `origin/laura` = `37efcd26`  
**Alcance de este informe:** solo lectura. No se modificó el veredicto histórico, no se reescribió evidencia, no se ejecutó restauración ni escritura contra TEST, no hay commit ni push.

---

## Resumen ejecutivo

El grupo G94 permanece **RECHAZADO** de forma coherente con el reporte automático de Cypress de la revisión 4 de TC-M09-179, no con el acta narrativa que clasifica esa corrida como APROBADO.

En rev4:

- La aserción de variante automática **sí se ejecutó y coincidió** con lo esperado (`--brand-500` = `#757575`, `data-theme=light`).
- axe registró **1 violación** `color-contrast` (16 nodos en pases). El spec **no aserta** `violations === 0`.
- El hook `after()` falló al restaurar el tema del productor: `restore theme_mode HTTP: expected 401 to equal 200`.
- Mocha/Cypress marca la suite como **fail**: `passes: 0`, `failures: 1`.
- El acta `G94-rev4-179-ejecucion.txt` declara 179 APROBADO y una “RESTORE API posterior” exitosa.

El antecedente del líder **queda confirmado por evidencia automática**: no se debe aprobar el caso solo porque la narrativa dice que la variante pasó. El fallo del hook es real en el runner.

Ese `401` **no demuestra por sí solo un defecto de accesibilidad del producto**. La evidencia disponible apunta a un **defecto del arnés de prueba** (JWT de productor capturado en el login y reutilizado tras `cy.visit('/dashboard')`, cuando el SPA rota/revoca el access token). La misma clase ya está documentada en G95.

---

## Estado real por subcaso

| Subcaso | Última ejecución TEST con artefactos | Resultado funcional | Accesibilidad | Limpieza | Veredicto usable para el grupo |
|---|---|---|---|---|---|
| TC-M09-178 | rev2 (`G94-rev2-test-ejecucion.txt`) | Login + contexto + axe en dashboard | 0 violaciones axe en la muestra (12 nodos aplicables; 0 “aplicables” en el JSON de detalle) | Restauración 179 no aplica a 178 | APROBADO **solo** como muestra de dashboard, no como “todo el tema” |
| TC-M09-179 | rev4 (Cypress JSON + acta) | Variante CSS aplicada en el `it` | axe: 1 violación; no hay aserción de 0 | Hook Cypress 401; acta alega restore posterior | **FAIL automático**. Acta APROBADO. Grupo se mantiene RECHAZADO |

**Clasificación:** el estado global del grupo G94 como RECHAZADO está **confirmado por evidencia** (reporte Mocha rev4). El APROBADO del acta es **discrepancia documentada**, no veredicto automático.

---

## Conclusión

1. **Resultado funcional (variante):** en rev4 hay evidencia de que el backend calculó `color_ajustado=#757575` para `#FFFFFF` sobre claro (`ratio=1`, `cumple_aa=false`) y el frontend pintó `--brand-500` con ese valor. **Confirmado por evidencia** (`G94-rev4-179-css-despues.json`, cuerpo del `it` en el JSON Mocha).
2. **Resultado de accesibilidad (4.5:1 de la UI resultante):** **no demostrado**. axe dejó 1 violación y el spec no falló por eso. 178 solo cubre una página y una regla. **Confirmado por evidencia** (alcance limitado) + **no verificable** el cumplimiento de “todo el tema”.
3. **Resultado de limpieza (hook Cypress):** **falló**. PATCH tema con Bearer de productor → 401. **Confirmado por evidencia** (`TC-M09-G94_179_rev4_test.json`).
4. **Limpieza posterior alegada en el acta:** GET/PATCH fuera de Cypress. **Inferencia razonable pendiente de verificación** respecto a si TEST quedó realmente en `theme_mode=2` e identidad `#1A6B3C` *hoy*; el acta lo afirma para el momento de la corrida.
5. **Causa del 401:** **inferencia razonable pendiente de verificación en una corrida controlada**: rotación `TOKEN_REVOCADO` tras refresh del SPA, no ausencia de contraseña (el login UI fue 200). El cuerpo JSON de la respuesta 401 **no está persistido** en artefactos G94. **No verificable** el `code` exacto (`TOKEN_REVOCADO` vs otro) en G94; sí está documentado para la misma clase en G95.

**No se cambia el veredicto histórico. La nueva ejecución queda pendiente de autorización explícita.**

---

## Hallazgos clasificados

| Id | Hallazgo | Clase | Evidencia |
|---|---|---|---|
| H1 | Mocha rev4: 0 pases, 1 fallo | Confirmado | `tests/Test_Testing/Test_Modulo9/RF-27/TC-M09-G94/Resultados/TC-M09-G94_179_rev4_test.json` |
| H2 | El error es `after all`, no la aserción `--brand-500` | Confirmado | mismo JSON, `err.message` |
| H3 | `--brand-500` = `#757575` con `data-theme=light` | Confirmado | `G94-rev4-179-css-despues.json` |
| H4 | axe rev4: 1 `color-contrast`, 16 nodos en pases | Confirmado | `G94-rev4-179-axe.json` (sin nodos fallidos detallados) |
| H5 | Acta clasifica 179 APROBADO | Confirmado | `G94-rev4-179-ejecucion.txt` |
| H6 | 178 rev2 APROBADO con 0 violaciones en muestra | Confirmado | `G94-rev2-test-ejecucion.txt`, `G94-rev2-178-axe.json` |
| H7 | 179 rev2 RECHAZADO: UI no aplicó variante (finca 34) | Confirmado | `G94-rev2-test-ejecucion.txt` |
| H8 | El 401 es de PATCH tema en restore, no de login | Confirmado | spec `after()` L82–114; mensaje `restore theme_mode HTTP` |
| H9 | Causa TOKEN_REVOCADO por refresh SPA | Inferencia razonable | `anotaciones/modulo_9/tc_m09_g94_contexto_401_no_es_bug.md`; `G95-rev2-test-restauracion.txt` |
| H10 | Playwright no se usó en G94 | Confirmado por ausencia | solo specs Cypress en `TC-M09-G94/` |
| H11 | Estado actual de TEST (tema/identidad) | No verificable en esta fase | no se consultó TEST en escritura; no hay GET posterior fechado aparte del acta |

---

## Qué no se hizo (restricciones)

- No se llamó PATCH/POST de restauración contra TEST.
- No se parcheó el hook Cypress.
- No se alteró el veredicto ni se borró evidencia histórica.
- No se ejecutó de nuevo Cypress/Playwright/Newman.
