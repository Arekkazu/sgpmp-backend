# 15 — Ejecución Cypress TC-M09-179 rev7 TEST

**G94 permanece RECHAZADO.** Mocha rev7 no aprueba 179. 178 no se reejecutó (sigue rev2, muestra dashboard). El grupo no se aprueba con 179 solo.

Una sola corrida. Exit **1**. HEAD `laura` `ad55f049`. Cypress 14.5.4 / Electron 130.

```
npx cypress run --config-file tests/Test_Testing/Test_Modulo9/RF-27/TC-M09-G94/cypress.config.179.rev7.cjs
```

Credenciales: `CYPRESS_contrasena` ya presente. No se documentan valores.

Rev4/rev5/rev6 JSON, HTML y `G94-rev6-*` **intactos**.

---

## Fase A (estática, antes de Cypress)

Archivos existentes:

- `sgpmp-backend/tests/Test_Testing/Test_Modulo9/RF-27/TC-M09-G94/tc_m09_g94_179_rev7_test.cy.js`
- `sgpmp-backend/tests/Test_Testing/Test_Modulo9/RF-27/TC-M09-G94/cypress.config.179.rev7.cjs`

`node --check` de ambos: OK.

| Condición | Resultado |
|---|---|
| Intercept refresh y GET tema **antes** del login UI | Sí (inicio del `it`) |
| `cy.wait('@temaPost')` | Ausente. Único `wait`: `@loginProd` (POST de login disparado por el submit) |
| UI lista antes de CSS | `url` dashboard + `html[data-theme=dark]` + `--brand-500` no vacío |
| Compara `--brand-500` con `color_ajustado` oscuro; ratio ≥ 4.5; axe 0 | Sí en el spec |
| Refresh: solo `http` y `error_code` | Sí. Sin JWT/cookies en logs |
| Identidad admin | GET control 200 null; no PATCH/POST/DELETE identidad |
| Restore | Si no hay PATCH, `omitido=true`. Si hay PATCH, exige HTTP 200 y `theme_mode` = snapshot; el `after` puede fallar |

Ajuste local **antes** de ejecutar: `pathname` y `--brand-500` se escriben juntos al medir; no se espera GET tema de navegador.

Defecto de persistencia **observado tras la corrida** (no reejecutada): `cy.writeFile` de CSS/ubicación queda en cola y el `expect` síncrono aborta antes de vaciarla. No se cambió el spec después ni se repitió Cypress.

---

## Mocha y hooks (hechos)

| | |
|---|---|
| tests / pases / fallos | **1 / 0 / 1** |
| start / end UTC | `2026-10-10T15:04:25.489Z` – `15:04:33.430Z` |
| duration | 7941 ms |
| Fail | `it`: `--brand-500` `#1A6B3C` ≠ `color_ajustado` `#249453` |
| `isHook` | false |
| `after` | Corrió; restore **omitido** (no hubo PATCH) |

---

## Contraste y axe

**Sí se leyó CSS** (el fail es la comparación de color). `html[data-theme=dark]` había pasado.

| Criterio | Estado |
|---|---|
| `--brand-500` renderizado | **`#1A6B3C`** (Mocha actual) |
| Esperado `color_ajustado` oscuro | **`#249453`** (Mocha + `G94-rev7-179-contexto-antes.json`) |
| Igualdad marca = ajustado | **FAIL** |
| Ratio ≥ 4.5 en el spec | **No asertado** (abortó antes). No hay `css-despues.json` con `ratio_brand_vs_fondo` |
| axe `color-contrast` = 0 | **No ejecutado**. No hay `G94-rev7-179-axe.json` |

API (no es medición CSS): primario `#1A6B3C`, oscuro `cumple_aa=false`, `ratio` API 2.69 vs `#171A15`, `color_ajustado` `#249453`.

**Inferencia (no usada como veredicto de ratio):** el color en UI coincide con el primario crudo, no con la variante. **No** se afirma el ratio WCAG de la página porque el spec no lo asertó ni persistió el fondo usado.

---

## Escrituras y restauración

- Snapshot: `theme_mode=2`, `fuente=personal`, `id_tema_visual=2`.
- **Sin PATCH** de tema (`tema-sin-patch.json`).
- Restore omitido; no hay `verificacion-final.json` (correcto: no se restauró nada).
- Identidad: solo GET admin 200 null. Sin PATCH/POST/DELETE de identidad.
- `/tema/global` no llamado por el spec.

---

## Autenticación / refresh

- Login productor UI: el `it` llegó al dashboard y a CSS; el fail no es 401 de login.
- `refresh_durante_it` en restore: **`[]`**.
- `G94-rev7-179-refresh.json` **no existe** (misma cola abortada).
- Recuento GET tema de navegador: **no persistido**. No se afirma que el SPA lo pidiera o no.

No se atribuye causa al 401 de rev6. En esta corrida **no** hay evidencia de un refresh 401.

---

## Evidencias rev7

- `sgpmp-backend/tests/Test_Testing/Test_Modulo9/RF-27/TC-M09-G94/Resultados/TC-M09-G94_179_rev7_test.json`
- `.../TC-M09-G94_179_rev7_test.html`
- `.../G94-rev7-179-ejecucion.txt`
- `.../G94-rev7-179-restore.json`
- `.../G94-rev7-179-snapshot-tema.json`
- `.../G94-rev7-179-contexto-antes.json`
- `.../G94-rev7-179-tema-sin-patch.json`
- `.../G94-rev7-179-admin-identidad-diseno.json`
- `.../screenshots-179-rev7-test/tc_m09_g94_179_rev7_test.cy.js/TC-M09-179 rev7 TEST -- TC-M09-179 aplica color_ajustado oscuro en --brand-500 con data-theme=dark (failed).png`

No creados: `css-despues.json`, `ubicacion.json`, `refresh.json`, `axe.json`, `tema-tras-patch.json`.

---

## Alcance del grupo

| Subcaso | Estado |
|---|---|
| TC-M09-179 rev7 | Mocha **FAIL** (variante no aplicada en `--brand-500`) |
| TC-M09-178 | APROBADO **rev2**, muestra dashboard; no cubre todo el tema; **no reconfirmado** |
| **G94** | **RECHAZADO** |

Qué falta para cerrar G94:

1. 179: evidencia Mocha de `--brand-500` = `color_ajustado` oscuro, ratio ≥ 4.5 **asertado**, axe 0, y archivos CSS/axe en disco. Eso es criterio de producto (y, en una próxima rev, persistir `writeFile` antes del `expect`).
2. 178: reevaluación del alcance (rev2 limitado al dashboard) con evidencia suficiente.
3. No marcar APROBADO con un solo subcaso.
