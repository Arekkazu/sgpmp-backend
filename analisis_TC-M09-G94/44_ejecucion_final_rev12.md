# 44 — Ejecución final TC-M09-179 rev12 (TEST)

**G94 oficial:** no se cambia en este informe (sigue el proceso de cierre; no se declara APROBADO aquí). Una sola corrida. Sin commit. Sin reintento.

**Veredicto de esta corrida:** Cypress **PASÓ** (1/1). Oráculo CSS medido. Restauración **verificada**. No existe `RESTORE-PENDIENTE.json`.

---

## 1. Preflight (antes de ejecutar)

| Condición | Resultado |
|---|---|
| Relogin UI productor **después** del estímulo | `loginProductorUi()` tras PATCH tema/identidad y `contexto_api_despues`; intercept `@temaPost` previo |
| Config / spec apuntan a TEST sslip.io | `cypress.config.179.rev12.cjs` `baseUrl` frontend TEST; spec `TEST_FRONT` / `TEST_API` TEST |
| Snapshot y paquete **antes** de PATCH | `G94-rev12-179-paquete-recuperacion.json` se escribe en `snapshot_tema`, antes de `api('PATCH'…)` |
| `CYPRESS_contrasena` | Presente (valor no documentado) |

Ninguna precondición falló. Se ejecutó **una** vez.

---

## 2. Comando, fecha y código de salida

Desde `sgpmp-backend`:

```
npx cypress run --config-file tests/Test_Testing/Test_Modulo9/RF-27/TC-M09-G94/cypress.config.179.rev12.cjs
```

| | |
|---|---|
| Mocha start | **2026-10-10T21:39:10.699Z** |
| Mocha end | **2026-10-10T21:39:30.766Z** |
| Duración Mocha | **20067 ms** (spec ~18320 ms) |
| Cypress | 14.5.4 / Electron 130 |
| `CYPRESS_EXIT` | **0** |
| Tests | 1 passing, 0 failing |

---

## 3. Resultado funcional

### Login UI y GET tema (navegador)

Tras el estímulo, el segundo `loginProductorUi()` aterrizó en `/dashboard`. `G94-rev12-179-tema-browser.json`: GET tema HTTP **200**, `theme_mode=1`.

`G94-rev12-179-refresh.json`: `llamadas` de refresh **[]**. `tema_browser`: GET 200 `theme_mode=2` (login inicial) y GET 200 `theme_mode=1` (relogin post-estímulo). No se repitió `REFRESH_TOKEN_REQUERIDO`.

### Estímulo API

- Preflight `apto: true`; JWT vigente admin/prod actualizado.
- PATCH tema HTTP **200**; GET `theme_mode=1`.
- Identidad: `primary=#FFFFFF`, version **8**, `color_ajustado=#757575`, `ratio=1`, `cumple_aa=false`.
- Paquete: `generado: antes de cualquier PATCH`, `snapshot_valido: true`. Snapshot identidad version **7**, primary `#1A6B3C`. Snapshot tema **2**.

### Oráculo CSS (aserciones)

| Medida | Valor | Aserción |
|---|---|---|
| `data-theme` | `light` | cumple |
| `--brand-500` (inline y computed) | `#757575` | cumple |
| `brand500_normalizado` | `#757575` | cumple |
| `coincide_ajustado` | `true` | — |
| Ratio marca vs fondo | 4.6075 (≥ 4.5) | diagnóstico |
| Pathname | `/dashboard` | — |
| axe color-contrast | ejecutado, **0** violations (19 nodos pass); **no** es criterio de aceptación | — |

`last_step`: `aserciones`. `mocha_state`: `passed`. Captura: `screenshots-179-rev12-test/.../G94-rev12-179-dashboard-light-variante.png`.

---

## 4. Restauración (GET posterior)

`after()` corrió. **No** hay `RESTORE-PENDIENTE.json`.

**Identidad:** GET previo al restore: `#FFFFFF`, version 8 (estímulo). PATCH restore **200**. GET final: primary `#1A6B3C`, secondary `#A8D5B5`, org `Acuícola El Remanso`, logo `/assets/logos/remanso.png`, version **9**, `id_finca=1`. `coincide_snapshot: true`. `pendiente: false`.

**Tema productor:** GET previo: `theme_mode=1`. PATCH restore **200**. GET final: `theme_mode=2`, `fuente=personal`. `coincide_snapshot: true`.

No se hicieron escrituras adicionales ni recuperación manual.

---

## 5. Evidencias

- Esta corrida: `sgpmp-backend/tests/Test_Testing/Test_Modulo9/RF-27/TC-M09-G94/Resultados/179-rev12/` (JSON `G94-rev12-179-*`, Mocha HTML/JSON, captura).
- Histórico corrida 38: `.../179-rev12/ejecucion-38/` (conservado; `trashAssetsBeforeRuns: false`).
- Informes `analisis_TC-M09-G94/38`–`43`: no se sobrescribieron.
- Mochawesome de esta corrida **sí** sobrescribe el HTML/JSON de la raíz `179-rev12/` (opción `overwrite: true` de la config). Las copias de `ejecucion-38/` no se tocaron.

---

## 6. Limitaciones

- Una sola corrida autorizada; no hay repetición ni rev13.
- El estado **oficial** de G94 no se actualiza en este archivo.
- axe es diagnóstico; el criterio de 179 rev12 es `--brand-500=#757575` con `data-theme=light`.
- TC-M09-178 rev4 no se reejecutó en esta autorización.

---

## Veredicto de la corrida

| Capa | Resultado |
|---|---|
| Cypress / oráculo CSS | **PASÓ** (`#757575`, `light`) |
| Relogin UI post-estímulo | GET tema navegador 200, `theme_mode=1`; refresh 401 no reapareció |
| Restauración | **Verificada** (GET identidad y tema = snapshot) |
| G94 oficial | **Sin cambio automático** |
