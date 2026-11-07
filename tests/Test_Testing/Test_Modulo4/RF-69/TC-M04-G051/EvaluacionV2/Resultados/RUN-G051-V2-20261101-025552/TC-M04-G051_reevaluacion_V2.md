# TC-M04-G051 — reevaluación V2 — APROBADO

## Identificación

Grupo G051; casos TC-M04-121, TC-M04-122, TC-M04-123, TC-M04-124, TC-M04-125, TC-M04-126, TC-M04-127; RF-69 v2.1; V2; RUN RUN-G051-V2-20261101-025552; operación REINTENTAR; intento 6; ambiente TEST; autorización AUT-G051-V2-R3-20261101. Issue #820 / PR #864: corrección informada por Desarrollo; despliegue en TEST no verificado antes del RUN. Commit de despliegue: no verificado por esta orden, que excluye Git. Newman 6.2.2; Cypress no aplica, pues los siete casos exigen API. Versión anterior: 1.

## Resumen y comparación V1 → V2

V1: [RUN-G051-V1-20261028-032158](../../../Resultados/RUN-G051-V1-20261028-032158/TC-M04-G051_resultado.md). Decisión V2: APROBADO.

| Caso | Comprobación | V1 | V2 | Propósito |
|---|---|---|---|---|
| TC-M04-121 | API-121-01 | APROBADO | APROBADO | Regresión |
| TC-M04-122 | API-122-01 | RECHAZADO | APROBADO | Corrección informada |
| TC-M04-123 | API-123-01 | RECHAZADO | APROBADO | Corrección informada |
| TC-M04-124 | API-124-01 | APROBADO | APROBADO | Regresión |
| TC-M04-125 | API-125-01 | APROBADO | APROBADO | Regresión |
| TC-M04-126 | API-126-01 | APROBADO | APROBADO | Regresión |
| TC-M04-127 | API-127-01 | RECHAZADO | APROBADO | Corrección informada |

INC-M04-G051-122: CORREGIDA. INC-M04-G051-VAL400: CORREGIDA; requiere aprobación conjunta de 123 y 127. Estas etiquetas describen el resultado de V2 y no cambian los veredictos de V1.

## Detalle por caso

### TC-M04-121 — APROBADO

**Qué se hizo:** 2 solicitudes POST de registro; se consultó el catálogo, se consultaron los listados inicial y final y se consultaron las versiones creadas por ID. Comprobación de regresión.

**Qué se esperaba:** Resultado esperado del caso: “Con variables existentes procede; con una inexistente HTTP 422 indicando el campo”. RF-69, entrada compatibilidad_variables (línea 1966) y fase 2 (líneas 2016-2017).

| Solicitud | Esperado | Observado | Evaluación |
|---|---|---|---|
| variables existentes / ayer | Registro HTTP 201 con ID y GET 200 | HTTP 201; código sin error; sin mensaje de error; sin campos detallados; ID 141; presente en listado final; GET 200; duración POST 549 ms (newman_responseTime) | APROBADO |
| variable inexistente | HTTP 422, sin ID ni versión en listado | HTTP 422; código VARIABLE_I3P1_NO_ENCONTRADA; Las siguientes variables no existen en el catálogo I3P-1: [17].; campos compatibilidad_variables: Las siguientes variables no existen en el catálogo I3P-1: [17].; ID ausente; ausente en listado final; duración POST 210 ms (newman_responseTime) | APROBADO |

**Qué se observó:** variables existentes / ayer: HTTP 201; código sin error; sin mensaje de error; sin campos detallados; ID 141; presente en listado final; GET 200; duración POST 549 ms (newman_responseTime) variable inexistente: HTTP 422; código VARIABLE_I3P1_NO_ENCONTRADA; Las siguientes variables no existen en el catálogo I3P-1: [17].; campos compatibilidad_variables: Las siguientes variables no existen en el catálogo I3P-1: [17].; ID ausente; ausente en listado final; duración POST 210 ms (newman_responseTime)

**Por qué APROBADO:** 2 solicitudes cumplen el oráculo.

### TC-M04-122 — APROBADO

**Qué se hizo:** 3 solicitudes POST de registro; se consultó el catálogo, se consultaron los listados inicial y final y se consultaron las versiones creadas por ID. La solicitud válida de ayer se comparte con TC-M04-121. Comprobación de la corrección informada.

**Qué se esperaba:** Resultado esperado del caso: “Las dos primeras se registran; la futura HTTP 422 sin crear la versión”. RF-69, fecha_entrenamiento (línea 1964) y E2 (líneas 2142-2151).

| Solicitud | Esperado | Observado | Evaluación |
|---|---|---|---|
| variables existentes / ayer | Registro HTTP 201 con ID y GET 200 | HTTP 201; código sin error; sin mensaje de error; sin campos detallados; ID 141; presente en listado final; GET 200; duración POST 549 ms (newman_responseTime) | APROBADO |
| ahora menos 10 s | Registro HTTP 201 con ID y GET 200 | HTTP 201; código sin error; sin mensaje de error; sin campos detallados; ID 142; presente en listado final; GET 200; duración POST 355 ms (newman_responseTime) | APROBADO |
| mañana | HTTP 422, sin ID ni versión en listado, fecha_entrenamiento | HTTP 422; código FECHA_ENTRENAMIENTO_FUTURA; La fecha_entrenamiento no puede ser una fecha futura.; campos fecha_entrenamiento: La fecha_entrenamiento no puede ser una fecha futura.; ID ausente; ausente en listado final; duración POST 478 ms (newman_responseTime) | APROBADO |

**Qué se observó:** variables existentes / ayer: HTTP 201; código sin error; sin mensaje de error; sin campos detallados; ID 141; presente en listado final; GET 200; duración POST 549 ms (newman_responseTime) ahora menos 10 s: HTTP 201; código sin error; sin mensaje de error; sin campos detallados; ID 142; presente en listado final; GET 200; duración POST 355 ms (newman_responseTime) mañana: HTTP 422; código FECHA_ENTRENAMIENTO_FUTURA; La fecha_entrenamiento no puede ser una fecha futura.; campos fecha_entrenamiento: La fecha_entrenamiento no puede ser una fecha futura.; ID ausente; ausente en listado final; duración POST 478 ms (newman_responseTime)

**Por qué APROBADO:** 3 solicitudes cumplen el oráculo.

### TC-M04-123 — APROBADO

**Qué se hizo:** 3 solicitudes POST de registro; se consultó el catálogo, se consultaron los listados inicial y final y no hubo GET de versión por ID. Comprobación de la corrección informada.

**Qué se esperaba:** Resultado esperado del caso: “Las tres HTTP 422 indicando el catálogo admitido”. RF-69, tipo_modelo (línea 1959), actualización RFC-009 (línea 1784) y RF-65 (líneas 381-390).

| Solicitud | Esperado | Observado | Evaluación |
|---|---|---|---|
| tipo inexistente | HTTP 422, sin ID ni versión en listado, tipo_modelo y seis tipos admitidos | HTTP 422; código TIPO_MODELO_INVALIDO; tipo_modelo es obligatorio y debe ser uno de: ['MODELO_ACUICULTURA', 'MODELO_AVES', 'MODELO_ESPECIES_GRANDES', 'MODELO_ESPECIES_MEDIANAS', 'MODELO_PORCINOS', 'MODELO_RIESGO_CONTAGIO'].; campos tipo_modelo: tipo_modelo es obligatorio y debe ser uno de: ['MODELO_ACUICULTURA', 'MODELO_AVES', 'MODELO_ESPECIES_GRAN | APROBADO |
| tipo vacío | HTTP 422, sin ID ni versión en listado, tipo_modelo y seis tipos admitidos | HTTP 422; código TIPO_MODELO_INVALIDO; tipo_modelo es obligatorio y debe ser uno de: ['MODELO_ACUICULTURA', 'MODELO_AVES', 'MODELO_ESPECIES_GRANDES', 'MODELO_ESPECIES_MEDIANAS', 'MODELO_PORCINOS', 'MODELO_RIESGO_CONTAGIO'].; campos tipo_modelo: tipo_modelo es obligatorio y debe ser uno de: ['MODELO_ACUICULTURA', 'MODELO_AVES', 'MODELO_ESPECIES_GRAN | APROBADO |
| tipo eliminado RFC-009 | HTTP 422, sin ID ni versión en listado, tipo_modelo y seis tipos admitidos | HTTP 422; código TIPO_MODELO_INVALIDO; tipo_modelo es obligatorio y debe ser uno de: ['MODELO_ACUICULTURA', 'MODELO_AVES', 'MODELO_ESPECIES_GRANDES', 'MODELO_ESPECIES_MEDIANAS', 'MODELO_PORCINOS', 'MODELO_RIESGO_CONTAGIO'].; campos tipo_modelo: tipo_modelo es obligatorio y debe ser uno de: ['MODELO_ACUICULTURA', 'MODELO_AVES', 'MODELO_ESPECIES_GRAN | APROBADO |

**Qué se observó:** tipo inexistente: HTTP 422; código TIPO_MODELO_INVALIDO; tipo_modelo es obligatorio y debe ser uno de: ['MODELO_ACUICULTURA', 'MODELO_AVES', 'MODELO_ESPECIES_GRANDES', 'MODELO_ESPECIES_MEDIANAS', 'MODELO_PORCINOS', 'MODELO_RIESGO_CONTAGIO'].; campos tipo_modelo: tipo_modelo es obligatorio y debe ser uno de: ['MODELO_ACUICULTURA', 'MODELO_AVES', 'MODELO_ESPECIES_GRAN tipo vacío: HTTP 422; código TIPO_MODELO_INVALIDO; tipo_modelo es obligatorio y debe ser uno de: ['MODELO_ACUICULTURA', 'MODELO_AVES', 'MODELO_ESPECIES_GRANDES', 'MODELO_ESPECIES_MEDIANAS', 'MODELO_PORCINOS', 'MODELO_RIESGO_CONTAGIO'].; campos tipo_modelo: tipo_modelo es obligatorio y debe ser uno de: ['MODELO_ACUICULTURA', 'MODELO_AVES', 'MODELO_ESPECIES_GRAN tipo eliminado RFC-009: HTTP 422; código TIPO_MODELO_INVALIDO; tipo_modelo es obligatorio y debe ser uno de: ['MODELO_ACUICULTURA', 'MODELO_AVES', 'MODELO_ESPECIES_GRANDES', 'MODELO_ESPECIES_MEDIANAS', 'MODELO_PORCINOS', 'MODELO_RIESGO_CONTAGIO'].; campos tipo_modelo: tipo_modelo es obligatorio y debe ser uno de: ['MODELO_ACUICULTURA', 'MODELO_AVES', 'MODELO_ESPECIES_GRAN

**Por qué APROBADO:** 3 solicitudes cumplen el oráculo.

### TC-M04-124 — APROBADO

**Qué se hizo:** 3 solicitudes POST de registro; se consultó el catálogo, se consultaron los listados inicial y final y no hubo GET de versión por ID. Comprobación de regresión.

**Qué se esperaba:** Resultado esperado del caso: “Las tres HTTP 422 identificando el campo ausente”. RF-69, métricas (línea 1962), fase 2 y E2 (líneas 2142-2151).

| Solicitud | Esperado | Observado | Evaluación |
|---|---|---|---|
| sin f1_score_global | HTTP 422, sin ID ni versión en listado | HTTP 422; código METRICAS_INCOMPLETAS; Los metadatos del modelo son inválidos o incompletos: faltan ['f1_score_global'].; campos metricas_validacion: Los metadatos del modelo son inválidos o incompletos: faltan ['f1_score_global'].; ID ausente; ausente en listado final; duración POST 473 ms (newman_responseTime) | APROBADO |
| sin recall_clase_riesgo_alto | HTTP 422, sin ID ni versión en listado | HTTP 422; código METRICAS_INCOMPLETAS; Los metadatos del modelo son inválidos o incompletos: faltan ['recall_clase_riesgo_alto'].; campos metricas_validacion: Los metadatos del modelo son inválidos o incompletos: faltan ['recall_clase_riesgo_alto'].; ID ausente; ausente en listado final; duración POST 419 ms (newman_responseTime) | APROBADO |
| sin matriz_confusion | HTTP 422, sin ID ni versión en listado | HTTP 422; código METRICAS_INCOMPLETAS; Los metadatos del modelo son inválidos o incompletos: faltan ['matriz_confusion'].; campos metricas_validacion: Los metadatos del modelo son inválidos o incompletos: faltan ['matriz_confusion'].; ID ausente; ausente en listado final; duración POST 212 ms (newman_responseTime) | APROBADO |

**Qué se observó:** sin f1_score_global: HTTP 422; código METRICAS_INCOMPLETAS; Los metadatos del modelo son inválidos o incompletos: faltan ['f1_score_global'].; campos metricas_validacion: Los metadatos del modelo son inválidos o incompletos: faltan ['f1_score_global'].; ID ausente; ausente en listado final; duración POST 473 ms (newman_responseTime) sin recall_clase_riesgo_alto: HTTP 422; código METRICAS_INCOMPLETAS; Los metadatos del modelo son inválidos o incompletos: faltan ['recall_clase_riesgo_alto'].; campos metricas_validacion: Los metadatos del modelo son inválidos o incompletos: faltan ['recall_clase_riesgo_alto'].; ID ausente; ausente en listado final; duración POST 419 ms (newman_responseTime) sin matriz_confusion: HTTP 422; código METRICAS_INCOMPLETAS; Los metadatos del modelo son inválidos o incompletos: faltan ['matriz_confusion'].; campos metricas_validacion: Los metadatos del modelo son inválidos o incompletos: faltan ['matriz_confusion'].; ID ausente; ausente en listado final; duración POST 212 ms (newman_responseTime)

**Por qué APROBADO:** 3 solicitudes cumplen el oráculo.

### TC-M04-125 — APROBADO

**Qué se hizo:** 4 solicitudes POST de registro; se consultó el catálogo, se consultaron los listados inicial y final y se consultaron las versiones creadas por ID. Comprobación de regresión.

**Qué se esperaba:** Resultado esperado del caso: “0.0 y 1.0 se aceptan; -0.01 y 1.01 HTTP 422 indicando el rango”. RF-69, métricas (línea 1962), fase 2 y E2 (líneas 2142-2151).

| Solicitud | Esperado | Observado | Evaluación |
|---|---|---|---|
| f1=0.0 | Registro HTTP 200 o 201 con ID y GET 200 | HTTP 200; código sin error; sin mensaje de error; sin campos detallados; ID 143; presente en listado final; GET 200; duración POST 51376 ms (newman_responseTime) | APROBADO |
| f1=1.0 | Registro HTTP 201 con ID y GET 200 | HTTP 201; código sin error; sin mensaje de error; sin campos detallados; ID 144; presente en listado final; GET 200; duración POST 560 ms (newman_responseTime) | APROBADO |
| f1=-0.01 | HTTP 422, sin ID ni versión en listado | HTTP 422; código METRICA_FUERA_DE_RANGO; El campo f1_score_global=-0.01 debe estar en el rango [0.0, 1.0].; campos metricas_validacion: El campo f1_score_global=-0.01 debe estar en el rango [0.0, 1.0].; ID ausente; ausente en listado final; duración POST 559 ms (newman_responseTime) | APROBADO |
| f1=1.01 | HTTP 422, sin ID ni versión en listado | HTTP 422; código METRICA_FUERA_DE_RANGO; El campo f1_score_global=1.01 debe estar en el rango [0.0, 1.0].; campos metricas_validacion: El campo f1_score_global=1.01 debe estar en el rango [0.0, 1.0].; ID ausente; ausente en listado final; duración POST 576 ms (newman_responseTime) | APROBADO |

**Qué se observó:** f1=0.0: HTTP 200; código sin error; sin mensaje de error; sin campos detallados; ID 143; presente en listado final; GET 200; duración POST 51376 ms (newman_responseTime) f1=1.0: HTTP 201; código sin error; sin mensaje de error; sin campos detallados; ID 144; presente en listado final; GET 200; duración POST 560 ms (newman_responseTime) f1=-0.01: HTTP 422; código METRICA_FUERA_DE_RANGO; El campo f1_score_global=-0.01 debe estar en el rango [0.0, 1.0].; campos metricas_validacion: El campo f1_score_global=-0.01 debe estar en el rango [0.0, 1.0].; ID ausente; ausente en listado final; duración POST 559 ms (newman_responseTime) f1=1.01: HTTP 422; código METRICA_FUERA_DE_RANGO; El campo f1_score_global=1.01 debe estar en el rango [0.0, 1.0].; campos metricas_validacion: El campo f1_score_global=1.01 debe estar en el rango [0.0, 1.0].; ID ausente; ausente en listado final; duración POST 576 ms (newman_responseTime)

**Por qué APROBADO:** 4 solicitudes cumplen el oráculo.

### TC-M04-126 — APROBADO

**Qué se hizo:** 6 solicitudes POST de registro; se consultó el catálogo, se consultaron los listados inicial y final y no hubo GET de versión por ID. Comprobación de regresión.

**Qué se esperaba:** Resultado esperado del caso: “Las seis HTTP 422 identificando el hash afectado”. RF-69, hash del artefacto (línea 1961), hash del dataset (línea 1963), fase 2 y E2 (líneas 2142-2151).

| Solicitud | Esperado | Observado | Evaluación |
|---|---|---|---|
| hash_artefacto_sha256: 63 caracteres | HTTP 422, sin ID ni versión en listado | HTTP 422; código HASH_SHA256_INVALIDO; hash_artefacto_sha256 debe ser un hash SHA-256 de 64 caracteres hexadecimales.; campos hash_artefacto_sha256: hash_artefacto_sha256 debe ser un hash SHA-256 de 64 caracteres hexadecimales.; ID ausente; ausente en listado final; duración POST 206 ms (newman_responseTime) | APROBADO |
| hash_artefacto_sha256: 65 caracteres | HTTP 422, sin ID ni versión en listado | HTTP 422; código HASH_SHA256_INVALIDO; hash_artefacto_sha256 debe ser un hash SHA-256 de 64 caracteres hexadecimales.; campos hash_artefacto_sha256: hash_artefacto_sha256 debe ser un hash SHA-256 de 64 caracteres hexadecimales.; ID ausente; ausente en listado final; duración POST 204 ms (newman_responseTime) | APROBADO |
| hash_artefacto_sha256: 64 no hexadecimal | HTTP 422, sin ID ni versión en listado | HTTP 422; código HASH_SHA256_INVALIDO; hash_artefacto_sha256 debe ser un hash SHA-256 de 64 caracteres hexadecimales.; campos hash_artefacto_sha256: hash_artefacto_sha256 debe ser un hash SHA-256 de 64 caracteres hexadecimales.; ID ausente; ausente en listado final; duración POST 205 ms (newman_responseTime) | APROBADO |
| dataset_entrenamiento_hash: 63 caracteres | HTTP 422, sin ID ni versión en listado | HTTP 422; código HASH_SHA256_INVALIDO; dataset_entrenamiento_hash debe ser un hash SHA-256 de 64 caracteres hexadecimales.; campos dataset_entrenamiento_hash: dataset_entrenamiento_hash debe ser un hash SHA-256 de 64 caracteres hexadecimales.; ID ausente; ausente en listado final; duración POST 215 ms (newman_responseTime) | APROBADO |
| dataset_entrenamiento_hash: 65 caracteres | HTTP 422, sin ID ni versión en listado | HTTP 422; código HASH_SHA256_INVALIDO; dataset_entrenamiento_hash debe ser un hash SHA-256 de 64 caracteres hexadecimales.; campos dataset_entrenamiento_hash: dataset_entrenamiento_hash debe ser un hash SHA-256 de 64 caracteres hexadecimales.; ID ausente; ausente en listado final; duración POST 203 ms (newman_responseTime) | APROBADO |
| dataset_entrenamiento_hash: 64 no hexadecimal | HTTP 422, sin ID ni versión en listado | HTTP 422; código HASH_SHA256_INVALIDO; dataset_entrenamiento_hash debe ser un hash SHA-256 de 64 caracteres hexadecimales.; campos dataset_entrenamiento_hash: dataset_entrenamiento_hash debe ser un hash SHA-256 de 64 caracteres hexadecimales.; ID ausente; ausente en listado final; duración POST 207 ms (newman_responseTime) | APROBADO |

**Qué se observó:** hash_artefacto_sha256: 63 caracteres: HTTP 422; código HASH_SHA256_INVALIDO; hash_artefacto_sha256 debe ser un hash SHA-256 de 64 caracteres hexadecimales.; campos hash_artefacto_sha256: hash_artefacto_sha256 debe ser un hash SHA-256 de 64 caracteres hexadecimales.; ID ausente; ausente en listado final; duración POST 206 ms (newman_responseTime) hash_artefacto_sha256: 65 caracteres: HTTP 422; código HASH_SHA256_INVALIDO; hash_artefacto_sha256 debe ser un hash SHA-256 de 64 caracteres hexadecimales.; campos hash_artefacto_sha256: hash_artefacto_sha256 debe ser un hash SHA-256 de 64 caracteres hexadecimales.; ID ausente; ausente en listado final; duración POST 204 ms (newman_responseTime) hash_artefacto_sha256: 64 no hexadecimal: HTTP 422; código HASH_SHA256_INVALIDO; hash_artefacto_sha256 debe ser un hash SHA-256 de 64 caracteres hexadecimales.; campos hash_artefacto_sha256: hash_artefacto_sha256 debe ser un hash SHA-256 de 64 caracteres hexadecimales.; ID ausente; ausente en listado final; duración POST 205 ms (newman_responseTime) dataset_entrenamiento_hash: 63 caracteres: HTTP 422; código HASH_SHA256_INVALIDO; dataset_entrenamiento_hash debe ser un hash SHA-256 de 64 caracteres hexadecimales.; campos dataset_entrenamiento_hash: dataset_entrenamiento_hash debe ser un hash SHA-256 de 64 caracteres hexadecimales.; ID ausente; ausente en listado final; duración POST 215 ms (newman_responseTime) dataset_entrenamiento_hash: 65 caracteres: HTTP 422; código HASH_SHA256_INVALIDO; dataset_entrenamiento_hash debe ser un hash SHA-256 de 64 caracteres hexadecimales.; campos dataset_entrenamiento_hash: dataset_entrenamiento_hash debe ser un hash SHA-256 de 64 caracteres hexadecimales.; ID ausente; ausente en listado final; duración POST 203 ms (newman_responseTime) dataset_entrenamiento_hash: 64 no hexadecimal: HTTP 422; código HASH_SHA256_INVALIDO; dataset_entrenamiento_hash debe ser un hash SHA-256 de 64 caracteres hexadecimales.; campos dataset_entrenamiento_hash: dataset_entrenamiento_hash debe ser un hash SHA-256 de 64 caracteres hexadecimales.; ID ausente; ausente en listado final; duración POST 207 ms (newman_responseTime)

**Por qué APROBADO:** 6 solicitudes cumplen el oráculo.

### TC-M04-127 — APROBADO

**Qué se hizo:** 3 solicitudes POST de registro; se consultó el catálogo, se consultaron los listados inicial y final y no hubo GET de versión por ID. Comprobación de la corrección informada.

**Qué se esperaba:** Resultado esperado del caso: “Las tres HTTP 422 sin crear la versión”. RF-69, restricción 8 (líneas 1893-1897) y E2 (líneas 2142-2151): identificar cada hash omitido.

| Solicitud | Esperado | Observado | Evaluación |
|---|---|---|---|
| sin hash_artefacto_sha256 | HTTP 422, sin ID ni versión en listado, hash_artefacto_sha256 | HTTP 422; código VAL_ENTRADA; Errores de validacion en la solicitud; campos hash_artefacto_sha256: Este campo es obligatorio.; ID ausente; ausente en listado final; duración POST 209 ms (newman_responseTime) | APROBADO |
| sin dataset_entrenamiento_hash | HTTP 422, sin ID ni versión en listado, dataset_entrenamiento_hash | HTTP 422; código VAL_ENTRADA; Errores de validacion en la solicitud; campos dataset_entrenamiento_hash: Este campo es obligatorio.; ID ausente; ausente en listado final; duración POST 212 ms (newman_responseTime) | APROBADO |
| sin ambos hashes | HTTP 422, sin ID ni versión en listado, hash_artefacto_sha256 y dataset_entrenamiento_hash | HTTP 422; código VAL_ENTRADA; Errores de validacion en la solicitud; campos hash_artefacto_sha256: Este campo es obligatorio.; dataset_entrenamiento_hash: Este campo es obligatorio.; ID ausente; ausente en listado final; duración POST 207 ms (newman_responseTime) | APROBADO |

**Qué se observó:** sin hash_artefacto_sha256: HTTP 422; código VAL_ENTRADA; Errores de validacion en la solicitud; campos hash_artefacto_sha256: Este campo es obligatorio.; ID ausente; ausente en listado final; duración POST 209 ms (newman_responseTime) sin dataset_entrenamiento_hash: HTTP 422; código VAL_ENTRADA; Errores de validacion en la solicitud; campos dataset_entrenamiento_hash: Este campo es obligatorio.; ID ausente; ausente en listado final; duración POST 212 ms (newman_responseTime) sin ambos hashes: HTTP 422; código VAL_ENTRADA; Errores de validacion en la solicitud; campos hash_artefacto_sha256: Este campo es obligatorio.; dataset_entrenamiento_hash: Este campo es obligatorio.; ID ausente; ausente en listado final; duración POST 207 ms (newman_responseTime)

**Por qué APROBADO:** 3 solicitudes cumplen el oráculo.

## Comprobaciones API y efectos

API-121-01 a API-127-01: 23 POST previstos. Fecha de servidor Sun, 01 Nov 2026 02:55:57 GMT; la variante “ahora” usa el reloj del cliente menos 10 segundos. Conteo inicial 1, final 5, delta 4, aceptados 4, rechazados con ID 0. La variante f1=0.0 creó una versión en estado RECHAZADO y puede enviar un aviso por correo; su entrega no se verificó. Antecedentes QA: RUN-G051-V2-20261101-022937 fue un intento técnico, exit 2; un POST f1=0.0 agotó 30 s, se registró y el ejecutor no concilió su id_proceso_rf71. El delta 4 frente a 3 respuestas aceptadas dejó los siete casos NO_CONCLUYENTE. RUN-G051-V2-20261101-024639 fue un reintento técnico detenido en PREFLIGHT_LOCAL por REEVALUACION_SIN_DECISION, sin peticiones a TEST ni cierre. Este parche usa 120 s para Newman, concilia el listado y admite REINTENTAR V2 con alcance válido; los antecedentes no son veredictos de producto. Los extractos saneados de [intento 1](api/antecedentes/intento-1.json) y [intento 2](api/antecedentes/intento-2.json), con [índice y SHA-256 de los originales](api/antecedentes/indice.json), quedan en este RUN oficial. Los dos RUN técnicos de origen fueron eliminados con autorización del responsable QA el 2026-11-01. Aceptados con respuesta 4; registrados por conciliación 0; delta 4. 

## Incidencias de producto

Sin incidencias de producto nuevas confirmadas.

## Problemas técnicos y análisis

Sin problemas técnicos observados en este RUN. Las respuestas públicas acreditan el comportamiento observado; el código local y el PR no prueban por sí solos la causa raíz ni el despliegue.

## Cierre y rollback

DELETE RUN HTTP 200. El sandbox respondió al cierre; la reversión de BD no se comprobó por consulta posterior. Los archivos residuales en MODELOS_STORAGE_PATH no se pueden verificar por esta API; si se requiere comprobarlos, correspondería a Implementación o DBA. Esto limita la comprobación de efectos persistentes y no cambia el veredicto de los casos. Tampoco se verificó la entrega de correo ni la eliminación de posibles respaldos RF-73.

## Evidencias

- preflight.json
- newman/newman-G051.json
- newman/newman-G051.html
- TC-M04-G051_reevaluacion_V2.md
- resultado.json

## Conclusión y acción

APROBADO. Registrar el cierre de las incidencias corregidas y conservar la evidencia del RUN.
