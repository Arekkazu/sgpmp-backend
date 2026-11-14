# 43 — Análisis `cy.wait('@temaPost')` y `REFRESH_TOKEN_REQUERIDO` (TC-M09-179 rev12)

**G94:** pendiente. Sin Cypress. Sin escrituras TEST. Sin cambios de frontend/backend. Sin commit.

**Corrida analizada:** la de `42_ejecucion_rev12_corregida.md` (Mocha 2026-10-10T21:24:57Z–21:25:33Z). Las evidencias de esa corrida están en `sgpmp-backend/tests/Test_Testing/Test_Modulo9/RF-27/TC-M09-G94/Resultados/179-rev12/` (raíz). `ejecucion-38/` es la corrida anterior (PATCH tema 401); **no** contiene el 401 de refresh.

---

## 1. Hechos observados

### 1.1 Punto exacto del fallo

- Mocha: 1 test, 0 passing, `CYPRESS_EXIT=1`.
- `last_step`: `contexto_api_despues`.
- Error: `cy.wait()` 20000 ms — no ocurrió la 1.ª petición de la ruta `temaPost`.
- `--brand-500` / `data-theme` / axe: no medidos (`brand500_normalizado: null`, `data_theme: null`, axe no ejecutado).

### 1.2 Estímulo y restauración (corrida 42, raíz `179-rev12/`)

| Paso | Evidencia | Resultado |
|---|---|---|
| Preflight | `G94-rev12-179-preflight-restore.json` | `apto: true`; logins 200; GET identidad/tema 200; `jwt_vigente_actualizado` admin y prod `true` |
| PATCH tema `{theme_mode:1}` | `G94-rev12-179-tema-patch-estimulo.json` | HTTP 200, `error_code: null` |
| GET tema tras PATCH | `G94-rev12-179-tema-tras-patch.json` | `theme_mode=1` |
| PATCH identidad `#FFFFFF` | `G94-rev12-179-identidad-despues.json` | version 6, `primary_color=#FFFFFF`, `color_ajustado=#757575` |
| Contexto API | `G94-rev12-179-contexto-api-despues.json` | primary `#FFFFFF`, ajustado claro `#757575` |
| Refresh (navegador) | `G94-rev12-179-restore.json` → `refresh_durante_it` | **una** llamada: HTTP **401**, `error_code=REFRESH_TOKEN_REQUERIDO` |
| Restore `after()` | mismo JSON + `G94-rev12-179-verificacion-final.json` | identidad `#1A6B3C` v7, logo/org coinciden, `theme_mode=2`, `coincide_snapshot: true` |
| `RESTORE-PENDIENTE.json` | búsqueda en G94 | **no existe** |

No hay `G94-rev12-179-tema-browser.json` ni `diagnostico-temprano.json`: el `it` murió en el `wait`.

### 1.3 Corrida 38 (`ejecucion-38/`)

Fallo distinto: PATCH tema 401 (JWT de UI revocado por `loginApi` de preflight). Identidad no se escribió. Restore omitió PATCH de tema porque GET ya era 2. `refresh_durante_it: []`. No es la corrida de este análisis.

### 1.4 Origen de `REFRESH_TOKEN_REQUERIDO`

**API real, no fixture ni stub del test.**

- El spec intercepta `POST /sesiones/refresh/` con `req.continue` y solo registra `http` + `error_code`. No sustituye cuerpo ni status.
- Backend (`sesiones_routers.refrescar_sesion`): si `Cookie(None)` (cookie `refresh_token` ausente), lanza `AuthenticationError(code="REFRESH_TOKEN_REQUERIDO")`.
- Test de integración `test_refresh_sin_cookie_responde_401`: POST `/sesiones/refresh` sin cookie → 401 + ese código.
- Cypress intercepta XHR/fetch del **navegador**, no `cy.request`. El 401 quedó en `refresh_durante_it` → lo emitió el dashboard (bundle TEST), no `loginApi` ni el restore.

Si la cookie existiera pero el refresh estuviera revocado, el código sería otro (p. ej. token desconocido/revocado), no `REQUERIDO`.

### 1.5 Alias `@temaPost`

Definido como `GET /configuracion/personalizacion/tema/` (mismo recurso que `@getTemaBrowser`). No es un POST a pesar del nombre. El frontend **sí debe** emitir ese GET cuando hay access token (`useTemaSesion`: si `!token` no llama; si hay token, `Promise.all` GET tema + GET contexto).

El `wait` no espera una petición obsoleta: espera la carga de preferencias de tema. En esta corrida esa petición **no salió**.

### 1.6 Frontend local vs bundle TEST

Checkout `SGPMP-FRONT-END-PWA`: `http.ts` no llama a `/sesiones/refresh`; ante 401 (excepto login) limpia token y `location.replace('/login')`. No hay `withCredentials`.

El bundle desplegado en TEST **sí** hizo `POST /sesiones/refresh/` (capturado). Ese bundle no se modificó.

### 1.7 Comparadores que pasaron

| | TC-M09-179 rev11 | TC-M09-178 rev4 |
|---|---|---|
| Login UI | Un productor; sin `loginApi` intermedio | Un admin UI |
| Estímulo API extra | No (tema ya oscuro; `patched_tema: false`) | No (solo lectura CSS) |
| Recarga | `cy.reload()` solo si hubo PATCH; en la corrida **no** hubo | No |
| Refresh log | `[]` | N/A (no se midió igual) |
| GET tema navegador | HTTP 200 (una vez, sesión SPA intacta) | GET implícito tras login |
| Oráculo | `--brand-500=#249453`, `data-theme=dark` | PASS |

La diferencia relevante: rev12 hace **preflight `loginApi(ADMIN)` + `loginApi(PRODUCTOR)`** (sesión única) **después** del login UI y **antes** de `cy.visit('/dashboard')`.

---

## 2. Hipótesis

**H1 (adoptada, defecto de arnés).** Tras el preflight, el access token del SPA ya no es la sesión vigente. `cy.visit('/dashboard')` recarga sin token en memoria; el bundle TEST pide refresh **sin cookie** → 401 `REFRESH_TOKEN_REQUERIDO`; `useTemaSesion` no ve token → no hay GET tema → timeout `@temaPost`.

**H2.** Race de intercepts (`@getTemaBrowser` vs `@temaPost`): el GET existió pero el alias nuevo no lo vio. **Rechazada:** Mocha dice “No request ever occurred”; un GET posterior al segundo intercept habría cumplido `wait`. El refresh 401 explica la ausencia del GET.

**H3.** El oráculo CSS o el backend de tema/identidad fallaron. **Rechazada:** PATCH/GET API 200; el CSS no se midió porque el `it` paró antes.

**H4.** Restore `after()` invalidó la sesión del `it`. **Rechazada para el timeout:** el `wait` falla dentro del `it`; `loginApi` de restore es `cy.request` (no entra al intercept del navegador). El restore usó logins frescos y verificó GET.

**H5 (mecanismo de cookie, no demostrada al detalle).** Por qué el POST refresh llegó **sin** cookie: (a) axios TEST sin `withCredentials`; (b) `cy.request` deja la cookie en el jar de Node y el documento no la reenvía; (c) SameSite cross-site (front sslip.io ≠ API sslip.io). Cualquiera basta para `Cookie: None`. No se inspeccionó el header en red (restricción: sin Cypress ni llamadas TEST).

---

## 3. Causa demostrada

Cadena con evidencia:

1. Login UI del productor deja un JWT en el SPA y dispara GET contexto/tema (antes del estímulo).
2. Preflight hace `POST /sesiones/` por `cy.request` (admin y productor). `emitir_sesion` **invalida** la sesión activa previa (`sesion_comun.py`). `adoptarJwt` actualiza `sesionVigente` → los PATCH del estímulo usan el JWT **nuevo** y responden 200.
3. El SPA sigue con el JWT **viejo** (o vacío tras recarga). El spec hacía `cy.visit('/dashboard')` sin volver a autenticar en el navegador.
4. Recarga: el bundle TEST POST `/sesiones/refresh/` → API 401 `REFRESH_TOKEN_REQUERIDO` (cookie ausente). Registrado en `refresh_durante_it`.
5. Sin access token, `useTemaSesion` no emite GET tema. `@temaPost` nunca dispara. El oráculo CSS no corre.
6. `after()` no depende del SPA: `loginApi` + GET/PATCH + GET final. Restauración verificada.

**Causa:** el arnés rompe la sesión del navegador (sesión única + recarga sin login UI) y espera un GET que el dashboard solo hace con token.

**No es:** RBAC/RLS, fallo del PATCH, alias apuntando a un verbo/recurso incorrecto, fixture de 401, ni un defecto que exija cambiar aserciones CSS.

**Certeza:** **alta** para la cadena timeout ↔ ausencia de GET ↔ refresh 401 ↔ recarga sin sesión SPA tras `loginApi`. **Media** para el detalle de por qué la cookie no viajó (H5).

---

## 4. Cambios locales (solo rev12)

Archivo: `sgpmp-backend/tests/Test_Testing/Test_Modulo9/RF-27/TC-M09-G94/tc_m09_g94_179_rev12_test.cy.js`.

- Helper `loginProductorUi()` (visit login, submit, `wait @loginProd` 200, `adoptarJwt('prod')`, URL `/dashboard`).
- Tras `contexto_api_despues`, en lugar de `cy.visit('/dashboard')`: registrar `@temaPost` y **volver a autenticar al productor en el navegador** para que el SPA tenga access token (y cookie de refresh emitida por el login UI) **después** del preflight/`loginApi`.
- `node --check` sobre ese spec: **OK** (exit 0).

No se debilitaron aserciones (`--brand-500=#757575`, `data-theme=light`, GET tema `theme_mode=1`). No se tocó frontend, backend, RLS ni evidencias 38/42.

---

## 5. Siguiente paso recomendado

Autorizar **una** corrida Cypress de 179 rev12 (mismo `cypress.config.179.rev12.cjs`) cuando se pida. Esperado si el arnés es la causa: `wait @temaPost` recibe GET 200 con `theme_mode=1` y el oráculo CSS puede medirse. G94 sigue **pendiente** hasta esa corrida y el veredicto formal.

Si tras el re-login UI el GET tema 200 y el CSS no es `#757575`, eso ya sería producto (marca/tema), no sesión. Si el refresh 401 reaparece **durante** el segundo login UI, entonces sí habría que mirar cookie/`withCredentials` del bundle TEST (fuera de este arnés).

---

## 6. Estado

| Ítem | Estado |
|---|---|
| Diagnóstico | Documentado |
| Arnés rev12 | Corregido en local; no ejecutado |
| Frontend / backend | Sin cambios |
| Finca 1 (corrida 42) | Restaurada y verificada |
| G94 | **Pendiente** |
