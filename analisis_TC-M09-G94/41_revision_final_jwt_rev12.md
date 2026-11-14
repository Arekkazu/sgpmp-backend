# 41 — Revisión final del ciclo JWT (rev12 corregida)

G94 **pendiente**. Cypress **no** se ejecutó. Informes 38–40 y evidencias históricas intactos.

**Veredicto:** `APTA PARA SOLICITAR NUEVA AUTORIZACIÓN`

Hallazgo menor corregido en esta pasada: el JSON del PATCH de estímulo no debe volcar el cuerpo de respuesta.

---

## 1. Secuencia de sesiones verificada

| # | Evento | JWT | `sesionVigente` |
|---|---|---|---|
| 1 | `loginApi(ADMIN)` + `adoptarJwt('admin')` | A1 | admin=A1 |
| 2 | Login UI productor + `adoptarJwt('prod', intercept)` | P1 | prod=P1 |
| 3 | GET snapshot identidad `api(..., 'admin')` / tema `api(..., 'prod')` | A1 / P1 | sin cambio |
| 4 | Paquete de recuperación | — | — |
| 5 | Preflight `loginApi(ADMIN)` + `adoptarJwt('admin')` | A2 (A1 revocado, sesión única) | admin=A2 |
| 6 | Preflight `loginApi(PRODUCTOR)` + `adoptarJwt('prod')` | P2 (P1 revocado) | prod=P2 |
| 7 | `expect(preflightOk)` | si falla, no hay PATCH | — |
| 8 | GET/PATCH tema e identidad vía `api()` | A2 / P2 | — |
| 9 | `after()` restore: `loginApi` + `tok` **local**; no llama `adoptarJwt` | A3 / P3 | no se usa para restore |

`adoptarJwt` exige `who` ∈ `{admin,prod}`, HTTP 200 y `body.token` string no vacío. `api()` lee solo `sesionVigente[who]` dentro de `cy.then`. No quedan `tokenProd`/`tokenAdmin`. Restore no reutiliza `sesionVigente`; su login ocurre en `after`, después de `afterEach`, y no deja un JWT necesario para otra operación del `it`.

**Sesión única vs SPA:** tras el preflight, el SPA puede conservar P1 en memoria (inválido). El access vigente para escrituras es P2. No hay dos sesiones **válidas** del mismo usuario. El cookie `refresh_token` del host API sigue el último `loginApi` (productor al cerrar el preflight). Un refresh del navegador tras `cy.visit /dashboard` podría rotar P2; las escrituras `api()` ya terminaron y el restore autentica de nuevo.

---

## 2. Referencias de código

- `sesionVigente`, `adoptarJwt`, `api`: `tc_m09_g94_179_rev12_test.cy.js` (objeto de sesión y helpers).
- Restore: `restaurarIdentidad` / `restaurarTema` → `loginApi` + `reqConToken(..., tok)`.
- Backend sesión única: `sesion_comun.emitir_sesion` (`invalidar_sesion` si hay sesión activa).
- 401 vs 403: `get_current_user` vs `require_permission`.

---

## 3. Hallazgos y correcciones

**Defecto (esta revisión):** `G94-rev12-179-tema-patch-estimulo.json` escribía `body_redactado: redactBody(pTema.body)`, es decir el objeto de respuesta menos tres claves. Incumple “no volcar el cuerpo completo”.

**Corrección local:** `diagnosticoHttp(res)` persiste solo `http`, `error_code` y `message` recortado a 200 caracteres, **antes** de `expect(status).eq(200)`. No convierte un 401 en éxito. Se eliminó `redactBody`.

No se debilitaron aserciones. Config Cypress sin cambios.

---

## 4. Registro de errores

Tras la corrección: el `error_code` sale de `body.error_code` o `body.code` de la respuesta real. Sin JWT, sin `Authorization`, sin cookies, sin body completo. El `expect` de PATCH 200 permanece.

---

## 5. Protecciones de datos (conservadas)

Snapshot + `snapshot_valido` + paquete **antes** del primer PATCH. Preflight sin PATCH. Restore: GET ternario (ya coincide / estímulo / concurrente). Login fresco. GET final de campos. `RESTORE-PENDIENTE.json` si no verifica. `retries: 0`. Kill de Cypress: no cubierto por hooks (`RECUPERACION_MANUAL.md`).

---

## 6. Validación

`node --check` spec y `cypress.config.179.rev12.cjs`: exit 0. Sin Cypress ni TEST.

---

## 7. Riesgos residuales

- `error_code` de la corrida 38 sigue ausente; la próxima corrida puede confirmar `TOKEN_REVOCADO`.
- Refresh del SPA tras `cy.visit` puede invalidar P2; no afecta restore.
- Cookie API compartida entre `cy.request` y XHR del front (dominio API).
- Oráculo `#757575` no revalidado hasta una corrida autorizada.

---

## 8. Veredicto

`APTA PARA SOLICITAR NUEVA AUTORIZACIÓN`

Comando (no ejecutado):

```
npx cypress run --config-file tests/Test_Testing/Test_Modulo9/RF-27/TC-M09-G94/cypress.config.179.rev12.cjs
```
