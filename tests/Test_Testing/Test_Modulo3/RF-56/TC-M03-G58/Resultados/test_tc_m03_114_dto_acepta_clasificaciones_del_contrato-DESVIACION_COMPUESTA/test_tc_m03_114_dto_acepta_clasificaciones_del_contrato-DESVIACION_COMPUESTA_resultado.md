# test_tc_m03_114_dto_acepta_clasificaciones_del_contrato[DESVIACION_COMPUESTA]

Nodo pytest original. RF-56. **No** es TC-M03-122 ni Edge.

## Identificador y nombre

`test_tc_m03_g58.py` 83–89, parámetro `DESVIACION_COMPUESTA`.

## RF y caso de uso

RF-56 / CU-02.

## Objetivo y precondiciones

DTO acepta el literal compuesto. Sin MQTT ni PostgreSQL.

## Datos de prueba

`_base(clasificacion_rf55="DESVIACION_COMPUESTA", severidad=None)`.

## Herramienta y comando

```
python -m pytest --noconftest -p no:cacheprovider -v --tb=short
  tests/.../test_tc_m03_g58.py::test_tc_m03_114_dto_acepta_clasificaciones_del_contrato[DESVIACION_COMPUESTA]
```

## Fecha, duración y código de salida

- 2026-10-25T15:39:13.691414-05:00 → 15:39:15.515908-05:00  
- Proceso 1.824 s; pytest **1 passed in 0.63s**; EXIT=0

## Resultado esperado / obtenido

PASSED.

## Estado

**PASSED** unitario DTO.

## Evidencias

`evidencias/pytest.txt`, `pytest.html`, `pytest.xml`
