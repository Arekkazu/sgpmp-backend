# TC-M04-G049 — RECHAZADO

## Decisión del caso

Caso agrupado TC-M04-G049 (RF-69); originales TC-M04-114, TC-M04-115, TC-M04-116 y TC-M04-117. Decisión: RECHAZADO. Motivo: TC-M04-115 incumple el formato UUID; los otros tres casos aprobaron.

| Caso | Comprobación | Decisión | Motivo breve |
|---|---|---|---|
| TC-M04-114 | API-114-01 | APROBADO | VERSION_REGISTRADA y VERSION_APROBADA de sistema con fuente id_proceso_rf71 (RF-69 Fase 6) |
| TC-M04-115 | API-115-01 | RECHAZADO | Identificadores observados: [58,59,60]; se exigen UUID distintos |
| TC-M04-116 | API-116-01 | APROBADO | Salida 1 completa e igual a la enviada |
| TC-M04-117 | API-117-01 | APROBADO | V3 refiere V2 y V1 se registró sin referencia |

RUN oficial: sí (registro QA OFICIAL, DELETE 200, rollback confirmado).

Qué falta: corrección de INC-M04-G049-115 por Desarrollo y reevaluación V2 autorizada de TC-M04-115.

## Detalle por caso

### TC-M04-114 — APROBADO

**Qué se hizo:** Se envió un modelo MODELO_ESPECIES_GRANDES por POST /prediccion/modelos como invocación interna de RF-71, con proceso 257bb6c0-ca88-4a05-bed7-42aa2ca5248b, F1 0.91 y recall de riesgo alto 0.93; se consultó su auditoría.
**Qué se esperaba:** Registro automático sin intervención humana, primero en EN_VALIDACION y luego con resultado automático; auditoría con VERSION_REGISTRADA y VERSION_APROBADA o VERSION_RECHAZADA, originadas por RF-71 (RF-69, líneas 1790, 2001-2004 y 2089-2095).
**Qué se observó:** POST HTTP 201 registró la versión 58; auditoría HTTP 200 mostró VERSION_APROBADA por SISTEMA, fuente 257bb6c0-ca88-4a05-bed7-42aa2ca5248b, estado APROBADO y VERSION_REGISTRADA por SISTEMA, fuente 257bb6c0-ca88-4a05-bed7-42aa2ca5248b, estado APROBADO.
**Por qué APROBADO:** Los dos eventos de sistema están vinculados al proceso RF-71 y acreditan registro y aprobación automáticos; el estado APROBADO del evento de registro es una foto final, no prueba de una transición omitida.

### TC-M04-115 — RECHAZADO

**Qué se hizo:** Se enviaron 3 versiones MODELO_ESPECIES_GRANDES desde procesos RF-71 257bb6c0-ca88-4a05-bed7-42aa2ca5248b, abb772f2-99ac-4435-afc0-9dd01869a6a1, a7564c85-2ab7-426c-9d25-4acb0c883f41, se compararon sus identificadores y se consultó la primera por GET.
**Qué se esperaba:** Tres identificadores UUID distintos para las tres versiones (RF-69, líneas 1794, 2001 y 2207).
**Qué se observó:** Los registros devolvieron HTTP 201 e identificador 58; HTTP 201 e identificador 59; HTTP 201 e identificador 60; la consulta de la primera versión devolvió HTTP 200 e identificador 58.
**Por qué RECHAZADO:** Se incumplió el criterio: Identificadores observados: [58,59,60]; se exigen UUID distintos. Incidencia INC-M04-G049-115.

### TC-M04-116 — APROBADO

**Qué se hizo:** Se envió el modelo MODELO_ESPECIES_GRANDES con proceso 257bb6c0-ca88-4a05-bed7-42aa2ca5248b, F1 0.91, recall alto 0.93, precisión 0.92, accuracy 0.94, ROC AUC 0.95, hashes de dataset 8d45c09b8b3048cb154542532ee9b1295078367ebbcf23ed25afaa60e5b46d88 y artefacto 46f971b933a3a104fedaa6058f6d1188b6ad97dc1ac9a9642d59df8518a1e470, fecha 2026-10-26T17:01:45.674Z; se leyó la versión 58 por GET.
**Qué se esperaba:** Persistencia fiel de todos los campos de Salida 1, incluidas métricas, hashes, fechas, origen RF-71 y notas de validación nulas hasta la revisión clínica (RF-69, líneas 2204-2223; formato UUID evaluado en TC-M04-115).
**Qué se observó:** GET /prediccion/modelos/58 respondió HTTP 200: estado APROBADO, F1 0.9100, recall alto 0.9300, precisión 0.9200, accuracy 0.9400, ROC AUC 0.9500, notas de validación nulas; demás campos y valores en la tabla de Salida 1.
**Por qué APROBADO:** Los campos de Salida 1 y sus valores coinciden con lo enviado, las fechas están presentes y las notas siguen nulas; el formato del identificador se decide en TC-M04-115.

### TC-M04-117 — APROBADO

**Qué se hizo:** Se registró V1 sin referencia, después V2 59 y V3 con referencia a V2; se consultaron V1 y V3 por GET usando los procesos RF-71 257bb6c0-ca88-4a05-bed7-42aa2ca5248b y a7564c85-2ab7-426c-9d25-4acb0c883f41.
**Qué se esperaba:** El registro sin version_referencia procede; cuando se envía, la versión anterior existe y la relación queda consultable (RF-69, línea 1965 y fase de recepción, líneas 1972-1985).
**Qué se observó:** V1 58 se registró sin referencia; V2 59 y V3 60 devolvieron HTTP 201 y 201; GET V3 HTTP 200 devolvió referencia 59.
**Por qué APROBADO:** V1 se registró sin referencia y V3 expone en GET la misma referencia enviada para V2; el formato UUID de esa referencia se decide en TC-M04-115.

## Identificación

RF-69 v2.1; versión V1; RUN RUN-G049-V1-20261027-170142; ambiente TEST; autorización AUT-G049-V1-20261027; código de referencia origin/test daefc3a5 (despliegue no verificado); Newman 6.2.2; Cypress no requerido, 0 ejecuciones.

## Esperado vs observado por caso

### TC-M04-114 · API-114-01

Esperado: VERSION_REGISTRADA (Fase 1, sistema, fuente id_proceso_rf71) y VERSION_APROBADA o VERSION_RECHAZADA (Fase 3, sistema). Observado para id_referencia 58:

| Evento | Actor | id_usuario | id_sistema | Estado del payload |
|---|---|---|---|---|
| VERSION_APROBADA | SISTEMA | nulo | 257bb6c0-ca88-4a05-bed7-42aa2ca5248b | APROBADO |
| VERSION_REGISTRADA | SISTEMA | nulo | 257bb6c0-ca88-4a05-bed7-42aa2ca5248b | APROBADO |

Decisión: APROBADO. VERSION_REGISTRADA y VERSION_APROBADA de sistema con fuente id_proceso_rf71 (RF-69 Fase 6)

### TC-M04-115 · API-115-01

Esperado: tres UUID distintos. Observado: POST 201 → 58; 201 → 59; 201 → 60; GET /prediccion/modelos/58 HTTP 200 devuelve id_version_modelo 58. Decisión: RECHAZADO.

### TC-M04-116 · API-116-01

Esperado: campos de Salida 1 presentes y fieles, con notas_validacion nulo. La comprobación de formato UUID corresponde a TC-M04-115.

| Campo | Enviado / exigido | GET V1 observado |
|---|---|---|
| id_version | UUID (formato evaluado en TC-M04-115) | 58 |
| tipo_modelo | MODELO_ESPECIES_GRANDES | MODELO_ESPECIES_GRANDES |
| estado | APROBADO automático | APROBADO |
| f1_score_global | 0.91 | 0.9100 |
| recall_clase_riesgo_alto | 0.93 | 0.9300 |
| precision_global | 0.92 | 0.9200 |
| accuracy | 0.94 | 0.9400 |
| roc_auc_score | 0.95 | 0.9500 |
| recall_por_clase | {"riesgo_alto":0.93,"riesgo_bajo":0.92} | {"riesgo_alto":0.93,"riesgo_bajo":0.92} |
| matriz_confusion | [[9,1],[1,9]] | [[9,1],[1,9]] |
| dataset_entrenamiento_hash | 8d45c09b8b3048cb154542532ee9b1295078367ebbcf23ed25afaa60e5b46d88 | 8d45c09b8b3048cb154542532ee9b1295078367ebbcf23ed25afaa60e5b46d88 |
| hash_artefacto_modelo | 46f971b933a3a104fedaa6058f6d1188b6ad97dc1ac9a9642d59df8518a1e470 | 46f971b933a3a104fedaa6058f6d1188b6ad97dc1ac9a9642d59df8518a1e470 |
| fecha_entrenamiento | 2026-10-26T17:01:45.674Z | 2026-10-26T17:01:45.674000Z |
| timestamp_registro | fecha válida | 2026-10-27T17:01:46.029224Z |
| id_proceso_rf71 | 257bb6c0-ca88-4a05-bed7-42aa2ca5248b | 257bb6c0-ca88-4a05-bed7-42aa2ca5248b |
| notas_validacion | nulo | nulo |

Decisión: APROBADO. Salida 1 completa e igual a la enviada

### TC-M04-117 · API-117-01

Esperado: V1 sin referencia y V3 con version_referencia de V2, consultable. Observado: V1 sin referencia true; V2 id 59; V3 version_referencia 59. Decisión: APROBADO.

## Observaciones

- VERSION_REGISTRADA: payload_evento de VERSION_REGISTRADA refleja APROBADO; es una foto del estado final, no la transición. El historial de transiciones no se expone por API pública.
- El tipo MODELO_ESPECIES_GRANDES fue aceptado en los tres POST.
- Tres artefactos ONNX de 84 bytes quedaron fuera del rollback de BD.

## Incidencias de producto

### INC-M04-G049-115 — El identificador de versión de modelo es un entero secuencial y no un UUID

- **Caso y equipo inicial:** TC-M04-115; Desarrollo. La primera discrepancia comprobada está en la respuesta del API público; se deriva a Desarrollo sin atribuir causa raíz.
- **Severidad y certeza:** MEDIA, CONFIRMADA. El registro, la unicidad local y las consultas funcionan; la desviación del contrato afecta trazabilidad e interoperabilidad: identificadores secuenciales predecibles y enumerables, no únicos fuera de la base de datos. No bloquea el flujo.
- **Requisito:** RF-69 línea 1794: “identificado de forma única mediante un id_version (UUID)”; Salida 1, línea 2207: “id_version (UUID)”; Entradas, línea 1965: “version_referencia | UUID (opcional)”
- **Precondiciones:** RUN autorizado, clave interna RF-71 válida, artefacto ONNX válido, metadatos completos y tipo MODELO_ESPECIES_GRANDES.
- **Pasos reproducibles:**

1. Enviar tres POST /prediccion/modelos multipart con X-RF71-Internal-Key y procesos RF-71 distintos.
2. Registrar los tres identificadores devueltos y usar el segundo como version_referencia del tercero.
3. Consultar GET /prediccion/modelos/{id} para la primera y la tercera versión; contrastar id y version_referencia.

- **Esperado:** Tres UUID distintos para id_version; version_referencia de V3 es el UUID de V2.
- **Obtenido:** POST HTTP 201: id_version_modelo 58; HTTP 201: id_version_modelo 59; HTTP 201: id_version_modelo 60; GET /prediccion/modelos/58 HTTP 200 devuelve id_version_modelo 58; V3 version_referencia 59 (number).
- **Evidencia:** newman/newman-G049.json; resultado.json; RUN-G049-V1-20261027-170142
- **Análisis e hipótesis:** El DTO y el schema tipan el identificador como entero (registrar_version_modelo_dto.py:48; version_modelo_schema.py:14,26). Clave autoincremental probable; causa raíz no confirmada.
- **Impacto:** Los consumidores que esperan UUID en version_referencia, correlación con RF-71/RF-73 y distribución RF-70 pueden recibir enteros; los identificadores expuestos son enumerables.
- **Para cerrarla:** Exponer id_version y version_referencia como UUID en respuesta, ruta GET y entrada; reevaluar TC-M04-115 en V2 autorizada.

## Problemas técnicos y análisis

Sin problemas técnicos observados. La causa raíz de las incidencias de producto no está confirmada.

## Cierre y rollback

DELETE RUN HTTP 200. Cierre de la transacción externa del sandbox confirmado: Transacción externa del sandbox cerrada; artefactos en disco y posible respaldo local fuera de alcance. Los artefactos en disco, posibles respaldos RF-73 y sesiones de login no se verificaron como eliminados.

## Revisión QA

Fecha 2026-10-27; realizada por orquestador QA; autorizada por responsable QA. La auditoria TEST acredita VERSION_REGISTRADA y VERSION_APROBADA de sistema con origen id_proceso_rf71; el payload de VERSION_REGISTRADA es una foto del estado final. Cambios: TC-M04-114 RECHAZADO→APROBADO; INC-M04-G049-114 retirada; INC-M04-G049-115 reescrita.

## Evidencias

- preflight.json
- newman/newman-G049.json
- newman/newman-G049.html
- TC-M04-G049_resultado.md
- resultado.json

## Conclusión y acción

RECHAZADO. Qué falta: corrección de INC-M04-G049-115 por Desarrollo y reevaluación V2 autorizada de TC-M04-115.
