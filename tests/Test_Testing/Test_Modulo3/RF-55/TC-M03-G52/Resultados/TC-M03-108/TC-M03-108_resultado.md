# TC-M03-108

Solo este caso (G52). No se documentó G51 (no pedido).

## Identificador y nombre

- **ID:** TC-M03-108  
- **Función:** `test_tc_m03_108_limite_correlacion_en_edge`  
- **Archivo:** `test_tc_m03_g52.py` líneas 17–23  
- **Nombre:** ventana de correlación en el nodo: justo bajo/sobre el límite oficial agrupa o descarta (E2)

## RF y caso de uso

**RF-55.2 / CU-02.** El script: la ficha contradice Proceso ≤5 s vs Restricciones 30 s (`VENTANA_CORRELACION_NO_RESUELTA`). El Δt de RF-56 **no** cierra este CA. No se usa `_validar_timestamps` de consolidación como esta regla.

## Objetivo y precondiciones

Decidir agrupación vs descarte en el límite temporal del nodo. Motor ausente **y** límite oficial no resuelto en `src/`.

## Datos de prueba

Ningún par de timestamps de Edge. Sin credenciales.

## Herramienta y comando

```
python -m pytest --noconftest -p no:cacheprovider -v -rs --tb=short
  tests/.../test_tc_m03_g52.py::test_tc_m03_108_limite_correlacion_en_edge
```

## Resultado esperado / obtenido

Esperado: agrupa o descarta según E2 en el límite. Obtenido: **SKIPPED**.

- 2026-10-25T16:59:51.406749-05:00 → 16:59:52.581955-05:00  
- **1 skipped in 0.08s**; EXIT=0  

## Estado funcional

**BLOQUEADO** (firmware + decisión 5 s vs 30 s). No es defecto de ventana demostrado. No es PASSED.

## Evidencias

`evidencias/pytest.txt`, `pytest.html`, `pytest.xml`

## Dependencias

- **QA / producto:** fijar el límite oficial.  
- **IoT/AIOT:** implementar E2 con ese límite.  
- **Backend:** no sustituir con FA-03 RF-56.
