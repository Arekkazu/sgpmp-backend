# 13 — Ejecución Cypress TC-M09-179 rev6 TEST

**G94 permanece RECHAZADO.** Mocha rev6 no aprueba 179. 178 no se reejecutó (sigue rev2, solo dashboard). El grupo no se aprueba con 179 solo.

Comando (cwd `sgpmp-backend`):

```
npx cypress run --config-file tests/Test_Testing/Test_Modulo9/RF-27/TC-M09-G94/cypress.config.179.rev6.cjs
```

`CYPRESS_contrasena` desde `SGPMP_TEST_PASSWORD`/`CONTRASENA`. Spec: `tc_m09_g94_179_rev6_test.cy.js`. Reporter: `TC-M09-G94_179_rev6_test`. Exit **1**.

---

## Mocha y hooks

| | |
|---|---|
| tests / pases / fallos | **1 / 0 / 1** |
| Fail | `it`: `cy.wait('@temaPost')` 20 s — ninguna respuesta GET tema |
| `after` | Corrió; restore **omitido** (no hubo PATCH) |
| isHook | false |

Rev4 y rev5 JSON/HTML **intactos**.

---

## Color, ratio, axe

No hay `G94-rev6-179-css-despues.json` ni `G94-rev6-179-axe.json`.  
`--brand-500`, ratio ≥ 4.5 y axe **no se midieron**. No se declara cumplimiento de variante en UI.

API sí: `color_ajustado` oscuro `#249453`, ratio API 2.69, `cumple_aa=false` (`G94-rev6-179-contexto-antes.json`).

---

## Restauración y snapshot

- Snapshot tema: `theme_mode=2`, `fuente=personal` (`G94-rev6-179-snapshot-tema.json`).
- `G94-rev6-179-tema-sin-patch.json`: ya oscuro, **sin PATCH**.
- Restore omitido; GET posterior a la corrida: `theme_mode=2`, `primary=#1A6B3C`.
- Identidad no mutada. `/tema/global` no llamado.

---

## Hallazgo de sesión (no se afirma TOKEN_REVOCADO del restore)

`refresh_durante_it`: una llamada `POST /sesiones/refresh` **HTTP 401**. Coherente con que el segundo `visit('/dashboard')` no disparara GET tema (sesión UI no recuperada). Body `error_code` **no** persistido. El wait es fallo **real** del runner; la causa del 401 de refresh **no** está cerrada.

---

## Evidencias rev6

- `Resultados/TC-M09-G94_179_rev6_test.json`
- `Resultados/TC-M09-G94_179_rev6_test.html`
- `Resultados/G94-rev6-179-ejecucion.txt`
- `Resultados/G94-rev6-179-restore.json`
- `Resultados/G94-rev6-179-snapshot-tema.json`
- `Resultados/G94-rev6-179-contexto-antes.json`
- `Resultados/G94-rev6-179-tema-sin-patch.json`
- `Resultados/G94-rev6-179-admin-identidad-diseno.json`
- `Resultados/screenshots-179-rev6-test/... (failed).png`

---

## Alcance del grupo

| Subcaso | Estado |
|---|---|
| TC-M09-179 rev6 | Mocha **FAIL** |
| TC-M09-178 | APROBADO **rev2**, muestra dashboard; no cubre todo el tema; no reconfirmado aquí |
| **G94** | **RECHAZADO** |
