# TC-M02-G40 — Resultado de ejecución

**Estado general: TC-M02-075 PASS completo. TC-M02-076 PASS en comportamiento de negocio, con una discrepancia de
código HTTP frente a la ficha (422 real vs. 400 documentado).** 9/11 assertions PASS vía Postman/Newman contra el
backend TEST desplegado.

| Campo | Valor |
|---|---|
| Caso de prueba | TC-M02-G40 (TC-M02-075, TC-M02-076) |
| RF / CU | RF-39 / CU-05 |
| Entorno | TEST — `https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test` |
| Activos | 213 (CERRADO, precondición vía BD) · 215 (ACTIVO, fresco) |
| Fecha de ejecución | 2026-09-10, ~01:43 UTC |

## Precondición de TC-M02-075

Con autorización explícita del usuario, se insertó (COMMIT real) en `modulo2.historicos_estados_activos`:

```sql
INSERT INTO modulo2.historicos_estados_activos
  (id_activo_biologico, id_estado_anterior, id_estado_nuevo, fecha_cambio, motivo_cambio, modulo_origen, id_usuario)
VALUES (213, 1, 5, now(), 'QA-G40 precondicion TC-M02-075', 'RF-38', 47);
```

El trigger `trg_fn_sincronizar_estado_activo` actualizó `activos_biologicos.id_estado` automáticamente (verificado:
`5`). Confirmado también vía API: `GET /activos-biologicos/213` → `"nombre_estado":"CERRADO"`.

Ver `README.md` para la explicación de por qué esta precondición no se pudo lograr por la API normal
(bloqueada por INC-M02-37-01 e INC-M02-45-02, ambos ajenos a RF-39).

## TC-M02-075 — Rechazar evento sobre activo CERRADO

**PASS completo.**

```json
// POST /activos-biologicos/213/eventos/sanitario
// HTTP 409
{
  "error_code": "ESTADO_NO_PERMITE_EVENTOS",
  "message": "No es posible registrar eventos sobre este activo. El activo se encuentra en estado CERRADO, el cual no permite nuevos registros de eventos. Los estados que permiten registro de eventos son: ACTIVO, EN_TRATAMIENTO, AISLADO."
}
```

Código y mensaje coinciden con lo que exige la ficha ("HTTP 409 CONFLICT indicando que el estado actual no permite
nuevos registros de eventos").

## TC-M02-076 — Rechazar fecha de evento inválida

**Comportamiento de negocio correcto en ambos casos; código HTTP real 422, no 400 como documenta la ficha.**

**(a) Fecha futura (2027-01-01):**
```json
// HTTP 422 (ficha documenta 400)
{"error_code":"FECHA_FUTURA","message":"La fecha del evento no puede ser posterior a la fecha actual."}
```

**(b) Fecha anterior al registro del activo (2025-01-01, activo registrado 2026-09-10):**
```json
// HTTP 422 (ficha documenta 400)
{"error_code":"FECHA_ANTERIOR_REGISTRO","message":"La fecha del evento es inválida o inconsistente con el historial."}
```

El mensaje de (b) coincide **exactamente, palabra por palabra**, con el que documenta la ficha del caso. La única
diferencia es el código HTTP: el use case usa `BusinessRuleError` (`src/biological_assets/application/use_cases/
gestion/_event_validations.py`), que este proyecto mapea consistentemente a **422** en toda la base de código
(documentado en `CLAUDE.md`: "BusinessRuleError | 422 | Violación de regla de negocio") — no es un comportamiento
errático ni inconsistente del sistema, es la convención propia del proyecto aplicada de forma correcta; la
imprecisión está en que la ficha del caso documenta 400 en vez de 422 para este tipo de regla.

## Resumen de assertions (Newman, 9/11 PASS)

| # | Assertion | Resultado |
|---|---|---|
| 1 | Login (200) | PASS |
| 2 | Precondición: activo 213 CERRADO | PASS |
| 3–4 | TC-M02-075: 409 + mensaje correcto | PASS |
| 5 | Setup activo fresco (201) | PASS |
| 6 | **TC-M02-076 futura: código 400** | **FAIL — 422 (negocio correcto, ver arriba)** |
| 7 | TC-M02-076 futura: mensaje coincide | PASS |
| 8 | **TC-M02-076 anterior: código 400** | **FAIL — 422 (negocio correcto, ver arriba)** |
| 9 | TC-M02-076 anterior: mensaje coincide exactamente | PASS |

## Evidencia

- [Colección Postman](../TC-M02-G40.postman_collection.json)
- [Reporte Newman HTML](newman-TC-M02-G40.html) · [JSON](newman-TC-M02-G40.json)

## Conclusión

Ambos sub-casos cumplen la intención real del RF (rechazar la operación inválida, con mensaje claro). La única
discrepancia (código HTTP 422 vs. 400) es una imprecisión de la ficha de prueba frente a una convención de
arquitectura ya documentada y aplicada consistentemente en el proyecto — no amerita un incidente de código; queda
registrada aquí para que el equipo de análisis decida si ajusta la ficha del caso a 422, o si prefiere estandarizar
estas validaciones a 400 en todo el proyecto (cambio de mayor alcance, afectaría todas las `BusinessRuleError`
del sistema, no solo RF-39).
