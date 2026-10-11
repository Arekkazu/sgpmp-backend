# 39 — Análisis del HTTP 401 en PATCH tema (TC-M09-179 rev12)

Sin Cypress, sin peticiones a TEST, sin reescritura de 38 ni de evidencias. G94 no se aprueba.

**Causa probable (alta certeza):** el preflight hace un segundo `POST /sesiones/` del productor. La política de **sesión única** invalida el JWT capturado en el login UI. El PATCH posterior reutiliza ese JWT ya revocado → `401` en `get_current_user`, no un fallo de RBAC ni de RLS.

El cuerpo `error_code` del 401 **no se persistió**; por eso no es certeza absoluta de `TOKEN_REVOCADO` frente a otros 401.

---

## 1. Hechos observados (corrida 38)

Orden real en el spec y en los JSON:

| Paso | Actor | Cómo se autentica | Resultado |
|---|---|---|---|
| Login API admin | `admin@pecuaria.co` | `loginApi` → `tokenAdmin` | 200 |
| Login UI productor | `productor@pecuaria.co` | intercept POST `/sesiones/` → `tokenProd = body.token` | 200; contexto `id_usuario=2`, finca 1 |
| GET identidad snapshot | admin | `api(..., 'admin')` = Bearer `tokenAdmin` | 200, primary `#1A6B3C` |
| GET tema snapshot | productor | Bearer **`tokenProd` (UI)** | **200**, `theme_mode=2` |
| Preflight | admin + productor | **nuevos** `loginApi`; GET con esos JWT frescos | `apto: true`; GET tema 200 |
| GET tema (antes del PATCH) | productor | otra vez Bearer **`tokenProd` (UI)** | **no se escribió el HTTP** |
| PATCH `{ theme_mode: 1 }` | productor | mismo `tokenProd` UI | **401** (Mocha) |
| Restore | productor | `loginApi` fresco; GET tema | 200, `theme_mode=2` = snapshot; sin PATCH |

Duración ~15 s: descarta inactividad de 30 min (`INACTIVIDAD_MINUTOS` en `dependencies.py`). `refresh_durante_it: []`: el intercept de `POST /sesiones/refresh` no vio llamadas.

No hay `RESTORE-PENDIENTE.json`. Identidad no se PATCHeó.

---

## 2. Identidad, rol, token, headers

- Productor UI: rol Productor, usuario 2, finca 1 (contexto).
- Admin API: recurso 23 para identidad; no interviene en el PATCH de tema.
- Helper `reqConToken`: `Authorization: Bearer ${token}`, `Accept: application/json`. PATCH tema **no** usa `form` (solo identidad). Body JSON `{ theme_mode: 1 }` — válido en `GuardarTemaDTO` (1, 2 o 3).
- El spec hace `expect(token).to.be.a('string').and.not.empty` **antes** de enviar: el 401 no es token ausente en el cliente.
- El PATCH usa **el mismo esquema** que el GET snapshot que fue 200 (mismo `api(..., 'prod')`). Cambia **cuál** JWT sigue vivo, no el formato de header.

Contrato PATCH (`tema_visual_router.py`): `get_current_user` + `require_permission(24, 3)` (Actualizar). GET: mismo usuario + permiso **2** (Leer). Falta de permiso → `AuthorizationError` **403** (`ACCESO_DENEGADO`), no 401. Un 401 sale de `get_current_user` (`TOKEN_REQUERIDO` / `TOKEN_REVOCADO` / inactividad).

El productor **puede** PATCH tema cuando el token es válido: rev4 lo hizo (HTTP 200 en el `it`); el 401 de rev4 fue el restore **después**, con el mismo JWT de SPA.

---

## 3. Diferencias vs 178-rev4 y 179-rev11

| | 178-rev4 | 179-rev11 | 179-rev12 |
|---|---|---|---|
| Actor PATCH tema | no hay PATCH | PATCH solo si no está en oscuro; **en TEST se omitió** (`tema-sin-patch`) | PATCH a claro |
| Segundo login del mismo usuario antes de escribir | no | no | **sí**: preflight `loginApi(PRODUCTOR)` y `loginApi(ADMIN)` |
| Token de escritura | — | `tokenProd` UI, si hubiera PATCH | `tokenProd` UI **tras** el segundo login |
| Restore | n/a | login fresco si hubo PATCH | login fresco; GET 200 |

178-rev4 solo GET admin con el JWT del login UI, sin segundo `POST /sesiones/`. 179-rev11 no introduce un login API extra del productor entre el GET y un PATCH.

---

## 4. Sesión de navegador vs `cy.request`

- Login UI: el SPA guarda el access en memoria y la cookie HttpOnly de refresh. `tokenProd` es una copia de ese access.
- `cy.request` (snapshot, PATCH, preflight, restore) **no** usa la cookie del navegador; solo el Bearer que el spec elige.
- Cypress `intercept` de GET tema aplica al navegador, no a `cy.request`.
- `loginApi` (Node/`cy.request`) **sí** ejecuta `POST /sesiones/` en el backend y dispara sesión única.

Código de producto (`sesion_comun.emitir_sesion`): si hay sesión activa de esa cuenta, `invalidar_sesion` (marca `tokens.fecha_uso`). Router: «si había otra sesión activa se cierra». `get_current_user`: token con `fecha_uso` → 401 `TOKEN_REVOCADO`.

El preflight del productor es exactamente un segundo login de la **misma** cuenta que el UI. Eso cierra la sesión cuyo JWT está en `tokenProd`.

El `loginApi(ADMIN)` del preflight también revocaría el primer `tokenAdmin`. El PATCH de identidad no se alcanzó; de haberse alcanzado con `tokenAdmin` viejo, el mismo 401 era previsible.

---

## 5. Qué no explica el 401

- RLS / cambio de permisos: no hay evidencia; un denegado RBAC sería **403**.
- Body inválido: 400, no 401.
- Token mal extraído en el login UI: el GET snapshot con ese mismo valor fue **200**.
- Expiración 8 h o timeout 30 min: la corrida duró segundos.
- Refresh del SPA: log de refresh vacío.

---

## 6. Causa probable y certeza

**Hipótesis principal (certeza alta, código + secuencia de evidencias):** `TOKEN_REVOCADO` porque `loginApi(PRODUCTOR)` en el preflight invalidó `tokenProd`. El GET de preflight usó otro JWT (`tokP`) y por eso fue 200. El PATCH usó el JWT UI muerto.

**No demostrado al 100 %:** el JSON de Mocha solo tiene el status 401, no `error_code`.

**Hipótesis débil:** GET post-preflight con `tokenProd` también 401 (no se persistió). Encaja con la misma causa.

---

## 7. Comprobación de solo lectura (si se autoriza más adelante)

Sin PATCH: persistir `status` y `error_code` de (a) GET tema con `tokenProd` **inmediatamente después** del preflight y (b) el PATCH 401. Esperado: ambos 401 y `TOKEN_REVOCADO`. Alternativa: GET con el `tokP` del preflight → 200, contrastando el JWT vivo vs el revocado.

No se ejecutó esa comprobación aquí.

---

## 8. Implicación para una rev futura (no ejecutada)

El PATCH de estímulo y el GET que lo precede deben usar un JWT **no revocado**: el del preflight (`tokP`) o un `loginApi` fresco **después** del preflight, no el `tokenProd` del UI una vez que ya hubo otro login. El restore de rev12 ya hace login fresco; el `it` no.
