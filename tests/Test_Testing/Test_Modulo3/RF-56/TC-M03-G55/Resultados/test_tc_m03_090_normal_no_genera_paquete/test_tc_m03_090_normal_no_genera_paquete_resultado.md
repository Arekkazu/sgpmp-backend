# test_tc_m03_090_normal_no_genera_paquete

Nodo pytest original. Script TC-M03-090 (RF-56). **No** es TC-M03-075 (NORMAL en Edge).

## Identificador y nombre

`test_tc_m03_g55.py` líneas 73–80.

## RF y caso de uso

RF-56 / CU-02: consolidación omite eventos `NORMAL`.

## Objetivo y precondiciones

`execute` con `clasificacion_rf55=NORMAL` retorna `None`, repo y motor vacíos.

## Datos de prueba

`evento_para_consolidar(clasificacion_rf55=TipoEventoEdge.NORMAL)`.

## Herramienta y comando

```
python -m pytest --noconftest -p no:cacheprovider -v --tb=short
  tests/.../test_tc_m03_g55.py::test_tc_m03_090_normal_no_genera_paquete
```

## Fecha, duración y código de salida

- 2026-10-25T15:39:21.547145-05:00 → 15:39:23.382316-05:00  
- Proceso 1.835 s; pytest **1 passed in 0.60s**; EXIT=0

## Resultado esperado / obtenido

Sin paquete. PASSED.

## Estado

**PASSED** este nodo. No demuestra `NORMAL` calculado en firmware.

## Evidencias

`evidencias/pytest.txt`, `pytest.html`, `pytest.xml`
