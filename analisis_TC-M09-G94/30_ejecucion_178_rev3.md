# 30 — Ejecución Cypress TC-M09-178 rev3 TEST

**Fecha/hora:** 2026-10-10, Mocha `2026-10-10T17:21:57.283Z`–`17:21:57.654Z` (UTC). Duración **371 ms**. Cypress 14.5.4 / Electron 130.

**G94 permanece RECHAZADO.** Una sola corrida. **No** se repitió. Sin PATCH, sin cambios de identidad/tema/RLS, sin commit/push/deploy. No se interpretó este fallo como incumplimiento visual.

```
npx cypress run --config-file tests/Test_Testing/Test_Modulo9/RF-27/TC-M09-G94/cypress.config.178.rev3.cjs
```

Directorio: `sgpmp-backend`. Precondiciones OK (informe 29, spec/config TEST, solo lectura, `Resultados/178-rev3/`, `CYPRESS_contrasena` presente).

---

## Resultado Cypress

| | |
|---|---|
| Exit | **1** |
| Mocha | 1 test, **0 passing**, 1 failing |
| Usuario previsto | `admin@pecuaria.co` |
| Llegada al dashboard | **No demostrada** (`last_step`: `inicio`) |
| Causa | Arnés: `apiGetLectura` se invocó **en el turno síncrono** del `it` (`expect(tokenAdmin)` con token aún `null`) **antes** de que `cy.wait('@loginAdmin')` asignara el token |

Mensaje: `token GET /configuracion/personalizacion/tema: expected null to be a string`.

No es un FAIL de contraste, axe ni tema. El login UI **no** llegó a evaluarse; la cola Cypress abortó al registrar el GET.

---

## Tema, colores, ratios, axe

**No medidos.** No hay `diagnostico.json`, `sidebar-nodos.json` ni `contexto.json`.

`G94-178-rev3-axe.json`: `ejecutado: false`; **no** se declara `color-contrast = 0`.

Captura de fallo: pantalla residual del runner (no se afirma que sea el dashboard TEST).

---

## Integridad TEST

| Acción | |
|---|---|
| PATCH tema / identidad | No |
| POST/DELETE negocio | No (el POST login no se confirmó 200) |
| Restore | No aplica |
| Evidencia histórica rev2 | Intacta (directorio distinto) |

---

## Evidencias (exclusivas 178-rev3)

Base: `sgpmp-backend/tests/Test_Testing/Test_Modulo9/RF-27/TC-M09-G94/Resultados/178-rev3/`

- `TC-M09-G94_178_rev3_test.json` / `.html`
- `G94-178-rev3-ejecucion.txt`
- `G94-178-rev3-ultimo-paso.json`
- `G94-178-rev3-axe.json` (no ejecutado)
- `screenshots-178-rev3-test/tc_m09_g94_178_rev3_test.cy.js/TC-M09-178 rev3 TEST -- TC-M09-178 verifica contraste minimo WCAG 4.51 en dashboard (tema activo) (failed).png`

Ausentes (no se alcanzó): contexto, diagnóstico, sidebar.

---

## Conclusión

| | |
|---|---|
| TC-M09-178 rev3 | **FALLÓ** (arnés, no WCAG) |
| Contraste / axe admin dashboard post-deploy | **Sin verificar** |
| TC-M09-179 rev11 | Sigue PASS (ciclo anterior) |
| G94 | **RECHAZADO** |

Siguiente paso (cuando se autorice, **otra** revisión de spec): envolver `apiGetLectura` en `cy.then()` **después** del login, como en 179. No se corrigió ni reejecutó en esta autorización.
