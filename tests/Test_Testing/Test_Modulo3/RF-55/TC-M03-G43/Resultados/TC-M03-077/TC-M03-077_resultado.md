# TC-M03-077

Solo este caso.

## Identificador y nombre

- **ID:** TC-M03-077 (G43)  
- **Función:** `test_tc_m03_077_sobre_maximo_edge`  
- **Archivo:** `test_tc_m03_g43.py` líneas 25–26  
- **Nombre:** valor > `umbral_max` en el nodo → `DESVIACION_SIMPLE`

## RF y caso de uso

RF-55.1 / CU-02. Recibir DTO ya clasificado no cubre el CA.

## Objetivo y precondiciones

Firmware compara contra umbral máximo local. Falta motor Edge y umbral en nodo. Sensores IoT identificados: temperatura, humedad, SpO2, acelerómetro.

## Datos de prueba

Ninguno. Sin credenciales.

## Herramienta y comando

```
python -m pytest --noconftest -p no:cacheprovider -v -rs --tb=short
  tests/.../test_tc_m03_g43.py::test_tc_m03_077_sobre_maximo_edge
```

## Resultado esperado / obtenido

Esperado: `DESVIACION_SIMPLE` en el Edge. Obtenido: SKIPPED (`rf55_preparacion.py:62`).

- 2026-10-25T15:46:05.265519-05:00 → 15:46:06.443467-05:00  
- Proceso 1.178 s; pytest **1 skipped in 0.11s**; EXIT=0  

## Estado

**BLOQUEADO** (SKIPPED). Unitarios que aceptan el literal `DESVIACION_SIMPLE` en el DTO no verifican el umbral.

## Evidencias

`evidencias/pytest.txt`, `pytest.html`, `pytest.xml`

## Siguiente acción

Firmware con umbral_max y medición por encima. Equipo AIOT.
