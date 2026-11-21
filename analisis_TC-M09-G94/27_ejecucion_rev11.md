# 27 — Ejecución Cypress TC-M09-179 rev11 TEST

**Fecha/hora:** 2026-10-10, Mocha `2026-10-10T17:09:55.097Z`–`17:10:05.791Z` (UTC). Duración **10694 ms**. Cypress 14.5.4 / Electron 130.

**G94 no se marca APROBADO.** TC-M09-179 rev11 **PASÓ** (1/1). TC-M09-178 **no** se reejecutó en este ciclo.

Una sola corrida. Exit Cypress **0**. Sin commit, push ni deploy. Sin PATCH de identidad, RLS ni `/tema/global`.

```
npx cypress run --config-file tests/Test_Testing/Test_Modulo9/RF-27/TC-M09-G94/cypress.config.179.rev11.cjs
```

Directorio de trabajo: `sgpmp-backend`. Credenciales: `CYPRESS_contrasena` (valor no documentado).

Precondiciones: spec/config rev11 presentes; `baseUrl` y `TEST_API` sslip.io TEST; evidencias en `Resultados/rev11/`; `trashAssetsBeforeRuns: false`; git sin cambios tracked (solo untracked QA).

---

## Resultado Cypress / Mocha

| | |
|---|---|
| Tests | 1 |
| Passing | **1** |
| Failing | 0 |
| Spec | `tc_m09_g94_179_rev11_test.cy.js` |
| `last_step` | `aserciones` |
| `mocha_state` | `passed` |
| Login | `productor@pecuaria.co` (UI HTTP 200) |
| Dashboard | `/dashboard` |
| `html data-theme` | `dark` (temprano y al cierre) |
| `body data-theme` | null |

---

## `--brand-500`

Diagnóstico **antes** de la espera de 20 s ya mostraba `#249453` (la espera no agotó el timeout). No se forzó CSS ni DOM.

| | |
|---|---|
| Computed / inline | `#249453` |
| Esperado CSS | `#249453` |
| `color_ajustado` API oscuro | `#249453` |
| Primario crudo | `#1A6B3C` (no aplicado) |
| `coincide_oscuro` | true |

GET tema navegador: HTTP 200. Refresh: 0 llamadas.

---

## Contraste

Fondo marca: `--surface-card` `#171A15`. Ratio `--brand-500` vs fondo: **4.55:1** (≥ 4.5).

Sidebar (fondo efectivo `.ds-sidebar` `#104325`, texto `#97B68F`; el propio nodo sigue transparente):

| Selector | Texto | Ratio |
|---|---|---|
| `.ds-sidebar__logo-sub` | Finca Acuícola El Remanso | **5.08:1** |
| sección 2 label | Módulos | **5.08:1** |
| sección 4 label | Mi cuenta | **5.08:1** |
| `.ds-sidebar__user-role` | Productor | **5.08:1** |

Rev8/rev10 era `#7D9A75` / `#104325` a 3.64:1. El redespliegue cambió el texto muted a `#97B68F`.

---

## axe

- Ejecutado: sí
- `color-contrast` violations: **0**
- Nodos que pasan: 19
- `violation_nodes`: `[]`

Criterio 0 violaciones **cumplido** en esta corrida de 179.

Nota: `diagnostico.json` guarda `axe_violations: null` porque se escribe **antes** de axe; el resultado válido está en `G94-rev11-179-axe.json` y `ultimo-paso.json` (`violations: 0`).

---

## Tema personal / restore

Snapshot: `theme_mode=2`, `fuente=personal`, `id_tema_visual=2`. **No PATCH** (ya oscuro). Restore **omitido**. Identidad visual no escrita.

---

## Evidencias (exclusivas rev11)

Base: `sgpmp-backend/tests/Test_Testing/Test_Modulo9/RF-27/TC-M09-G94/Resultados/rev11/`

- `TC-M09-G94_179_rev11_test.json` / `.html`
- `G94-rev11-179-ejecucion.txt`
- `G94-rev11-179-snapshot-tema.json`
- `G94-rev11-179-contexto-antes.json`
- `G94-rev11-179-tema-sin-patch.json`
- `G94-rev11-179-diagnostico-temprano.json`
- `G94-rev11-179-diagnostico.json`
- `G94-rev11-179-ubicacion.json`
- `G94-rev11-179-css-despues.json`
- `G94-rev11-179-sidebar-nodos.json`
- `G94-rev11-179-axe.json`
- `G94-rev11-179-refresh.json`
- `G94-rev11-179-ultimo-paso.json`
- `G94-rev11-179-estado-tema-final.json`
- `G94-rev11-179-restore.json`
- `screenshots-179-rev11-test/tc_m09_g94_179_rev11_test.cy.js/G94-rev11-179-dashboard-dark-variante.png`

Rev4–rev10 no se sobrescribieron.

---

## Conclusión

| Criterio | Estado |
|---|---|
| TC-M09-179 rev11 (TEST, post-redespliegue) | **PASÓ** |
| `--brand-500` = `#249453` con `data-theme=dark` | Cumple |
| Ratio marca ≥ 4.5 | Cumple (4.55:1) |
| Sidebar AA 4.5 (cuatro nodos) | Cumple (5.08:1) |
| axe color-contrast = 0 | Cumple |
| TC-M09-178 revalidación este ciclo | **Pendiente** |
| G94 (178 + 179) | **No aprobado** en este informe |

Pendiente: revalidar TC-M09-178 si el proceso de G94 lo exige tras el redespliegue, y decisión formal de G94 fuera de esta corrida única de 179.
