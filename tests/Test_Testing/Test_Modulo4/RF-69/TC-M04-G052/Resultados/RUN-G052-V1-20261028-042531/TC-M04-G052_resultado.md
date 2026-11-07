# TC-M04-G052 — APROBADO

## Decisión del caso

Caso agrupado TC-M04-G052 (RF-69), originales TC-M04-129, TC-M04-130, TC-M04-131, TC-M04-132, TC-M04-133, TC-M04-134. **Decisión: APROBADO.** La evaluación automática aplica f1 ≥ 0.80 y recall ≥ 0.85 de forma simultánea e inclusiva, informa el umbral incumplido y ningún usuario puede alterar el estado.

| Caso | Comprobación | Decisión | Motivo breve |
|---|---|---|---|
| TC-M04-129 | API-129-01 | APROBADO | 129: f1=0.91, recall=0.93, HTTP 201, id 82, APROBADO; auditoría VERSION_REGISTRADA + VERSION_APROBADA de SISTEMA |
| TC-M04-130 | API-130-01 | APROBADO | 130: f1=0.72, recall=0.95, HTTP 200, id 83, RECHAZADO |
| TC-M04-131 | API-131-01 | APROBADO | 131: f1=0.95, recall=0.7, HTTP 200, id 84, RECHAZADO |
| TC-M04-132 | API-132-01 | APROBADO | 132-a: f1=0.8, recall=0.85, HTTP 201, id 85, APROBADO; 132-b: f1=0.7999, recall=0.85, HTTP 200, id 86, RECHAZADO; 132-c: f1=0.8, recall=0.8499, HTTP 200, id 87, RECHAZADO; 132-d: f1=0.7999, recall=0.8499, HTTP 200, id 88, RECHAZADO |
| TC-M04-133 | API-133-01 | APROBADO | 130/id 83: f1=0.72<0.80; 131/id 84: recall=0.7<0.85; 132-b/id 86: f1=0.7999<0.80; 132-c/id 87: recall=0.8499<0.85; 132-d/id 88: f1=0.7999<0.80 y recall=0.8499<0.85 |
| TC-M04-134 | API-134-01 | APROBADO | 12 intentos; PATCH /notas 400, PUT 405, PATCH 405; 0 cambios de estado en GET posterior |

RUN oficial: sí (registro QA OFICIAL, intento 2; DELETE 200, rollback confirmado por sandbox). Qué falta: nada para este grupo; se deja una observación de rendimiento.

## Detalle por caso

### TC-M04-129 — APROBADO
**Qué se hizo:** Se registró por POST una versión de MODELO_ESPECIES_GRANDES con f1 0.91 y recall 0.93; se consultaron la versión 82 y su auditoría.
**Qué se esperaba:** RF-69, Fase 3 y CA-4 (líneas 2030-2043 y 2291-2295), exige aprobación automática al cumplir ambos umbrales; Fase 6 (líneas 2089-2099) exige historial automático.
**Qué se observó:** POST HTTP 201 y GET HTTP 200 para la versión 82, estado APROBADO y detalle de rechazo nulo; auditoría HTTP 200 con registro y aprobación atribuidos a SISTEMA.
**Por qué APROBADO:** f1 0.91 ≥ 0.80 y recall 0.93 ≥ 0.85; el estado y los dos eventos de auditoría acreditan la aprobación automática sin intervención humana.

### TC-M04-130 — APROBADO
**Qué se hizo:** Se registró por POST una versión con f1 0.72 y recall 0.95, y se consultó la versión 83 por GET.
**Qué se esperaba:** RF-69, E3 (líneas 2169-2175), exige HTTP 200, estado RECHAZADO, mensaje de umbrales no alcanzados y aviso al Veterinario cuando f1 es inferior a 0.80; Salida 2 (líneas 2225-2229) exige identificar el umbral incumplido.
**Qué se observó:** POST y GET HTTP 200; versión 83 en RECHAZADO, con detalle que indica f1 0.72 inferior a 0.80. El POST tardó 34.126 s; no hay traza pública de entrega del aviso.
**Por qué APROBADO:** La comprobación API acreditó el código, el estado y el umbral f1 exigidos. La entrega del aviso no quedó comprobada por esta API y la duración total del POST no aísla el tiempo de validación.

### TC-M04-131 — APROBADO
**Qué se hizo:** Se registró por POST una versión con f1 0.95 y recall 0.70, y se consultó la versión 84 por GET.
**Qué se esperaba:** RF-69, Fase 3 y CA-4 (líneas 2030-2043 y 2291-2295), exige cumplir simultáneamente f1 ≥ 0.80 y recall ≥ 0.85; E3 (líneas 2169-2175) exige rechazar la versión que incumpla uno de ellos.
**Qué se observó:** POST y GET HTTP 200; versión 84 en RECHAZADO, con detalle que indica recall 0.70 inferior a 0.85 aunque f1 fue 0.95. El POST tardó 32.774 s.
**Por qué APROBADO:** La versión quedó RECHAZADO por el recall insuficiente pese al f1 conforme, tal como exige la regla simultánea; la duración total incluye pasos ajenos a la validación medida por RNF-01.

### TC-M04-132 — APROBADO
**Qué se hizo:** Se registraron y consultaron cuatro versiones de frontera: 85 con f1 0.80 y recall 0.85; 86 con 0.7999 y 0.85; 87 con 0.80 y 0.8499; 88 con 0.7999 y 0.8499.
**Qué se esperaba:** RF-69, Restricción 4 y CA-4 (líneas 1878-1882 y 2291-2295), fija umbrales inclusivos: solo la combinación 0.80/0.85 aprueba; las otras tres se rechazan.
**Qué se observó:** Versión 85: POST 201, GET 200, APROBADO. Versiones 86, 87 y 88: POST y GET 200, RECHAZADO; sus detalles señalan f1, recall y ambos, respectivamente. Sus POST tardaron 33.424, 18.133 y 5.859 s.
**Por qué APROBADO:** La igualdad exacta de ambos umbrales aprobó la versión 85 y cada valor inferior rechazó la versión correspondiente; los GET confirmaron los cuatro estados y detalles.

### TC-M04-133 — APROBADO
**Qué se hizo:** Se revisaron por GET los detalles de las cinco versiones rechazadas: 83, 84, 86, 87 y 88, procedentes de los casos 130, 131 y 132.
**Qué se esperaba:** RF-69, Salida 2 (líneas 2225-2229) y Fase 4 (líneas 2045-2059), exige que cada rechazo describa el umbral concreto no alcanzado.
**Qué se observó:** GET HTTP 200 para las cinco: 83 indicó f1 0.72; 84, recall 0.70; 86, f1 0.7999; 87, recall 0.8499; 88, f1 0.7999 y recall 0.8499, todos frente a los umbrales 0.80 y 0.85 correspondientes.
**Por qué APROBADO:** Los cinco detalles identificaron correctamente f1, recall o ambos según el valor inferior observado; no hubo versiones rechazadas sin evidencia.

### TC-M04-134 — APROBADO
**Qué se hizo:** Administrador y Veterinario intentaron cambiar APROBADO a RECHAZADO en la versión 82 y RECHAZADO a APROBADO en la 83 mediante PATCH de notas, PUT y PATCH directos; se hizo GET tras cada uno de los 12 intentos.
**Qué se esperaba:** RF-69, CA-4 (líneas 2291-2295) y Fase 3 (líneas 2030-2043), exige que ningún usuario modifique el estado definitivo; la matriz exige ambos roles y ambos sentidos.
**Qué se observó:** En ambos roles y versiones, PATCH de notas respondió HTTP 400 y PUT/PATCH directos HTTP 405; los 12 GET posteriores respondieron HTTP 200 y conservaron los estados iniciales APROBADO y RECHAZADO.
**Por qué APROBADO:** Ninguno de los 12 intentos cambió el estado; la comprobación cubrió los dos roles, los dos sentidos y la ausencia de una operación directa aceptada para fijarlo.

## Identificación

Grupo G052; RF-69 v2.1; V1; RUN RUN-G052-V1-20261028-042531; ambiente TEST; autorización AUT-G052-V1-R2-20261028; código local consultado origin/test daefc3a5 (despliegue no verificado); Newman 6.2.2; Cypress no aplica: 0 ejecuciones.

## Esperado vs observado por solicitud

- TC-M04-129: esperado APROBADO automático, detalle nulo e historial VERSION_REGISTRADA + VERSION_APROBADA de sistema. Observado: 129: f1=0.91, recall=0.93, HTTP 201, id 82, APROBADO; auditoría VERSION_REGISTRADA + VERSION_APROBADA de SISTEMA.
- TC-M04-130: esperado HTTP 200, RECHAZADO, umbral f1 identificado; aviso al veterinario. Observado: 130: f1=0.72, recall=0.95, HTTP 200, id 83, RECHAZADO.
- TC-M04-131: esperado RECHAZADO por recall aunque f1 cumpla. Observado: 131: f1=0.95, recall=0.7, HTTP 200, id 84, RECHAZADO.
- TC-M04-132: esperado Solo (0.80, 0.85) APROBADO; otras tres RECHAZADO. Observado: 132-a: f1=0.8, recall=0.85, HTTP 201, id 85, APROBADO; 132-b: f1=0.7999, recall=0.85, HTTP 200, id 86, RECHAZADO; 132-c: f1=0.8, recall=0.8499, HTTP 200, id 87, RECHAZADO; 132-d: f1=0.7999, recall=0.8499, HTTP 200, id 88, RECHAZADO.
- TC-M04-133: esperado Cada rechazo identifica f1, recall o ambos umbrales incumplidos. Observado: 130/id 83: f1=0.72<0.80; 131/id 84: recall=0.7<0.85; 132-b/id 86: f1=0.7999<0.80; 132-c/id 87: recall=0.8499<0.85; 132-d/id 88: f1=0.7999<0.80 y recall=0.8499<0.85.
- TC-M04-134: esperado Ningún Administrador ni Veterinario puede alterar el estado en ambos sentidos. Observado: 12 intentos; PATCH /notas 400, PUT 405, PATCH 405; 0 cambios de estado en GET posterior.

| Dato | f1 | recall | Esperado HTTP / estado | POST HTTP | ID | Estado POST | GET HTTP / estado | Detalle observado | Duración POST (ms) |
|---|---:|---:|---|---:|---:|---|---|---|---:|
| 129 | 0.91 | 0.93 | 201 / APROBADO | 201 | 82 | APROBADO | 200 / APROBADO | nulo | 477 |
| 130 | 0.72 | 0.95 | 200 / RECHAZADO | 200 | 83 | RECHAZADO | 200 / RECHAZADO | f1_score_global=0.72 < umbral requerido 0.80 | 34126 |
| 131 | 0.95 | 0.7 | 200 / RECHAZADO | 200 | 84 | RECHAZADO | 200 / RECHAZADO | recall_clase_riesgo_alto=0.7 < umbral requerido 0.85 | 32774 |
| 132-a | 0.8 | 0.85 | 201 / APROBADO | 201 | 85 | APROBADO | 200 / APROBADO | nulo | 205 |
| 132-b | 0.7999 | 0.85 | 200 / RECHAZADO | 200 | 86 | RECHAZADO | 200 / RECHAZADO | f1_score_global=0.7999 < umbral requerido 0.80 | 33424 |
| 132-c | 0.8 | 0.8499 | 200 / RECHAZADO | 200 | 87 | RECHAZADO | 200 / RECHAZADO | recall_clase_riesgo_alto=0.8499 < umbral requerido 0.85 | 18133 |
| 132-d | 0.7999 | 0.8499 | 200 / RECHAZADO | 200 | 88 | RECHAZADO | 200 / RECHAZADO | f1_score_global=0.7999 < umbral requerido 0.80; recall_clase_riesgo_alto=0.8499 < umbral requerido 0.85 | 5859 |

Listado de conciliación: HTTP 200, eco RUN true, 0 coincidencias recuperadas. Auditoría RF-73: HTTP 200; VERSION_APROBADA (SISTEMA, versión 82); VERSION_REGISTRADA (SISTEMA, versión 82).

## TC-M04-133: detalle de versiones rechazadas

| Dato | Caso de origen | Versión | Umbral exigido | Resultado |
|---|---|---|---|---|
| 130 | TC-M04-130 | 83 | f1 | APROBADO |
| 131 | TC-M04-131 | 84 | recall | APROBADO |
| 132-b | TC-M04-132 | 86 | f1 | APROBADO |
| 132-c | TC-M04-132 | 87 | recall | APROBADO |
| 132-d | TC-M04-132 | 88 | f1 y recall | APROBADO |

Excluidas del dominio de 133:

- Ninguna.

Sin evidencia suficiente:

- Ninguna.

## TC-M04-134: intentos de alterar el estado

| Rol | Versión y estado inicial | Operación | HTTP | Estado antes → después |
|---|---|---|---:|---|
| Administrador | 82 (APROBADO) | PATCH /prediccion/modelos/82/notas | 400 | APROBADO → APROBADO (GET 200) |
| Administrador | 82 (APROBADO) | PUT /prediccion/modelos/82 | 405 | APROBADO → APROBADO (GET 200) |
| Administrador | 82 (APROBADO) | PATCH /prediccion/modelos/82 | 405 | APROBADO → APROBADO (GET 200) |
| Administrador | 83 (RECHAZADO) | PATCH /prediccion/modelos/83/notas | 400 | RECHAZADO → RECHAZADO (GET 200) |
| Administrador | 83 (RECHAZADO) | PUT /prediccion/modelos/83 | 405 | RECHAZADO → RECHAZADO (GET 200) |
| Administrador | 83 (RECHAZADO) | PATCH /prediccion/modelos/83 | 405 | RECHAZADO → RECHAZADO (GET 200) |
| Veterinario | 82 (APROBADO) | PATCH /prediccion/modelos/82/notas | 400 | APROBADO → APROBADO (GET 200) |
| Veterinario | 82 (APROBADO) | PUT /prediccion/modelos/82 | 405 | APROBADO → APROBADO (GET 200) |
| Veterinario | 82 (APROBADO) | PATCH /prediccion/modelos/82 | 405 | APROBADO → APROBADO (GET 200) |
| Veterinario | 83 (RECHAZADO) | PATCH /prediccion/modelos/83/notas | 400 | RECHAZADO → RECHAZADO (GET 200) |
| Veterinario | 83 (RECHAZADO) | PUT /prediccion/modelos/83 | 405 | RECHAZADO → RECHAZADO (GET 200) |
| Veterinario | 83 (RECHAZADO) | PATCH /prediccion/modelos/83 | 405 | RECHAZADO → RECHAZADO (GET 200) |

## Observaciones

Los POST con estado RECHAZADO tardaron entre 5.859 y 34.126 s; los APROBADOS, entre 0.205 y 0.477 s. La validación de las dos versiones APROBADAS quedó por debajo de 0.5 s. El total del POST rechazado no aísla la validación que mide RNF-01.

- 130: POST 34126 ms; RF-69 RNF-01 (líneas 2350-2352) exige validación de métricas ≤ 5 s por versión. La medida incluye correo y no aísla Fases 2-3; solo observación de rendimiento.
- 131: POST 32774 ms; RF-69 RNF-01 (líneas 2350-2352) exige validación de métricas ≤ 5 s por versión. La medida incluye correo y no aísla Fases 2-3; solo observación de rendimiento.
- 132-b: POST 33424 ms; RF-69 RNF-01 (líneas 2350-2352) exige validación de métricas ≤ 5 s por versión. La medida incluye correo y no aísla Fases 2-3; solo observación de rendimiento.
- 132-c: POST 18133 ms; RF-69 RNF-01 (líneas 2350-2352) exige validación de métricas ≤ 5 s por versión. La medida incluye correo y no aísla Fases 2-3; solo observación de rendimiento.
- 132-d: POST 5859 ms; RF-69 RNF-01 (líneas 2350-2352) exige validación de métricas ≤ 5 s por versión. La medida incluye correo y no aísla Fases 2-3; solo observación de rendimiento.
- El correo a Veterinario no tiene traza de entrega por API pública; API-130-01 evalúa HTTP, estado y detalle.

Los POST rechazados pueden incluir el aviso síncrono por destinatario tras el commit; la lectura local de src/prediction/application/use_cases/versiones_modelo/registrar_version_modelo_use_case.py:183-191, src/prediction/infrastructure/adapters/aviso_version_modelo_email_adapter.py:74-81,101-104 y src/shared/email.py:37,70 muestra timeout SMTP de 8 s. Es hipótesis de latencia, no causa raíz acreditada en TEST. Los POST aprobados observados son inferiores a 0.5 s; RNF-01 exige la validación de métricas en ≤ 5 s y la medida del POST rechazado incluye más pasos, por lo que no acredita un incumplimiento. La entrega del correo no es verificable por API. El sandbox no revierte los siete ONNX cargados ni avisos ya emitidos. El intento 1 pudo emitir avisos para las versiones cuyos POST agotaron 30 s; el intento 2 generó cinco registros RECHAZADO que disparan la ruta local de aviso. Ni los destinatarios efectivos ni la entrega de esos correos se acreditan por API.

## Historial de intentos

Intento 1: `RUN-G052-V1-20261028-040338`, autorización `AUT-G052-V1-20261028`, resultado **NO_CONCLUYENTE TÉCNICO (exit 2)**, no oficial. Se enviaron siete POST de registro a TEST con siete archivos ONNX previstos: cuatro tuvieron respuesta y tres agotaron los 30 s del ejecutor sin respuesta ni GET verificable. El detalle extraído de su `resultado.json` fue:

| Dato / caso | POST y lectura observados | Decisión del intento 1 |
|---|---|---|
| 129 / TC-M04-129 | HTTP 201, id 75, APROBADO; GET 200, historial VERSION_REGISTRADA + VERSION_APROBADA de SISTEMA | APROBADO |
| 130 / TC-M04-130 | POST sin respuesta a 30 s; sin GET; id 76 consumido por la secuencia, estado y HTTP no acreditados | NO_CONCLUYENTE |
| 131 / TC-M04-131 | POST sin respuesta a 30 s; sin GET; id 77 consumido por la secuencia, estado y HTTP no acreditados | NO_CONCLUYENTE |
| 132-a / TC-M04-132 | HTTP 201, id 78, APROBADO; GET 200 | Conforme; caso completo NO_CONCLUYENTE |
| 132-b / TC-M04-132 | POST sin respuesta a 30 s; sin GET; id 79 consumido por la secuencia, estado y HTTP no acreditados | Sin comprobación concluyente |
| 132-c / TC-M04-132 | HTTP 200, id 80, RECHAZADO; GET 200; `recall_clase_riesgo_alto=0.8499 < umbral requerido 0.85` | Conforme; caso completo NO_CONCLUYENTE |
| 132-d / TC-M04-132 | HTTP 200, id 81, RECHAZADO; GET 200; `f1_score_global=0.7999 < umbral requerido 0.80; recall_clase_riesgo_alto=0.8499 < umbral requerido 0.85` | Conforme; caso completo NO_CONCLUYENTE |
| 133 / TC-M04-133 | Solo los detalles de 132-c/id 80 y 132-d/id 81 fueron comprobables | APROBADO parcial por fallo de automatización QA; no acreditaba los cinco rechazos |
| 134 / TC-M04-134 | 12 intentos de Administrador y Veterinario, HTTP 400/405; GET posteriores 200 sin cambio de estado | APROBADO |

Las peticiones del intento 1 a TEST incluyeron dos inicios de sesión previos, GET de catálogo, siete POST de registro, cuatro GET por id, GET de auditoría RF-73, 12 intentos de cambio de estado y 12 GET posteriores. El cierre DELETE del RUN respondió HTTP 200; el sandbox confirmó cierre y rollback, **sin consulta posterior de BD**. La reversión de los ONNX y la entrega o reversión de avisos no se verificaron. Los POST sin respuesta de 130, 131 y 132-b probablemente continuaron en servidor y pudieron intentar avisos al Veterinario; la secuencia de ids 76/77/79 no prueba estado, HTTP ni entrega de correo. `ORD-G052-003` corrigió el timeout y añadió conciliación sin reintento; `ORD-G052-005` corrigió la aprobación parcial de 133. El responsable QA decidió eliminar la evidencia nativa del intento 1 el 2026-10-28; este resumen conserva sus datos esenciales, pero no sustituye los reportes originales eliminados. El intento 2 evaluó cinco versiones rechazadas y aprobó los seis casos.

## Incidencias de producto

Sin incidencias de producto confirmadas.

## Incidencias técnicas QA y análisis

Sin problemas técnicos en este RUN. Quedaron resueltos los dos problemas de automatización del intento 1: el límite de 30 s dejaba POST rechazados sin respuesta ni conciliación (`ORD-G052-003`: timeout de 120 s, duración medida y conciliación por listado/id de proceso sin reintentar) y el ejecutor aprobaba 133 con solo dos de cinco rechazos comprobados (`ORD-G052-005`: evaluación de versiones rechazadas, exclusiones justificadas y decisión no concluyente cuando falta evidencia). La latencia exacta de TEST y la entrega de avisos no quedaron explicadas por la corrección QA. No se atribuye causa raíz de producto por lectura de código local.

## Revisión QA

2026-10-28; orquestador QA; reescritura con datos reales; sin cambio de veredictos.

## Cierre y rollback

DELETE RUN HTTP 200. Sandbox confirmó cierre y rollback; no hubo consulta posterior de BD. La entrega de avisos y la eliminación de ONNX no se verificaron mediante la API.

## Evidencias

- preflight.json
- newman/newman-G052.json
- newman/newman-G052.html
- TC-M04-G052_resultado.md
- resultado.json

## Conclusión y acción

APROBADO. Nada para este grupo; se deja una observación de rendimiento.
