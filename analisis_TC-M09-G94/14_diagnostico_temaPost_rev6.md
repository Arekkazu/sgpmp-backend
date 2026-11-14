# 14 — Por qué falló `@temaPost` en rev6

**G94 sigue RECHAZADO.** Mocha rev6 no se altera. No Cypress, no PATCH TEST, no commit.

---

## Qué esperaba el spec (confirmado)

Tras el login el productor **ya está** en `/dashboard`. El spec registra un intercept nuevo:

```js
cy.intercept({ method: 'GET', url: /\/configuracion\/personalizacion\/tema\/?$/ }).as('temaPost');
cy.visit(`${TEST_FRONT}/dashboard`);
cy.url().should('include', '/dashboard');
cy.wait('@temaPost', { timeout: 20000 })
```

Ese `wait` exige un **GET del navegador** (no `cy.request`) cuyo URL case con el regex, **después** de registrar `temaPost`. Lo copió de rev4, donde ese GET **sí** llegó (`G94-rev4-179-tema-browser.json`: HTTP 200, `theme_mode=1`) porque acababan de PATCH tema a claro y recargaban para pintar `data-theme=light`.

En rev6 **no hubo PATCH** (`theme_mode` ya era 2). El segundo `visit` no era necesario para aplicar un cambio de API.

---

## Qué ocurrió (confirmado)

| Hecho | Evidencia |
|---|---|
| Mocha 0/1 | `TC-M09-G94_179_rev6_test.json` |
| Fail | `No response ever occurred` para alias `temaPost` |
| La aserción `url … /dashboard` **pasó** (el wait es el siguiente comando) | orden en el `it` + mensaje de error |
| GET tema **de Cypress `cy.request`** sí 200 | snapshot + `tema-sin-patch.json` |
| Ningún GET tema **de navegador** llegó al alias `temaPost` | texto Cypress |
| Un `POST /sesiones/refresh` HTTP **401** | `G94-rev6-179-restore.json` `refresh_durante_it` |
| Sin `error_code`, sin URL, sin instante respecto al `visit` | el intercept solo guardó `{ http, t }` |
| CSS/axe no corridos | archivos ausentes |
| `after` no falló | restore omitido |

“No response ever occurred” significa: **el intercept no vio esa petición**. No distingue “no se envió”, “URL distinta” y “se envió antes del alias”.

---

## Relación con el refresh 401 (no cerrada)

Tres lecturas **compatibles** con los artefactos; **ninguna está demostrada sola**:

1. **Sincronización Cypress / SPA (probable como defecto del spec).** Ya en dashboard; `cy.visit` a la misma ruta puede no repetir el GET que el spec espera. Rev4 necesitaba remount porque el tema **cambió**; rev6 no. El wait es una dependencia de red **no garantizada**.
2. **Frontend TEST.** Un reload puede pedir refresh **antes** de GET tema. Si el refresh falla, el GET puede no salir. El workspace local (`useTheme` + `localStorage`) **no** llama `/personalizacion/tema`; el TEST de septiembre **sí** lo hacía (rev4). El desplegable actual no está en este repo.
3. **Auth.** Hay un refresh **401** real. **No** hay body. **No** se sabe si fue en el segundo `visit` o antes. No se afirma `TOKEN_REVOCADO`. Rev4: GET tema navegador 200 y 401 **después** en restore con Bearer viejo (refresh entonces habría sido 200). Aquí el 401 es del **refresh**, clase distinta al 401 de PATCH restore.

El 401 **puede** explicar la ausencia de GET; **no está ordenado en el tiempo** con la granularidad de “antes/después del segundo visit”. Sí hay un ancla gruesa: Mocha `start` `2026-10-10T14:53:28.924Z`, `duration` 28261 ms (20 s del wait + ~8 s de setup). El `t` del refresh (`1791644016785`) está ~7.8 s tras el start, **no** al agotar el wait. Encaja con el tramo login/dashboard o el segundo `visit`, no con el timeout. **No** hay `error_code`.

El wait **sí** es un error de arnés: convierte “no vi la petición en el alias `temaPost`” en FAIL sin medir CSS.

Hay un segundo defecto de interceptación **confirmado**: antes del login ya existía `cy.intercept(GET tema).as('getTema')`. El spec **nunca** hace `wait('@getTema')`. El alias `temaPost` se registra **después** de los GET `cy.request` y del primer `/dashboard`. Un GET de navegador en el primer dashboard **no** puede satisfacer `temaPost` aunque hubiera ocurrido. `cy.request` tampoco alimenta intercepts.

---

## Distinción

| Capa | Qué se puede decir |
|---|---|
| Intercept Cypress | Alias `temaPost` registrado tarde; `wait` obligatorio; `cy.request` no alimenta el alias. **Confirmado.** |
| Sincronización | Segundo visit copiado de rev4 sin PATCH. **Confirmado como diseño del spec.** Que el visit no dispare GET: **no verificado** (faltan log de href y de todas las XHR). |
| Frontend | TEST no es el `useTheme` local. Comportamiento de fetch tema: **solo** evidenciado en rev4 (sí) vs rev6 (no visto). |
| Auth | Refresh 401 **confirmado** como status. Causa y nexo causal con el wait: **no verificable** con logs actuales. |

No es un fallo de contraste RF-27: esa parte no se ejecutó.

---

## Corrección: rev7 (no reescribir rev6)

Evidencia Mocha rev6 se conserva. Archivos nuevos:

- `tc_m09_g94_179_rev7_test.cy.js`
- `cypress.config.179.rev7.cjs` (reporter `TC-M09-G94_179_rev7_test`)

Cambios de comportamiento:

1. **No** segundo `cy.visit('/dashboard')` ni `wait('@temaPost')` si ya hay dashboard y no hubo PATCH de tema.
2. Medir `--brand-500`, ratio ≥ 4.5 y axe **en la página ya cargada** (`html[data-theme=dark]`).
3. `theme_mode` de API: el GET `cy.request` del snapshot (ya 200).
4. Intercept GET tema y POST refresh **desde el inicio**, log `{ http, error_code }` **sin** tokens/cookies.
5. Tras login: `writeFile` de `pathname`/`hash` (no query con secretos).
6. Restore y umbral axe **iguales**. Login fresco si hubiera PATCH.

---

## Instrumentación si aún faltara causa del 401

En la próxima corrida (rev7): recuento y `error_code` de cada refresh; si GET tema de navegador existe, su HTTP; `document.location.pathname` al medir CSS. Sigue prohibido volcar JWT o `Set-Cookie`.

---

## Reejecución (pendiente de autorización)

```
npx cypress run --config-file tests/Test_Testing/Test_Modulo9/RF-27/TC-M09-G94/cypress.config.179.rev7.cjs
```

Sin PATCH si `theme_mode=2`. Riesgo: axe/CSS pueden RECHAZAR de verdad. G94 no APROBADO hasta Mocha verde **y** alcance de 178.
