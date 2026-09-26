# INC-M09-27-G24 / INC-M09-26-G28 / INC-M09-31-G22 — POST /configuracion/umbrales → 500

Issues: `#148`, `#149`, `#158`.

## Síntoma reportado por QA

`POST /configuracion/umbrales` con configuración válida (especie activa, variable
activa, `valor_min < valor_max`, tres niveles contiguos sin solapamientos, dentro
del rango físico) responde:

```json
{ "error_code": "ERROR_INTERNO", "message": "Error inesperado en base de datos", "fields": [], "timestamp": "…" }
```

Reproducibilidad 8/8 en TEST, sin persistencia.

## Causa raíz (confirmada)

La columna `modulo9.niveles_alerta_ambientales.nivel` es un **ENUM nativo** de
PostgreSQL (`enum_nivel_alerta`: `normal`/`precaucion`/`critico`), pero el modelo
ORM la mapea como `String(20)` (patrón documentado en CLAUDE.md para columnas ENUM
ya existentes, para que SQLAlchemy no intente recrear el tipo en un `ALTER TABLE`).

Cuando el motor arranca con `insertmanyvalues` (comportamiento por defecto de
SQLAlchemy 2.0), el `flush()` que inserta los **tres niveles juntos** de un umbral
se agrupa en una única sentencia y cada parámetro se castea a `::VARCHAR`:

```
psycopg2.errors.DatatypeMismatch: column "nivel" is of type modulo9.enum_nivel_alerta
but expression is of type character varying
```

`DatatypeMismatch` (dentro de `ProgrammingError`) **no** es `IntegrityError`,
`DataError` ni `OperationalError`, así que `raise_from_db_error()` cae al caso
genérico y levanta `InfrastructureError("Error inesperado en base de datos")` → 500.

## Fix

`use_insertmanyvalues=False` en el `create_engine()` de `src/shared/database.py`
(PR #146, commit `d0c1286`). Vuelve al INSERT fila-por-fila (SQLAlchemy < 2.0),
sin el casteo a `::VARCHAR` que rompe las columnas ENUM.

**Este fix ya está en `dev`.** La rama de QA desplegada en TEST
(`qa/juan-esteban-m09`) divergió antes del PR #146 y perdió la línea
`use_insertmanyvalues=False`, por eso los tres casos fallaron en TEST mientras en
`dev` el mismo flujo persiste correctamente.

## Verificación

- `git diff dev origin/qa/juan-esteban-m09 -- src/shared/database.py` muestra que
  la rama de QA elimina la línea del fix.
- Reproducción con el motor **sin** el flag: `DatatypeMismatch` en la columna
  `nivel` al insertar 3 niveles en un `flush`.
- Reproducción con el motor **con** el flag (motor real de `dev`): el umbral y sus
  tres niveles persisten y el `refresh()` lee los niveles correctamente.

## Regresión

`tests/configuration/test_rf17_umbral_enum_insertmanyvalues.py` fija los dos
extremos del invariante: (1) el motor de la API desactiva `insertmanyvalues` y
(2) la columna `nivel` sigue mapeada como `String`. Si alguien vuelve a quitar el
guard (como ocurrió en la rama de QA), el test lo delata en CI.
