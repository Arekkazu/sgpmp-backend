# test_tc_m03_114_dto_acepta_clasificaciones_del_contrato[ERROR_CONFIGURACION]

Nodo pytest original. RF-56 DTO. **No** prueba umbrales ausentes o cero en Edge (TC-M03-083 / 095).

## Identificador y nombre

`test_tc_m03_g58.py` 83–89, parámetro `ERROR_CONFIGURACION`.

## RF y caso de uso

RF-56 / CU-02.

## Objetivo y precondiciones

El contrato del DTO admite el literal `ERROR_CONFIGURACION` de entrada (ya clasificado). No calcula la clasificación.

## Datos de prueba

`_base(..., clasificacion_rf55="ERROR_CONFIGURACION", severidad=None)`.

## Herramienta y comando

```
python -m pytest --noconftest -p no:cacheprovider -v --tb=short
  tests/.../test_tc_m03_g58.py::test_tc_m03_114_dto_acepta_clasificaciones_del_contrato[ERROR_CONFIGURACION]
```

## Fecha, duración y código de salida

- 2026-10-25T15:39:15.518246-05:00 → 15:39:17.373880-05:00  
- Proceso 1.856 s; pytest **1 passed in 0.64s**; EXIT=0

## Resultado esperado / obtenido

PASSED.

## Estado

**PASSED** unitario DTO. TC-M03-083 sigue BLOQUEADO.

## Evidencias

`evidencias/pytest.txt`, `pytest.html`, `pytest.xml`
