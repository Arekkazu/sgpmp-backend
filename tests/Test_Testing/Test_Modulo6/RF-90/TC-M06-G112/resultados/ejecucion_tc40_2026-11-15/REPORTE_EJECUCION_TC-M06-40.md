# Ejecución autorizada TC-M06-40 / G112

**Fecha UTC:** 2026-11-16T02:35:41.955272+00:00  
**Ambiente:** `https://api.inmero.co/api-sgpmp-test`  
**Dictamen TC-M06-40:** **APROBADO**  
**Dictamen G112 global:** no aprobado (grupo incompleto)

## POST

- HTTP **201**
- id_registro_costo: `4497`
- id_linea: `6918`
- política: `GASTO`
- cuentas: D`510506` / C`250505`

## Matriz

| ID | Criterio | Resultado |
|---|---|---|
| 40.1 | POST HTTP éxito | CUMPLE |
| 40.2 | Línea REGISTRADA | CUMPLE |
| 40.3 | Origen MANO_OBRA_PROPIA | CUMPLE |
| 40.4 | Subtipo INVERSION_DIRECTA | CUMPLE |
| 40.5 | Política GASTO | CUMPLE |
| 40.6 | Débito 510506 | CUMPLE |
| 40.7 | Crédito 250505 | CUMPLE |
| 40.8 | Asignación ganadora 8581 (inferida por cuentas+ámbito) | CUMPLE |
| 40.9 | Activo 2552 ACTIVO | CUMPLE |
| 40.10 | Valor costo permanece 3.000.000 | CUMPLE |
| 40.11 | Capitalización no confirmada / sin asiento CAPITALIZACION indebido | CUMPLE |
| 40.12 | Período 629 ABIERTO | CUMPLE |
| 40.13 | Períodos 219/220 intactos | CUMPLE |

## Hallazgo H1

No se declara que la asignación 34 conserve D158405/C250505. La reevaluación identificó general vigente 8898 D510506/C250505 y específica 8581 para especie 655 + INVERSION_DIRECTA. Hallazgo de configuración separado; ninguna asignación fue modificada en esta ejecución.

## Evidencias

`C:/Users/ll529/OneDrive/Documentos/proyecto_integrador/sgpmp-backend/tests/Test_Testing/Test_Modulo6/RF-90/TC-M06-G112/resultados/ejecucion_tc40_2026-11-15/`
