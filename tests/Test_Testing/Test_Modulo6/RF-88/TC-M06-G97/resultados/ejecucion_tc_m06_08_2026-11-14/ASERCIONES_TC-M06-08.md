# Aserciones TC-M06-08

**Resultado escenario:** **APROBADO**  
**Activo:** 2553 (`QA-M06-G97-SIN-VIDA`)  
**UTC:** 2026-11-15T03:46:26.222161+00:00 → 2026-11-15T03:46:26.607578+00:00  
**HTTP POST:** 422  

| ID | Aserción | Esperado | Obtenido | Resultado |
|---|---|---|---|---|
| A1 | Activo 2553 existe antes | `QA-M06-G97-SIN-VIDA` | `QA-M06-G97-SIN-VIDA` | PASS |
| A2 | Especie asociada 718 | `718` | `718` | PASS |
| A3 | Vida util vacia | `None` | `None` | PASS |
| A4 | Clasificacion PRODUCCION | `PRODUCCION` | `PRODUCCION` | PASS |
| A5 | Propuesta bloqueo VIDA_UTIL_NO_CONFIGURADA | `['VIDA_UTIL_NO_CONFIGURADA']` | `['VIDA_UTIL_NO_CONFIGURADA']` | PASS |
| A6 | POST HTTP 422 | `422` | `422` | PASS |
| A7 | Codigo exacto VIDA_UTIL_NO_CONFIGURADA | `VIDA_UTIL_NO_CONFIGURADA` | `VIDA_UTIL_NO_CONFIGURADA` | PASS |
| A8 | Activo sigue sin reconocer | `{'reconocimientos': 0, 'valoracion_costo': None}` | `{'reconocimientos': 0, 'valoracion_costo': None}` | PASS |
| A9 | Sin movimientos contables nuevos | `sin cambio / cero` | `{'lineas_antes': 0, 'lineas_despues': 0, 'calculos_antes': 0, 'calculos_despues': 0}` | PASS |
| A10 | Sin periodos ni reconocimientos nuevos | `{'periodos': 0, 'reconocimientos': 0}` | `{'periodos': 0, 'reconocimientos': 0}` | PASS |
| A11 | Sin modificaciones inesperadas (bloqueo/costo/especie) | `invariantes preservados` | `{'bloqueos': ['VIDA_UTIL_NO_CONFIGURADA'], 'costo': '900000.0000', 'especie': 718, 'vida': None}` | PASS |

Aprobadas: **11/11**
