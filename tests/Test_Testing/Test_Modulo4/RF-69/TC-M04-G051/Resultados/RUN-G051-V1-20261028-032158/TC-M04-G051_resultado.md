# TC-M04-G051 — RECHAZADO

## Decisión del caso

Caso agrupado TC-M04-G051 (RF-69); originales TC-M04-121, TC-M04-122, TC-M04-123, TC-M04-124, TC-M04-125, TC-M04-126, TC-M04-127. Decisión: RECHAZADO. Motivo: Fecha futura responde 500 (TC-M04-122) y los campos obligatorios vacíos u omitidos responden 400 en lugar de 422 (TC-M04-123 y TC-M04-127); el resto de validaciones de metadatos cumple.

| Caso | Comprobación | Decisión | Motivo breve |
|---|---|---|---|
| TC-M04-121 | API-121-01 | APROBADO | 2 solicitudes cumplen el oráculo |
| TC-M04-122 | API-122-01 | RECHAZADO | Fecha futura: HTTP 500 genérico; se esperaba 422 sin versión. |
| TC-M04-123 | API-123-01 | RECHAZADO | Tipo vacío: HTTP 400; se esperaba 422. |
| TC-M04-124 | API-124-01 | APROBADO | 3 solicitudes cumplen el oráculo |
| TC-M04-125 | API-125-01 | APROBADO | 4 solicitudes cumplen el oráculo |
| TC-M04-126 | API-126-01 | APROBADO | 6 solicitudes cumplen el oráculo |
| TC-M04-127 | API-127-01 | RECHAZADO | Tres omisiones de hash: HTTP 400; se esperaba 422. |

RUN oficial: sí (registro QA OFICIAL, intento 3; DELETE 200, rollback confirmado).

Qué falta: Corrección de INC-M04-G051-122 e INC-M04-G051-VAL400 por Desarrollo y reevaluación V2 de 122, 123, 127.

## Detalle por caso

### TC-M04-121 — APROBADO

**Qué se hizo:** Tras el inicio de sesión como Administrador, la integración RF-71 envió 2 solicitudes POST de registro para estos datos: variables [16], fecha 2026-10-27T03:22:02.414Z (proceso RF-71 1b7ec2a3-7756-449e-9b84-3213cc89a958), tipo MODELO_ESPECIES_GRANDES; variables [16, 17], fecha 2026-10-27T03:22:02.414Z (proceso RF-71 cc78ade0-908b-4737-82e6-b994e080a39a), tipo MODELO_ESPECIES_GRANDES. Se consultó el catálogo; se consultaron los listados inicial y final; los registros creados se consultaron por ID.
**Qué se esperaba:** Matriz G051: “Con variables existentes procede; con una inexistente HTTP 422 indicando el campo”. RF-69, entrada compatibilidad_variables (línea 1966), fase 2 (líneas 2016-2017) y E2 (líneas 2148-2151).
**Qué se observó:** variables existentes / ayer: HTTP 201, versión 70 en estado APROBADO, GET 200, presente en listado final; variable inexistente: HTTP 422, señaló variables compatibles, sin versión en listado final.
**Por qué APROBADO:** La variable 16 permitió registrar la versión; al añadir la inexistente 17 se obtuvo HTTP 422 que señaló las variables compatibles y no apareció otra versión.

### TC-M04-122 — RECHAZADO

**Qué se hizo:** Tras el inicio de sesión como Administrador, la integración RF-71 envió 2 solicitudes POST de registro para estos datos: fecha 2026-10-28T03:21:52.414Z (proceso RF-71 3396e128-c313-41dd-bcdc-453770b33dc3), tipo MODELO_ESPECIES_GRANDES, variable 16; fecha 2026-10-29T03:22:02.414Z (proceso RF-71 53ff2a26-9f74-4785-bb79-1de6d64835a5), tipo MODELO_ESPECIES_GRANDES, variable 16. Se reutilizó la solicitud de ayer del caso anterior (proceso RF-71 1b7ec2a3-7756-449e-9b84-3213cc89a958). Se consultó el catálogo; se consultaron los listados inicial y final; los registros creados se consultaron por ID.
**Qué se esperaba:** Matriz G051: “Las dos primeras se registran; la futura HTTP 422 sin crear la versión”. RF-69, entrada fecha_entrenamiento (línea 1964) y E2 (líneas 2148-2151).
**Qué se observó:** ayer: HTTP 201, versión 70, GET 200, presente en listado final; ahora menos 10 s: HTTP 201, versión 71 en estado APROBADO, GET 200, presente en listado final; mañana: HTTP 500, error interno genérico, sin versión en listado final.
**Por qué RECHAZADO:** La fecha futura devolvió HTTP 500 con error interno genérico en lugar de HTTP 422, aunque no apareció una versión; INC-M04-G051-122.

### TC-M04-123 — RECHAZADO

**Qué se hizo:** Tras el inicio de sesión como Administrador, la integración RF-71 envió 3 solicitudes POST de registro para estos datos: tipo MODELO_QA_INEXISTENTE (proceso RF-71 4c72b24c-f849-4a15-b66c-fde7403cff9e); tipo vacío (proceso RF-71 d0a8ff0d-bd07-45a5-bbd0-4988aee709f8); tipo MODELO_ESPECIES_PEQUEÑAS (proceso RF-71 f9ba3add-9fc8-43af-b825-3e792054db17). Se consultó el catálogo; se consultaron los listados inicial y final; los registros creados se consultaron por ID.
**Qué se esperaba:** Matriz G051: “Las tres HTTP 422 indicando el catálogo admitido”. RF-69, entrada tipo_modelo (línea 1959), actualización RFC-009 (línea 1784) y E2 (líneas 2148-2151).
**Qué se observó:** tipo inexistente: HTTP 422, enumeró los seis tipos admitidos, sin versión en listado final; tipo vacío: HTTP 400, indicó que el tipo es obligatorio, sin enumerar el catálogo, sin versión en listado final; tipo eliminado RFC-009: HTTP 422, enumeró los seis tipos admitidos, sin versión en listado final.
**Por qué RECHAZADO:** El tipo vacío devolvió HTTP 400 en lugar de HTTP 422 y no enumeró el catálogo admitido en esa respuesta; INC-M04-G051-VAL400.

### TC-M04-124 — APROBADO

**Qué se hizo:** Tras el inicio de sesión como Administrador, la integración RF-71 envió 3 solicitudes POST de registro para estos datos: sin f1 global (proceso RF-71 d5345b91-87ac-4773-aaf6-666858d14612), tipo MODELO_ESPECIES_GRANDES, variable 16; sin recall de riesgo alto (proceso RF-71 13f2f3b1-f09c-4854-9f65-4dae5dbfb6f0), tipo MODELO_ESPECIES_GRANDES, variable 16; sin matriz de confusión (proceso RF-71 eee6bb87-a9a6-406d-86d6-f97c565cd361), tipo MODELO_ESPECIES_GRANDES, variable 16. Se consultó el catálogo; se consultaron los listados inicial y final; los registros creados se consultaron por ID.
**Qué se esperaba:** Matriz G051: “Las tres HTTP 422 identificando el campo ausente”. RF-69, entrada metricas_validacion (línea 1962), fase 2 (líneas 2013-2015) y E2 (líneas 2142-2151).
**Qué se observó:** sin f1 global: HTTP 422, identificó la ausencia de f1 global, sin versión en listado final; sin recall de riesgo alto: HTTP 422, identificó la ausencia de recall de riesgo alto, sin versión en listado final; sin matriz de confusión: HTTP 422, identificó la ausencia de matriz de confusión, sin versión en listado final.
**Por qué APROBADO:** Las tres omisiones devolvieron HTTP 422 e identificaron la métrica faltante, sin crear versiones.

### TC-M04-125 — APROBADO

**Qué se hizo:** Tras el inicio de sesión como Administrador, la integración RF-71 envió 4 solicitudes POST de registro para estos datos: f1=0.0 (proceso RF-71 06d46fa8-5d9c-41fc-ab3c-b586cd88a8be), tipo MODELO_ESPECIES_GRANDES, variable 16; f1=1.0 (proceso RF-71 82ab9cfe-51ee-45aa-a7ea-f6d67ebce810), tipo MODELO_ESPECIES_GRANDES, variable 16; f1=-0.01 (proceso RF-71 2b5df1a5-bbf8-4e0a-ab3d-5f7491db51ed), tipo MODELO_ESPECIES_GRANDES, variable 16; f1=1.01 (proceso RF-71 d54ad8f6-8e2a-40b8-8902-9d59b2ce8418), tipo MODELO_ESPECIES_GRANDES, variable 16. Se consultó el catálogo; se consultaron los listados inicial y final; los registros creados se consultaron por ID.
**Qué se esperaba:** Matriz G051: “0.0 y 1.0 se aceptan; -0.01 y 1.01 HTTP 422 indicando el rango”. RF-69, entrada metricas_validacion (línea 1962), fase 2 (líneas 2013-2015) y E2 (líneas 2142-2151).
**Qué se observó:** f1=0.0: HTTP 200, versión 73 en estado RECHAZADO, GET 200, presente en listado final; f1=1.0: HTTP 201, versión 74 en estado APROBADO, GET 200, presente en listado final; f1=-0.01: HTTP 422, indicó el rango válido de 0.0 a 1.0, sin versión en listado final; f1=1.01: HTTP 422, indicó el rango válido de 0.0 a 1.0, sin versión en listado final.
**Por qué APROBADO:** Los extremos 0.0 y 1.0 se registraron; los valores -0.01 y 1.01 devolvieron HTTP 422 indicando el rango y no crearon versiones. La versión con 0.0 quedó en estado RECHAZADO por umbrales, pero sí se registró.

### TC-M04-126 — APROBADO

**Qué se hizo:** Tras el inicio de sesión como Administrador, la integración RF-71 envió 6 solicitudes POST de registro para estos datos: hash del artefacto: 63 caracteres (valor aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa) (proceso RF-71 5c05f7cd-67d6-413d-95c9-454c1faa5f61), tipo MODELO_ESPECIES_GRANDES, variable 16; hash del artefacto: 65 caracteres (valor aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa) (proceso RF-71 99f99d6f-9506-40b6-bcb2-df3e0dd4a8a6), tipo MODELO_ESPECIES_GRANDES, variable 16; hash del artefacto: 64 no hexadecimal (valor aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaag) (proceso RF-71 6d22e415-2fb4-4606-bdf5-2ad514ee1a45), tipo MODELO_ESPECIES_GRANDES, variable 16; hash del dataset: 63 caracteres (valor aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa) (proceso RF-71 2e10c7ca-59ca-4bed-953f-95299093e6df), tipo MODELO_ESPECIES_GRANDES, variable 16; hash del dataset: 65 caracteres (valor aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa) (proceso RF-71 60b67924-8f67-4102-a008-29d0de528394), tipo MODELO_ESPECIES_GRANDES, variable 16; hash del dataset: 64 no hexadecimal (valor aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaag) (proceso RF-71 2a9b7185-0de5-4e14-af49-09fe46ac6ea9), tipo MODELO_ESPECIES_GRANDES, variable 16. Se consultó el catálogo; se consultaron los listados inicial y final; los registros creados se consultaron por ID.
**Qué se esperaba:** Matriz G051: “Las seis HTTP 422 identificando el hash afectado”. RF-69, entradas de hashes (líneas 1961 y 1963), fase 2 (líneas 2008-2012) y E2 (líneas 2143-2151).
**Qué se observó:** hash del artefacto: 63 caracteres: HTTP 422, señaló hash del artefacto, sin versión en listado final; hash del artefacto: 65 caracteres: HTTP 422, señaló hash del artefacto, sin versión en listado final; hash del artefacto: 64 no hexadecimal: HTTP 422, señaló hash del artefacto, sin versión en listado final; hash del dataset: 63 caracteres: HTTP 422, señaló hash del dataset, sin versión en listado final; hash del dataset: 65 caracteres: HTTP 422, señaló hash del dataset, sin versión en listado final; hash del dataset: 64 no hexadecimal: HTTP 422, señaló hash del dataset, sin versión en listado final.
**Por qué APROBADO:** Las seis variantes devolvieron HTTP 422, señalaron el hash afectado y no crearon versiones.

### TC-M04-127 — RECHAZADO

**Qué se hizo:** Tras el inicio de sesión como Administrador, la integración RF-71 envió 3 solicitudes POST de registro para estos datos: sin hash del artefacto (proceso RF-71 0d11e8c2-e2dc-4431-b47c-3c4a1214b958), tipo MODELO_ESPECIES_GRANDES, variable 16; sin hash del dataset (proceso RF-71 9630cfdd-5eb9-49a0-b3d3-ee9d40bf41d5), tipo MODELO_ESPECIES_GRANDES, variable 16; sin ambos hashes (proceso RF-71 5bb72309-c77d-483e-8764-18a71fc495a9), tipo MODELO_ESPECIES_GRANDES, variable 16. Se consultó el catálogo; se consultaron los listados inicial y final; los registros creados se consultaron por ID.
**Qué se esperaba:** Matriz G051: “Las tres HTTP 422 sin crear la versión”. RF-69, restricción 8 (líneas 1893-1897) y E2 (líneas 2148-2151).
**Qué se observó:** sin hash del artefacto: HTTP 400, indicó que hash del artefacto es obligatorio, sin versión en listado final; sin hash del dataset: HTTP 400, indicó que hash del dataset es obligatorio, sin versión en listado final; sin ambos hashes: HTTP 400, indicó que hash del artefacto y hash del dataset son obligatorios, sin versión en listado final.
**Por qué RECHAZADO:** Las tres omisiones devolvieron HTTP 400 en lugar de HTTP 422; no crearon versiones, pero incumplieron el estado HTTP exigido; INC-M04-G051-VAL400.

## Identificación

Grupo G051; RF-69 v2.1; versión V1; RUN RUN-G051-V1-20261028-032158; ambiente TEST; autorización AUT-G051-V1-R3-20261028; referencia de código origin/test daefc3a5 (despliegue no verificado); Newman 6.2.2; Cypress no aplica (solo API).

## Esperado vs observado por solicitud

| Caso | Dato enviado | Esperado | HTTP POST | Código; mensaje; campos | Versión creada / GET |
|---|---|---|---|---|---|
| TC-M04-121 | variables existentes / ayer | Registro | 201 | nulo; nulo; nulo | sí (listado); GET 200 |
| TC-M04-121 | variable inexistente | 422 sin versión | 422 | VARIABLE_I3P1_NO_ENCONTRADA; Las siguientes variables no existen en el catálogo I3P-1: [17].; [{"campo":"compatibilidad_variables","mensaje":"Las siguientes variables no existen en el catálogo I3P-1: [17]."}] | no (listado); GET no aplica |
| TC-M04-122 | ahora menos 10 s | Registro | 201 | nulo; nulo; nulo | sí (listado); GET 200 |
| TC-M04-122 | mañana | 422 sin versión | 500 | ERROR_INTERNO; Ocurrió un error interno. Intenta de nuevo; si el problema persiste, contacta al equipo de soporte.; [] | no (listado); GET no aplica |
| TC-M04-123 | tipo inexistente | 422 sin versión | 422 | TIPO_MODELO_INVALIDO; lista de 6 tipos válidos; tipo_modelo: lista de 6 tipos válidos | no (listado); GET no aplica |
| TC-M04-123 | tipo vacío | 422 sin versión | 400 | VAL_ENTRADA; Errores de validacion en la solicitud; [{"campo":"tipo_modelo","mensaje":"Este campo es obligatorio."}] | no (listado); GET no aplica |
| TC-M04-123 | tipo eliminado RFC-009 | 422 sin versión | 422 | TIPO_MODELO_INVALIDO; lista de 6 tipos válidos; tipo_modelo: lista de 6 tipos válidos | no (listado); GET no aplica |
| TC-M04-124 | sin f1_score_global | 422 sin versión | 422 | METRICAS_INCOMPLETAS; Los metadatos del modelo son inválidos o incompletos: faltan ['f1_score_global'].; [{"campo":"metricas_validacion","mensaje":"Los metadatos del modelo son inválidos o incompletos: faltan ['f1_score_global']."}] | no (listado); GET no aplica |
| TC-M04-124 | sin recall_clase_riesgo_alto | 422 sin versión | 422 | METRICAS_INCOMPLETAS; Los metadatos del modelo son inválidos o incompletos: faltan ['recall_clase_riesgo_alto'].; [{"campo":"metricas_validacion","mensaje":"Los metadatos del modelo son inválidos o incompletos: faltan ['recall_clase_riesgo_alto']."}] | no (listado); GET no aplica |
| TC-M04-124 | sin matriz_confusion | 422 sin versión | 422 | METRICAS_INCOMPLETAS; Los metadatos del modelo son inválidos o incompletos: faltan ['matriz_confusion'].; [{"campo":"metricas_validacion","mensaje":"Los metadatos del modelo son inválidos o incompletos: faltan ['matriz_confusion']."}] | no (listado); GET no aplica |
| TC-M04-125 | f1=0.0 | Registro | 200 | nulo; nulo; nulo | sí (listado); GET 200 |
| TC-M04-125 | f1=1.0 | Registro | 201 | nulo; nulo; nulo | sí (listado); GET 200 |
| TC-M04-125 | f1=-0.01 | 422 sin versión | 422 | METRICA_FUERA_DE_RANGO; El campo f1_score_global=-0.01 debe estar en el rango [0.0, 1.0].; [{"campo":"metricas_validacion","mensaje":"El campo f1_score_global=-0.01 debe estar en el rango [0.0, 1.0]."}] | no (listado); GET no aplica |
| TC-M04-125 | f1=1.01 | 422 sin versión | 422 | METRICA_FUERA_DE_RANGO; El campo f1_score_global=1.01 debe estar en el rango [0.0, 1.0].; [{"campo":"metricas_validacion","mensaje":"El campo f1_score_global=1.01 debe estar en el rango [0.0, 1.0]."}] | no (listado); GET no aplica |
| TC-M04-126 | hash_artefacto_sha256: 63 caracteres | 422 sin versión | 422 | HASH_SHA256_INVALIDO; hash_artefacto_sha256 debe ser un hash SHA-256 de 64 caracteres hexadecimales.; [{"campo":"hash_artefacto_sha256","mensaje":"hash_artefacto_sha256 debe ser un hash SHA-256 de 64 caracteres hexadecimales."}] | no (listado); GET no aplica |
| TC-M04-126 | hash_artefacto_sha256: 65 caracteres | 422 sin versión | 422 | HASH_SHA256_INVALIDO; hash_artefacto_sha256 debe ser un hash SHA-256 de 64 caracteres hexadecimales.; [{"campo":"hash_artefacto_sha256","mensaje":"hash_artefacto_sha256 debe ser un hash SHA-256 de 64 caracteres hexadecimales."}] | no (listado); GET no aplica |
| TC-M04-126 | hash_artefacto_sha256: 64 no hexadecimal | 422 sin versión | 422 | HASH_SHA256_INVALIDO; hash_artefacto_sha256 debe ser un hash SHA-256 de 64 caracteres hexadecimales.; [{"campo":"hash_artefacto_sha256","mensaje":"hash_artefacto_sha256 debe ser un hash SHA-256 de 64 caracteres hexadecimales."}] | no (listado); GET no aplica |
| TC-M04-126 | dataset_entrenamiento_hash: 63 caracteres | 422 sin versión | 422 | HASH_SHA256_INVALIDO; dataset_entrenamiento_hash debe ser un hash SHA-256 de 64 caracteres hexadecimales.; [{"campo":"dataset_entrenamiento_hash","mensaje":"dataset_entrenamiento_hash debe ser un hash SHA-256 de 64 caracteres hexadecimales."}] | no (listado); GET no aplica |
| TC-M04-126 | dataset_entrenamiento_hash: 65 caracteres | 422 sin versión | 422 | HASH_SHA256_INVALIDO; dataset_entrenamiento_hash debe ser un hash SHA-256 de 64 caracteres hexadecimales.; [{"campo":"dataset_entrenamiento_hash","mensaje":"dataset_entrenamiento_hash debe ser un hash SHA-256 de 64 caracteres hexadecimales."}] | no (listado); GET no aplica |
| TC-M04-126 | dataset_entrenamiento_hash: 64 no hexadecimal | 422 sin versión | 422 | HASH_SHA256_INVALIDO; dataset_entrenamiento_hash debe ser un hash SHA-256 de 64 caracteres hexadecimales.; [{"campo":"dataset_entrenamiento_hash","mensaje":"dataset_entrenamiento_hash debe ser un hash SHA-256 de 64 caracteres hexadecimales."}] | no (listado); GET no aplica |
| TC-M04-127 | sin hash_artefacto_sha256 | 422 sin versión | 400 | VAL_ENTRADA; Errores de validacion en la solicitud; [{"campo":"hash_artefacto_sha256","mensaje":"Este campo es obligatorio."}] | no (listado); GET no aplica |
| TC-M04-127 | sin dataset_entrenamiento_hash | 422 sin versión | 400 | VAL_ENTRADA; Errores de validacion en la solicitud; [{"campo":"dataset_entrenamiento_hash","mensaje":"Este campo es obligatorio."}] | no (listado); GET no aplica |
| TC-M04-127 | sin ambos hashes | 422 sin versión | 400 | VAL_ENTRADA; Errores de validacion en la solicitud; [{"campo":"hash_artefacto_sha256","mensaje":"Este campo es obligatorio."},{"campo":"dataset_entrenamiento_hash","mensaje":"Este campo es obligatorio."}] | no (listado); GET no aplica |

## Comprobaciones API y observaciones

API-121-01 a API-127-01 se evaluaron por significado. TC-M04-121 con variables existentes reutiliza el POST de ayer de TC-M04-122. Para “ahora” se envió el instante del cliente menos 10 segundos; fecha HTTP del servidor: Wed, 28 Oct 2026 03:22:02 GMT. f1=0.0 produjo una versión RECHAZADO por umbrales con HTTP 200; el correo previsto, entregado o no, quedó fuera de verificación. Conteo inicial 1, final 5, delta 4, aceptados 4, rechazados con id 0. La ausencia de versión se acredita con el delta y la ausencia de id en cada rechazo; si el listado no fue verificable, el caso queda no concluyente.

## Historial de intentos

| Intento / RUN | Referencia | Resultado y causa | Peticiones a TEST | Escrituras y archivos | Correo | Cierre / rollback |
|---|---|---|---|---|---|---|
| 1 · `RUN-G051-V1-20261028-024835` | `AUT-G051-V1-20261028` | `PREFLIGHT_LOCAL`, exit 2; los siete casos `NO_CONCLUYENTE`. `g051.mjs` no cargaba `.env.qa`; fallo de automatización QA corregido por `ORD-G051-003`. | 0; `bitacora` y `solicitudes` vacías. | 0 escrituras de prueba; sin archivos ONNX ni efectos del RUN. | Ninguno. | Registro de cierre `INCIERTO`; no hubo DELETE ni rollback verificable. |
| 2 · `RUN-G051-V1-20261028-025601` | `AUT-G051-V1-R2-20261028` | `TÉCNICO`, exit 2. 121 conforme: POST 201, versión 67; variable 17 → 422 `VARIABLE_I3P1_NO_ENCONTRADA`. 122 «ahora» → 201, versión 68; «mañana» (`2026-10-29T02:56:05.304Z`) → 500 `ERROR_INTERNO`, sin versión en listado final. Newman se detuvo; 123–127 no ejecutados. Fallo de continuidad QA corregido por `ORD-G051-005`. | 11: login anterior al RUN, GET de catálogo y listado inicial, 4 POST, 2 GET de versiones, listado final y DELETE. | 2 versiones en el RUN (total 1 → 3); el sandbox confirmó cierre. Se prevén 2 ONNX de los POST 201 y posiblemente un tercero huérfano tras el 500: 2–3 archivos persistentes, sin inspección del almacenamiento de TEST. | Ninguno; no se ejecutó f1=0.0. | DELETE 200; rollback marcado confirmado por el sandbox, sin consulta posterior de BD ni verificación de archivos. |
| 3 · `RUN-G051-V1-20261028-032158` | `AUT-G051-V1-R3-20261028` | RUN oficial `RECHAZADO`: 121, 124–126 aprobados; 122, 123 y 127 rechazados. Los casos independientes terminaron. | 32: login anterior al RUN, GET de catálogo y listado inicial, 23 POST, 4 GET de versiones, listado final y DELETE. Evidencia nativa conservada en `resultado.json` y `newman/`. | Delta de 4 versiones antes del cierre; se prevén 4 ONNX y quizá un quinto huérfano, no inspeccionados. | Aviso posible por f1=0.0; entrega no verificada. | DELETE 200; sandbox confirmó cierre, sin consulta posterior de BD. |

El 500 del intento 2 fue la primera observación de `INC-M04-G051-122`; el intento 3 la confirmó. Por decisión expresa del responsable QA del 2026-10-28, se eliminaron los directorios y la evidencia nativa de los intentos 1 y 2 después de transcribir esta síntesis. El historial no sustituye la evidencia nativa conservada del RUN oficial ni modifica sus veredictos.

## Incidencias de producto

### INC-M04-G051-122 — Una fecha de entrenamiento futura produce error interno 500 en lugar de rechazo 422

- **Casos afectados y equipo inicial:** TC-M04-122; Desarrollo. Primera discrepancia comprobada en la API; Desarrollo atiende inicialmente. La causa raíz no está determinada.
- **Severidad y certeza:** MEDIA, CONFIRMADA. La fecha futura no creó una versión según el listado, pero el 500 genérico no identifica el campo ni permite a RF-71 distinguir el dato inválido de una caída; un ONNX huérfano es probable y no está verificado en TEST.
- **Requisito:** Matriz G051: “Las dos primeras se registran; la futura HTTP 422 sin crear la versión”. RF-69 Entrada fecha_entrenamiento, línea 1964: “No puede ser futura.”; E2, líneas 2142-2151: HTTP 422 y registro no creado.
- **Precondiciones:** RUN RUN-G051-V1-20261028-032158 autorizado; catálogo I3P-1 leído; clave interna RF-71; artefacto ONNX y hash real.
- **Pasos:**
  1. Consultar GET /prediccion/modelos?tipo_modelo=MODELO_ESPECIES_GRANDES&limit=100&offset=0 y conservar el total inicial.
  2. Enviar POST /prediccion/modelos multipart con tipo_modelo=MODELO_ESPECIES_GRANDES, fecha_entrenamiento=2026-10-29T03:22:02.414Z, artefacto ONNX y hash SHA-256 real, id_proceso_rf71 único y cabecera X-RF71-Internal-Key.
  3. Comparar la respuesta y el listado final con el inicial; comprobar que el proceso rechazado no aparece.
- **Esperado:** Matriz G051: “Las dos primeras se registran; la futura HTTP 422 sin crear la versión”. RF-69 Entrada fecha_entrenamiento, línea 1964: “No puede ser futura.”; E2, líneas 2142-2151: HTTP 422 y registro no creado.
- **Obtenido:** TC-M04-121 variables existentes / ayer: HTTP 201, código nulo, mensaje nulo, campos [], id 70, en listado final true; TC-M04-122 ahora menos 10 s: HTTP 201, código nulo, mensaje nulo, campos [], id 71, en listado final true; TC-M04-122 mañana (2026-10-29T03:22:02.414Z): HTTP 500, código ERROR_INTERNO, mensaje Ocurrió un error interno. Intenta de nuevo; si el problema persiste, contacta al equipo de soporte., campos [], id nulo, en listado final false
- **Evidencia:** newman/newman-G051.json; resultado.json; RUN RUN-G051-V1-20261028-032158
- **Análisis:** Hipótesis local (no causa confirmada en TEST): el DTO y normalizador UTC no rechazan futuro (registrar_version_modelo_dto.py:45; src/shared/fechas.py:33-40); el use case guarda el archivo antes del INSERT (registrar_version_modelo_use_case.py:105-155), el trigger rechaza fecha futura con P0408 (alembic/baseline/esquema_baseline.sql:10642-10654) y ese código no figura en src/shared/db_error_translator.py:255-283, cuyo caso residual devuelve ERROR_INTERNO (:432-435). Puede quedar un ONNX huérfano; no se verificó el disco de TEST.
- **Impacto:** RF-71 no puede distinguir un dato inválido de una caída; probablemente queda un archivo ONNX huérfano, sin verificación del disco de TEST.
- **Cierre:** Traducir P0408 a HTTP 422 E2 identificando fecha_entrenamiento, o validar antes del guardado; no guardar el ONNX antes de validar. Reevaluar TC-M04-122 en V2 autorizada.

### INC-M04-G051-VAL400 — Los campos obligatorios vacíos u omitidos del registro de versión se rechazan con HTTP 400 en lugar de 422

- **Casos afectados y equipo inicial:** TC-M04-123, TC-M04-127; Desarrollo. Primera discrepancia comprobada en la API; Desarrollo atiende inicialmente. La causa raíz no está determinada.
- **Severidad y certeza:** BAJA, CONFIRMADA. Los cuatro datos se rechazaron, identificaron el campo y no crearon versión; solo difiere el HTTP 400 del 422 contractual, con impacto menor en clientes como RF-71.
- **Requisito:** RF-69 E2, líneas 2142-2151: HTTP 422 — “Los metadatos del modelo son inválidos o incompletos: [detalle del campo específico].” y “El registro no se crea.” Restricción 8, líneas 1893-1897: “Cada versión debe estar asociada a:”, “hash SHA-256 del dataset de entrenamiento”, “hash SHA-256 del artefacto del modelo” y “No se registran versiones sin ambos hashes.” Matriz G051, subcaso 3: “Las tres HTTP 422 indicando el catálogo admitido”; subcaso 7: “Las tres HTTP 422 sin crear la versión”.
- **Precondiciones:** RUN RUN-G051-V1-20261028-032158 autorizado; catálogo I3P-1 leído; clave interna RF-71; artefacto ONNX y hash real.
- **Pasos:**
  1. Consultar GET /prediccion/modelos?tipo_modelo=MODELO_ESPECIES_GRANDES&limit=100&offset=0 y conservar el total inicial.
  2. Enviar POST /prediccion/modelos multipart con X-RF71-Internal-Key e id_proceso_rf71 único para tipo_modelo vacío (TC-M04-123); repetir omitiendo hash_artefacto_sha256, omitiendo dataset_entrenamiento_hash y omitiendo ambos (TC-M04-127).
  3. Comprobar HTTP, error_code, message y fields en cada respuesta; comparar los procesos RF-71 y el total del listado final con el inicial.
- **Esperado:** HTTP 422 con detalle del campo inválido o incompleto y sin crear versión; para TC-M04-123, indicar el catálogo admitido según la matriz; para TC-M04-127, no registrar sin ambos hashes.
- **Obtenido:** TC-M04-123 tipo vacío: HTTP 400, código VAL_ENTRADA, mensaje Errores de validacion en la solicitud, campos [{"campo":"tipo_modelo","mensaje":"Este campo es obligatorio."}], id nulo, en listado final false; TC-M04-127 sin hash_artefacto_sha256: HTTP 400, código VAL_ENTRADA, mensaje Errores de validacion en la solicitud, campos [{"campo":"hash_artefacto_sha256","mensaje":"Este campo es obligatorio."}], id nulo, en listado final false; TC-M04-127 sin dataset_entrenamiento_hash: HTTP 400, código VAL_ENTRADA, mensaje Errores de validacion en la solicitud, campos [{"campo":"dataset_entrenamiento_hash","mensaje":"Este campo es obligatorio."}], id nulo, en listado final false; TC-M04-127 sin ambos hashes: HTTP 400, código VAL_ENTRADA, mensaje Errores de validacion en la solicitud, campos [{"campo":"hash_artefacto_sha256","mensaje":"Este campo es obligatorio."},{"campo":"dataset_entrenamiento_hash","mensaje":"Este campo es obligatorio."}], id nulo, en listado final false
- **Evidencia:** newman/newman-G051.json; resultado.json; RUN RUN-G051-V1-20261028-032158
- **Análisis:** Hipótesis local, no causa raíz confirmada en TEST: Form(...) obligatorio para los hashes (src/prediction/infrastructure/dto/registrar_version_modelo_dto.py:42-43) y para tipo_modelo (:41), junto al manejador src/shared/error_handlers.py:193-200,298-324, que usa 400 por defecto si la ruta no declara x-codigo-validacion 422; la ruta revisada src/prediction/infrastructure/routers/version_modelo_router.py:47-77 no lo declara.
- **Impacto:** Clientes como RF-71 que distinguen validación por HTTP 422 pueden manejar este rechazo como otra clase de error; los cuatro registros inválidos fueron rechazados y no aparecen en el listado.
- **Cierre:** Declarar HTTP 422 para la validación de esta ruta o tratar los campos vacíos/ausentes en el caso de uso; reevaluar TC-M04-123 y TC-M04-127 en V2 autorizada.

## Incidencias técnicas QA

- **Intento 1, resuelta (`ORD-G051-003`):** `g051.mjs` no cargaba `.env.qa`; el preflight terminó con exit 2 antes de cualquier petición. El resultado fue técnico, sin veredicto de producto.
- **Intento 2, resuelta (`ORD-G051-005`):** Newman detenía los subcasos independientes después del HTTP 500 de la fecha futura. El ejecutor se ajustó para conservar ese 500 como observación de 122 y continuar los demás casos. El HTTP 500 es discrepancia de producto confirmada en el intento 3; la detención prematura era un problema de automatización QA.

Sin problemas técnicos observados en el intento 3. Las hipótesis de código local no demuestran causa raíz en TEST.

## Cierre y rollback

DELETE RUN HTTP 200. Respuesta de cierre del sandbox recibida; no se verificó por consulta posterior la reversión de BD: Sandbox confirmó cierre; no hay consulta posterior de BD. Los archivos en MODELOS_STORAGE_PATH, posibles respaldos RF-73 y el correo no son revertidos por el sandbox; su eliminación o entrega no se verificó.

## Evidencias

- preflight.json
- newman/newman-G051.json
- newman/newman-G051.html
- TC-M04-G051_resultado.md
- resultado.json

## Revisión QA

2026-10-28; orquestador QA: reescritura con formato acordado; unificación de incidencias por causa; sin cambio de veredictos.

2026-10-28; `ORD-G051-008`: síntesis de los tres intentos y eliminación autorizada de la evidencia nativa de los dos RUN técnicos; sin cambio de veredictos ni de evidencias del RUN oficial.

## Conclusión y acción

RECHAZADO. Corrección de INC-M04-G051-122 e INC-M04-G051-VAL400 por Desarrollo y reevaluación V2 de 122, 123, 127.
