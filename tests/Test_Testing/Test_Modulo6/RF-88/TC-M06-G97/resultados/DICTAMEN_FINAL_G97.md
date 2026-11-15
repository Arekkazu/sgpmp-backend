# Dictamen final — TC-M06-G97

**Dictamen del grupo:** **APROBADO**  
**Fecha de consolidación:** 2026-11-14  
**RF:** RF-88 (CU07)  
**Ambiente:** `https://api.inmero.co/api-sgpmp-test`  
**Commit evidencia:** `3995b923` · rama `laura`  
**Fuente oficial:** `estado_oficial_G97.json` · informe HTML `REPORTE_FINAL_G97.html`

## Matriz de escenarios

| Escenario | Resultado | Aserciones | Evidencia principal |
|---|---|---|---|
| TC-M06-08 | **APROBADO** | 11/11 | `ejecucion_tc_m06_08_2026-11-14/` — POST `/finanzas/reconocimientos/2553` → HTTP **422** `VIDA_UTIL_NO_CONFIGURADA` · HTML `REPORTE_TC-M06-08.html` |
| TC-M06-09 | **APROBADO** | 7/7 | `ejecucion_tc_m06_09_2026-11-14/` — GET `/finanzas/activos/1858/depreciacion?fecha=2027-11-12` → HTTP **200** · HTML `REPORTE_TC-M06-09.html` |
| **G97** | **APROBADO** | **18/18** | `estado_oficial_G97.json` · `REPORTE_FINAL_G97.html` |

## Hallazgos verificados (sin inventar)

### TC-M06-08
- Fixture: activo **2553** / `QA-M06-G97-SIN-VIDA`, especie **718**, vida útil vacía, clasificación PRODUCCION.
- POST autorizado únicamente sobre 2553 en TEST.
- Respuesta: HTTP **422**, `error_code`: `VIDA_UTIL_NO_CONFIGURADA`.
- Sin efectos secundarios: reconocimientos 0, sin valoración al costo, sin líneas/periodos nuevos; activo permanece sin reconocer.

### TC-M06-09
- Fixture: activo **1858** / `QA-RF88-AL-COSTO`.
- GET de solo lectura.
- Valores: depreciación anual **340000**, acumulada **340000**, valor contable **1360000**, registrada **0**, meses **12**.
- Sin efectos secundarios sobre la valoración persistida ni líneas contables.

## Notas de trazabilidad

- Correcciones previas relacionadas: #1114 / #1118 / #1121 (despliegue verificado antes de la ejecución funcional).
- Diagnóstico previo, reevaluación PR1118, auditoría PR1121 y preparación funcional se conservan en `evaluaciones/` sin reescritura.
- El `estado_ejecucion_G97.json` de la carpeta 09 refleja el momento parcial (08 pendiente entonces); **no** es el estado vigente del grupo.

## Confirmaciones

Sin staging, commit ni push en esta consolidación documental.
