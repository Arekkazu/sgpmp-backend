# 20 — Revisión estática TC-M09-179 rev9

**G94 permanece RECHAZADO.** Cypress **no se ejecutó**. Rev4–rev8 y sus evidencias no se modificaron.

Archivos nuevos:

- `sgpmp-backend/tests/Test_Testing/Test_Modulo9/RF-27/TC-M09-G94/tc_m09_g94_179_rev9_test.cy.js`
- `sgpmp-backend/tests/Test_Testing/Test_Modulo9/RF-27/TC-M09-G94/cypress.config.179.rev9.cjs`

---

## Cambios respecto de rev8

1. Intercepts de contexto, login, refresh y GET tema **al inicio** del `it`.
2. Tras `/dashboard` (y recarga solo si hubo PATCH): `G94-rev9-179-diagnostico-temprano.json` con `href_sin_query`, `pathname`, `html_data_theme` / `body_data_theme`, flags `hasAttribute`, `readyState`. **No** se escribe `data-theme` desde Cypress.
3. Espera `cy.get('html', { timeout: THEME_WAIT_MS })` con `THEME_WAIT_MS = 20000` hasta `data-theme="dark"`. Mensaje de fail cita los JSON temprano y final. Si no aparece, el `should` aborta el `it`; **no** se miden CSS/axe como si el oscuro estuviera confirmado.
4. `afterEach` escribe `G94-rev9-179-estado-tema-final.json` (mismo estado de html/body).
5. Tras confirmar dark: `--brand-500` vs `color_ajustado` oscuro; ratio CSS renderizado (sin copiar el de la API); cuatro nodos de sidebar (texto, fg/bg, ratio, selector) en `sidebar-nodos.json`.
6. axe `color-contrast` persistido **antes** de asertar 0 violaciones. Si no corre, `axe.json` con `ejecutado: false`.
7. Criterios iguales: ratio marca ≥ 4.5; cada nodo sidebar presente con ratio ≥ 4.5; axe 0. Restore/snapshot como rev8 (sin PATCH si `theme_mode=2`).
8. Reporter `TC-M09-G94_179_rev9_test`, screenshots `screenshots-179-rev9-test`, prefijo `G94-rev9-179-*`, `trashAssetsBeforeRuns: false`.

---

## Validaciones estáticas

| Comprobación | Resultado |
|---|---|
| Archivos rev9 independientes; no pisan rev8 | **OK** (`reportFilename`, carpeta screenshots, prefijo JSON) |
| Intercepts al inicio del `it` | **OK** |
| Diagnóstico temprano antes de esperar dark | **OK** (`diagnostico-temprano.json`) |
| Espera `html[data-theme=dark]` 20 s; fail diagnóstico si no | **OK** |
| No se continúa la medición oscura si el wait falla | **OK** (Cypress aborta el resto del `it`) |
| Persistencia CSS/sidebar/axe **antes** de expects de igualdad/ratio/axe/sidebar | **OK** |
| `afterEach` estado final + axe no ejecutado explícito | **OK** |
| Ratio con colores renderizados, no API | **OK** (`fondoRenderizado` + `ratioWcagHex`) |
| Cuatro selectores sidebar registrados | **OK** |
| Criterios 4.5 y axe 0 no rebajados | **OK** |
| Sin PATCH si tema ya es 2; restore con snapshot | **OK** (estático) |
| Sin secretos en `writeFile` | **OK** (href sin query; intercepts solo http/`error_code`) |
| No se fuerza CSS/`data-theme` desde el spec | **OK** |
| `node --check` spec y config | **OK** |
| Cypress ejecutado | **No.** Confirmado: esta fase no lanzó `npx cypress`. |

---

## Persistencia si falla una aserción

- Temprano: `writeFile` de diagnóstico temprano **antes** del `should` de `data-theme`.
- Si el wait de 20 s falla: queda temprano + `ultimo-paso` + `estado-tema-final` + `axe.json` `ejecutado: false`. No hay CSS oscuro fingido.
- Si dark confirma y falla igualdad/ratio/axe/sidebar: `diagnostico.json`, `css-despues.json`, `sidebar-nodos.json` y `axe.json` (si se alcanzó) ya se escribieron en cadena `writeFile.then` **antes** de los `expect`.

---

## Limitaciones pendientes

- 20 s pueden no bastar si TEST nunca pone `data-theme` en `<html>` (rev8 lo midió `null`). Eso sería FAIL de producto/despliegue, no un pase.
- Fondo del sidebar puede ser `transparent` en computed; el ratio del nodo queda `null` y la aserción **falla** (no se declara 4.5).
- El bundle TEST sigue sin estar en este repo.
- 178 no se toca (rev2).
- Rev9 **no autorizada** para Cypress.

Comando futuro (no ejecutado):

```
npx cypress run --config-file tests/Test_Testing/Test_Modulo9/RF-27/TC-M09-G94/cypress.config.179.rev9.cjs
```
