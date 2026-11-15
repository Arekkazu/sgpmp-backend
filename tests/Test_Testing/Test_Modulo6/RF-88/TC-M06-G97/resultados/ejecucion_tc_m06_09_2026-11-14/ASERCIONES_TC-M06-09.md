# Aserciones TC-M06-09

**Activo:** 1858  
**Fecha consulta:** 2027-11-12  
**Resultado escenario:** **APROBADO**  
**UTC:** 2026-11-14T06:41:19.080176+00:00 → 2026-11-14T06:41:19.467778+00:00

| ID | Aserción | Esperado | Obtenido | Resultado |
|---|---|---|---|---|
| A1_HTTP_exitoso | HTTP exitoso | `200` | `200` | PASS |
| A2_depreciacion_anual | depreciacion_anual == 340000 | `340000` | `340000.0000` | PASS |
| A3_depreciacion_acumulada | depreciacion_acumulada == 340000 | `340000` | `340000.0000` | PASS |
| A4_valor_contable | valor_contable == 1360000 | `1360000` | `1360000.0000` | PASS |
| A5_depreciacion_registrada | depreciacion_registrada == 0 | `0` | `0.0000` | PASS |
| A6_meses_transcurridos | meses_transcurridos == 12 | `12` | `12` | PASS |
| A7_sin_efectos_secundarios | Sin side-effect en valoracion/lineas | `{'depreciacion_acumulada_registrada': '0.0000', 'valor_contable_por_costo': '1700000.0000', 'deterioro_acumulado': '0.0000', 'lineas_count': 1}` | `{'depreciacion_acumulada_registrada': '0.0000', 'valor_contable_por_costo': '1700000.0000', 'deterioro_acumulado': '0.0000', 'lineas_count_despues': 1, 'http': 200}` | PASS |

Aprobadas: **7/7**
