# INC-M02-35-G84 v2.0 — Advertencia de dispositivo IoT desconectado ausente en POST .../sensores

**RF:** RF-49 (Asociación de Activos Biológicos con Sensores IoT), CU11.
**Issue:** #347.

## Qué reportó QA

`POST /activos-biologicos/{id_activo}/sensores` nunca devuelve la advertencia informativa que
exige el flujo alterno "Dispositivo IoT Fuera de Línea" de RF-49 cuando el dispositivo asociado
lleva más de 30 minutos sin heartbeat. El campo `advertencia` de la respuesta siempre es `null`.

## Causa raíz

`advertencia=None` estaba hardcodeado en `activo_biologico_router.py` (endpoint `asociar_sensor_iot`)
y `AsociarSensorActivoUseCase` no tenía ningún puerto hacia M03 (Telemetría) para consultar el
estado de conectividad del dispositivo antes de responder — coincide exactamente con el
diagnóstico ya documentado en `anotaciones/modulo_2/gaps_flujo_alterno_modulo2.md` (tabla RF-49).

## Fix

Se sigue el patrón de puerto/adaptador ya usado en el módulo (`SensorConsultaPort`/`SensorM09Adapter`,
`InfraestructuraConsultaPort`/`InfraestructuraM09Adapter`):

1. **Puerto** `DispositivoIotEstadoPort` (`domain/repositories/dispositivo_iot_estado_port.py`):
   `obtener_estado(id_dispositivo_iot) -> EstadoDispositivoIot | None`.
2. **Adaptador** `DispositivoIotEstadoM03Adapter` (`infrastructure/adapters/dispositivo_iot_estado_m03_adapter.py`):
   consulta `modulo3.estados_dispositivos_iot.fecha_ultimo_contacto` (UNIQUE por `id_dispositivo_iot`,
   ver `[[unique_estado_dispositivo_iot]]`). No requiere cambios de esquema.
3. **Entidad** `AsociacionSensorActivo` gana un campo `advertencia: Optional[str] = None`, no
   persistido — igual patrón que `advertencia_integridad` en `ResultadoConsultaAsociacion` (RF-34).
4. **Use case** `AsociarSensorActivoUseCase`: tras guardar la asociación (la operación **nunca se
   bloquea** por esto, coherente con que el RF exige seguir respondiendo `201 Created`), calcula la
   advertencia con `sensor.id_dispositivo_iot` — no `dto.dispositivo_iot_id` (el DTO es dato del
   cliente; el sensor ya resuelto es la fuente de verdad). Sin heartbeat registrado o con heartbeat
   dentro de los últimos 30 min → `advertencia=None`, mismo comportamiento actual.
5. **Router**: inyecta el adaptador y usa `resultado.advertencia` en vez del `None` hardcodeado.

El endpoint `GET /{id_activo}/sensores` (consulta de asociaciones existentes) mantiene
`advertencia=None` — el flujo alterno del RF aplica al momento de creación (`POST`), no a la
consulta posterior.

## Pruebas

`tests/biological_assets/test_asociar_sensor_advertencia_dispositivo_desconectado.py` — 4 casos:
sin puerto configurado, heartbeat reciente, heartbeat >30 min (advertencia presente y la asociación
sí se crea), y dispositivo sin fila de estado en M03. Suite completa de `biological_assets`:
218 passed, mismos 2 fallos preexistentes en `test_registrar_transferencia_use_case.py` (no
relacionados, ya presentes en `fix/m02` antes de este cambio).
