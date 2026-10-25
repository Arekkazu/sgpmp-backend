# TC-M03-105

Solo este identificador. Tres filas `AIRE_105`; cada nodo se ejecutó aparte. Evidencias nombradas `fila0|1|2` (no un único `pytest.txt`).

## Identificador y nombre

- **ID:** TC-M03-105 (G48)  
- **Función:** `test_tc_m03_105_matriz_and_en_edge`  
- **Archivo:** `test_tc_m03_g48.py` líneas 29–35  
- **Nombre:** matriz AND aire: combinaciones NH3/CO2 → verdadero solo si ambos superan umbral  
- **Filas (`AIRE_105`):**  
  - fila0: NH3=26, CO2=2001 → compuesto True  
  - fila1: NH3=26, CO2=1999 → False  
  - fila2: NH3=24, CO2=2001 → False  

## RF y caso de uso

RF-55.2 / CU-02. Ventana de correlación del nodo, no FA-03 RF-56.

## Objetivo y precondiciones

Evaluar AND y no-AND en Edge. Mismos bloqueos que 085: motor ausente; NH3/CO2 no están en la lista de sensores confirmada (temp/humedad/SpO2/acelerómetro).

## Datos de prueba

Literales anteriores. Sin hardware. Sin credenciales.

## Comandos

```
python -m pytest --noconftest -p no:cacheprovider -v -rs --tb=short
  tests/.../test_tc_m03_g48.py::test_tc_m03_105_matriz_and_en_edge[fila0]
  ...[fila1]
  ...[fila2]
```

## Resultado del runner

Los tres: **SKIPPED**, EXIT=0, `rf55_preparacion.py:62`.

| Nodo | Inicio -05:00 | pytest |
|---|---|---|
| fila0 | 16:17:30.171010 | 1 skipped in 0.07s |
| fila1 | 16:17:31.260791 | 0.08s |
| fila2 | 16:17:32.372832 | 0.08s |

## Estado funcional

**BLOQUEADO.** Tres omisiones; no se demostró que el AND esté mal implementado.

## Evidencias

`evidencias/fila0.txt|html|xml`, `fila1.*`, `fila2.*`

## Discrepancia / QA

Matriz pide NH3/CO2; inventario IoT previo no los incluye. El script no cambia de RF. Ventana 5 s vs 30 s anotada en `VENTANA_CORRELACION_NO_RESUELTA`, no resuelta en `src/`.
