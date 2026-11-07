# TC-M03-085

Solo este caso.

## Identificador y nombre

- **ID:** TC-M03-085 (G48)  
- **Función:** `test_tc_m03_085_and_calidad_aire_en_edge`  
- **Archivo:** `test_tc_m03_g48.py` líneas 20–26  
- **Nombre:** AND de calidad de aire en el nodo: NH3=30 ppm y CO2=2200 ppm (`AIRE_085`) en la ventana de correlación → `DESVIACION_COMPUESTA` con trazabilidad de regla

## RF y caso de uso

**RF-55.2 / CU-02.** El script: el Δt≤5 s de `ConsolidarEnviarPaqueteUseCase` es FA-03 de **RF-56**, no esta regla. `VENTANA_CORRELACION_NO_RESUELTA` en el helper: ficha RF-55.2 Proceso ≤5 s vs Restricciones 30 s.

## Objetivo y precondiciones

Regla AND NH3>25 y CO2>2000 en ventana Edge.  
Bloqueos: (1) no hay motor Edge; (2) el equipo IoT identificó sensores temp/humedad/SpO2/acelerómetro — **no hay evidencia en este trabajo de sensores NH3/CO2**. No se presupone que existan.

## Datos de prueba (solo literales del helper)

`nh3_ppm=30`, `co2_ppm=2200`, `desviacion_compuesta=True`. No enviados a dispositivo. Sin credenciales.

## Herramienta y comando

```
python -m pytest --noconftest -p no:cacheprovider -v -rs --tb=short
  tests/.../test_tc_m03_g48.py::test_tc_m03_085_and_calidad_aire_en_edge
```

## Resultado esperado / obtenido

Esperado: `DESVIACION_COMPUESTA` en el nodo. Obtenido: **SKIPPED**.

- 2026-10-25T16:17:29.029680-05:00 → 16:17:30.168459-05:00  
- **1 skipped in 0.10s**; EXIT=0  

## Estado funcional

**BLOQUEADO** (firmware + posible ausencia de NH3/CO2). No es defecto funcional confirmado del AND.

## Evidencias

`evidencias/pytest.txt`, `pytest.html`, `pytest.xml`

## Dependencias

- **IoT/AIOT:** regla AND, ventana de correlación, sensores de aire si aplican.  
- **Backend:** no usar Δt de consolidación RF-56 como evidencia.  
- **QA:** confirmar si NH3/CO2 forman parte del alcance frente a los sensores ya identificados.
