# INC-M02-76-G55 — Evento reproductivo POBLACIONAL con categoría distinta a nacimiento responde 500

**RF:** RF-42 — Registrar eventos reproductivos (CU08)

## Causa raíz

El propio reporte de QA ya identificaba dos partes:

1. `RegistrarEventoReproductivoUseCase` comparaba `activo.tipo` contra el literal
   `'LOTE'`, pero el enum real (`TipoActivo`) solo define `INDIVIDUAL`/`POBLACIONAL`
   — la condición nunca era verdadera. **Esta parte ya estaba corregida** en
   `dev` desde el commit `cb43add3` (2026-09-02, `destroyerban`), anterior a que
   se abriera este issue.
2. El trigger de BD `trg_fn_evento_reproductivo_secuencia` (`modulo2`) sí
   compara correctamente y bloquea la operación con `RAISE EXCEPTION ...
   USING ERRCODE = 'P0220'`, pero ese ERRCODE (clase `P0`, PL/pgSQL) no está
   en el mapeo de `db_error_translator.py` — psycopg2/SQLAlchemy no lo
   reconoce como `IntegrityError`, cae al branch genérico y sale como 500.
   El propio commit `cb43add3` ya dejaba esto explícitamente fuera de su
   alcance.

Con (1) ya resuelto, el use case cubre el caso documentado en este issue antes
de llegar a la base de datos. El gap real que queda — y que este fix cierra —
es (2): cualquier otra vía que dispare el trigger sin pasar por esa validación
de aplicación (un futuro caller, una migración de datos, un bug en el use
case) seguiría produciendo 500 en vez del 422 de negocio.

## Fix

`src/shared/db_error_translator.py`: se agrega `_ERRCODE_EVENTO_REPRODUCTIVO_TIPO_INVALIDO
= "P0220"` mapeado a `BusinessRuleError(code="EVENTO_NO_PERMITIDO_LOTE")` (422),
mismo patrón ya usado para `P0130`/`P0140` (INC-M09-107-G64). Es defensa en
profundidad: el use case sigue siendo la validación primaria, esto es la red
de seguridad para cualquier vía que la sortee.

Sin cambios de esquema de BD (el trigger y su ERRCODE ya existían).

## Relación con INC-M02-75-G53 (issue #226)

El mismo trigger `trg_fn_evento_reproductivo_secuencia` también señala
`P0221` (`SEQUENCE_VIOLATION`, ej. parto sin diagnóstico positivo previo) y
`P0222` (`INVALID_VALUE`, numero_crias inválido) — **ninguno de los dos está
mapeado tampoco**. #226 ("500 en el primer evento reproductivo válido") no
comparte el mismo síntoma exacto que #227, así que no se asume aquí que sea
el mismo gap, pero si la causa resulta ser una vía que dispara el trigger sin
pasar por la validación de aplicación, `P0221`/`P0222` son candidatos a
mapear con el mismo patrón que este fix.

## Pruebas

- `tests/shared/test_db_error_translator.py::test_errcode_evento_reproductivo_tipo_invalido_es_422_no_500` (nuevo).
- Suite completa de `tests/shared/` y `tests/biological_assets/test_registrar_evento_reproductivo_use_case.py`: 35 passed, sin regresiones.
