# INC-M09-77-G137 (#513) — Observaciones de visión para la calibración VISION de RF-24

## Problema

Después de #525 (INC-M09-78-G138), `POST /configuracion/calibraciones-vision` existe y valida
sus precondiciones, pero leía las observaciones de cámara de un stub que siempre devolvía una
lista vacía (`ObservacionVisionStubAdapter`). Un área válida terminaba en
`422 LINEA_BASE_NO_CALCULADA`, así que TC-M09-275 (Ingeniero) y TC-M09-276 (Administrador) no
podían obtener nunca el 2xx con línea base nueva.

La causa no estaba en M09: **nadie producía observaciones de visión**.

- Edge y broker no tenían rama de cámara.
- M03 solo guardaba telemetría escalar (`valor_crudo`).
- Las fichas RF-53/RF-56/RF-62 v2.0 solo traen el bloque de actualización de RFC-011, sin el
  esquema del vector (ET-01) ni la fórmula del índice de calidad de visión.

## Solución (contrato provisional, decisión del 2026-10-08)

1. **M03 recibe las observaciones:** `POST /iot/telemetria/vision`. Usa la misma autenticación
   por `access_key` que el resto de la ingesta y lotes de hasta 500. Valida que el dispositivo
   sea `CAMARA` y que pertenezca al `area_id`, y que el timestamp no esté en el futuro. Los
   reenvíos se cuentan como duplicados.
2. **RF-62 v2.0:** índice de calidad propio de visión sobre las cuatro dimensiones de la ficha,
   con la misma clasificación 80/40 (`clasificar_desde_indice` / `derivar_aptitud`).
   `apto_para_nic41` es siempre `false`.
3. **M09:** `ObservacionVisionM03Adapter` lee `modulo3.observaciones_vision` y reemplaza al stub,
   que se eliminó. El use case de calibración VISION no cambió.

Curls y errores: `anotaciones/modulo_3/curls_m03_cu01_ingerir_telemetria.md`, Flujo V.

## Paso 0 — BD (migración `88496bce07b6`, `down_revision` `d7a41c9e2b58`)

| Gap | Decisión |
|---|---|
| No existía dónde guardar el vector | `modulo3.observaciones_vision`, una fila por (cámara, instante) |
| Unicidad del reenvío | `uq_observacion_vision_id_dispositivo_iot_fecha_observacion`; también sirve de índice para la consulta de RF-24 por cámara y ventana, así que no se agrega un `idx_` |
| Dimensiones de RF-62 v2.0 | `cobertura_ventana NUMERIC(5,4)`, `cantidad_tracks`, `cantidad_tracks_perdidos`, `fps_efectivo NUMERIC(6,2)`, `estado_calibracion` (CHECK) |
| Vector | `json_vector JSONB` (prefijo `json_` de la convención) |
| Resultado de calidad | `indice_calidad SMALLINT`, `clasificacion_calidad` (CHECK), `es_apto_para_ia` |
| `apto_para_nic41` | Sin columna: es constante (`false`) para visión; se expone en la API |
| RLS | No aplica, igual que el resto de `modulo3`: escribe el dispositivo, no un usuario |
| GRANT | Solo `INSERT, SELECT` (observación inmutable) a `sgpmp_app`, `rol_app`, `rol_dev`, `rol_impl`, `rol_migracion` y `rol_aiot`, si existen |

La API usa los nombres de RFC-011 (`n_tracks`, `n_tracks_perdidos`). En BD van como
`cantidad_tracks*`, porque la convención evita las abreviaturas.

**RBAC:** no hay cambios. La ingesta IoT no usa JWT, igual que `POST /iot/telemetria`. La
calibración VISION sigue usando el recurso 12 (`sensores`).

## Verificación

- 16 tests en `tests/telemetry/test_inc_m09_77_g137_observaciones_vision.py`: fórmula y tramos,
  ingesta, duplicados, rechazos, HTTP y el encadenamiento ingesta → línea base `EXITOSA`.
- De punta a punta en un Postgres 17 desechable (`alembic upgrade head` desde cero), con la app
  real:

| Paso | Resultado |
|---|---|
| Ingesta de 40 observaciones | 201, 40 aceptadas |
| Reenvío del mismo lote | 201, 40 duplicadas |
| `access_key` incorrecto / área ajena | 401 `ERROR_AUTENTICACION` / 422 `AREA_NO_COINCIDE` |
| TC-M09-275 Ingeniero | 201 `EXITOSA`, `MANUAL`, `id_usuario` del Ingeniero |
| TC-M09-276 Administrador | 201 `EXITOSA`, `MANUAL`, `id_usuario` del Administrador; reemplaza la vigente (1 fila en `lineas_base_vision`) y el historial muestra los dos |
| TC-M09-277 Productor | 403 `ACCESO_DENEGADO` con el texto de RF-24 |
| TC-M09-278 área sin cámara | 422 `VISION_NO_DISPONIBLE` |
| RF-10 | tipo 30 `exitoso` para cada éxito y tipo 29 `fallido` para cada rechazo, con `operacion = CALIBRACION_VISION` |

## Cómo prepara QA TC-M09-275/276 en TEST

1. Un área activa con `id_especie` y `tipo_modelo_asignado` POBLACIONAL (p. ej. `MODELO_AVES`).
2. Un dispositivo del tipo `CAMARA_VISION` asociado a esa área, activo y con `fps` registrado.
3. Al menos **30 observaciones aptas** en la ventana (`POST /iot/telemetria/vision`, Flujo V),
   con al menos 10 datos por componente del vector.
4. `POST /configuracion/calibraciones-vision` con esa ventana, como Ingeniero y luego como
   Administrador.

## Pendiente para Análisis / AIoT (el contrato es provisional)

1. **ET-01:** el esquema definitivo del vector de comportamiento (componentes y unidades) y del
   sobre de RF-56 v2.0.
2. **RF-62 v2.0:** la fórmula y los pesos del índice de calidad de visión. Hoy se usan pesos
   iguales, y `estado_calibracion` puntúa `CALIBRADA` 100, `DEGRADADA` 50, `SIN_DETECCION` 0.
3. **RF-24 v2.0:** los umbrales de las tres etapas (`ParametrosLineaBase`: mínimo 30
   observaciones, cobertura ≥ 0,5, 10 datos por componente, ε = 1 %, 10 iteraciones), que la
   ficha deja "configurados" sin fijar valores.
4. **Edge de visión (RF-55 v2.0):** no existe; hasta que exista, las observaciones se cargan
   por API.
