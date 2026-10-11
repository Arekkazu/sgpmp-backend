# INC-M02-63-G88 — Activo biológico inexistente responde 404 en vez de 422

**RF:** RF-49 — Asociación de sensores IoT (CU11)
**Endpoint:** `POST /activos-biologicos/{id_activo}/sensores`

## Análisis (antes de tocar código)

El título del issue por sí solo no basta para decidir: HTTP 404 es la
convención REST estándar para un recurso de ruta inexistente, así que un
cambio a 422 podría ser innecesario si el reporte solo reflejara preferencia
de QA. Se verificó contra la fuente primaria antes de actuar: el propio
cuerpo del issue adjunta `resultado_tc_m02_g88.md`, que cita textualmente el
Flujo Alterno del CU11:

> "Activo Biológico No Válido (Inexistente o Baja) — Condición: El ID no
> existe o el campo estado es 'BAJA'. Respuesta del Sistema: HTTP 422
> Unprocessable Entity."

El contrato agrupa **inexistente y BAJA en un mismo flujo alterno con una
sola respuesta**. Esto se confirma además por inconsistencia interna del
propio código: `AsociarSensorActivoUseCase.execute()` ya tenía V2 (`ACTIVO_EN_BAJA`)
usando `BusinessRuleError` (422) correctamente — solo V1 (`ACTIVO_NO_ENCONTRADO`,
el caso "inexistente" del mismo flujo alterno) seguía usando `NotFoundError`
(404). No es un desacuerdo de interpretación de REST; es un caso donde el
propio código ya resuelve la mitad del flujo bien y la otra mitad mal.

## Fix

`V1` cambia de `NotFoundError` a `BusinessRuleError`, mismo `code`
(`ACTIVO_NO_ENCONTRADO`), mismo mensaje — solo cambia la clase de excepción
(y por tanto el HTTP status, vía `src/shared/error_handlers.py`). Ningún
cliente que ya lea el `error_code` se ve afectado; solo cambia el status code
HTTP de 404 a 422.

El router ya documentaba `422` en `responses` para este endpoint (por V2 y
otras reglas de negocio), así que no hizo falta tocar el contrato OpenAPI.
`404` se mantiene documentado — sigue siendo la respuesta correcta para
`SENSOR_NO_ENCONTRADO` (V3), un caso distinto no cubierto por este flujo
alterno.

## Pruebas

No existía ninguna prueba unitaria previa de `AsociarSensorActivoUseCase`
para V1/V2 (solo V8c, agregado por INC-M02-64-G88 en esta misma cadena).
Se agrega `tests/biological_assets/test_asociar_sensor_v1_activo_no_valido.py`
(2 casos: activo inexistente → 422, activo en BAJA → 422, ambos verificando
`BusinessRuleError` y el `code` correcto). Suite completa de
`tests/biological_assets/`: 102 passed, sin regresiones.
