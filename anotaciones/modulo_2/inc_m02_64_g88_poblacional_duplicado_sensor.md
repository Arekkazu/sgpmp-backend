# INC-M02-64-G88 — Sensor POBLACIONAL duplicado entre lotes (RF-49)

**RF:** RF-49 (CU11), Restricción 4 — "Tipo POBLACIONAL: un sensor se asocia
a un único lote activo a la vez".
**Endpoint:** `POST /activos-biologicos/{id_activo}/sensores`

## Causa raíz

`AsociarSensorActivoUseCase.execute()` ya tenía el bloque **V8b** (cardinalidad
POBLACIONAL), pero solo validaba en un sentido: que el **activo** destino no
tuviera ya otro sensor POBLACIONAL activo (`listar_activas_por_activo`). Nunca
validaba el sentido simétrico — que el **sensor** no estuviera ya
POBLACIONAL-activo en otro activo/lote (`listar_activas_por_sensor`, que ya
existía en el puerto, sin usar para este caso).

Reproducido por QA: Sensor 1 → Lote 20 (201, asociación 105), luego
Sensor 1 → Lote 53 (201, asociación 106) en vez de 409. Resultado: dos filas
`ACTIVA` con `fecha_fin IS NULL` para el mismo sensor en lotes distintos —
lecturas IoT ambiguas entre dos poblaciones.

## Fix

Nuevo bloque **V8c**, inmediatamente después de V8b: usa
`listar_activas_por_sensor(dto.sensor_id, 'poblacional')` y rechaza con
`ConflictError(code='SENSOR_YA_ASOCIADO_A_OTRO_LOTE')` (409) si existe una
asociación POBLACIONAL activa del mismo sensor en un `id_activo_biologico`
distinto al de la petición. Sin cambios de esquema — la restricción ya la
exige el RF-49, solo faltaba aplicarla en código (se evaluó un `UNIQUE`
parcial de BD como alternativa, pero la validación en el use case ya sigue el
mismo patrón que V8b para el caso simétrico, sin necesidad de tocar el
esquema).

## Pruebas

`tests/biological_assets/test_asociar_sensor_v8c_poblacional_otro_lote.py`
(nuevo, no existía ningún test unitario previo de `AsociarSensorActivoUseCase`
en este repo): rechaza sensor ya activo en otro lote, permite si la única
asociación activa es del mismo activo. Suite completa
`tests/biological_assets/`: 100 passed (98 + 2 nuevos), sin regresiones.

## Contexto para #213 y #212 (siguientes en esta cadena)

Sin cambios relevantes al panorama ya documentado en
`anotaciones/modulo_2/inc_m02_65_g89_patch_ciclo_vida_asociacion_sensor.md` —
este fix solo tocó el bloque V8b/V8c; V1 (para #213) y el gap de RBAC de
Productor (para #212) siguen intactos y sin relación con este cambio.
