# TC-M03-106

Solo este identificador (G49). Tres nodos `HIDRICA_106`; cada uno se ejecutó aparte. Evidencias `fila0|1|2` para no pisarse.

## Identificador y nombre

- **ID:** TC-M03-106  
- **Función:** `test_tc_m03_106_calidad_hidrica_en_edge`  
- **Archivo:** `tests/Test_Testing/Test_Modulo3/RF-55/TC-M03-G49/test_tc_m03_g49.py` líneas 19–25  
- **Nombre:** (pH fuera de 6.5–8.5) AND O2 < 5 mg/L en el **nodo**  
- **Filas:**  
  - fila0: pH=6.0, O2=4.0 → compuesto True  
  - fila1: pH=6.0, O2=6.0 → False  
  - fila2: pH=7.0, O2=4.0 → False  

## RF y caso de uso

**RF-55.2 / CU-02.** El script: las combinaciones **no se evalúan** aquí; no hay motor de reglas. Matriz de diseño no versionada en `Test_Modulo3/`.

## Objetivo y precondiciones

AND hídrico en firmware. `localizar_motor_edge()` → `None`. `skip_sin_motor_edge`.  
Inventario IoT previo: temperatura, humedad, SpO2, acelerómetro — **no pH**. O2 disuelto (mg/L) tampoco está en esa lista (SpO2 ≠ O2 en agua).

## Datos de prueba

Literales `HIDRICA_106` en `rf55_preparacion.py`. No enviados a hardware. Sin credenciales.

## Comandos

```
python -m pytest --noconftest -p no:cacheprovider -v -rs --tb=short
  tests/.../test_tc_m03_g49.py::test_tc_m03_106_calidad_hidrica_en_edge[fila0]
  ...[fila1]
  ...[fila2]
```

## Resultado del runner

Los tres: **SKIPPED**, EXIT=0, `rf55_preparacion.py:62`.

| Nodo | Inicio -05:00 | pytest |
|---|---|---|
| fila0 | 16:59:45.688522 | 1 skipped in 0.07s |
| fila1 | 16:59:46.756238 | 0.10s |
| fila2 | 16:59:47.936026 | 0.08s |

## Estado funcional

**BLOQUEADO** (motor Edge + posible ausencia de pH/O2 hídrico). EXIT=0 no es PASSED. No es defecto del AND demostrado.

## Evidencias

`evidencias/fila0.txt|html|xml`, `fila1.*`, `fila2.*`

## Dependencias

- **IoT/AIOT:** regla hídrica y sensores si aplican.  
- **Backend:** no hay motor de reglas compuesto en este repo.  
- **QA:** alcance pH/O2 vs sensores ya identificados.
