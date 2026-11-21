# test_tc_m03_114_dto_acepta_clasificaciones_del_contrato[DESVIACION_SIMPLE]

Nodo pytest original. RF-56 / TC-M03-114 en el script. **No** es clasificación Edge.

## Identificador y nombre

`test_tc_m03_g58.py` líneas 83–89, parámetro `DESVIACION_SIMPLE`.

## RF y caso de uso

RF-56 / CU-02.

## Objetivo y precondiciones

El DTO acepta `clasificacion_rf55=DESVIACION_SIMPLE` con `severidad=None`. Doble in-memory; sin red.

## Datos de prueba

Payload `_base()` con ese literal. Sin credenciales.

## Herramienta y comando

```
python -m pytest --noconftest -p no:cacheprovider -v --tb=short
  tests/.../test_tc_m03_g58.py::test_tc_m03_114_dto_acepta_clasificaciones_del_contrato[DESVIACION_SIMPLE]
```

Corrida individual, no los lotes 1.03s / 0.98s.

## Fecha, duración y código de salida

- 2026-10-25T15:39:11.627217-05:00 → 15:39:13.688203-05:00  
- Proceso 2.061 s; pytest **1 passed in 0.70s**; EXIT=0

## Resultado esperado / obtenido

Literal conservado. PASSED.

## Estado

**PASSED** unitario DTO.

## Evidencias

`evidencias/pytest.txt`, `pytest.html`, `pytest.xml`

## Siguiente acción

No sustituye G38.
