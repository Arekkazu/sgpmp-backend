# TC-M02-G17 (issue #327) — atributos dinámicos y TRANSFERENCIA_INTERNA

**RF:** RF-33 — Registro de Activos Biológicos.
**Endpoint:** `POST /activos-biologicos`.

## Qué reportó QA — 3 sub-casos

- **TC-M02-187** (atributo dinámico obligatorio ausente) y **TC-M02-188**
  (tipo de dato incorrecto): bloqueados porque `GET /configuracion/metricas`
  respondía error, así que QA no podía determinar qué atributo probar.
- **TC-M02-189** (`origen_financiero=transferencia_interna`, `costo_adquisicion=null`,
  `soporte_documental=null`): reportado como `HTTP 500`.

## Diagnóstico

**TC-M02-187/188** no son un gap de código — el código de validación
(`ATRIBUTO_REQUERIDO`/`ATRIBUTO_TIPO_INVALIDO` → 422) ya existe y es
correcto (`_validar_atributos_dinamicos` en `registrar_activo_use_case.py`).
Quedan desbloqueados por el fix de **#324** (`GET /configuracion/metricas`
500/400, ver `inc_m02_45_g12_peso_destete.md` y el nuevo doc de #324) — sin
tocar más código aquí. Reverificados manualmente tras ese fix (ver ese PR).

**TC-M02-189**: el `500` reportado no fue reproducible contra el código
actual (mismo patrón de entorno/migración que #322/#325, comentado aparte en
esos issues) — 4 escenarios distintos, incluido este exacto payload, dieron
`201` en este checkout. Pero sí hay un **gap real** en
`_validar_origen_financiero()`: tiene ramas explícitas para
`compra`/`donacion`/`nacimiento`, pero **ninguna para
`transferencia_interna`** — caía sin validar nada, así que hoy se podía
registrar `costo_adquisicion` sin `soporte_documental` para ese origen,
violando la restricción de RF-33 ("Si TRANSFERENCIA_INTERNA: costo
opcional; si se informa, debe ser > 0 y llevar soporte_documental").

## Fix

Rama nueva en `_validar_origen_financiero`, mismo patrón/mismo tipo de error
que `compra`/`donacion` (`BusinessRuleError` → 422):

```python
elif origen == 'transferencia_interna':
    if dto.costo_adquisicion is not None:
        if dto.costo_adquisicion <= 0:
            raise BusinessRuleError(code='COSTO_ADQUISICION_INVALIDO', ...)
        if not dto.soporte_documental:
            raise BusinessRuleError(code='SOPORTE_DOCUMENTAL_REQUERIDO', ...)
```
(costo y soporte ambos `None` sigue permitido, tal como pide el RF).

## Verificación

- 4 tests nuevos en `test_registrar_activo_use_case.py` (mismo patrón que los
  ya existentes para compra/nacimiento): sin costo ni soporte → no lanza;
  costo ≤ 0 → 422 `COSTO_ADQUISICION_INVALIDO`; costo > 0 sin soporte → 422
  `SOPORTE_DOCUMENTAL_REQUERIDO`; costo > 0 con soporte → no lanza.
- End-to-end (TestClient, rollback): `POST /activos-biologicos` con
  `transferencia_interna` — costo=100/sin soporte → 422; costo=0 → 422;
  costo=None/soporte=None → 201 (comportamiento ya correcto, sin cambios).
