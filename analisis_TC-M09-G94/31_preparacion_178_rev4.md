# 31 — Preparación TC-M09-178 rev4 (orden Cypress del GET autenticado)

**G94 permanece RECHAZADO.** TC-M09-178 **no** se declara aprobado. Cypress TEST **no** se ejecutó. Sin commit/push/deploy. Rev3 y sus evidencias **intactas**.

---

## 1. Causa raíz (rev3)

En `tc_m09_g94_178_rev3_test.cy.js`, `apiGetLectura` hacía esto **al ser llamada**:

```javascript
function apiGetLectura(path) {
  expect(tokenAdmin, `token GET ${path}`).to.be.a('string').and.not.empty; // síncrono
  return cy.request({ ... Bearer tokenAdmin ... });
}
```

El `it` invocaba `apiGetLectura('/configuracion/personalizacion/tema')` **en el mismo turno** en que se encolaban `cy.visit` y `cy.wait('@loginAdmin')`. Cypress aún no había corrido el login; `tokenAdmin` era `null`. Mocha falló en **371 ms** (`last_step: inicio`), sin dashboard, sin axe. Informe: `30_ejecucion_178_rev3.md`.

No fue un fallo de contraste ni de TEST.

---

## 2. Cambios (solo archivos nuevos)

| Archivo | Rol |
|---|---|
| `tests/.../TC-M09-G94/tc_m09_g94_178_rev4_test.cy.js` | spec |
| `tests/.../TC-M09-G94/cypress.config.178.rev4.cjs` | config TEST, evidencias `Resultados/178-rev4/` |
| `tests/.../TC-M09-G94/Resultados/178-rev4/NO_EJECUTADO.md` | marcador |
| este informe | preparación |

**No tocados:** spec/config/JSON de 178-rev3, rev2, 179 rev11.

### Orden de comandos

1. `cy.visit` login → type admin → submit.
2. `cy.wait('@loginAdmin')` → persiste `G94-178-rev4-login.json` (HTTP + `token_presente`, sin token) → `expect` HTTP 200 y token string → **entonces** `tokenAdmin = tok`.
3. `cy.url()` incluye `/dashboard` y no `/login`.
4. `cy.then()`: si no hay token, **falla** con `last_step` y tipo observado; **no** sigue a GET.
5. `apiGetLectura` ahora es solo `return cy.then(() => { expect(token); return cy.request GET log:false })`. Llamarla desde el `it` **encola**; no ejecuta `expect` al evaluar el cuerpo del `it`.
6. GET tema y GET contexto (lectura). Sin PATCH, sin `/identidad-visual`, sin exigir `#249453` ni body null.
7. Diagnóstico CSS + sidebar con fondo efectivo → screenshot → axe → `violations === 0`.

Criterios de rev3 conservados: `admin@pecuaria.co`, dashboard TEST, tema activo, ratios efectivos, axe 0, umbral 4.5.

---

## 3. Validaciones estáticas

```
node --check tests/Test_Testing/Test_Modulo9/RF-27/TC-M09-G94/tc_m09_g94_178_rev4_test.cy.js
node --check tests/Test_Testing/Test_Modulo9/RF-27/TC-M09-G94/cypress.config.178.rev4.cjs
```

Ambos **exit 0**. `178-rev3/TC-M09-G94_178_rev3_test.json` sigue en disco.

Revisión del flujo: no hay `expect(tokenAdmin)` fuera de `cy.then` / `cy.wait().then`. `pass()` solo lee `Cypress.env` (no API).

---

## 4. Comando para la corrida (cuando se autorice)

Desde `sgpmp-backend`, **una** vez:

```
npx cypress run --config-file tests/Test_Testing/Test_Modulo9/RF-27/TC-M09-G94/cypress.config.178.rev4.cjs
```

179 rev11 sigue PASS de este ciclo. G94 sigue RECHAZADO hasta revisar 178-rev4 y la cobertura global.
