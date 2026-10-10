# 04 — HTTP 401 en el hook de restauración (rev4)

Prioridad del análisis. **No se reprodujo el PATCH contra TEST.**

---

## Ubicación del hook

**Archivo:** `sgpmp-backend/tests/Test_Testing/Test_Modulo9/RF-27/TC-M09-G94/tc_m09_g94_179_rev4_test.cy.js`

Función `restoreTodo()` invocada desde `after(() => { restoreTodo(); })`.

El stack del JSON Mocha apunta a la aserción de status del PATCH de **tema** (en el spec fuente, bloque `if (patchedTema)`):

```text
AssertionError: restore theme_mode HTTP: expected 401 to equal 200
Because this error occurred during a `after all` hook we are skipping the remaining tests...
at ... tc_m09_g94_179_rev4_test.cy.js:105:57
```

**Confirmado.** Cypress trata el fallo de `after all` como fallo de la suite; no hay tests posteriores que saltar (un solo `it`).

---

## Acción, endpoint, método

| Paso | Actor | Método | Recurso | Token usado | Esperado | Rev4 |
|---|---|---|---|---|---|---|
| Restore identidad | admin | PATCH | `/configuracion/identidad-visual/{FINCA}` (`FINCA=1`) | `tokenAdmin` (login `cy.request` al inicio) | 200/201 | No aparece en el error. **Inferencia:** pudo ejecutarse antes del PATCH tema |
| Restore tema | productor | PATCH | `/configuracion/personalizacion/tema` body `{ theme_mode: snapTema }` (2) | `tokenProd` capturado del intercept POST `/sesiones/` del login UI | 200 | **401** |

Helper `api()`: `cy.request` con `Authorization: Bearer ${tok}` y `failOnStatusCode: false`, luego `expect(status).to.eq(200)` en restore.

---

## Credenciales y autenticación

- Contraseña: `Cypress.env('contrasena')` — no hardcodeada. Login admin y productor **200** en el `it` (`expect(..., 'login admin un intento').to.eq(200)` y login UI productor 200). **Confirmado:** el 401 **no** es “faltó password en el login inicial”.
- `tokenProd` se asigna **una vez** en `cy.wait('@loginProd')` → `intc.response.body.token`.
- Después, el spec hace `cy.visit(.../dashboard)`, espera GET tema y GET contexto **del navegador**. Eso dispara el ciclo de vida del SPA (AuthContext). Documentación interna del módulo 9: un `POST /sesiones/refresh` exitoso **rota y revoca** el access token previo.

**Confirmado por código del spec.**  
**Inferencia razonable de causa:** Bearer de productor ya revocado cuando corre `after()`.  
**No verificable en G94:** cuerpo JSON del 401 (`TOKEN_REVOCADO` vs `TOKEN_EXPIRADO` vs `NO_AUTORIZADO`). Ese body **no se escribió** a `Resultados/`. G95 sí nombra `TOKEN_REVOCADO` para la misma clase.

`tokenAdmin` proviene de `cy.request` POST `/sesiones/` **sin** pasar por el navegador. Un refresh en la sesión del **productor** no debería rotar el JWT del admin, salvo bug de backend de denegación global. Por eso es plausible que identidad se restaurara y tema no. **Inferencia razonable.**

---

## Respuesta del servidor

Único dato persistido: **HTTP 401** comparado contra 200 (`diff: - '401' + '200'`).

No hay HAR, no hay log de `code`, no hay captura del header `WWW-Authenticate`.

---

## Momento de ejecución

Orden en el `it` (resumido): login → snapshots → PATCH tema=1 → PATCH identidad blanco → visita dashboard → aserción CSS → screenshot → axe.writeFile → **fin del it** → **after restore**.

La restauración corre **después** de evidencias de variante. Las aserciones de `--brand-500` y API de `color_ajustado` **ya habían pasado a nivel de comando Cypress**; el reporter igual marca el test `failed` por el hook.

Duración Mocha: suite ~10774 ms; el objeto `tests[0].duration` = 659 ms (atribución Cypress al fallo de hook, no al wall-clock completo). **Confirmado** en stats JSON.

Fecha runner: `2026-09-25T07:19:23.009Z` – `07:19:33.783Z`.

---

## Estado que se pretendía restaurar

Snapshots escritos por el spec:

- `G94-rev4-179-snapshot-identidad.json` — `primary_color` original `#1A6B3C` + secondary, org, version, logo.
- `G94-rev4-179-snapshot-tema.json` — `theme_mode` original **2**.

Alteraciones durante el test: `theme_mode=1`, `primary_color=#FFFFFF`.

---

## Aserciones antes / después del fallo

**Antes (comandos del `it`, evidencias en disco):** login 200, finca 1, PATCH tema 200, PATCH identidad 200/201, ratio 1, CSS `#757575`, axe JSON escrito (sin expect 0).

**En el fallo:** restore `theme_mode` 401.

**Después:** Mocha no ejecuta más tests. Acta afirma restore API posterior (Python/manual) identidad + tema. **Narrativa confirmada como texto; resultado en TEST no re-muestreado aquí.**

---

## Comportamiento del runner

- Tipo: **error de hook `after all`**, no `test body` assertion message sobre variante.
- Cypress **falla el test** asociado (`pass: false`, `failures: 1`, `passPercent: 0`).
- Mensaje: *skipping remaining tests* (estándar Mocha; suite de un test).
- `failOnStatusCode: false` evita que `cy.request` lance por status; el `expect(200)` **sí** lanza.

---

## Riesgo de entorno alterado

| Recurso | Si after se detuvo en tema | Si restore posterior del acta es cierta |
|---|---|---|
| Identidad finca 1 | Pudo volver a `#1A6B3C` si el PATCH admin corrió | Restaurado |
| Tema productor (usuario 2) | **Queda theme_mode=1** si el PATCH 401 no aplicó | `theme_mode=2` |
| TEST compartido | Otros casos G91/G94/G95 sensibles a tema/identidad | Riesgo residual si alguien reusa finca 1 |

**Riesgo confirmado a nivel de diseño del hook** (un 401 aborta el `expect` y, si identidad iba **después**, se perdería; en este spec identidad va **antes**).  
Estado *actual* de TEST: **no verificable** en esta fase.

---

## Causas evaluadas

| Hipótesis | Veredicto | Base |
|---|---|---|
| Password ausente / login fallido | **Descartada** | login 200 en el mismo `it` |
| Token nunca enviado | **Poco probable** | `api()` siempre pone Bearer si `tokenProd` se asignó; GET tema intermedios del `it` fueron 200 con ese token **antes** del visit dashboard |
| Token malformado al captura | **No verificable** | token no se persiste (correcto) |
| Permisos: productor no puede PATCH tema | **Descartada como causa del 401 de restore** | el mismo `tokenProd` hizo PATCH tema=1 con 200 **antes** del visit |
| Identidad / rol cambiado | **No verificable** | |
| Refresh SPA revoca Bearer | **Inferencia más fuerte** | visit dashboard + GET tema/contexto en browser; nota G94 `tc_m09_g94_contexto_401_no_es_bug.md`; G95-rev2 misma clase |
| Caducidad temporal (~10 s de suite) | **Poco probable** | TTL de minutos; 401 inmediato post-visit encaja más con rotación |
| Defecto de producto “PATCH tema debe ser 200 con token revocado” | **No es defecto de accesibilidad RF-27** | 401 a token revocado es el diseño de sesiones documentado |

Conclusión de clasificación del 401:

- **No** se afirma defecto funcional de contraste/variante por este código HTTP.
- **Sí** es fallo **real del arnés** que invalida el PASS automático y deja **duda de integridad** de limpieza.
- Causa exacta `TOKEN_REVOCADO`: **inferencia razonable**; falta el body 401 de G94.

---

## ¿Se puede reproducir de forma segura?

Sí, **sin escribir TEST**, de forma controlada:

1. No rehacer PATCH identidad blanco.
2. En un entorno local o con feature flag: login UI, capturar token, `cy.visit` dashboard, `POST refresh` observado, repetir GET con Bearer viejo → esperar 401. Eso es diagnóstico de sesiones, no de G94 completo.
3. Reejecutar G94 completo **altera** identidad y tema: **requiere autorización** y restore con **login fresco**, no token cacheado.

Esta fase **no** ejecutó esos pasos.

---

## Relación con el antecedente del líder

> “El reporte automático de rev4 marca un fallo real, el hook de restauración con 401, aunque la aserción de la variante pasó.”

**Confirmado por evidencia.** El acta APROBADO no debe prevalecer. El 401 es del restore, no de `--brand-500`.
