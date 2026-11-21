# 09 — Ejecución rev5 TEST (2026-10-10)

**Grupo G94: RECHAZADO.** Mocha rev5 no aprueba 179. No hay commit/push.

Credenciales: `SGPMP_TEST_PASSWORD` / `CONTRASENA` / `CYPRESS_contrasena` presentes en Process/User/Machine. No se documentan valores.

Comando (cwd `sgpmp-backend`):

```
npx cypress run --config-file tests/Test_Testing/Test_Modulo9/RF-27/TC-M09-G94/cypress.config.179.rev5.cjs
```

`CYPRESS_contrasena` se asignó en el proceso; no se pasó el secreto en la línea de comandos visible.

---

## Intentos

| Intento | Mocha | Fail | Mutación TEST | Hook after |
|---|---|---|---|---|
| 1 | 0 pass / 1 fail | `token para GET ... expected null to be a string` (spec: `api()` leía el JWT al encolar) | No | omitido |
| 2 | 0 pass / 1 fail | `Cannot read properties of null (reading 'primary_color')` | No | omitido |
| 3 (oficial `TC-M09-G94_179_rev5_test.json`) | **0 pass / 1 fail** | `GET identidad finca 1 no nulo: expected null to not equal null` | No | omitido |

Corrección local entre 1 y 2: `api()` resuelve el token **dentro** de `cy.then` (igual que rev4). No se debilitó auth ni se cambiaron criterios de variante/contraste/restore.

---

## Preguntas del objetivo (intento 3)

1. **¿El token capturado sigue válido?** No se llegó a la sonda. Login admin y productor **200**. GET contexto con sesión UI **200**.
2. **¿Refresh interceptado?** `restore.json.refresh_durante_it: []`. El `it` abortó antes del segundo `cy.visit('/dashboard')`. **No hay evidencia de refresh ni de 401 en rev5.**
3. **¿Restore con login fresco?** **No aplicó** (`omitido: true`, no hubo PATCH).
4. **¿GET final = snapshot?** No hubo snapshot RF-26 ni PATCH. Post-corrida: `theme_mode=2`, contexto `primary_color=#1A6B3C`.
5. **¿Variante aplicada?** No. No se envió `#FFFFFF`.
6. **¿Contraste ≥ 4.5 de la variante?** No medido (no se aplicó).
7. **¿Axe 0 `color-contrast`?** No se ejecutó axe.
8. **¿Mocha fallos en test o hooks?** Fail en el **`it`**. El `after` corrió y **no falló** (restore omitido). `beforeHooks`/`afterHooks` vacíos en el JSON Mocha; la evidencia del after es `G94-rev5-179-restore.json`.

### Causa del 401 de rev4

**No reproducida en rev5.** No hay `error_code`. Sigue sin confirmarse `TOKEN_REVOCADO` con body de G94/G94-rev5.

### Bloqueo que impidió 179

`GET /configuracion/identidad-visual/1` → **HTTP 200 con `null`**. `GET .../1/auditoria` → **404**.  
`GET /configuracion/interfaz/contexto` del productor (finca 1) **sí** trae `identidad_visual.primary_color=#1A6B3C` y accesibilidad.

No se hizo POST de alta ni PATCH a blanco: no hay `version` ni fila RF-26 restaurable. Eso **no** se eludió.

---

## TC-M09-178

Última evidencia TEST: **rev2** (`G94-rev2-test-ejecucion.txt`, axe 0 violaciones, 12 nodos, dashboard). Alcance: **solo ese dashboard**, no todo el tema. No se reejecutó 178 en esta ventana. **No basta** para APROBAR el grupo.

---

## Veredicto

| Ítem | Resultado |
|---|---|
| Mocha 179 rev5 | FAIL (1/1) |
| 179 criterio funcional (variante) | No ejecutado — BLOQUEADO por GET identidad nulo |
| 178 | APROBADO rev2, muestra limitada, no reconfirmado |
| **G94** | **RECHAZADO** |

Rev4 permanece intacta (`TC-M09-G94_179_rev4_test.json`).
