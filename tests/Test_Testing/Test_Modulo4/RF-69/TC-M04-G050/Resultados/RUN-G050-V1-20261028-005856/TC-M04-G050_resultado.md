# TC-M04-G050 — RECHAZADO

## Decisión del caso

Caso agrupado TC-M04-G050 (RF-69); originales TC-M04-118, TC-M04-119 y TC-M04-120. Decisión: RECHAZADO. Motivo: TC-M04-119: el SavedModel válido se registra con formato ONNX; ONNX y los seis tipos de RFC-009 se registran correctamente.

| Caso | Comprobación | Decisión | Motivo breve |
|---|---|---|---|
| TC-M04-118 | API-118-01 | APROBADO | POST 201; GET ONNX y hash SHA-256 fiel |
| TC-M04-119 | API-119-01 | RECHAZADO | formato_artefacto ONNX en lugar de TENSORFLOW_SAVED_MODEL; hash fiel |
| TC-M04-120 | API-120-01 | APROBADO | Seis tipos con POST 201 y GET, paradigmas, componentes y métricas independientes |

RUN oficial: sí (registro QA OFICIAL, DELETE 200, rollback confirmado).

Qué falta: corrección de INC-M04-G050-119 por Desarrollo y reevaluación V2 autorizada de TC-M04-119.

## Detalle por caso

### TC-M04-118 — APROBADO

**Qué se hizo:** Como servicio interno RF-71, sin actor humano, se envió POST /prediccion/modelos con archivo ONNX, tipo especies grandes, paradigma individual, hash SHA-256 7004471518983d131c924f96a30662bb4bf5e1324321ed60aacbd3c452e30fd9, F1 0.91 y recall 0.93; se consultó GET /prediccion/modelos/61 (ID 61).  
**Qué se esperaba:** “Registro completo con formato identificado como ONNX” (matriz G050, TC-M04-118; RF-69, restricción 2, línea 1873, y fase 1, líneas 1993-1995).  
**Qué se observó:** POST HTTP 201, ID 61 y estado APROBADO; GET HTTP 200, formato ONNX, hash 7004471518983d131c924f96a30662bb4bf5e1324321ed60aacbd3c452e30fd9 (igual al enviado).  
**Por qué APROBADO:** El registro y la consulta se completaron; el formato fue ONNX y el hash coincidió con el archivo enviado.

### TC-M04-119 — RECHAZADO

**Qué se hizo:** Como servicio interno RF-71, sin actor humano, se envió POST /prediccion/modelos con saved_model.pb, tipo especies medianas, paradigma individual, hash SHA-256 6f76bdabbc9789b1ae227386e90a2cfc46343f657ec98098390a766691f90bd0, F1 0.91 y recall 0.93; se consultó GET /prediccion/modelos/62 (ID 62).  
**Qué se esperaba:** “Registro completo con formato identificado como TensorFlow SavedModel” (matriz G050, TC-M04-119; RF-69, restricción 2, línea 1873, y fase 1, líneas 1993-1995; la matriz exige identificar la firma binaria, no la extensión).  
**Qué se observó:** POST HTTP 201, ID 62 y estado APROBADO; GET HTTP 200, formato ONNX, hash 6f76bdabbc9789b1ae227386e90a2cfc46343f657ec98098390a766691f90bd0 (igual al enviado).  
**Por qué RECHAZADO:** Se exigía TensorFlow SavedModel y se obtuvo ONNX en GET HTTP 200 tras POST HTTP 201; el hash sí coincidió. Incidencia INC-M04-G050-119.

### TC-M04-120 — APROBADO

**Qué se hizo:** Como servicio interno RF-71, sin actor humano, se enviaron 6 POST para especies grandes en ONNX (ID 61), especies medianas en TensorFlow SavedModel (ID 62), riesgo contagio en ONNX (ID 63), aves en ONNX (ID 64), porcinos en ONNX (ID 65), acuicultura en ONNX (ID 66); los tipos individual y meta llevaron F1 0,91 y recall 0,93, y aves con componente detector, porcinos con componente seguimiento, acuicultura con componente anomalias llevaron calibración completa, falsos positivos 0,02 y detección 0,96; se consultaron los IDs recibidos por GET.  
**Qué se esperaba:** “Los seis registros se completan y cada tipo se gestiona de forma independiente” (matriz G050, TC-M04-120; RF-69, actualización RFC-009, línea 1784, y enumerado de seis tipos, líneas 383-389).  
**Qué se observó:** especies grandes: POST HTTP 201, GET HTTP 200, ID 61, estado APROBADO, paradigma INDIVIDUAL, componente ninguno; especies medianas: POST HTTP 201, GET HTTP 200, ID 62, estado APROBADO, paradigma INDIVIDUAL, componente ninguno; riesgo contagio: POST HTTP 201, GET HTTP 200, ID 63, estado APROBADO, paradigma META, componente ninguno; aves: POST HTTP 201, GET HTTP 200, ID 64, estado APROBADO, paradigma POBLACIONAL, componente DETECTOR; porcinos: POST HTTP 201, GET HTTP 200, ID 65, estado APROBADO, paradigma POBLACIONAL, componente SEGUIMIENTO; acuicultura: POST HTTP 201, GET HTTP 200, ID 66, estado APROBADO, paradigma POBLACIONAL, componente ANOMALIAS. En los GET poblacionales constan calibración completa, falsos positivos 0.02 y detección 0.96.  
**Por qué APROBADO:** Los seis tipos tuvieron POST 201 y GET 200 con IDs propios; coincidieron tipo, paradigma, componente y métricas de cada registro.

## Identificación

Grupo G050; casos TC-M04-118, TC-M04-119 y TC-M04-120; RF-69 v2.1; versión V1; RUN RUN-G050-V1-20261028-005856; ambiente TEST; autorización AUT-G050-V1-20261028; referencia de código origin/test daefc3a5 (despliegue no verificado); Newman 6.2.2; Cypress no requerido (solo API).

## Esperado vs observado por caso

- **TC-M04-118 / API-118-01:** Esperado de matriz: “Registro completo con formato identificado como ONNX”. Observado: POST 201, GET 200, formato_artefacto ONNX, hash fiel. Decisión APROBADO.
- **TC-M04-119 / API-119-01:** Esperado de matriz: “Registro completo con formato identificado como TensorFlow SavedModel”. Observado: POST 201, id 62, estado APROBADO; GET 200, formato_artefacto ONNX, hash fiel al enviado. Decisión RECHAZADO.
- **TC-M04-120 / API-120-01:** Esperado de matriz: “Los seis registros se completan y cada tipo se gestiona de forma independiente”. Observado: 6 POST 201 y 6 GET 200 de los seis tipos; paradigmas, componentes y métricas detallados abajo. Decisión APROBADO.

| Versión y tipo | ID | Esperado | HTTP POST / GET | GET observado: formato; paradigma; componente; estado | Hash GET | Métricas GET |
|---|---|---|---|---|---|---|
| V1 MODELO_ESPECIES_GRANDES | 61 | ONNX; INDIVIDUAL; sin componente | 201 / 200 | ONNX; INDIVIDUAL; nulo; APROBADO | 7004471518983d131c924f96a30662bb4bf5e1324321ed60aacbd3c452e30fd9 | f1 0.9100, recall 0.9300 |
| V2 MODELO_ESPECIES_MEDIANAS | 62 | TENSORFLOW_SAVED_MODEL; INDIVIDUAL; sin componente | 201 / 200 | ONNX; INDIVIDUAL; nulo; APROBADO | 6f76bdabbc9789b1ae227386e90a2cfc46343f657ec98098390a766691f90bd0 | f1 0.9100, recall 0.9300 |
| V3 MODELO_RIESGO_CONTAGIO | 63 | ONNX; META; sin componente | 201 / 200 | ONNX; META; nulo; APROBADO | 7004471518983d131c924f96a30662bb4bf5e1324321ed60aacbd3c452e30fd9 | f1 0.9100, recall 0.9300 |
| V4 MODELO_AVES | 64 | ONNX; POBLACIONAL; DETECTOR | 201 / 200 | ONNX; POBLACIONAL; DETECTOR; APROBADO | 7004471518983d131c924f96a30662bb4bf5e1324321ed60aacbd3c452e30fd9 | calibración true, FP 0.02, detección 0.96 |
| V5 MODELO_PORCINOS | 65 | ONNX; POBLACIONAL; SEGUIMIENTO | 201 / 200 | ONNX; POBLACIONAL; SEGUIMIENTO; APROBADO | 7004471518983d131c924f96a30662bb4bf5e1324321ed60aacbd3c452e30fd9 | calibración true, FP 0.02, detección 0.96 |
| V6 MODELO_ACUICULTURA | 66 | ONNX; POBLACIONAL; ANOMALIAS | 201 / 200 | ONNX; POBLACIONAL; ANOMALIAS; APROBADO | 7004471518983d131c924f96a30662bb4bf5e1324321ed60aacbd3c452e30fd9 | calibración true, FP 0.02, detección 0.96 |

## Observaciones

Se envió saved_model.pb como binario único porque el API admite un único archivo_modelo; no se comprobó la carga del directorio SavedModel en un runtime TensorFlow. Los hashes enviados y consultados constan en resultado.json y Newman JSON. V2b no fue necesario porque V2 se registró; API-120-01 usa V2 para MEDIANAS. Para POBLACIONAL, el código origin/test consultado solo usa calibracion_completada para aprobar; no define umbral de aprobación para las tasas 0.02 y 0.96.

## Incidencias de producto

### INC-M04-G050-119 — Un TensorFlow SavedModel válido se registra con formato ONNX

- **Caso y equipo inicial:** TC-M04-119; Desarrollo. La primera discrepancia está comprobada en POST/GET de la API pública; Desarrollo es el primer equipo de atención. La causa raíz en TEST no está demostrada.
- **Severidad y certeza:** MEDIA, CONFIRMADA. El registro se completa y el hash es fiel, pero el metadato de formato es incorrecto. Los consumidores que dependan del formato (RF-66 al ejecutar y RF-70 al distribuir al Edge) podrían cargar el artefacto con el runtime equivocado; no bloquea el registro.
- **Requisito:** RF-69, Restricción 2, línea 1873: “Solo se aceptan artefactos en formato ONNX o TensorFlow SavedModel.” Fase 1, líneas 1993-1995: “El sistema verifica que el formato del artefacto sea ONNX o TensorFlow SavedModel. Si el formato es inválido → E1.” RNF-09, línea 2391: “Solo ONNX y TensorFlow SavedModel.” Matriz G050, nota de TC-M04-119: “la detección se basa en la firma binaria del archivo, no en su extensión”.
- **Precondiciones:** RUN RUN-G050-V1-20261028-005856 autorizado; clave RF-71 válida; catálogo I3P-1; saved_model.pb de 155 bytes construido según tensorflow/core/protobuf/saved_model.proto, con saved_model_schema_version=1 y MetaGraph “serve”; hash SHA-256 6f76bdabbc9789b1ae227386e90a2cfc46343f657ec98098390a766691f90bd0.
- **Pasos:**
  1. En el RUN autorizado, enviar POST /prediccion/modelos multipart con archivo_modelo=saved_model.pb, tipo_modelo=MODELO_ESPECIES_MEDIANAS, hash_artefacto_sha256=6f76bdabbc9789b1ae227386e90a2cfc46343f657ec98098390a766691f90bd0 y cabecera X-RF71-Internal-Key.
  2. Consultar GET /prediccion/modelos/62 y comparar formato_artefacto y hash_artefacto_sha256 con el archivo enviado.
- **Esperado:** POST 201 y GET 200 con formato_artefacto TENSORFLOW_SAVED_MODEL y hash SHA-256 igual al enviado
- **Obtenido:** POST 201, id 62, estado APROBADO; GET 200, formato_artefacto ONNX, hash 6f76bdabbc9789b1ae227386e90a2cfc46343f657ec98098390a766691f90bd0 igual al enviado 6f76bdabbc9789b1ae227386e90a2cfc46343f657ec98098390a766691f90bd0; primeros bytes 08 01 12 96.
- **Evidencia:** newman/newman-G050.json; resultado.json; RUN RUN-G050-V1-20261028-005856
- **Análisis:** La API demuestra la discrepancia de formato. Hipótesis a comprobar: en origin/test, registrar_version_modelo_use_case.py:250-270 decide por el primer byte (0x08 → ONNX; 0x0a → TensorFlow). Un SavedModel real empieza con 0x08 porque el campo 1 saved_model_schema_version es varint, igual que el campo inicial de ModelProto ONNX. Esa lectura local no confirma la causa raíz en TEST.
- **Impacto:** Los consumidores que seleccionan runtime por formato (RF-66 y RF-70) podrían elegir ONNX para un SavedModel; además, un SavedModel podría guardarse con extensión .onnx. Impacto potencial, no observado en este RUN.
- **Cierre:** Identificar el formato por la estructura del mensaje y no por el primer byte, o recibir el formato declarado y validarlo contra la estructura; después, reevaluación V2 autorizada de TC-M04-119.

## Problemas técnicos y análisis

Sin problemas técnicos observados. La hipótesis de código local no demuestra la causa raíz en TEST.

## Cierre y rollback

DELETE RUN HTTP 200. Cierre de la transacción externa confirmado: Transacción externa cerrada; archivos y respaldo local fuera de rollback. La eliminación de archivos en MODELOS_STORAGE_PATH y de posibles respaldos RF-73 no se verificó.

## Revisión QA

Fecha 2026-10-28; realizada por orquestador QA. Motivo: reescritura de informe e incidencia según formato acordado; sin cambio de veredictos. Se corrigió la descripción de formato y hash de TC-M04-119 y se completó la incidencia con requisito, datos observados e hipótesis; no se modificaron veredictos ni evidencias.

## Evidencias

- preflight.json
- newman/newman-G050.json
- newman/newman-G050.html
- TC-M04-G050_resultado.md
- resultado.json

## Conclusión y acción

RECHAZADO. Acción pendiente: corrección de INC-M04-G050-119 por Desarrollo y reevaluación V2 autorizada de TC-M04-119.
