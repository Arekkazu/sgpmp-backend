# test_tc_m03_117_error_configuracion_guarda_evento_sin_paquete

Nodo pytest original. El script lo agrupa bajo TC-M03-117 (RF-56). **No** es emisión Edge TC-M03-083.

## Identificador y nombre

`test_tc_m03_g59.py` líneas 63–71.

## RF y caso de uso

RF-56 / CU-02: recepción de evento **ya** clasificado.

## Objetivo y precondiciones

Con `clasificacion_rf55=ERROR_CONFIGURACION`: guardar evento en memoria, no crear paquete, no llamar al motor. Dobles `recibir_use_case()` / `SesionNula`.

## Datos de prueba

`dto_evento_edge(clasificacion_rf55=ERROR_CONFIGURACION)` en `rf56_dobles.py`. Sin PostgreSQL.

## Herramienta y comando

```
python -m pytest --noconftest -p no:cacheprovider -v --tb=short
  tests/.../test_tc_m03_g59.py::test_tc_m03_117_error_configuracion_guarda_evento_sin_paquete
```

Corrida individual, no los lotes 1.03s / 0.98s.

## Fecha, duración y código de salida

- 2026-10-25T15:39:17.377565-05:00 → 15:39:19.656780-05:00  
- Proceso 2.279 s; pytest **1 passed in 0.89s**; EXIT=0

## Resultado esperado / obtenido

Evento guardado; `paquete_inferencia_estado is None`; motor y paquetes vacíos. PASSED.

## Estado

**PASSED** unitario de recepción. No aprueba umbrales Edge.

## Evidencias

`evidencias/pytest.txt`, `pytest.html`, `pytest.xml`

## Limitación

Memoria ≠ bitácora HTTP ni firmware.
