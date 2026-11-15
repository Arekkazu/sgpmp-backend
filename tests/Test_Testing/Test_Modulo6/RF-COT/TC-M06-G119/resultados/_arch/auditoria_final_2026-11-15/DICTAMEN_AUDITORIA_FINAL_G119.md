# Dictamen auditoría final — TC-M06-G119

**Fecha UTC:** 2026-11-15T07:54:53.829209+00:00  
**Ambiente:** `https://api.inmero.co/api-sgpmp-test`  
**Modo:** solo lectura (sin POST/PATCH/PUT/DELETE; sin commit; estado oficial no modificado)

## Dictamen global

**PARCIALMENTE APROBADO** — el grupo **no** puede aprobarse completo.

| Subcaso | Estado |
|---|---|
| TC-M06-51 (anulación cotización 6) | **PENDIENTE DE EJECUCIÓN** |
| TC-M06-52 (vencimiento automático cotización 7) | **APROBADO** (confirmado) |

## TC-M06-52 — APROBADO (confirmación)

Estado vivo en TEST consistente con evidencia histórica:

- Cotización **7**: `VENCIDA`, versión **2**, `fecha_actualizacion=2026-11-09T00:00:06.613021Z`
- Evento **`COTIZACION_VENCIDA`** id **7098**, `id_referencia=7`, actor sistema `M06_VENCIMIENTO_COTIZACIONES`
- Activo **1570**: `ACTIVO`, VR neto `3760000.0000`
- Evidencia histórica: `resultados/ultima_evaluacion/evidencia_escenario_tc52_TC-M06-G119.json`

No se reprocesó el vencimiento.

## TC-M06-51 — PENDIENTE DE EJECUCIÓN

No existe evidencia posterior de anulación. Estado vivo:

- Cotización **6**: `COTIZADO`, versión `1`, `motivo_anulacion=None`
- Eventos `COTIZACION_ANULADA` ref 6: **0**
- Activo **1571** baseline: `ACTIVO`, VR `3760000.0000`
- Período **220**: `ABIERTO`

### Solicitud de autorización (no ejecutada)

```http
POST /finanzas/cotizaciones/6/anulacion
```

```json
{
  "version": 1,
  "motivo_anulacion": "TC-M06-G119 / TC-M06-51 — anulación controlada de cotización 6 (activo 1571). Motivo de prueba QA; pendiente autorización."
}
```

Esperado tras autorización: `ANULADA` + motivo + evento `COTIZACION_ANULADA`; segundo intento `422 COTIZACION_NO_MODIFICABLE`; activo 1571 intacto.

## Matriz de criterios

| ID | Criterio | Resultado |
|---|---|---|
| 51.1 | Cotización 6 inicialmente COTIZADO | CUMPLE |
| 51.2 | Anulación exitosa con motivo obligatorio | PENDIENTE DE EJECUCIÓN |
| 51.3 | Estado final ANULADA | PENDIENTE DE EJECUCIÓN |
| 51.4 | Motivo persistido y conservado | PENDIENTE DE EJECUCIÓN |
| 51.5 | Evento COTIZACION_ANULADA registrado en RF-94 | PENDIENTE DE EJECUCIÓN |
| 51.6 | Segundo intento rechazado por irreversibilidad | PENDIENTE DE EJECUCIÓN |
| 51.7 | Activo 1571 sin cambios de estado ni valoración | NO VERIFICABLE |
| 51.8 | Sin efectos contables indebidos | NO VERIFICABLE |
| 52.1 | Cotización 7 estado VENCIDA | CUMPLE |
| 52.2 | Versión 1 → 2 | CUMPLE |
| 52.3 | Evento COTIZACION_VENCIDA 7098 actor SISTEMA | CUMPLE |
| 52.4 | Activo 1570 ACTIVO VR 3.760.000 sin cambio | CUMPLE |
| 52.5 | Evidencia histórica disponible y consistente | CUMPLE |

## Identificadores de auditoría

- TC-52: evento **7098** `COTIZACION_VENCIDA`
- TC-51: **ningún** evento `COTIZACION_ANULADA` para ref 6

## Rutas de evidencia

- `C:/Users/ll529/OneDrive/Documentos/proyecto_integrador/sgpmp-backend/tests/Test_Testing/Test_Modulo6/RF-COT/TC-M06-G119/resultados/auditoria_final_2026-11-15/`
- Histórico TC-52: `resultados/ultima_evaluacion/`
- Preparación TC-51: `resultados/preparacion/solicitud_anulacion_preparada_G119.json`

## Nota

No se modificó `resumen_ejecucion_vigente_TC-M06-G119.json` ni la matriz oficial: faltan criterios 51.2–51.8 con evidencia de escritura autorizada.
