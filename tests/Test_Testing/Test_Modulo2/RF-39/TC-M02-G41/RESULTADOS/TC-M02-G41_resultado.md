# TC-M02-G41 — Resultado de ejecución

**Estado general: PASS — 3/3 sub-casos, 12/12 assertions vía Postman/Newman contra el backend TEST desplegado.**

| Campo | Valor |
|---|---|
| Caso de prueba | TC-M02-G41 (TC-M02-077, 078, 079) |
| RF / CU | RF-39 / CU-05 |
| Entorno | TEST — `https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test` |
| Activos | 218 (individual, fresco) · 130 (lote preexistente, con fase activa) · 219 (lote fresco, cantidad=50) |
| Fecha de ejecución | 2026-09-10, ~01:52 UTC |

## TC-M02-077 — Esquema incompleto (SANITARIO/DIAGNOSTICO sin `diagnostico`)

```json
// POST /activos-biologicos/218/eventos/sanitario {"tipo":"DIAGNOSTICO","fecha":"..."}
// HTTP 400
{"error_code":"VAL_ENTRADA","message":"Errores de validacion en la solicitud",
 "fields":[{"field":null,"message":"Value error, DIAGNOSTICO requiere el campo diagnostico."}]}
```

Rechazo correcto, con mensaje específico del campo faltante según el esquema del `tipo_evento` (`DIAGNOSTICO`).

## TC-M02-078 — LOTE + CRECIMIENTO sin campos de agregación

Activo 130 (POBLACIONAL, especie Cachama) tiene una fase productiva activa ya sembrada en TEST antes de esta
sesión ("Fase juvenil cachama"), lo que permitió llegar al punto del código donde se valida la agregación sin
necesitar crear una fase nueva (bloqueado hoy por INC-M02-37-01):

```json
// POST /activos-biologicos/130/eventos/crecimiento {"tipo_medicion":"PESO","valor_medicion":260,"unidad_medida":"kg","fecha":"..."}
// HTTP 400
{"error_code":"NUEVO_PESO_REQUERIDO","message":"El campo nuevo_peso_promedio es obligatorio para activos de tipo POBLACIONAL.",
 "fields":[{"field":"nuevo_peso_promedio","message":"..."}]}
```

Rechazo correcto, identifica el campo obligatorio faltante para LOTE tal como exige el RF. No se persistió ningún
evento sobre el activo 130 (petición rechazada, sin `id_eventos` en la respuesta).

## TC-M02-079 — BAJA con `cantidad_afectada` excesiva

Se creó un lote fresco (`id=219`) con `cantidad_inicial=50`:

```json
// POST /activos-biologicos/219/eventos/baja {"tipo_baja":"muerte","fecha_baja":"...","motivo_baja":"...","cantidad_afectada":80}
// HTTP 422
{"error_code":"CANTIDAD_BAJA_SUPERIOR_EXISTENCIA",
 "message":"La cantidad a dar de baja (80) es superior a la existencia actual del lote (50).",
 "fields":[{"field":"cantidad_afectada","message":"..."}]}
```

`GET /activos-biologicos/219` posterior confirma `cantidad_actual` sin cambios (sigue en 50) — el rechazo no dejó
ningún efecto parcial.

**Nota:** esta validación ocurre en Python antes de que el use case intente el `INSERT` en `eventos_bajas` (donde
vive el trigger roto de **INC-M02-45-02**), por lo que el bug de mayúsculas del enum no interfiere aquí — solo
afectaría a una baja con cantidad válida, que sí llegaría a ese `INSERT`.

## Resumen de assertions (Newman, 12/12 PASS)

| # | Assertion | Resultado |
|---|---|---|
| 1 | Login (200) | PASS |
| 2 | Setup activo individual (201) | PASS |
| 3–4 | TC-M02-077: 400 + mensaje menciona diagnostico | PASS |
| 5–6 | TC-M02-078: 400 + campo `nuevo_peso_promedio` identificado | PASS |
| 7–8 | Setup lote cantidad=50 (201) + cantidad_actual=50 | PASS |
| 9–10 | TC-M02-079: 422 + mensaje con 80 y 50 | PASS |
| 11–12 | Verificación: cantidad_actual sigue en 50 | PASS |

## Evidencia

- [Colección Postman](../TC-M02-G41.postman_collection.json)
- [Reporte Newman HTML](newman-TC-M02-G41.html) · [JSON](newman-TC-M02-G41.json)

## Conclusión

RF-39 cumple correctamente sus 3 exigencias de validación de esquema: rechazo por tipo de evento incompleto,
rechazo por campos de agregación faltantes en lotes, y rechazo por cantidad de baja superior a la existencia —
los tres con mensajes claros y específicos, sin necesidad de reportar ningún hallazgo nuevo en este caso.
