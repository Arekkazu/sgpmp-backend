# INC-M02-91-G93 (issue #242) — datos-consolidados acepta rangos de fechas futuras

**RF:** RF-50 · **CU:** CU12 · **Endpoint:** `GET /activos-biologicos/{id_activo}/datos-consolidados`
**TC:** TC-M02-156-B

## Causa raíz

`DatosConsolidadosDTO.validar_rango_fechas` solo comprobaba que `fecha_inicio` no
fuera posterior a `fecha_fin`, pero nunca comprobaba el rango contra la fecha actual.
Un rango íntegramente futuro (`fecha_inicio=2026-09-11`, `fecha_fin=2026-09-12` con
fecha actual `2026-09-10`) pasaba la validación y el endpoint respondía `200` con
datos consolidados (peso actual, historial de eventos) sobre un período que aún no
había ocurrido.

## Fix

- `DatosConsolidadosDTO.validar_rango_fechas` (model_validator) rechaza con
  `ValueError` si `fecha_inicio` es posterior a `date.today()`. Como el validador
  existente ya garantiza `fecha_inicio <= fecha_fin`, basta con acotar el inicio: si
  el inicio no es futuro, el fin tampoco puede serlo por sí solo sin violar esa cota
  (y si lo fuera de forma aislada, el rango sigue siendo consultable hasta hoy sin
  exponer nada que no haya ocurrido).
- El router ya envolvía la construcción del DTO en `except ValueError` /
  `except pydantic.ValidationError`, mapeando a `DomainValidationError` → HTTP 400,
  `PARAMETROS_INVALIDOS` — no requirió cambios.
- Sin cambios de esquema de BD.

## Alcance no cubierto (fuera de este ticket)

- `ConsultarIndicadoresDTO` (RF-51, endpoint `/indicadores`) tiene el mismo gap: no
  rechaza un rango íntegramente futuro. No es parte de este issue (que es
  específicamente sobre `datos-consolidados`) — queda para un ticket propio si QA lo
  reporta sobre ese endpoint.
- El router ya tenía (antes de este fix) un `except ValueError` seguido de un
  `except pydantic.ValidationError` inalcanzable en esta misma función (pydantic
  `ValidationError` es subclase de `ValueError`, así que el segundo `except` nunca se
  ejecuta) — pyright ya lo marca (`reportUnusedExcept`) en varios puntos del router.
  Por eso el mensaje de error que ve el cliente es el `str()` crudo de la excepción de
  pydantic en vez del mensaje limpio que el código pretendía extraer. Es un defecto
  preexistente que afecta a todas las validaciones de este endpoint (tipo_dato,
  paginación, orden de fechas), no algo introducido por este fix ni exclusivo de él —
  se documenta aquí porque se detectó durante esta revisión, pero corregirlo excede el
  alcance de INC-M02-91-G93.

## Pruebas

- `tests/biological_assets/test_datos_consolidados_dto.py` (nuevo): 4 casos — rechazo
  por fecha de inicio futura, acepta inicio = hoy, acepta rango pasado, acepta sin
  fechas.
- Suite completa de `tests/biological_assets/`: 80 passed, sin regresiones.

## Frontend

No requiere cambios — el defecto es de validación backend.
