# 17 — Revisión estática TC-M09-179 rev8

**G94 permanece RECHAZADO.** Cypress no se ejecutó. Rev4–rev7 no se modificaron.

Archivos: `tc_m09_g94_179_rev8_test.cy.js`, `cypress.config.179.rev8.cjs`, `16_diagnostico_css_api_rev7.md`.

Correcciones **solo en rev8** tras el primer pase (FALLÓ → OK):

- Ratio: se eliminó el fallback a `#171A15` de dominio/API; solo `--surface-card` o `html` background parseable.
- Axe: `ejecutado` true/false en `axe.json` y `ultimo-paso.json`; no se declara 0 violaciones si no corrió.
- `lastStep` ya no se asigna fuera de callbacks de Cypress.
- `data-theme=dark` y hex de marca se asertan **después** de persistir el diagnóstico.

`node --check` de spec y config: OK (tras el arreglo).

---

## Comprobaciones (estado final)

### 1. Captura diagnóstica antes de igualdad, ratio y axe — **OK**

En el `it`, `writeFile` de `G94-rev8-179-diagnostico.json`, `ubicacion.json` y `css-despues.json` se encadena y termina (`lastStep = 'diagnostico_persistido'`) **antes** del `cy.then` de aserciones (igualdad, ratio, axe). Screenshot y axe van después de esa persistencia y **antes** de esos `expect`.

Un `expect` fallido al final no revierte los `writeFile` ya encolados y resueltos. `afterEach` vuelve a persistir `ultimo-paso.json`.

Residual estático: el vaciado real de disco lo confirma solo una corrida Cypress (no hecha). La estructura ya no replica el defecto de rev7 (`expect` síncrono en el mismo `then` que `writeFile`).

### 2. pathname, data-theme, --brand-500, esperado, coincidencia, último paso — **OK**

`medicion` / `diagnostico.json`: `pathname`, `data_theme`, `brand500_inline|computed|normalizado`, `esperado_ajustado_oscuro`, `coincide_oscuro|crudo|claro`.

`afterEach` → `G94-rev8-179-ultimo-paso.json`: `last_step`, Mocha, los mismos campos de color si ya hubo medición.

### 3. Ratio con colores renderizados, no el de la API — **OK** (tras corrección)

`ratioWcagHex(aplicado, fondo.hex)` con `fondoRenderizado()`: `--surface-card` o `backgroundColor` de `html`. Si ninguno es `#RRGGBB`, `ratio_brand_vs_fondo` queda `null` y `fondo_origen = no_renderizado`; el `expect` de origen y de número **falla** (no se usa `oscuro.ratio` 2.69 ni `#171A15` de dominio). Flag `ratio_api_oscuro_no_usado: true` en el diagnóstico.

### 4. axe si se llega; si no, queda registrado — **OK** (tras corrección)

Si el `it` llega al dashboard y persiste CSS, sigue `axe.run` y `G94-rev8-179-axe.json` con `ejecutado: true`. Si no llega, `afterEach` escribe el mismo archivo con `ejecutado: false` y nota de que **no** se declara `color-contrast = 0`. El `expect(axeEjecutado).to.eq(true)` impide un pase silencioso.

### 5. Fallos de medición no se marcan como OK ni se omiten — **OK**

Los `expect` de `data-theme`, hex, origen de fondo, igualdad con `color_ajustado` oscuro, ratio ≥ 4.5 y axe 0 siguen al final. `coincide_*` es diagnóstico, no sustituye aserciones. Restore, si hubo PATCH, exige HTTP 200 y `theme_mode` = snapshot; login de restore fallido deja `patch_tema.http` null y el `expect` del `after` falla.

### 6. Sin PATCH innecesario; rama PATCH con snapshot y restore — **OK** (estático)

Si `theme_mode === 2` → `tema-sin-patch.json`, `patchedTema` sigue false, `restoreTema` omite (`razon: no hubo PATCH`).

Si no es 2: snapshot previo (`snapTema`), PATCH mínimo a 2, GET de comprobación, `patchedTema = true`, recarga, restore con login fresco y GET final = snapshot. No se ejecutó esa rama.

### 7. Sin secretos en disco — **OK**

Intercepts: `{ http, error_code }`. Restore login: `{ http, error_code }` (el token queda en variable local). `redactBody` quita `token` / `refresh_token` / `access_token` de la sonda. Password con `{ log: false }`. No hay `writeFile` de JWT, cookies ni `Authorization`.

### 8. Salida exclusiva rev8 — **OK**

`cypress.config.179.rev8.cjs`: `reportFilename: TC-M09-G94_179_rev8_test`, `screenshots-179-rev8-test`, `trashAssetsBeforeRuns: false`. Prefijo de evidencias `G94-rev8-179-*`. `overwrite: true` solo pisa **rev8** si se reejecuta, no rev4–rev7.

### 9. `node --check` — **OK**

Spec y config, tras las correcciones.

---

## Listo para autorización

Rev8 está **lista para una ejecución controlada posterior** (una corrida, mismos límites de TEST). No se declara 179 ni G94 APROBADO. 178 sigue en rev2.
