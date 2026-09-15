# SEG-M09-01 [RF-22] — Resumen

Issue #290 · rama `fix/seg-m09-01-reasignacion-sensor-cierra-asociaciones`

`AsociarSensorAreaUseCase` (RF-22) terminaba correctamente la asociación
sensor-área anterior al reasignar un sensor, pero nunca tocaba las
asociaciones sensor→activo biológico de M02 (RF-49). Una asociación
`AMBIENTAL` o `POBLACIONAL` seguía `ACTIVA` aunque la premisa espacial que la
justificó (compartir área con el activo, validación V6 de
`AsociarSensorActivoUseCase`) ya hubiera dejado de cumplirse — el sensor
reubicado seguía imputando telemetría al activo/lote de la ubicación
anterior.

## Decisión

- **AMBIENTAL**: se cierra (`SUPERADA`) al reasignar. Es la premisa explícita
  del issue: el sensor mide el activo por compartir área.
- **POBLACIONAL**: se cierra igual que AMBIENTAL. Estructuralmente es la
  misma forma de asociación (atada a un `id_infraestructura` capturado al
  crearla, no a un individuo instrumentado) — el lote se mide por estar en
  esa área, igual que un activo individual bajo AMBIENTAL.
- **DIRECTA**: no se toca. Vincula al individuo, no al lugar; el propio
  issue lo señala como el caso donde el área es "menos relevante".

No se pidió confirmación adicional al usuario para cerrar las asociaciones
(a diferencia de la reasignación sensor-área, que si la pide): el cierre es
consecuencia automática de una reasignación ya confirmada, no una segunda
decisión de negocio.

## El fix

Nuevo puerto de dependencia hacia M02, siguiendo el mismo patrón que ya usa
`CicloM02Adapter` (supplies) — un adaptador de otro módulo que importa
directamente los modelos ORM de `biological_assets` y opera sobre la misma
`Session`, en vez de SQL crudo:

- `src/configuration/domain/repositories/asociacion_sensor_activo_dependency_port.py`
  — `AsociacionSensorActivoDependencyPort.superar_ambientales_y_poblacionales(...)`
- `src/configuration/infrastructure/adapters/asociacion_sensor_activo_m02_adapter.py`
  — implementación: filtra `asociaciones_activos_sensores` por
  `id_sensor`+`ACTIVA`+`tipo IN ('ambiental','poblacional')`, las marca
  `SUPERADA` con `fecha_fin`/`motivo`, y registra la auditoría
  correspondiente en `modulo2.auditorias_asociaciones_sensor_activo`.

`AsociarSensorAreaUseCase` recibe el puerto por constructor y lo invoca justo
después de terminar la asociación sensor-área anterior — misma `Session`,
mismo `commit()` final, así que el cierre de M02 queda en la **misma
transacción** que la reasignación de M09: si algo falla, todo se revierte
junto.

No se filtra por el área anterior explícitamente: como un sensor solo puede
tener una asociación de área activa a la vez (invariante de RF-22), "todas
las asociaciones ambientales/poblacionales activas de este sensor" es
equivalente a "las que dependían del área que se está abandonando".

## Verificación

- `tests/configuration/test_rf22_reasignacion_sensor.py` (unitario, con
  fakes): la reasignación confirmada invoca el puerto con el sensor y
  usuario correctos; la primera asociación (sin reasignación) no lo invoca.
- `tests/integration/test_seg_m09_01_reasignacion_cierra_asociaciones.py`
  (nuevo, contra Postgres real vía `TEST_DATABASE_URL`): crea la cadena
  completa (finca → 2 áreas → dispositivo → sensor → sensor-área → activo →
  asociación sensor-activo) y ejecuta `AsociarSensorAreaUseCase` con los
  repositorios/adaptadores reales — 3 casos: AMBIENTAL queda `SUPERADA` con
  auditoría, POBLACIONAL queda `SUPERADA`, DIRECTA permanece `ACTIVA`.
- `pytest tests/ -q` (sin `TEST_DATABASE_URL`): 633 passed, 183 skipped, 2
  failed — los mismos 2 fallos preexistentes en `dev`
  (`test_registrar_transferencia_use_case.py`, ajenos a M09).
- `pytest tests/ -q -m integration` (con `TEST_DATABASE_URL=pruebas`): 9
  fallos preexistentes en `dev` (confirmados revirtiendo este cambio antes
  de tocar nada — `test_rf20_tipos_area.py`, `test_rf45_trigger_baja.py`,
  dos de `identity_access`), ninguno relacionado con este fix; los 3 tests
  nuevos de este PR pasan.

## Fuera de alcance

El issue marca como abierto si además de cerrar la asociación conviene
**re-validar** (en vez de solo cerrar) — p. ej. si existiera otro activo ya
en la nueva área con el mismo sensor, ¿debería re-crearse la asociación
automáticamente? No hay ningún RF que pida ese comportamiento y añadirlo
sin pedido es inventar alcance de negocio; se deja documentado para que
Análisis lo defina si lo considera necesario.
