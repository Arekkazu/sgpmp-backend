# TC-M02-G12 (issue #324) — GET /configuracion/metricas?id_especie=4 fallaba

**RF:** RF-16 (configuración de parámetros por especie).
**Endpoint:** `GET /configuracion/metricas`.

## Qué reportó QA

`GET /configuracion/metricas?id_especie=4&solo_activas=true` (y sin
`solo_activas`) respondía error para la especie 4 (Cachama Blanca). Esto
bloqueaba a su vez `TC-M02-013`/`TC-M02-014` (validación de atributos
dinámicos) y — vía #327 — `TC-M02-187`/`TC-M02-188`.

## Causa raíz

`NombreMetrica` (regex de RF-16 CU02, `src/configuration/domain/value_objects/nombre_metrica.py`)
no permitía `_`. El dato ya persistido `nombre='peso_destete'` (id
`id_metrica_produccion=15`, especie 4) predata esa validación y revienta al
reconstruirse en cada lectura — `SqlAlchemyMetricaProduccionRepository._a_entidad`
re-valida en cada `GET` un valor que ya está guardado en la base.

Reproducido en este checkout como `400 NOMBRE_METRICA_FORMATO_INVALIDO`
(la regex correctamente mapeada a `ValidationError`). La hipótesis de por
qué QA ve `500` en TEST: `_a_entidad` construía `TipoMedicion(...)`,
`AplicaTipoActivo(...)` y `TipoDatoAtributo(...)` con el **constructor crudo
del enum**, no con su propio `.desde_string(...)` (que sí existe en las 3
clases y sí mapea a `ValidationError`) — cualquier valor legacy no mapeado
en esas 3 columnas se habría ido directo a una `ValueError` sin capturar →
500 genérico. No se pudo confirmar si TEST tiene ese dato legacy adicional,
pero el gap de robustez es real independientemente del código de respuesta
exacto que QA vio.

## Fix

- `nombre_metrica.py`: regex amplía a `[A-Za-z...0-9 _\-()/]` (agrega `_`) —
  `peso_destete` es un nombre de métrica legítimo, la regex era la que
  estaba mal, no el dato. Mensaje de error actualizado para mencionar
  "guiones bajos".
- `metrica_produccion_repository.py::_a_entidad`: los 3 constructores crudos
  de enum pasan a `.desde_string(...)`, para que cualquier futuro dato
  legacy degrade a `ValidationError` (400) en vez de un `ValueError` sin
  controlar (500).

## Verificación

- Nuevo `tests/configuration/test_tc_m02_g12_metrica_nombre_legacy.py`:
  `NombreMetrica('peso_destete')` ya no lanza; `_a_entidad` reconstruye el
  dato legacy real (`peso_destete`); un valor de enum legacy no mapeado
  (`'CATEGORIA_VIEJA_YA_NO_EXISTE'`) da `ValidationError` (400), no
  `ValueError`/500.
- End-to-end (TestClient) contra datos reales de `sgpmp`:
  `GET /configuracion/metricas?id_especie=4&solo_activas=true` → `200`, con
  `peso_destete` en `items`; sin `solo_activas` → también `200`.
- Suite completa `tests/configuration/` + `tests/biological_assets/`: 445
  passed, mismos 2 fallos preexistentes en
  `test_registrar_transferencia_use_case.py` (no relacionados).
