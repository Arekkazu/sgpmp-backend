# Ejecución autorizada TC-M06-51 / G119

**Fecha UTC:** 2026-11-15T07:59:15.599986+00:00  
**Ambiente:** `https://api.inmero.co/api-sgpmp-test`  
**Autorización:** expresa — anulación cotización 6 + segundo intento de irreversibilidad

## Resultado

| Ítem | Estado |
|---|---|
| TC-M06-51 | **APROBADO** |
| TC-M06-52 (histórico + vivo) | **APROBADO** |
| Dictamen G119 | **APROBADO** |

## Precondiciones

Todas cumplidas: `True`

- Cotización 6: `COTIZADO` v`1` motivo=`None`
- Activo 1571: `ACTIVO` VR=`3760000.0000`
- Período 220: `ABIERTO`
- Permiso anular: `True`

## POST 1 — Anulación

- HTTP **200**
- Estado → `ANULADA` versión `2`
- Motivo: `TC-M06-G119 / TC-M06-51 — anulación controlada de cotización 6 (activo 1571). Motivo de prueba QA; pendiente autorización.`

## RF-94

- Eventos `COTIZACION_ANULADA` ref 6: antes=0 → después=1 → tras 2º=1
- Evento principal: `{"id_evento": 25569, "tipo_evento": "COTIZACION_ANULADA", "id_referencia": 6, "timestamp_evento": "2026-11-15T07:59:09.966276Z", "tipo_actor": "USUARIO", "id_usuario": 141, "id_sistema": null, "severidad": null, "payload": {}, "justificacion": null}`

## POST 2 — Irreversibilidad

- HTTP **422** code=`None`
- Cotización permanece `ANULADA`
- Sin segundo evento: `True`

## Activo 1571

| | Antes | Después |
|---|---|---|
| Estado | ACTIVO | ACTIVO |
| VR neto | 3760000.0000 | 3760000.0000 |
| Líneas | 2 | 2 |

## Matriz

| ID | Criterio | Resultado |
|---|---|---|
| 51.1 | Cotización inicialmente COTIZADO | CUMPLE |
| 51.2 | Anulación exitosa con motivo obligatorio | CUMPLE |
| 51.3 | Estado final ANULADA | CUMPLE |
| 51.4 | Motivo persistido y conservado | CUMPLE |
| 51.5 | Evento COTIZACION_ANULADA en RF-94 | CUMPLE |
| 51.6 | Segundo intento rechazado (irreversibilidad) | CUMPLE |
| 51.7 | Activo 1571 sin cambios de estado ni valoración | CUMPLE |
| 51.8 | Sin efectos contables indebidos | CUMPLE |

## Evidencias

`C:/Users/ll529/OneDrive/Documentos/proyecto_integrador/sgpmp-backend/tests/Test_Testing/Test_Modulo6/RF-COT/TC-M06-G119/resultados/ejecucion_tc51_2026-11-15/`

## RF-94 (detalle enriquecido)

- id_evento: **25569**
- tipo: COTIZACION_ANULADA
- id_referencia: 6
- tipo_actor: USUARIO / id_usuario: 141
- timestamp: 2026-11-15T07:59:09.966276Z
- motivo en payload_evento.cambios.motivo_anulacion: sí
- justificacion en payload_evento: sí
- total eventos ref 6: 1 (sin segundo evento tras intento 422)

## Segundo intento (código confirmado)

- HTTP 422
- error_code: **COTIZACION_NO_MODIFICABLE**
- message: La cotización está anulada: ya no se puede cambiar.
