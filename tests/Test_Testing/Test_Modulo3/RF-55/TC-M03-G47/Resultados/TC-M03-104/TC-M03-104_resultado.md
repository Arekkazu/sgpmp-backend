# TC-M03-104

Solo este identificador. Seis nodos pytest (cortes THI); cada uno se ejecutó por separado. Los nombres `pytest.txt` se adaptaron a `evidencias/<corte>.txt` para no pisarse.

## Identificador y nombre

- **ID:** TC-M03-104 (G47)  
- **Función:** `test_tc_m03_104_cortes_thi_en_edge`  
- **Archivo:** `test_tc_m03_g47.py` líneas 31–37  
- **Nombre:** cortes THI en Edge: NORMAL&lt;72; LEVE 72–78; MODERADO 78–84; CRÍTICO≥84  
- **Nodos:** `[71.9-NORMAL]`, `[72.0-LEVE]`, `[77.9-LEVE]`, `[78.0-MODERADO]`, `[83.9-MODERADO]`, `[84.0-CRITICO]` (`CORTES_THI`)

## RF y caso de uso

RF-55.2 / CU-02. Fórmula no está en `src/telemetry`.

## Objetivo y precondiciones

Clasificar por valor THI en el nodo. Motor Edge ausente. Inclusividad exacta de 72/78/84 es la de la tupla del helper; no evaluada en firmware.

## Datos de prueba

Literales `CORTES_THI` en `rf55_preparacion.py`. Sin hardware. Sin credenciales.

## Comandos (uno por nodo)

```
python -m pytest --noconftest -p no:cacheprovider -v -rs --tb=short
  tests/.../test_tc_m03_g47.py::test_tc_m03_104_cortes_thi_en_edge[<nodo>]
```

## Resultado del runner

Los seis: **SKIPPED**, EXIT=0, `rf55_preparacion.py:62`.

| Nodo | Inicio -05:00 | pytest |
|---|---|---|
| 71.9-NORMAL | 16:17:21.989631 | 1 skipped in 0.08s |
| 72.0-LEVE | 16:17:23.192857 | 0.08s |
| 77.9-LEVE | 16:17:24.362622 | 0.09s |
| 78.0-MODERADO | 16:17:25.538474 | 0.08s |
| 83.9-MODERADO | 16:17:26.652655 | 0.09s |
| 84.0-CRITICO | 16:17:27.859479 | 0.08s |

## Estado funcional

**BLOQUEADO** para el CA completo. Seis omisiones, cero PASSED. No es defecto de cortes THI demostrado.

## Evidencias

`evidencias/71.9-NORMAL.txt|html|xml` y análogos para 72.0-LEVE, 77.9-LEVE, 78.0-MODERADO, 83.9-MODERADO, 84.0-CRITICO.

## Dependencias

IoT/AIOT: cortes THI en nodo. Backend: fórmula ausente. QA: inclusividad de 72/78/84.
