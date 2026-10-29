# 35 — Preparación TC-M09-179 rev12 (sin ejecución TEST)

**Estado oficial de G94:** no se cambia (pendiente). Cypress **no** se ejecutó. No hay PATCH, commit ni deploy.

Rev12 está **lista para una corrida controlada** una vez exista autorización explícita de escritura sobre identidad de la finca 1 y, si aplica, tema personal del productor. No está bloqueada por diseño del spec.

---

## 1. Archivos creados

| Archivo | Rol |
|---|---|
| `sgpmp-backend/tests/Test_Testing/Test_Modulo9/RF-27/TC-M09-G94/tc_m09_g94_179_rev12_test.cy.js` | Spec independiente |
| `sgpmp-backend/tests/Test_Testing/Test_Modulo9/RF-27/TC-M09-G94/cypress.config.179.rev12.cjs` | Config: Mocha/screenshots en `Resultados/179-rev12/` |
| `sgpmp-backend/tests/Test_Testing/Test_Modulo9/RF-27/TC-M09-G94/Resultados/179-rev12/NO_EJECUTADO.md` | Marcador; carpeta exclusiva |

No se tocó `Resultados/G94-rev4-179-*`, `Resultados/rev11/` ni `Resultados/178-rev4/`.

---

## 2. Antecedentes usados (fuente de verdad)

- `34_plan_cierre_brechas.md`: polo claro `#FFFFFF` → `--brand-500=#757575`; restore con login fresco; axe no es CA si se copia el oráculo rev4.
- `03_analisis_TC-M09-179.md` + `tc_m09_g94_179_rev4_test.cy.js`: PATCH form identidad finca 1; PATCH tema productor a 1; `claro.ratio===1`, `cumple_aa===false`, `color_ajustado=#757575`; `data-theme=light`.
- `G94-rev4-179-css-despues.json`: `--brand-500` inline/computed `#757575`.
- `TC-M09-G94_179_rev4_test.json`: Mocha FAIL en `after all`: `restore theme_mode HTTP: expected 401 to equal 200` (JWT del SPA).
- `tc_m09_g94_179_rev11_test.cy.js` + `27_ejecucion_rev11.md`: espera CSS con timeout; GET autenticado en `cy.then`; restore con `POST /sesiones/` fresco; evidencias exclusivas.
- `32_ejecucion_178_rev4.md`: no reejecutar 178.

**No añadido como CA:** `axe violations === 0` (rev4 no lo asertó; midió 1 violación). Rev12 **registra** axe y el ratio CSS vs fondo efectivo; **solo aserta** marca `#757575` y `data-theme=light` (más HTTP/API del estímulo rev4).

**Adaptación documentada (no oráculo nuevo):** rev4 exigía snapshot `theme_mode===2` y siempre PATCHeaba a 1. Rev12 fotografíá el tema real y PATCHea a 1 **solo si no está en claro** (mismo criterio de “no alterar innecesariamente” que rev11). El estímulo de medición sigue siendo tema claro.

Precondición conservada de rev4: `primary_color` snapshot de finca 1 = `#1A6B3C`. Si TEST no está en ese baseline, el spec **falla antes de escribir**.

---

## 3. Secuencia del spec

1. Login API `admin@pecuaria.co` (`POST /sesiones/`).
2. Login UI `productor@pecuaria.co` → `/dashboard`, contexto `id_finca=1`, `id_usuario=2`.
3. Snapshot `GET /configuracion/identidad-visual/1` (admin) y `GET /configuracion/personalizacion/tema` (productor).
4. **Preflight (solo lecturas):** login fresco admin + GET identidad 200 objeto; login fresco productor + GET tema 200. Si no, `expect` y **cero PATCH**.
5. PATCH tema `{ theme_mode: 1 }` solo si hace falta (recurso 24).
6. PATCH form identidad finca 1 `primary_color: #FFFFFF` + campos del snapshot + `version` vigente (recurso 23).
7. Comprobar API: persistido `#FFFFFF`; `claro.color_ajustado=#757575`.
8. `cy.visit /dashboard`; GET tema navegador = 1.
9. Esperar hasta 20000 ms `--brand-500 === #757575` y `data-theme=light` (`getComputedStyle`; sin tocar DOM).
10. Persistir CSS, ratio WCAG marca vs `--surface-card` o `html` background, screenshot, axe diagnóstico.
11. Aserciones de marca. **No** `expect(axe).eq(0)`.
12. `after()` restore identidad y tema con **nuevos** logins. HTTP 401 se marca `pendiente` y **no** se reintenta con el token del SPA. Fallo de identidad detiene más PATCH de identidad (`restoreDetenido`). El restore de tema (recurso distinto) sigue intentándose.

---

## 4. Mecanismo de snapshot / restore

| Recurso | Quién | Lectura | Escritura / restore |
|---|---|---|---|
| Identidad finca 1 | Admin, recurso 23 | `GET /configuracion/identidad-visual/1` | `PATCH` **form** mismos campos que rev4 (`primary_color`, `secondary_color`, `org_display_name`, `version` actual) |
| Tema personal | Productor, recurso 24 | `GET /configuracion/personalizacion/tema` | `PATCH` JSON `{ theme_mode: snapTema }` |

Éxito de restore: HTTP **200/201** (identidad) o **200** (tema) **y** GET posterior igual al snapshot. **401 no cuenta como éxito.**

Limitación estática: el preflight **no puede** demostrar un PATCH de restore sin escribir. Confirma que los logins y GET que usa el restore responden 200. Un 409 de `version` en restore se registra como pendiente y no se reintenta en bucle.

---

## 5. Validaciones ejecutadas (locales)

- `node --check` del spec y de la config: **exit 0**.
- Secuencia login → snapshot → preflight → estímulo → espera CSS → medición → restore en `after`.
- GET/PATCH autenticados envueltos en `cy.then` (lección 178-rev3).
- `trashAssetsBeforeRuns: false`; `specPattern` y `reportDir` apuntan solo a rev12.
- Contraseña vía `Cypress.env('contrasena')` con `{ log: false }` en el input; JSON de restore redacta `token`.

**No ejecutado:** `npx cypress run`; ningún HTTP de escritura a TEST.

---

## 6. Comando futuro (una corrida, solo con autorización)

Desde `sgpmp-backend`, con `CYPRESS_contrasena` ya definida en el entorno (valor no documentado):

```
npx cypress run --config-file tests/Test_Testing/Test_Modulo9/RF-27/TC-M09-G94/cypress.config.179.rev12.cjs
```

---

## 7. Riesgos

- Identidad de la **finca 1** es compartida (admin y productor). Un restore fallido deja `#FFFFFF` visible para otros usuarios hasta corrección manual autorizada.
- El JWT del SPA puede expirar o invalidarse por refresh (causa del 401 de rev4). Rev12 no lo reutiliza en restore.
- Si el baseline no es `#1A6B3C`, no hay estímulo (protección).
- Ratio CSS vs superficie se **registra**; no se usa como CA (rev4 no lo asertaba). Un contraste de marca bajo no haría fallar este spec.
- `after()` con `expect` de restore puede marcar Mocha FAIL aunque el `it` de marca haya pasado (igual que rev4). Eso es intencional: restore fallido no es PASS de revisión.

---

## 8. Condiciones previas a autorizar TEST

1. Acuerdo de ventana: PATCH identidad finca 1 y posible PATCH tema del productor.
2. Confirmación de que nadie más edita esa identidad en paralelo.
3. Restauración obligatoria; si Mocha FAIL en hook, tratar `G94-rev12-179-restore.json` como incidente (campo `pendiente`).
4. No repetir 178-rev4 ni 179-rev11.
5. No cambiar G94 a APROBADO solo por preparar rev12.

---

## 9. Veredicto de preparación

**Lista para corrida controlada**, pendiente de autorización de escritura. G94 sigue pendiente. 178-rev4 y 179-rev11 se reutilizan como evidencia ya existente y no se reejecutan en este plan.
