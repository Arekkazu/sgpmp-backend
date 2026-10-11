# Fix RF-24 VISION — `json_linea_base` como SQL NULL (#548 G139, #549 G140)

## Síntoma

Toda calibración VISION sin línea base (`FALLIDA`/`FILTRADO` con N−1 = 29 aptas en
TC-M09-283, `NO_CONVERGIDA`/`REFINAMIENTO` en TC-M09-286) respondía
`400 VALOR_NO_PERMITIDO` (`field = calibracion_vision_resultado_coherente`) en vez de
`422 LINEA_BASE_NO_CALCULADA`. No quedaba en el historial ni en RF-10. La línea base
vigente no se tocaba.

## Causa raíz

`CalibracionVisionModel.json_linea_base` estaba mapeada como `JSONB` a secas.
SQLAlchemy usa `none_as_null=False` por defecto, así que el `None` del dominio se
enviaba como `'null'::jsonb`. En PostgreSQL `'null'::jsonb IS NULL` es falso, y
`ck_calibracion_vision_resultado_coherente` exige `json_linea_base IS NULL` cuando
`estado <> 'EXITOSA'`. El INSERT de `_registrar_fallida` violaba el CHECK y
`raise_from_db_error` lo convertía en el 400.

El caso de uso y el algoritmo ya hacían lo correcto: el problema estaba solo en el mapeo.

## Cambio

- `src/configuration/infrastructure/models/calibracion_vision_model.py`:
  `mapped_column(JSONB(none_as_null=True))`.
- `tests/configuration/test_inc_m09_g139_g140_json_linea_base_null.py`: comprueba
  que `None` sale como SQL NULL. Falla sin el fix.

Sin migración ni cambios en la BD. El CHECK se mantiene igual.

## Verificación

- Contra Postgres local (`sgpmp_dev`, dentro de una transacción con rollback):
  sin el fix, el INSERT `FALLIDA`/`FILTRADO` con `json_linea_base=None` lanza
  `CheckViolation` en `ck_calibracion_vision_resultado_coherente`. Con el fix, `FALLIDA`
  y `NO_CONVERGIDA` se insertan y `json_linea_base IS NULL` da verdadero.
- `pytest tests/configuration/test_inc_m09_g139_g140_json_linea_base_null.py
  tests/configuration/test_inc_m09_78_g138_calibracion_vision.py`: 22 passed.

## Fuera de alcance

Otras columnas `JSONB` anulables de otros módulos (`valores_anteriores`, `metadatos`,
etc.) tienen el mismo comportamiento por defecto. Hoy ningún CHECK ni consulta
`IS NULL` depende de eso, así que no se tocan.
