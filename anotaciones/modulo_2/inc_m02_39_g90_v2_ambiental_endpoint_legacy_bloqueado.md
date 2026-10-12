# INC-M02-39-G90 v2.0 (issue #351) — AMBIENTAL seguía aceptándose en el endpoint por activo

**RF:** RF-49 (CU11) — Asociación de sensores IoT a activos biológicos.
**Endpoint afectado:** `POST /activos-biologicos/{id_activo}/sensores`.

## Qué reportó QA (re-evaluación v2.0)

`TC-M02-221`: se asoció un sensor de la Infraestructura 1 a un activo de la
Infraestructura 2 (misma finca) vía `POST /activos-biologicos/{id_activo}/sensores`
con `tipo_asociacion=AMBIENTAL`. El backend respondió `201 Created` en vez de
rechazar la operación.

## Causa raíz

`INC-M02-66-G90/#217` (ver `inc_m02_66_g90_217_asociacion_ambiental_infraestructura.md`)
agregó el endpoint correcto para AMBIENTAL —
`POST /infraestructuras/{id_infraestructura}/sensores`, que persiste
`id_activo_biologico=NULL` anclado a la infraestructura — pero **nunca cerró
el endpoint viejo** para ese mismo caso. `AsociarSensorActivoDTO` seguía
declarando `tipo_asociacion: Literal['DIRECTA', 'AMBIENTAL', 'POBLACIONAL']`
y `AsociarSensorActivoUseCase._execute()` no tenía ninguna rama condicional
para `AMBIENTAL` (solo V8 para `DIRECTA` y V8b/V8c para `POBLACIONAL`) — caía
directo a persistir `id_activo_biologico=<el activo del path>`, exactamente
el defecto original que #217 debía cerrar, pero por la puerta que #217 dejó
abierta.

**El 409 por "infraestructuras distintas en la misma finca" que pedía el
issue original no es correcto pedirlo** — ya está documentado y decidido en
`inc_m02_66_g90_217_asociacion_ambiental_infraestructura.md` (`OBS-M02-G90-02`)
que la coherencia territorial es a nivel de finca (lo que el código ya
implementa, V6), no de infraestructura; es una decisión de negocio pendiente,
no un bug. El bug real es el que se corrige aquí: bloquear `AMBIENTAL` en el
endpoint que no lo soporta, para que solo se pueda crear por la infraestructura.

## Fix

- `asociar_sensor_activo_dto.py`: `tipo_asociacion` pasa de
  `Literal['DIRECTA', 'AMBIENTAL', 'POBLACIONAL']` a
  `Literal['DIRECTA', 'POBLACIONAL']`.
- `asociar_sensor_activo_use_case.py`: se quita la entrada
  `'AMBIENTAL': 'ambiental'` de `_TIPO_DB` (ya inalcanzable).

Al no estar `AMBIENTAL` en el `Literal`, FastAPI/Pydantic la rechaza como
`RequestValidationError` **antes** de llegar al use case, que este proyecto
ya mapea de forma consistente a **400 `VAL_ENTRADA`**
(`src/shared/error_handlers.py::request_validation_error_handler`) — mismo
tratamiento que cualquier otro valor de enum fuera del conjunto permitido en
este código base. RF-49 no define un "Flujo alterno" para este escenario (es
un caso nuevo, introducido por la separación de endpoints de #217, no
contemplado en el RF original), así que se sigue la convención ya establecida
del proyecto en vez de inventar un código nuevo.

## Frontend (`sgpmp-frontend`)

`AsociarSensorModal.tsx` (dentro de la ficha de un activo puntual) todavía
ofrecía "AMBIENTAL" en el combo de tipo de asociación y lo enviaba por
`sensoresApi.asociar` → el endpoint viejo. No existe ningún flujo de UI para
el endpoint nuevo (anclado a infraestructura) — se retira la opción del
modal en vez de construir ese flujo, que ningún issue de este lote pide.

## Pruebas

`tests/biological_assets/test_asociar_sensor_ambiental_rechazado.py` (nuevo):
`AsociarSensorActivoDTO(tipo_asociacion='AMBIENTAL', ...)` levanta
`pydantic.ValidationError`; `DIRECTA`/`POBLACIONAL` se siguen aceptando.

Suite completa `tests/biological_assets/`: 197 passed + 2 nuevos, mismos 2
fallos preexistentes en `test_registrar_transferencia_use_case.py` (no
relacionados, confirmados también en `fix/m02` sin este cambio).
