# TC-M04-G049 — APROBADO

## Decisión del caso

Caso agrupado TC-M04-G049 (RF-69); originales TC-M04-114, TC-M04-115, TC-M04-116 y TC-M04-117. Decisión: APROBADO. Motivo: Estados: APROBADO, APROBADO, APROBADO, APROBADO.

| Caso | Comprobación | Decisión | Motivo breve |
|---|---|---|---|
| TC-M04-114 | API-114-01 | APROBADO | VERSION_REGISTRADA y VERSION_APROBADA de sistema con fuente id_proceso_rf71 (RF-69 Fase 6) |
| TC-M04-115 | API-115-01 | APROBADO | Tres identificadores enteros positivos distintos; GET de V1 devuelve el mismo identificador |
| TC-M04-116 | API-116-01 | APROBADO | Salida 1 completa e igual a la enviada |
| TC-M04-117 | API-117-01 | APROBADO | V3 refiere V2 y V1 se registró sin referencia |

RUN oficial: sí (registro QA OFICIAL, DELETE 200, rollback confirmado).

Qué sigue: cerrar la reevaluación V2 con su evidencia y revisión QA.

## Detalle por caso

### TC-M04-114 — APROBADO

**Qué se hizo:** Se envió un modelo MODELO_ESPECIES_GRANDES por POST /prediccion/modelos como invocación interna de RF-71, con proceso 32ba4557-24d8-4f0a-bcbd-85ba014f15aa, F1 0.91 y recall de riesgo alto 0.93; se consultó su auditoría.
**Qué se esperaba:** Registro automático sin intervención humana, primero en EN_VALIDACION y luego con resultado automático; auditoría con VERSION_REGISTRADA y VERSION_APROBADA o VERSION_RECHAZADA, originadas por RF-71 (RF-69, líneas 1790, 2001-2004 y 2089-2095).
**Qué se observó:** POST HTTP 201 registró la versión 128; auditoría HTTP 200 mostró VERSION_APROBADA por SISTEMA, fuente 32ba4557-24d8-4f0a-bcbd-85ba014f15aa, estado APROBADO y VERSION_REGISTRADA por SISTEMA, fuente 32ba4557-24d8-4f0a-bcbd-85ba014f15aa, estado APROBADO.
**Por qué APROBADO:** Los dos eventos de sistema están vinculados al proceso RF-71 y acreditan registro y aprobación automáticos; el estado APROBADO del evento de registro es una foto final, no prueba de una transición omitida.

### TC-M04-115 — APROBADO

**Qué se hizo:** Se enviaron 3 versiones MODELO_ESPECIES_GRANDES desde procesos RF-71 32ba4557-24d8-4f0a-bcbd-85ba014f15aa, 8968c608-f162-40a5-85a4-217ba40330e6, 216b1815-b262-4a14-9140-a1784a468496, se compararon sus identificadores y se consultó la primera por GET.
**Qué se esperaba:** Tres identificadores enteros positivos distintos, consultables por GET (decisión de Análisis del 2026-10-31 sobre RF-69, líneas 1794 y 2207).
**Qué se observó:** Los registros devolvieron HTTP 201 e identificador 128; HTTP 201 e identificador 129; HTTP 201 e identificador 130; la consulta de la primera versión devolvió HTTP 200 e identificador 128.
**Por qué APROBADO:** Los tres identificadores son enteros positivos distintos y la primera versión se puede consultar con el identificador recibido.

### TC-M04-116 — APROBADO

**Qué se hizo:** Se envió el modelo MODELO_ESPECIES_GRANDES con proceso 32ba4557-24d8-4f0a-bcbd-85ba014f15aa, F1 0.91, recall alto 0.93, precisión 0.92, accuracy 0.94, ROC AUC 0.95, hashes de dataset 8d45c09b8b3048cb154542532ee9b1295078367ebbcf23ed25afaa60e5b46d88 y artefacto 46f971b933a3a104fedaa6058f6d1188b6ad97dc1ac9a9642d59df8518a1e470, fecha 2026-10-31T01:47:33.387Z; se leyó la versión 128 por GET.
**Qué se esperaba:** Persistencia fiel de todos los campos de Salida 1, incluido id_version entero, métricas, hashes, fechas, origen RF-71 y notas de validación nulas hasta la revisión clínica (RF-69, líneas 2204-2223; decisión de Análisis del 2026-10-31).
**Qué se observó:** GET /prediccion/modelos/128 respondió HTTP 200: estado APROBADO, F1 0.9100, recall alto 0.9300, precisión 0.9200, accuracy 0.9400, ROC AUC 0.9500, notas de validación nulas; demás campos y valores en la tabla de Salida 1.
**Por qué APROBADO:** Los campos de Salida 1 y sus valores coinciden con lo enviado, las fechas están presentes y las notas siguen nulas; el formato del identificador se decide en TC-M04-115.

### TC-M04-117 — APROBADO

**Qué se hizo:** Se registró V1 sin referencia, después V2 129 y V3 con referencia a V2; se consultaron V1 y V3 por GET usando los procesos RF-71 32ba4557-24d8-4f0a-bcbd-85ba014f15aa y 216b1815-b262-4a14-9140-a1784a468496.
**Qué se esperaba:** El registro sin version_referencia procede; cuando se envía, la versión anterior existe y la relación queda consultable (RF-69, línea 1965 y fase de recepción, líneas 1972-1985).
**Qué se observó:** V1 128 se registró sin referencia; V2 129 y V3 130 devolvieron HTTP 201 y 201; GET V3 HTTP 200 devolvió referencia 129.
**Por qué APROBADO:** V1 se registró sin referencia y V3 expone en GET el mismo entero positivo recibido como identificador de V2.

## Comparación V1 → V2 por caso

| Caso | V1 | V2 | Comparación |
|---|---|---|---|
| TC-M04-114 | APROBADO | APROBADO | Registro y auditoría automáticos; V2: VERSION_REGISTRADA y VERSION_APROBADA de sistema con fuente id_proceso_rf71 (RF-69 Fase 6) |
| TC-M04-115 | RECHAZADO | APROBADO | V1 rechazó 58, 59 y 60 por UUID; V2 aplica la decisión de Análisis y comprueba entero positivo, unicidad y GET fiel; V2: Tres identificadores enteros positivos distintos; GET de V1 devuelve el mismo identificador |
| TC-M04-116 | APROBADO | APROBADO | Persistencia fiel de la Salida 1 con id_version entero; V2: Salida 1 completa e igual a la enviada |
| TC-M04-117 | APROBADO | APROBADO | V1 sin referencia y V3 con referencia entera igual a V2; V2: V3 refiere V2 y V1 se registró sin referencia |

## Identificación

RF-69 v2.1; versión V2; RUN RUN-G049-V2-20261101-014729; ambiente TEST; autorización AUT-G049-V2-20261101; código de referencia origin/test daefc3a5 (despliegue no verificado); Newman 6.2.2; Cypress no requerido, 0 ejecuciones.

Decisión de Análisis del 2026-10-31: id_version y version_referencia pueden ser enteros. Sustituye el texto UUID de RF-69 en las líneas 1794, 1965 y 2207; el documento de requerimientos aún no está actualizado.

## Esperado vs observado por caso

### TC-M04-114 · API-114-01

Esperado: VERSION_REGISTRADA (Fase 1, sistema, fuente id_proceso_rf71) y VERSION_APROBADA o VERSION_RECHAZADA (Fase 3, sistema). Observado para id_referencia 128:

| Evento | Actor | id_usuario | id_sistema | Estado del payload |
|---|---|---|---|---|
| VERSION_APROBADA | SISTEMA | nulo | 32ba4557-24d8-4f0a-bcbd-85ba014f15aa | APROBADO |
| VERSION_REGISTRADA | SISTEMA | nulo | 32ba4557-24d8-4f0a-bcbd-85ba014f15aa | APROBADO |

Decisión: APROBADO. VERSION_REGISTRADA y VERSION_APROBADA de sistema con fuente id_proceso_rf71 (RF-69 Fase 6)

### TC-M04-115 · API-115-01

Esperado: tres identificadores enteros positivos distintos y consultables por GET. Observado: POST 201 → 128; 201 → 129; 201 → 130; GET /prediccion/modelos/128 HTTP 200 devuelve id_version_modelo 128. Decisión: APROBADO.

### TC-M04-116 · API-116-01

Esperado: campos de Salida 1 presentes y fieles, con notas_validacion nulo. El formato entero del identificador corresponde a TC-M04-115.

| Campo | Enviado / exigido | GET V1 observado |
|---|---|---|
| id_version | entero positivo (formato evaluado en TC-M04-115) | 128 |
| tipo_modelo | MODELO_ESPECIES_GRANDES | MODELO_ESPECIES_GRANDES |
| estado | APROBADO automático | APROBADO |
| f1_score_global | 0.91 | 0.9100 |
| recall_clase_riesgo_alto | 0.93 | 0.9300 |
| precision_global | 0.92 | 0.9200 |
| accuracy | 0.94 | 0.9400 |
| roc_auc_score | 0.95 | 0.9500 |
| recall_por_clase | riesgo_alto: 0.93; riesgo_bajo: 0.92 | riesgo_alto: 0.93; riesgo_bajo: 0.92 |
| matriz_confusion | 9 / 1 / 1 / 9 | 9 / 1 / 1 / 9 |
| dataset_entrenamiento_hash | 8d45c09b8b3048cb154542532ee9b1295078367ebbcf23ed25afaa60e5b46d88 | 8d45c09b8b3048cb154542532ee9b1295078367ebbcf23ed25afaa60e5b46d88 |
| hash_artefacto_modelo | 46f971b933a3a104fedaa6058f6d1188b6ad97dc1ac9a9642d59df8518a1e470 | 46f971b933a3a104fedaa6058f6d1188b6ad97dc1ac9a9642d59df8518a1e470 |
| fecha_entrenamiento | 2026-10-31T01:47:33.387Z | 2026-10-31T01:47:33.387000Z |
| timestamp_registro | fecha válida | 2026-11-01T01:47:34.032130Z |
| id_proceso_rf71 | 32ba4557-24d8-4f0a-bcbd-85ba014f15aa | 32ba4557-24d8-4f0a-bcbd-85ba014f15aa |
| notas_validacion | nulo | nulo |

Decisión: APROBADO. Salida 1 completa e igual a la enviada

### TC-M04-117 · API-117-01

Esperado: V1 sin referencia y V3 con version_referencia entera igual al identificador de V2, consultable. Observado: V1 sin referencia true; V2 id 129; V3 version_referencia 129. Decisión: APROBADO.

## Observaciones

- VERSION_REGISTRADA: payload_evento de VERSION_REGISTRADA refleja APROBADO; es una foto del estado final, no la transición. El historial de transiciones no se expone por API pública.
- El tipo MODELO_ESPECIES_GRANDES fue aceptado en los tres POST.
- Tres artefactos ONNX de 84 bytes quedaron fuera del rollback de BD.
- Para Análisis: los identificadores secuenciales son enumerables; riesgo señalado en V1, sin efecto en el veredicto.

## Incidencias de producto

### INC-M04-G049-115 — CERRADA POR CAMBIO DE REQUISITO

La decisión de Análisis del 2026-10-31 acepta identificadores enteros; el producto no cambió. La incidencia V1 se cierra por cambio del oráculo, no por corrección del producto.

Sin incidencias de producto confirmadas.

## Problemas técnicos y análisis

Sin problemas técnicos observados. La causa raíz de las incidencias de producto no está confirmada.

## Cierre y rollback

DELETE RUN HTTP 200. Cierre de la transacción externa del sandbox confirmado: Transacción externa del sandbox cerrada; artefactos en disco y posible respaldo local fuera de alcance. Los artefactos en disco, posibles respaldos RF-73 y sesiones de login no se verificaron como eliminados.

## Revisión QA

Informe generado con los criterios vigentes del ejecutor; sin revisión QA posterior registrada.

## Evidencias

- preflight.json
- newman/newman-G049.json
- newman/newman-G049.html
- TC-M04-G049_reevaluacion_V2.md
- resultado.json

## Conclusión y acción

APROBADO. Qué sigue: cerrar la reevaluación V2 con su evidencia y revisión QA.
