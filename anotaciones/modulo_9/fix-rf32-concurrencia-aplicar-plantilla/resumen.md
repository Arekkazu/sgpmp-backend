# Resumen — RF-32: fix concurrencia optimista en aplicar plantilla

Issue #1630. Rama `fix/rf32-concurrencia-aplicar-plantilla`.

## Bug

`aplicar_plantilla_use_case.py` comparaba `especie_destino.fecha_creacion` —fijada una
sola vez al crear la especie, inmutable— contra `dto.fecha_creacion_especie_destino`. Esa
comparación nunca podía detectar una edición concurrente real, así que el `412` de
"conflicto de modificación concurrente" que pide el RF-32 no se cumplía en la práctica.

## Cambios aplicados

- **DTO** (`src/configuration/infrastructure/dto/aplicar_plantilla_dto.py`): campo
  renombrado `fecha_creacion_especie_destino` → `fecha_actualizacion_especie_destino`,
  tipado `datetime | None` (una especie recién creada y nunca editada tiene
  `fecha_actualizacion = NULL` en DB; el cliente debe poder enviar `null` en ese caso).
- **Use case** (`aplicar_plantilla_use_case.py:85-99`): la comparación ahora usa
  `especie_destino.fecha_actualizacion` vs `dto.fecha_actualizacion_especie_destino`, con
  el mismo patrón de doble rama null-safe que `editar_especie_use_case.py` (normaliza a
  UTC cuando ambos valores existen; comparación directa cuando alguno es `None`, para
  evitar el falso positivo de comparar `None` con un timestamp real).
- **Docs**: `anotaciones/modulo_9/api_reference_configuration.md` (tabla de entradas del
  endpoint) y `anotaciones/modulo_9/curls_m09_cu07_plantillas.md` (curl de ejemplo y
  descripción del error `412`) actualizados al nuevo nombre de campo.
- **Test** (`tests/configuration/test_rf32_concurrencia_aplicar_plantilla.py`): no existía
  suite para el módulo `configuration`, así que se usó el patrón liviano de repos falsos +
  `DbFake` que ya usa `tests/identity_access/test_tokens_un_solo_uso.py` (sin tocar
  Postgres). Tres casos:
  1. `fecha_actualizacion_especie_destino` coincide con la de la entidad → aplica y hace
     `commit()`.
  2. No coincide → `PreconditionFailedError(code="CONFLICTO_CONCURRENCIA")`, sin `commit()`.
  3. Regresión explícita del bug original: una `fecha_creacion` distinta ya **no** bloquea
     la operación (antes sí lo hacía, incorrectamente).

## Base de datos

Ningún cambio. `modulo9.especies.fecha_actualizacion` ya existía (`timestamptz`, nullable)
y ya estaba en uso por `editar_especie_use_case.py` — verificado vía MCP postgres antes de
tocar código.

## Verificación

```
pytest tests/configuration/test_rf32_concurrencia_aplicar_plantilla.py -v   # 3 passed
pytest tests/ -m "not integration"                                         # 28 passed
grep -rn "fecha_creacion_especie_destino" src/ anotaciones/                # sin resultados en código
```

`anotaciones/modulo_9/estado.md` (auditoría 2026-08-05) sigue describiendo el bug como
hallazgo histórico — no se tocó, ya que es un documento de auditoría fechado; este mismo
resumen sirve como registro de que quedó resuelto.
