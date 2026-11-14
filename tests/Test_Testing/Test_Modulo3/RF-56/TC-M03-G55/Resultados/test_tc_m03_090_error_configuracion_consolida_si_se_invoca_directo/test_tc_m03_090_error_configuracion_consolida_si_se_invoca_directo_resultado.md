# test_tc_m03_090_error_configuracion_consolida_si_se_invoca_directo

Nodo pytest original. El script lo agrupa bajo TC-M03-090 (RF-56). **No** es G38.

## Identificador y nombre

`test_tc_m03_g55.py` líneas 108–118.

## RF y caso de uso

RF-56 / CU-02. Comentario del test: consolidar omite `NORMAL`; Recibir no llama este camino para `ERROR_CONFIGURACION` (FA-07 / G59).

## Objetivo y precondiciones

Si se invoca `ConsolidarEnviarPaqueteUseCase` **directo** con `ERROR_CONFIGURACION`, sí hay paquete. `MotorObservado(exito=False)`, repo memoria.

## Datos de prueba

`evento_para_consolidar(clasificacion_rf55=ERROR_CONFIGURACION)`.

## Herramienta y comando

```
python -m pytest --noconftest -p no:cacheprovider -v --tb=short
  tests/.../test_tc_m03_g55.py::test_tc_m03_090_error_configuracion_consolida_si_se_invoca_directo
```

## Fecha, duración y código de salida

- 2026-10-25T15:39:19.659465-05:00 → 15:39:21.544903-05:00  
- Proceso 1.885 s; pytest **1 passed in 0.64s**; EXIT=0

## Resultado esperado / obtenido

Paquete no nulo, `estado_desviacion=ERROR_CONFIGURACION`, un guardado y un intento de motor. PASSED.

## Estado

**PASSED** este nodo. No aprueba clasificación Edge. `MotorObservado` no es ACK M04.

## Evidencias

`evidencias/pytest.txt`, `pytest.html`, `pytest.xml`
