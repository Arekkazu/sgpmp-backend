# Tarea: RF-32 — Fix concurrencia optimista en aplicar plantilla

Issue #1630. Ver plan completo negociado en sesión de planning; resumen del bug: la
concurrencia optimista de `aplicar_plantilla_use_case.py` compara `fecha_creacion`
(inmutable) en vez de `fecha_actualizacion`, por lo que el 412 de conflicto nunca se
dispara ante una edición concurrente real. Patrón correcto ya usado en
`editar_especie_use_case.py`.

**Cambio de BD: ninguno.** `modulo9.especies.fecha_actualizacion` ya existe (verificado
vía MCP postgres) y ya está en uso por el flujo de edición de especie.

## Checklist

- [x] DTO `aplicar_plantilla_dto.py`: renombrar `fecha_creacion_especie_destino` →
      `fecha_actualizacion_especie_destino`
- [x] Use case `aplicar_plantilla_use_case.py`: comparar `fecha_actualizacion` en vez de
      `fecha_creacion`, mismo patrón de doble rama que `editar_especie_use_case.py`
- [x] Doc `anotaciones/modulo_9/api_reference_configuration.md`: actualizar nombre de campo
- [x] Doc `anotaciones/modulo_9/curls_m09_cu07_plantillas.md`: actualizar curl + descripción
      del error 412
- [x] Test de regresión `tests/configuration/test_rf32_concurrencia_aplicar_plantilla.py`
      (repos falsos, sin DB real)
- [x] `grep -rn "fecha_creacion_especie_destino" src/ anotaciones/` sin resultados (solo queda
      la mención histórica en `estado.md`, que documenta el bug ya corregido)
- [x] `pytest tests/configuration/test_rf32_concurrencia_aplicar_plantilla.py -v` en verde
      (3/3), y `pytest tests/ -m "not integration"` sin regresiones (28/28)
- [x] `resumen.md` final en esta misma carpeta
