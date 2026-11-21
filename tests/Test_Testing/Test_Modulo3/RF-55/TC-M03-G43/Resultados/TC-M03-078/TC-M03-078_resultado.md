# TC-M03-078

Solo este caso.

## Identificador y nombre

- **ID:** TC-M03-078 (G43)  
- **Función:** `test_tc_m03_078_bajo_minimo_edge`  
- **Archivo:** `test_tc_m03_g43.py` líneas 29–30  
- **Nombre:** valor < `umbral_min` → `DESVIACION_SIMPLE`

## RF y caso de uso

RF-55.1 / CU-02.

## Objetivo y precondiciones

Clasificación bajo mínimo en el nodo. Motor Edge ausente.

## Datos de prueba

Ninguno. Sin credenciales.

## Herramienta y comando

```
python -m pytest --noconftest -p no:cacheprovider -v -rs --tb=short
  tests/.../test_tc_m03_g43.py::test_tc_m03_078_bajo_minimo_edge
```

## Resultado esperado / obtenido

Esperado: `DESVIACION_SIMPLE` por infracción de mínimo. Obtenido: SKIPPED.

- 2026-10-25T15:46:06.446002-05:00 → 15:46:07.533466-05:00  
- Proceso 1.087 s; pytest **1 skipped in 0.07s**; EXIT=0  

## Estado

**BLOQUEADO** (SKIPPED).

## Evidencias

`evidencias/pytest.txt`, `pytest.html`, `pytest.xml`

## Siguiente acción

Nodo con umbral_min y medición por debajo. AIOT.
