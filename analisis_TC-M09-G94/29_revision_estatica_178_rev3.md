# 29 — Revisión estática TC-M09-178 rev3 (pre-ejecución)

**G94 permanece RECHAZADO.** Cypress **no** se ejecutó. Sin commit/push/deploy.

Comparado con `28_cobertura_y_revalidacion_178.md` y la lista de verificación pedida.

---

## Checklist

| # | Criterio | Resultado |
|---|---|---|
| 1 | Admin + dashboard TEST | **OK.** `admin@pecuaria.co`, `TEST_FRONT` sslip.io TEST, `/login` → URL incluye `/dashboard` y no `/login`. |
| 2 | Tema activo, sin exigir `#249453` | **OK.** Se registra `--brand-500` y `data-theme`. No hay `expect` de `#249453` ni espera de 20 s a ese hex. |
| 3 | Ratios con colores/fondos efectivos | **OK.** `fondoEfectivo` sube padres si el nodo es transparente (sidebar → `.ds-sidebar`). |
| 4 | Axe dashboard; infracciones fallan | **OK.** `axe.run` `color-contrast` sobre `document`; persistencia; `expect(violations).to.eq(0)`. |
| 5 | Sin PATCH / escritura de datos | **OK.** Solo POST login y GET `tema` + `interfaz/contexto`. No hay `/identidad-visual`. |
| 6 | Evidencias solo `Resultados/178-rev3/` | **OK.** `EVIDENCIA`, `reportDir` y `screenshotsFolder` bajo ese directorio. `trashAssetsBeforeRuns: false`. Rev2 intacto. |
| 7 | TEST + secretos | **OK.** `baseUrl` y API TEST. Contraseña `log: false`; GET autenticados `log: false`; token en variable, no `cy.wrap`. El runner de Cypress puede seguir mostrando el POST `/sesiones/` (limitación de la UI). |
| 8 | No depender de GET identidad `null` | **OK.** No se llama RF-26. El contexto se **registra** (objeto o campos nulos) sin asertar `null`. |

---

## Correcciones aplicadas (solo rev3)

Tras la revisión se ajustó `tc_m09_g94_178_rev3_test.cy.js`:

1. `lastStep = 'dashboard'` se asigna **dentro** del `.then()` de `cy.url()`, no en el turno síncrono.
2. Se exige `not.include('/login')`.
3. Se eliminó `cy.wrap(token)` (el alias volcaba el JWT al log de comandos).
4. GET con Bearer usan `log: false`; `cy.wait('@loginAdmin', { log: false })`.
5. `fondoEfectivo` también acepta fondo hex si no viene como `rgb()`.
6. Nota del JSON de contexto: no se exige body nulo.

`cypress.config.178.rev3.cjs` no requirió cambios de entorno ni de rutas.

`node --check` spec y config: **0**.

---

## Alineación con el informe 28

La propuesta de 28 (admin, dashboard, tema activo, axe 0, sidebar AA, sin PATCH, sin espera `#249453`, directorio propio) coincide con el spec. La ampliación de los cuatro nodos del sidebar sigue justificada ahí (RF-27 + hallazgo rev8), no por copiar 179.

---

## ¿Listo para una corrida controlada?

**Sí**, una sola vez, cuando se autorice:

```
npx cypress run --config-file tests/Test_Testing/Test_Modulo9/RF-27/TC-M09-G94/cypress.config.178.rev3.cjs
```

desde `sgpmp-backend`. G94 no se aprueba con esta revisión estática.
