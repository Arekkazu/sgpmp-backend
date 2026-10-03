# INC-M09-02-115 (#318) — Creación fallida de plantilla no auditada

Fecha: 2026-09-18

## Síntoma reportado

La creación fallida de una plantilla (nombre duplicado, datos inválidos) no
quedaba registrada en auditoría — solo la creación exitosa se auditaba.

## Resolución

Mismo defecto que INC-M09-01-109 (#319), aplicado al escenario de creación:
resuelto por el mecanismo agregado en esa rama
(`RegistrarPlantillaUseCase.execute()` envuelve toda la validación y
persistencia en un try/except que audita cualquier fallo, en una transacción
propia, antes de re-lanzar). No fue necesario tocar código adicional en esta
rama — solo se agrega la prueba de regresión específica.

## Prueba de regresión agregada

`tests/integration/test_rf30_auditoria_plantillas.py::test_auditoria_registra_creacion_fallida_por_especie_inactiva`:
crea una plantilla contra una especie que se desactiva justo antes del POST
(RF-31 FA "Especie de referencia inactiva o no encontrada", 422) y verifica
que queda una fila `CREATE`/`FALLIDO` en `/configuracion/plantillas/auditoria`.
El escenario de nombre duplicado ya lo cubre una prueba de la rama de #319
(`test_auditoria_registra_creacion_fallida_por_nombre_duplicado`); esta rama
prueba un motivo de fallo distinto para no duplicar cobertura.

## Límite conocido, fuera de alcance de esta ficha

El propio texto del issue ejemplifica con "sin `template_name`" o "datos
inválidos" — esos casos particulares son validaciones de **Pydantic en el
DTO** (`RegistrarPlantillaDTO.validar_nombre`, `validar_estructura_snapshot`),
que corren durante el parseo del request, **antes** de que FastAPI invoque el
cuerpo del endpoint. En ese punto no existe todavía ninguna variable del use
case (`usuario_actual`, sesión de dominio) a la que engancharse: un 400 de
validación de esquema nunca llega a `RegistrarPlantillaUseCase.execute()`, así
que el mecanismo de esta rama (a nivel de use case) no lo intercepta.

Cerrar ese residual exigiría un hook a nivel de `RequestValidationError` en
`src/shared/error_handlers.py` (infraestructura global, no específica de
plantillas) — cambio de mayor alcance que no se incluye aquí sin pedirlo
explícitamente. Los fallos de **regla de negocio** (nombre duplicado, especie
inactiva, scope creep, rango físico) sí quedan cubiertos: son los que RF-31
describe con su propio código HTTP en el flujo alterno, y todos se validan
dentro del use case.
