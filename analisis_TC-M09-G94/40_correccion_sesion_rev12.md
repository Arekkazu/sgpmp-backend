# 40 — Corrección del ciclo de sesión TC-M09-179 rev12 (sin ejecución)

G94 sigue **pendiente**. Cypress **no** se ejecutó. Informes 37–39 y evidencias de `179-rev12/` intactos.

**Veredicto:** `CORRECCIÓN ESTÁTICA VALIDADA`

---

## 1. Causa y certeza

Causa (informe 39, certeza **alta**): sesión única. El preflight hace `POST /sesiones/` de productor (y admin), `emitir_sesion` invalida el JWT del login UI, y el PATCH de tema reutilizaba `tokenProd` revocado → HTTP 401. El `error_code` no se persistió en la corrida 38.

No es un problema de permisos ni de RLS. No se tocó el backend.

---

## 2. Secuencia de sesiones

**Antes (corrida 38)**

1. `loginApi(ADMIN)` → `tokenAdmin` (A1)
2. Login UI productor → `tokenProd` (P1)
3. GET snapshot identidad A1, GET tema P1 → 200
4. Paquete de recuperación
5. Preflight `loginApi(ADMIN)` → A2 (A1 revocado); `loginApi(PRODUCTOR)` → P2 (P1 revocado); GET con A2/P2 → 200
6. GET/PATCH tema con **P1** → 401
7. Restore: login fresco (P3), GET coincide snapshot

**Después (spec local, no corrido)**

1. Login admin API → `sesionVigente.admin` = A1 (`adoptarJwt`)
2. Login UI productor → `sesionVigente.prod` = P1
3. Snapshots y paquete **antes** de PATCH (igual)
4. Preflight logins → `adoptarJwt('admin'| 'prod')` **sustituye** A1/P1 por A2/P2
5. `api()` lee solo `sesionVigente`: GET/PATCH tema e identidad usan A2/P2
6. Restore: `loginApi` + `tok` local; **no** escribe `sesionVigente`; guarda de concurrencia y GET final sin cambio

Si el preflight no es apto, el `expect` impide escrituras (los JWT vigentes ya son A2/P2, pero no hay PATCH).

---

## 3. Archivos locales modificados

- `sgpmp-backend/tests/Test_Testing/Test_Modulo9/RF-27/TC-M09-G94/tc_m09_g94_179_rev12_test.cy.js`
- `cypress.config.179.rev12.cjs`: sin cambios
- `RECUPERACION_MANUAL.md`: sigue válida (login fresco, GET ternario, sin bucle)

---

## 4. Cómo se evita la revocación en uso

`sesionVigente = { admin, prod }` es la única fuente de `api()`. Cada login 200 del `it` llama `adoptarJwt`, de modo que no queda ninguna variable con un JWT que la sesión única acaba de matar. Restore sigue autenticando aparte. No hay reintentos de PATCH. 401/403/412 siguen siendo fallo. Se persistirá `G94-rev12-179-tema-patch-estimulo.json` (`http`, `error_code`, body redactado) **antes** del `expect` de PATCH, sin relajar la aserción 200.

---

## 5. Validaciones

- `node --check` spec y config: exit 0
- Grep: no quedan `tokenProd` / `tokenAdmin`
- Restore: `reqConToken` con `tok` del login del hook, no `sesionVigente`
- No Cypress, no TEST

---

## 6. Riesgos abiertos

- Un `POST /sesiones/refresh` del SPA puede seguir rotando el access del **navegador**; las escrituras van por `cy.request` + `sesionVigente`, no por ese access.
- Kill de Cypress: paquete + recuperación manual.
- Certeza 401=`TOKEN_REVOCADO` se podrá confirmar en la próxima corrida con `tema-patch-estimulo.json`.
- El oráculo `#757575` sigue sin revalidar en TEST.

---

## 7. Comando futuro (no ejecutado)

Desde `sgpmp-backend`:

```
npx cypress run --config-file tests/Test_Testing/Test_Modulo9/RF-27/TC-M09-G94/cypress.config.179.rev12.cjs
```

Requiere nueva autorización explícita.

---

## 8. Veredicto

`CORRECCIÓN ESTÁTICA VALIDADA`. Lista para solicitar una corrida controlada; no corrida en esta tarea. G94 no se aprueba.
