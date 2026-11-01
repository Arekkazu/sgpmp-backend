# Criterio de trabajo adoptado — G43 oficial / CA-6

Fecha: 2026-11-01.  
Alcance: cierre de validación QA de TC-M03-076, 077 y 078.  
**No** es un acta de Análisis ni una versión archivada del SRS.

## Qué se adopta

Para esta validación se usa como criterio **prioritario** el CA-6 de RF-55 v2.0 tal como consta en `AUDITORIA_CRITERIO_ACEPTACION_TC_M03_076.md` (paráfrasis de contenido comunicado el 2026-10-30, **sin** fichero SRS versionado en el repositorio):

| Caso | Criterio de trabajo |
|---|---|
| TC-M03-076 | Lectura en banda `normal` → **evento estructurado** `NORMAL` (no basta el historial local) |
| TC-M03-077 | Valor > `valor_max` → `DESVIACION_SIMPLE` / `CRITICO` |
| TC-M03-078 | Valor < `valor_min` → `DESVIACION_SIMPLE` / `CRITICO` |

El firmware que omitía MQTT de NORMAL **no** se usa para declarar APROBADO 076 si contradice este criterio.

## Trazabilidad documental (no inventada)

| Fuente | Qué aporta | Limitación |
|---|---|---|
| `AUDITORIA_CRITERIO_ACEPTACION_TC_M03_076.md` | CA-6: generar evento ante condición normal **o** anómala; C2/C4 evento estructurado; CA-8 envío al sistema central | El PDF/Markdown **RF-55 v2.0 no está en el repo** |
| `docs/CONTRATO_EVENTO_EDGE.md` §2 (worktree `e618a75`) | `clasificacion_rf55`: `NORMAL` **nunca se emite** (rate limit) | **Contradice** el CA-6 de trabajo. **No se modificó** este contrato |
| INC-M03-111 | Backend no clasifica; DTO ya trae `clasificacion_rf55` | POST fabricado no cubre G43 |

Hasta que Análisis archive el SRS v2.0 y resuelva CONTRATO vs CA-6, este documento es **criterio de trabajo QA**, no aprobación formal de producto.

## Decisión de implementación (firmware, no contrato)

Se implementó `EventoEdge` NORMAL en `evaluar_simple` y su encolado por el agente (un `id_evento` por lectura).  
**No** se reescribió `CONTRATO_EVENTO_EDGE.md`. La incompatibilidad de contrato permanece abierta para Análisis/broker/backend.
