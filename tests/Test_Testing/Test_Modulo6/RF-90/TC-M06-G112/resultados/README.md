# TC-M06-G112 — Índice de evidencias

Grupo de pruebas **RF-90 / RF-109 / RF-94**: TC-M06-39 (CAPITALIZAR) + TC-M06-40 (GASTO).  
**RF-93** es requisito **relacionado** (decisión B); no condiciona la aprobación del grupo. Ver `DICTAMEN_ALCANCE_RF93_G112.md`.

## Dictamen del grupo

**G112 global: APROBADO** (alcance RF-90 / RF-109 / RF-94)

| Escenario | Dictamen | Evidencia |
|---|---|---|
| TC-M06-39 | **APROBADO** | `ejecucion_tc39_2026-11-15/` |
| TC-M06-40 | **APROBADO** | `ejecucion_tc40_2026-11-15/` |
| RF-93 | `PENDIENTE_CASO_INDEPENDIENTE` (ni aprobado ni fallido) | `DICTAMEN_ALCANCE_RF93_G112.md` |

**Informe HTML consolidado:** [`REPORTE_FINAL_G112_RF90.html`](REPORTE_FINAL_G112_RF90.html)

## Evidencia clave TC-M06-39

- HTTP 201 · costo **4498** · línea **7121** · política **CAPITALIZAR**
- D**158405** / C**250505** · sentido **CAPITALIZACION**
- RF-94 **28938** `COSTO_REGISTRADO`
- Activo 1573 `ACTIVO` · valor **$4.100.000** · período 220 `ABIERTO`
- Criterios: 15 CUMPLE · 0 NO CUMPLE · 1 NO VERIFICABLE (39-X1 RF-93/cerrar 220)

## Evidencia clave TC-M06-40

- HTTP 201 · costo **4497** · línea **6918** · política **GASTO**
- D**510506** / C**250505** · `REGISTRADA` · MOP · `INVERSION_DIRECTA`
- RF-94 **28193** `COSTO_REGISTRADO`
- Activo 2552 `ACTIVO` · valor **$3.000.000** · período 629 `ABIERTO`
- Criterios: **13/13 CUMPLE**
- Hallazgo H1 (configuración 8898/8581) documentado; sin modificar matrices

## Estructura

| Ruta | Rol |
|---|---|
| `REPORTE_FINAL_G112_RF90.html` | Informe HTML final consolidado |
| `ejecucion_tc39_2026-11-15/` | Ejecución autorizada TC-39 **APROBADA** (intacta) |
| `ejecucion_tc40_2026-11-15/` | Ejecución autorizada TC-40 **APROBADA** (intacta) |
| `prevalidacion_tc39_2026-11-15/` | Prevalidación solo lectura previa al POST 39 |
| `estado_oficial_G112.json` | Estado oficial del grupo (**APROBADO**) |
| `DICTAMEN_ALCANCE_RF93_G112.md` | Alcance formal de RF-93 vs G112 |
| `ORGANIZACION_FINAL_G112.json` | Inventario de organización / publicación |
| `_arch/primera_evaluacion_bloqueada_2026-11-08/` | Histórico bloqueado (conservado) |
| `_arch/` | Diagnósticos/preparaciones intermedias + scripts auxiliares excluidos del paquete QA mínimo |

## Paquete QA mínimo (publicación)

Scripts: `_ejecutar_tc39_autorizado.py`, `_ejecutar_tc40_autorizado.py`, `ejecutar_tc_m06_g112.py`  
Más evidencias 39/40, prevalidación, docs oficiales, HTML final e histórico bloqueado.  
**Excluidos del paquete:** `_arch/scripts_auxiliares/`, check local en `_arch/cierre_documental_2026-11-15/`.

## Restricciones de cierre

- No se cerró el período 220.
- No se declaró RF-93 como aprobado ni como fallido.
- No se sobrescribieron matrices ni respuestas HTTP de las ejecuciones.
