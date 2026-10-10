# 18 — Ejecución Cypress TC-M09-179 rev8 TEST

**G94 permanece RECHAZADO.** Una sola corrida. Exit **1**. HEAD `laura` `ad55f049`. Cypress 14.5.4 / Electron 130.

Precondiciones: spec/config rev8, reporter `TC-M09-G94_179_rev8_test`, screenshots `screenshots-179-rev8-test`, `trashAssetsBeforeRuns: false`. JSON rev6/rev7 siguen en disco. `CYPRESS_contrasena` presente (valor no documentado). Restore omite si no hay PATCH.

```
npx cypress run --config-file tests/Test_Testing/Test_Modulo9/RF-27/TC-M09-G94/cypress.config.179.rev8.cjs
```

Mocha: 1 test, 0 pases, 1 fallo, 10227 ms, `2026-10-10T15:17:21.309Z`–`15:17:31.536Z`. `isHook: false`.

La captura diagnóstica **sí** quedó en disco (`diagnostico.json`, `css-despues.json`, `ubicacion.json`, `axe.json`).

---

## Hechos (informe pedido)

### 1. pathname y data-theme

- `pathname`: `/dashboard`
- `data-theme`: **`null`** (`getAttribute` en `<html>` al medir)

### 2. `--brand-500` y esperado

- Renderizado: inline y computed **`#1A6B3C`**
- `color_ajustado` oscuro API: **`#249453`**
- Primario / `claro.color_ajustado`: `#1A6B3C`

### 3. Comparación de colores

- `coincide_oscuro`: **false**
- `coincide_crudo`: true
- `coincide_claro`: true  
El `expect` de igualdad **no se ejecutó**: el `it` falló antes en `data-theme=dark`.

### 4. Ratio CSS (renderizado)

- Primer plano: `#1A6B3C` (`--brand-500`)
- Fondo: `#FFFFFF` (`--surface-card` computed; `fondo_origen=surface-card`)
- `html` background: `rgba(0, 0, 0, 0)` (no usado)
- `ratio_brand_vs_fondo`: **6.537…** (cálculo local; no es el 2.69 de la API)
- Aserción ≥ 4.5: **no ejecutada** (fail previo en `data-theme`)

### 5. axe

**Sí se ejecutó.** `color-contrast`: **1 violación**, 4 nodos (sidebar: `.ds-sidebar__logo-sub`, labels «Módulos»/«Mi cuenta», `.ds-sidebar__user-role`). fg `#7d9a75` / bg `#104325`, ratio axe **3.64** (umbral 4.5). 15 nodos en `passes`. Aserción `violations === 0`: **no ejecutada**.

### 6. Último paso y causa observada

- `last_step`: **`aserciones`**
- Mocha: `data-theme=dark: expected null to equal 'dark'`

Hecho: al asertar, el atributo seguía `null`. No se afirma por qué el SPA no lo puso (el GET tema de navegador fue 200).

### 7. Tema personal y restore

- Inicial: `theme_mode=2`, `fuente=personal`, `id_tema_visual=2`
- Sin PATCH (`tema-sin-patch.json`)
- Restore **omitido** (`no hubo PATCH`)
- Identidad: GET admin 200 null; sin PATCH/POST/DELETE
- `/tema/global` no usado

### 8. Auth / refresh

- Login UI llegó a `/dashboard` (pathname medido)
- `refresh_log`: **[]**
- GET `/personalizacion/tema` navegador: **1 × HTTP 200**, `error_code` null

### 9. Rutas y exit

Exit Cypress: **1**

- `sgpmp-backend/tests/Test_Testing/Test_Modulo9/RF-27/TC-M09-G94/Resultados/TC-M09-G94_179_rev8_test.json`
- `.../TC-M09-G94_179_rev8_test.html`
- `.../G94-rev8-179-ejecucion.txt`
- `.../G94-rev8-179-diagnostico.json`
- `.../G94-rev8-179-css-despues.json`
- `.../G94-rev8-179-ubicacion.json`
- `.../G94-rev8-179-ultimo-paso.json`
- `.../G94-rev8-179-axe.json`
- `.../G94-rev8-179-refresh.json`
- `.../G94-rev8-179-restore.json`
- `.../G94-rev8-179-snapshot-tema.json`
- `.../G94-rev8-179-tema-sin-patch.json`
- `.../G94-rev8-179-contexto-antes.json`
- `.../G94-rev8-179-admin-identidad-diseno.json`
- `.../screenshots-179-rev8-test/.../G94-rev8-179-dashboard-dark-variante.png`
- `.../screenshots-179-rev8-test/... (failed).png`

---

## Inferencias (no veredicto)

La superficie `#FFFFFF` y `data-theme=null` son **compatibles** con tokens de tema claro, a pesar de API `theme_mode=2`. No se demuestra que el GET tema 200 no se aplicara; solo que el atributo no estaba en `dark` al medir. Rev7 sí asertó `data-theme=dark` **antes** de leer CSS; esta corrida midió sin esa espera. No se reejecuta.

---

## Decisión de cobertura

| Subcaso | Evidencia |
|---|---|
| TC-M09-179 rev8 | Mocha **FAIL**. No hay evidencia **suficiente y satisfactoria** de contraste oscuro + axe 0. Sí hay diagnóstico: marca `#1A6B3C` ≠ `#249453`; axe 1 violación en el DOM medido. |
| TC-M09-178 | Sigue rev2 (dashboard); no reconfirmado |
| **G94** | **RECHAZADO** |

No se vuelve a correr Cypress. No se cambia el producto.
