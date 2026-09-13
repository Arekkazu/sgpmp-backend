# INC-M02-65-G89 — PATCH para ciclo de vida de asociaciones sensor-activo (RF-49)

**RF:** RF-49 (CU11) — Asociar sensor IoT al activo biológico
**Endpoint nuevo:** `PATCH /activos-biologicos/{id_activo}/sensores/{id_asociacion}`

## Causa raíz

El backend solo exponía `POST /{id_activo}/sensores` (crear). No existía ningún
endpoint para las 3 transiciones formales del ciclo de vida que define el
RF-49: desactivación manual (`ACTIVA → INACTIVA`), reactivación
(`INACTIVA → ACTIVA`) y rechazo de transición inválida (`INACTIVA → SUPERADA`).
Los 3 subcasos devolvían 404 por ausencia de ruta, no por lógica de negocio.

La infraestructura de persistencia (`AsociacionSensorActivoRepository.actualizar_estado`)
ya existía y ya se usaba internamente (para marcar `SUPERADA` una asociación
reemplazada) — solo faltaba la capa de aplicación/API para invocarla
manualmente. El CHECK `asociaciones_activos_sensores_estado_asociacion_check`
en `modulo2.asociaciones_activos_sensores` ya permite `ACTIVA`/`INACTIVA`/`SUPERADA`
— no hizo falta ninguna migración de esquema.

## Fix

- `CambiarEstadoAsociacionSensorDTO` (nuevo): acepta `estado_nuevo` (validado
  contra el mismo set del CHECK de BD) y `motivo` opcional.
- `CambiarEstadoAsociacionSensorUseCase` (nuevo): tabla de transiciones válidas
  (`ACTIVA↔INACTIVA`; `SUPERADA` sin salidas, inalcanzable como destino desde
  ningún estado). Rechaza con `BusinessRuleError(TRANSICION_INVALIDA)` (422)
  cualquier transición no permitida, `ConflictError(ESTADO_REDUNDANTE)` (409)
  si ya está en el estado pedido, `NotFoundError(ASOCIACION_NO_ENCONTRADA)`
  (404) si la asociación no existe o no pertenece al `id_activo` de la ruta.
  Al desactivar fija `fecha_fin=now()`; al reactivar la limpia a `null`.
- Router: nuevo `@router.patch`, mismo recurso RBAC (`id_recurso=30`,
  `asociacion_sensor_activo`) con acción `U` (actualizar, `id_accion=3`).

## Gap de RBAC resuelto (Paso 0)

Ningún rol tenía la acción `U` sobre el recurso 30 — ni siquiera Administrador
(que solo tenía `C`/`R`). Se insertaron permisos para Administrador (`id_rol=1`)
e Ingeniero de Campo (`id_rol=4`), mismos roles que ya tenían `C`, en **ambas**
bases (`sgpmp` y `pruebas`):

```sql
INSERT INTO modulo1.permisos (nombre, descripcion, id_recurso, id_accion, id_rol, es_activo)
VALUES
  ('admin_actualizar_asociacion_sensor_activo', '...', 30, 3, 1, true),
  ('ing_actualizar_asociacion_sensor_activo', '...', 30, 3, 4, true);
```

**Nota para #212** (Productor sin permiso de `C` sobre este recurso): si ese
fix le otorga `C`, considerar si también necesita `U` aquí — no se decidió en
este PR para no invadir el alcance de #212.

## Pruebas

`tests/biological_assets/test_cambiar_estado_asociacion_sensor_use_case.py`
(nuevo, 6 casos: desactivar, reactivar, rechazo SUPERADA, estado redundante,
404 sin asociación, 404 asociación de otro activo). Suite completa
`tests/biological_assets/`: 98 passed, sin regresiones.

---

## Panorama del submódulo RF-49 (para #214, #213, #212)

Todo vive en:
- Router: `src/biological_assets/infrastructure/routers/activo_biologico_router.py`
  (buscar `_RECURSO_SENSOR = 30`, sección `CU11 RF-49`)
- Use case: `src/biological_assets/application/use_cases/gestion/asociar_sensor_activo_use_case.py`
- Puerto: `src/biological_assets/domain/repositories/asociacion_sensor_activo_repository.py`
- Repo: `src/biological_assets/infrastructure/repositories/asociacion_sensor_activo_repository.py`
- Entidad: `AsociacionSensorActivo` en `src/biological_assets/domain/entities/activo_biologico.py`
- DTO existente: `src/biological_assets/infrastructure/dto/asociar_sensor_activo_dto.py`

### #214 (INC-M02-64-G88) — POBLACIONAL duplicado entre lotes

Causa raíz ya localizada en `AsociarSensorActivoUseCase.execute()`, bloque
**V8b** (`# Cardinalidad POBLACIONAL`): solo valida que el **activo** no tenga
ya otro sensor poblacional activo (`listar_activas_por_activo`). Nunca valida
que el **sensor** no esté ya poblacional-asociado a otro activo/lote
(`listar_activas_por_sensor`) — la Restricción 4 del RF-49 exige justo eso
("un sensor se asocia a un único lote activo a la vez"). El fix probablemente
es un `V8c` simétrico a V8b, usando `self.repo.listar_activas_por_sensor(dto.sensor_id, 'poblacional')`
(ya existe en el puerto, no hace falta agregarlo) y comparando contra `id_activo`
en vez de contra `sensor_id`.

### #213 (INC-M02-63-G88) — 404 en vez de 422 para activo inexistente

`AsociarSensorActivoUseCase.execute()`, bloque **V1**, usa `NotFoundError`
(`ACTIVO_NO_ENCONTRADO`) cuando el activo no existe. El CU11 exige 422 para
ese flujo alterno según el propio issue. Mismo tipo de fix que #223 en esta
misma cadena (cambiar la clase de excepción, no la lógica) — revisar si real
mente debe ser `BusinessRuleError` o si por convención de "recurso padre en
la URL no existe" debería seguir siendo 404 en otros módulos: **antes de
tocarlo, confirmar contra el documento RF-49/CU11 real si 422 aplica solo a
este caso o si contradice el patrón 404 que sí usan otros módulos para
"recurso padre inexistente"** — el propio issue afirma que el flujo alterno
del CU11 exige 422 textualmente, así que probablemente sí hay que cambiarlo,
pero vale la pena citar el texto exacto del CU11 en el PR.

### #212 (INC-M02-62-G87) — Productor sin permiso de creación

Gap de RBAC puro, no de código: `modulo1.permisos` no tiene fila para
(Productor, `C`, recurso 30) — el propio issue ya lo diagnostica exactamente
así. Fix = Paso 0 (INSERT en `modulo1.permisos` en `sgpmp` y `pruebas`), sin
tocar ningún archivo de `src/`. Revisar también si Productor necesita otras
acciones (`R` ya la tiene) una vez agregada `C`.

Ningún hallazgo bloquea a los otros tres — pueden implementarse en cualquier
orden dentro de la cadena.
