# INC-M02-66-G90 / issue #217 — Asociación Ambiental Compartida a nivel de infraestructura (RF-49 Tipo B)

**RF:** RF-49 (CU11) — Asociación de sensores IoT a activos biológicos.
**Endpoint nuevo:** `POST /infraestructuras/{id_infraestructura}/sensores`.

> Nota de numeración: este ticket reutiliza el número `INC-M02-66-G90` ya
> usado por el issue #216 (trigger de unicidad, ver
> `inc_m02_66_g90_trigger_unicidad_asociacion_sensor.md`) — son dos defectos
> distintos del mismo grupo de pruebas `TC-M02-G89`/`TC-M02-G90`, reportados
> como issues de GitHub separados (#216 y #217).

## Qué reportó QA

`TC-M02-220`: el RF-49 describe el Tipo B ("Asociación Ambiental Compartida") como un sensor ambiental asociado a una infraestructura productiva completa, que aplica automáticamente a todos los activos biológicos de esa infraestructura (cardinalidad 1 sensor → N activos, mediada por la infraestructura). El backend no lo implementaba: el único endpoint (`POST /activos-biologicos/{id_activo}/sensores`) exige un activo puntual en el path y `AsociarSensorActivoUseCase` siempre escribe `id_activo_biologico` con ese valor — no existía ninguna rama condicional para `AMBIENTAL` ni ningún endpoint a nivel de infraestructura. Para monitorear N activos había que crear N asociaciones idénticas.

`OBS-M02-G90-02` (documental, no defecto): el RF-49 tiene una contradicción interna sobre si la coherencia territorial debe exigirse a nivel de finca (permisivo, lo que el código ya implementa) o de infraestructura (estricto). Se deja fuera de este fix — es una decisión de negocio pendiente, no un bug.

## Decisiones de diseño (confirmadas con el usuario antes de implementar)

Al ser una funcionalidad nueva y no un bug, se confirmaron 3 decisiones de diseño antes de escribir código:

1. **Modelo de datos:** una única fila con `id_activo_biologico = NULL` (la columna ya lo permitía en el esquema, `is_nullable = YES`) — no un "fan-out" de N filas por cada activo actual, porque eso no cubriría automáticamente un activo agregado después a la infraestructura (contradiría el "aplica automáticamente" del RF).
2. **Alcance:** completo — no solo crear la asociación, también propagar la lectura. `ConsultarAsociacionesSensorUseCase` (`GET /activos-biologicos/{id_activo}/sensores`) ahora resuelve las asociaciones AMBIENTAL heredadas de la infraestructura del activo consultado, además de las propias.
3. **Ubicación del endpoint:** `POST /infraestructuras/{id_infraestructura}/sensores`, en un router nuevo (`infraestructura_sensor_router.py`) dentro del mismo módulo `biological_assets` (reutiliza `AsociacionSensorActivoRepository`, `SensorM09Adapter`, `InfraestructuraM09Adapter` ya existentes) — no en M09, para no crear una dependencia cruzada de módulo. El router de activos biológicos (`activo_biologico_router.py`) tiene `prefix='/activos-biologicos'` fijo, así que el nuevo endpoint vive en un `APIRouter` separado con `prefix='/infraestructuras'`, incluido aparte en `main.py`.

## Cambios

- **Entidad** `AsociacionSensorActivo`: `id_activo_biologico` y `tipo_activo` pasan a `Optional` (siguen siendo posicionales/requeridos en el constructor — solo cambia el tipo, para que `None` sea un valor válido y explícito, no un olvido).
- **Puerto** `AsociacionSensorActivoRepository`: 3 métodos nuevos — `obtener_activa_por_sensor_e_infraestructura` (evita duplicados exactos sensor+infraestructura, ya que el índice único de BD `uix_asociacion_sensor_activo_vigente` compara `id_activo_biologico` y `NULL` nunca es igual a `NULL`), `listar_activas_por_infraestructura` y `listar_todas_por_infraestructura` (ambas filtran `id_activo_biologico IS NULL`).
- **DTO nuevo** `AsociarSensorInfraestructuraDTO`: solo `dispositivo_iot_id`, `sensor_id`, `fecha_inicio`/`fecha_fin`/`motivo` opcionales — sin `tipo_activo`/`tipo_asociacion` (siempre `ambiental`) ni `id_infraestructura` (viene de la ruta).
- **Use case nuevo** `AsociarSensorInfraestructuraUseCase`: mismas validaciones V1/V3/V4/V4b/V5/V6 que `AsociarSensorActivoUseCase` (existencia y estado de infraestructura/sensor/dispositivo, área asociada, misma finca), adaptadas para comparar directo contra la infraestructura destino en vez de contra un activo. Sin validación de cardinalidad (AMBIENTAL "sin restricción de exclusividad", igual que el flujo por activo) más allá de rechazar un duplicado exacto sensor+infraestructura.
- **`ConsultarAsociacionesSensorUseCase`**: además de `listar_activas_por_activo`/`listar_todas_por_activo`, ahora también llama `listar_activas_por_infraestructura`/`listar_todas_por_infraestructura` sobre `activo.id_infraestructura` y fusiona ambas listas.
- **Router nuevo** `infraestructura_sensor_router.py`: `POST /infraestructuras/{id_infraestructura}/sensores`, mismo recurso RBAC (`id_recurso=30`, `asociacion_sensor_activo`) y acción `C` (`id_accion=1`) que ya usa `POST /activos-biologicos/{id_activo}/sensores` — sin gap de RBAC nuevo, es la misma tabla/agregado.
- **Schema** `AsociacionSensorActivoResponse`: `id_activo_biologico` y `tipo_activo` pasan a `Optional` para poder serializar `null` en las filas a nivel de infraestructura.

## Pruebas

- `tests/biological_assets/test_asociar_sensor_infraestructura_use_case.py` (nuevo, 8 casos): infraestructura inexistente/inactiva (422), sensor inexistente (404), sensor/dispositivo inactivo (422 cada uno), sensor sin área (422), finca incompatible (409), asociación AMBIENTAL duplicada sensor+infraestructura (409), creación exitosa con `id_activo_biologico=None` persistido correctamente.
- `tests/biological_assets/test_consultar_asociaciones_sensor_use_case.py`: 2 casos nuevos (`ACTIVA` y `HISTORIAL` incluyen las asociaciones heredadas de la infraestructura), más el fake de repositorio actualizado con los 2 métodos nuevos del puerto (necesario para que los 5 tests existentes de este archivo siguieran pasando).

Suite completa sin regresiones: 668 passed (658 previos + 8 + 2 nuevos), mismos 2 fallos preexistentes en `test_registrar_transferencia_use_case.py` (no relacionados).

## Fuera de alcance

- `OBS-M02-G90-02` (contradicción documental del RF-49 sobre coherencia de infraestructura vs. finca) — es una decisión de negocio, no un defecto; no se cambia el criterio existente (misma finca).
- Actualizar `sgpmp_test` — responsabilidad de despliegue/DevOps.
- Propagar la herencia de sensores AMBIENTAL a otros endpoints de consulta que no listan sensores hoy (ej. `GET /{id}/infraestructura`, que expone `sensores_en_infraestructura` pero es un concepto distinto — sensores físicamente instalados en el área vía RF-22, no asociaciones de `asociaciones_activos_sensores`).
