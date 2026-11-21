# TC-M06-G119 — Análisis de hallazgos (vigente, parcial)

## Dictamen de grupo

**PARCIALMENTE_PENDIENTE** — no declarar G119 completo como aprobado.

| Subcaso | Estado |
|---|---|
| TC-M06-51 Anulación (cotización 6) | **PENDIENTE_AUTORIZACION** |
| TC-M06-52 Vencimiento automático (cotización 7) | **APROBADO** |

## TC-M06-52 — APROBADO

Evidencia exclusivamente de lectura (preparación 2026-11-13):

- Cotización **7** en estado **VENCIDA**, versión **2** (incremento desde 1).
- `fecha_vencimiento` = `2026-11-08`.
- `fecha_actualizacion` = `2026-11-09T00:00:06.613021Z`.
- Evento **`COTIZACION_VENCIDA`** id **7098**, `id_referencia=7`, actor **SISTEMA**, `id_sistema=M06_VENCIMIENTO_COTIZACIONES`.
- Timestamp del evento coincide con la actualización de la cotización → transición automática del proceso de fondo (`main.py` → `vencer()`).
- Activo **1570** permanece **ACTIVO** con VR neto **`3760000.0000`** (sin modificación atribuible al vencimiento).

No se ejecutó `vencer()` manual ni ninguna escritura en esta fase.

## TC-M06-51 — Pendiente

- Cotización **6** sigue **COTIZADO**, versión 1, activo 1571, sin vencimiento.
- Anulación no ejecutada.
- Dependencia con **G118** (mismo activo 1571 / baseline comercial).

## Histórico

La evaluación BLOQUEADA del 2026-11-08 se conserva intacta en `resultados/primera_evaluacion/`.
