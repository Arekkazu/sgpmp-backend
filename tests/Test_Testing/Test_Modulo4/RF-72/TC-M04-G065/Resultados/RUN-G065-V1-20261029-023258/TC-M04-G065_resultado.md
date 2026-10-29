# TC-M04-G065 — APROBADO

## Identificación

Grupo G065; casos TC-M04-198, TC-M04-199, TC-M04-223, TC-M04-224; RF-72; versión 1; RUN RUN-G065-V1-20261029-023258; ambiente TEST; autorización AUT-G065-V1-20261029; contrato revisado origin/test daefc3a5; Node.js. Solo API.

## Decisión del caso

Los cuatro casos cumplen RF-72: observaciones opcionales, fuente persistida, marca de fuente desconocida y rechazo de la fuente fuera del catálogo sin persistir; la respuesta a la fuente inválida usa HTTP 400 en lugar del 422 recomendado, registrado como observación.

| Caso | Estado | Motivo |
|---|---|---|
| TC-M04-198 | APROBADO | Cumplió las comprobaciones de respuesta, historial y auditoría descritas abajo. |
| TC-M04-199 | APROBADO | Cumplió las comprobaciones de respuesta, historial y auditoría descritas abajo. |
| TC-M04-223 | APROBADO | Cumplió las comprobaciones de respuesta, historial y auditoría descritas abajo. |
| TC-M04-224 | APROBADO con observación | La fuente inválida se rechazó, identificó el campo y el catálogo completo y no persistió; HTTP 400 en lugar del 422 recomendado (OBS-M04-G065-224). |

RUN oficial: sí. Qué falta: nada para este grupo. El ensayo loopback nunca constituye evidencia TEST.

## Precondición de datos (semilla)

72 eventos examinados; modelos {"MODELO_ESPECIES_MEDIANAS":14,"MODELO_ACUICULTURA":57}; 10/10 resultados asignados. Se requieren 10 inferencias distintas de modelo INDIVIDUAL, sin retroalimentación previa del Veterinario, con patología activa aplicable. La procedencia de la semilla externa debe constar en la orquestación.

## Detalle por caso

### TC-M04-198 — APROBADO

**Qué se hizo:** Se enviaron dos CORRECTO: f80c05d9 con observaciones clínicas de prueba y 31e7239e sin el campo observaciones_clinicas.

**Qué se esperaba:** Ambos HTTP 201; el historial debe conservar íntegro el texto enviado, incluidos acentos, signos y salto de línea; al omitir el campo debe quedar nulo (RF-72, Entrada 4164).

**Qué se observó:** f80c05d9: CORRECTO, fuente omitida, HTTP 201; 31e7239e: CORRECTO, fuente omitida, HTTP 201. El historial mostró el texto enviado sin cambios en el primero y nulo en el segundo; ambos registros tuvieron lectura de historial y auditoría HTTP 200.

**Por qué APROBADO:** El texto se comparó carácter por carácter con el enviado y la omisión quedó nula; los dos POST fueron aceptados.

### TC-M04-199 — APROBADO

**Qué se hizo:** Se enviaron cuatro INCORRECTO: 5dbe4510 con OBSERVACION_DIRECTA; f7fea6d3 con LABORATORIO; 32985675 con HISTORIAL_CLINICO; 98c7697c con OTRO.

**Qué se esperaba:** Cada valor OBSERVACION_DIRECTA, LABORATORIO, HISTORIAL_CLINICO, OTRO debe dar HTTP 201, conservar la fuente en respuesta y auditoría y mostrar es_fuente_desconocida=false (RF-72, Entrada 4167; Salida 4316-4317).

**Qué se observó:** 5dbe4510: HTTP 201, OBSERVACION_DIRECTA, marca false; f7fea6d3: HTTP 201, LABORATORIO, marca false; 32985675: HTTP 201, HISTORIAL_CLINICO, marca false; 98c7697c: HTTP 201, OTRO, marca false. La auditoría registró esas mismas fuentes y la marca false en los cuatro casos.

**Por qué APROBADO:** Las cuatro fuentes enviadas se conservaron en respuesta y auditoría, con marca false y HTTP 201.

### TC-M04-223 — APROBADO

**Qué se hizo:** Se enviaron INCORRECTO sobre f056f99d y PARCIAL sobre 997b8cda sin fuente; PARCIAL sobre d1f3cc43 con LABORATORIO como contraste.

**Qué se esperaba:** Los dos registros sin fuente deben dar HTTP 201 y marca true; el contraste con LABORATORIO, HTTP 201 y marca false, también en auditoría (RF-72, 4118-4120).

**Qué se observó:** f056f99d: HTTP 201, marca true; 997b8cda: HTTP 201, marca true; d1f3cc43: HTTP 201, marca false. La auditoría confirmó true, true y false, respectivamente.

**Por qué APROBADO:** Omitir la fuente marcó true para INCORRECTO y PARCIAL; informar LABORATORIO dejó la marca false en respuesta y auditoría.

### TC-M04-224 — APROBADO con observación

**Qué se hizo:** Se envió INCORRECTO sobre 511a6d66 con fuente RESONANCIA_MAGNETICA, fuera del catálogo.

**Qué se esperaba:** Rechazar la fuente fuera del catálogo identificando `fuente_diagnostico` y OBSERVACION_DIRECTA, LABORATORIO, HISTORIAL_CLINICO, OTRO, sin registro en historial ni auditoría. RF-72 Entrada 4167 define `fuente_diagnostico` como Enum opcional y la Regla 2 (4033-4041) enumera las fuentes para la prioridad. La matriz G065 subcaso 4 escribió HTTP 422 como código recomendado; RF-72 no fija un código para este rechazo.

**Qué se observó:** HTTP 400, error FUENTE_DIAGNOSTICO_INVALIDA, campo fuente_diagnostico, catálogo completo true; historial con 14 eventos antes y 14 después (HTTP 200), auditoría HTTP 200 con 0 registros del intento.

**Por qué APROBADO:** El valor inválido se rechazó, se identificaron el campo `fuente_diagnostico` y el catálogo completo, y no se persistió nada. HTTP 400 en lugar de 422 queda como observación porque RF-72 no fija 422 para esta fuente.

## Registros y observaciones

| Registro | Resultado | Estado enviado | Fuente enviada | HTTP | Fuente observada | Marca observada |
|---|---|---|---|---:|---|---|
| 224-invalida | 511a6d66-a862-4822-bf47-2634333531b3 | INCORRECTO | RESONANCIA_MAGNETICA | 400 | nula | ausente |
| 223-incorrecto | f056f99d-78bf-478d-86f0-5b2ee1a70873 | INCORRECTO | omitida | 201 | nula | true |
| 223-parcial | 997b8cda-b608-4bb3-a7d2-ea37cf12b944 | PARCIAL | omitida | 201 | nula | true |
| 223-contraste | d1f3cc43-3bf9-4492-a5b9-ec0cc5025d7e | PARCIAL | LABORATORIO | 201 | LABORATORIO | false |
| 199-1 | 5dbe4510-af8e-4ea7-8688-7efa0751800d | INCORRECTO | OBSERVACION_DIRECTA | 201 | OBSERVACION_DIRECTA | false |
| 199-2 | f7fea6d3-9bc1-49de-a88e-3be75f399b87 | INCORRECTO | LABORATORIO | 201 | LABORATORIO | false |
| 199-3 | 32985675-9bbf-46ae-a37d-dc1833155627 | INCORRECTO | HISTORIAL_CLINICO | 201 | HISTORIAL_CLINICO | false |
| 199-4 | 98c7697c-0cb8-403c-9421-07679e59cac8 | INCORRECTO | OTRO | 201 | OTRO | false |
| 198-con | f80c05d9-59d9-4b7e-9786-c3794979cc77 | CORRECTO | omitida | 201 | nula | false |
| 198-sin | 31e7239e-699a-4a3a-94b1-6cd7835cf260 | CORRECTO | omitida | 201 | nula | false |

Observaciones: OBS-M04-G065-224 por el código HTTP 400; sin otras observaciones. El texto clínico de prueba se compara en memoria y no se vuelca al informe.

## Observación QA

### OBS-M04-G065-224 — Fuente de diagnóstico fuera del catálogo responde HTTP 400; se recomienda 422 por coherencia con RF-72 E3 y E5

- Caso y estado: TC-M04-224, APROBADO con observación. Certeza del HTTP observado: CONFIRMADA por respuesta de API pública en TEST.
- Atención sugerida: Desarrollo, por el código HTTP de la API pública; la causa raíz no está determinada.
- Requisito y criterio: RF-72 Entrada 4167 (Enum opcional), Regla 2 (4033-4041) y matriz G065 subcaso 4. La fuente fuera del catálogo debe rechazarse con campo y catálogo identificados, sin persistir; HTTP 422 es recomendado, ya que RF-72 no fija código para este caso.
- Precondiciones: resultado de inferencia 511a6d66-a862-4822-bf47-2634333531b3 apto para retroalimentación, estado INCORRECTO, diagnóstico real activo y fuente RESONANCIA_MAGNETICA fuera del catálogo.
- Pasos: 1. Consultar historial del activo antes del POST. 2. Enviar POST /prediccion/retroalimentacion con ese resultado y fuente_diagnostico=RESONANCIA_MAGNETICA. 3. Revisar respuesta, historial y auditoría de RETROALIMENTACION_REGISTRADA.
- Observado: HTTP 400, FUENTE_DIAGNOSTICO_INVALIDA, field=fuente_diagnostico, catálogo completo=true; historial 14 eventos antes y 14 después (HTTP 200); auditoría HTTP 200 con 0 registros del intento.
- Evidencia: resultado.json del mismo RUN, registro 224-invalida y solicitudes POST, GET historial y GET auditoría.
- Hipótesis para Desarrollo, sin causa raíz demostrada: en el contrato consultado origin/test daefc3a5, src/prediction/domain/entities/retroalimentacion_clinica.py:62-67 lanza ValidationError; src/shared/errors.py:69-77 asigna HTTP 400 a ValidationError y src/shared/errors.py:91-98 asigna HTTP 422 a BusinessRuleError.
- Relación: INC-M04-G051-VAL400 sigue siendo incidencia porque RF-69 E2 sí fija HTTP 422 explícitamente. G051 no se modifica.
- Acción sugerida: considerar HTTP 422 por coherencia, evaluando compatibilidad con clientes; no se requiere repetir G065 para aprobarlo.

## Incidencias de producto

Ninguna.

## Problemas técnicos y causas

Sin problemas técnicos registrados. La observación de HTTP 400 orienta la atención sugerida a Desarrollo sin atribuir causa raíz.

## Historial, cierre y rollback

50 solicitudes; DELETE HTTP 200; rollback verificado por lectura pública: Registros del RUN ausentes en historial público poscierre. Las lecturas poscierre pueden crear HISTORIAL_CONSULTADO fuera del sandbox; no prueban ausencia de esos eventos.

## Conclusión y acciones

G065 queda APROBADO. Conservar las evidencias del RUN; Desarrollo puede considerar HTTP 422 por coherencia con RF-72 E3 y E5 y evaluar la compatibilidad de ese cambio.

## Revisión QA

- Fecha: 2026-10-29.
- Realizada por el orquestador QA; autorizada por el responsable QA conforme a su decisión «Sí, hagámoslo, pero no toquemos G051».
- Cambios: TC-M04-224 RECHAZADO → APROBADO con observación; INC-M04-G065-224 convertida en OBS-M04-G065-224; G065 RECHAZADO → APROBADO.
- Fundamento: el código HTTP se exige cuando lo fija el requisito. RF-72 no fija un código para la fuente fuera del catálogo; el 422 procedía de la decisión escrita en la matriz G065. El rechazo, el campo, el catálogo y la ausencia de persistencia sí están comprobados.
- Trazabilidad: resultado.json conserva el veredicto histórico RECHAZADO del ejecutor, sus comprobaciones y su incidencia histórica como evidencia nativa. No se modifica. El veredicto vigente de este informe incorpora la decisión QA documentada aquí.

## Herramientas y evidencias

Este RUN se ejecutó por API con fetch; Newman no se ejecutó (desviación de la herramienta indicada en la matriz, API - Postman). La evidencia funcional completa está en resultado.json. El ejecutor se corrigió el 2026-10-29 para usar Newman en las ejecuciones siguientes (ORD-G065-005).

## Evidencias

- preflight.json
- resultado.json
- TC-M04-G065_resultado.md
