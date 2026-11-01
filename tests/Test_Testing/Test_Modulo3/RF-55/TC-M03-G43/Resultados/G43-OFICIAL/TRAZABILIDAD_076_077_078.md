# Trazabilidad de identificadores — TC-M03-076 / 077 / 078

Corrida oficial: `evidencias/run-2026-11-01-integracion/`  
Reconsulta SQL de cierre: 2026-11-01 03:17 -05:00, clúster `g43-postgres` / `sgpmp_g43_test`.  
Criterio: CA-6 de trabajo (`DECISION_CA6_TRABAJO.md`). CONTRATO §2 no reescrito. **No hay acta de Análisis.**

## TC-M03-076

| Capa | Valor |
|---|---|
| Firmware historial | `edge-evt-813be948-1919-4175-b0b3-2ab0bfc03e3a` — NORMAL, severidad `null`, 21.0 C, umbral 90043 |
| MQTT `sgpmp/G43-LAB-001/evento` | mismo `metadata_edge.id_evento`; `clasificacion_rf55=NORMAL`; **no** hay campo `severidad` |
| Gateway handlers | parseo del mismo payload e id; `device_id=52` |
| HTTP | POST `/iot/eventos-edge` → **201** (08:10:22Z) |
| PostgreSQL | 1 fila; `metadatos.clasificacion_rf55=NORMAL`; `severidad` NULL; `tipo_evento=DATOS_PROCESADOS` |

Discrepancias: ninguna de identificador. NORMAL **no** tiene severidad CRITICO.

## TC-M03-077

| Capa | Valor |
|---|---|
| Firmware | `edge-evt-6063f185-ecb2-443a-ad4c-418f190749b2` — DESVIACION_SIMPLE / CRITICO, 35.0 C, 90043 |
| MQTT | mismo id; `severidad=CRITICO` |
| Gateway | parseo + POST 201 (08:11:06Z) |
| PostgreSQL | 1 fila; DESVIACION_SIMPLE / CRITICO; `tipo_evento=ALERTA_GENERADA`; valor 35.0 |

## TC-M03-078

| Capa | Valor |
|---|---|
| Firmware | `edge-evt-0fe71210-6dcd-428e-a6be-ab40130f55e7` — DESVIACION_SIMPLE / CRITICO, 10.0 C, 90043 |
| MQTT | mismo id; `severidad=CRITICO` |
| Gateway | parseo + POST 201 (08:11:34Z) |
| PostgreSQL | 1 fila; DESVIACION_SIMPLE / CRITICO; valor 10.0 |

## Consistencia cruzada

- Tres UUID distintos (un disparo por caso).
- `count(*) = 1` por cada id (reconsulta 03:17).
- `mqtt.jsonl`: 3 líneas `/evento`, 0 `/command`.
- Serial único `G43-LAB-001` en todas las capas.
- Umbral `90043` en firmware `umbrales.json`, MQTT `metadata_edge` y PG `metadatos`.

## Contrato vs CA-6 (076)

El CONTRATO_EVENTO_EDGE §2 dice que NORMAL no se emite. El criterio de trabajo QA (CA-6) exige evento estructurado también en banda normal. Esta integración demuestra que el firmware **sí emitió** NORMAL y el backend **sí persistió** el evento. Eso no equivale a acta formal de Análisis.
