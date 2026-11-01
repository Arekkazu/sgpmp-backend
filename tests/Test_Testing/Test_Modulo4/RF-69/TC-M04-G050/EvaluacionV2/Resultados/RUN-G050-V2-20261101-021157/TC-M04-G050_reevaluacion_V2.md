# TC-M04-G050 — APROBADO

## Decisión del caso

Caso agrupado TC-M04-G050 (RF-69); originales TC-M04-118, TC-M04-119 y TC-M04-120. Decisión: APROBADO. Motivo: Los tres casos cumplen sus oráculos de formato y tipos por API.

| Caso | Comprobación | Decisión | Motivo breve |
|---|---|---|---|
| TC-M04-118 | API-118-01 | APROBADO | POST 201; POST si incluye formato/hash y GET ONNX con hash SHA-256 fiel |
| TC-M04-119 | API-119-01 | APROBADO | POST 201; POST si incluye formato/hash y GET TENSORFLOW_SAVED_MODEL con hash SHA-256 fiel |
| TC-M04-120 | API-120-01 | APROBADO | Seis tipos con POST 201 y GET 200, IDs propios, paradigmas, componentes y métricas independientes |

RUN oficial: sí (registro QA OFICIAL, DELETE 200, rollback confirmado).

Qué falta: Ninguna comprobación pendiente en este RUN.

## Detalle por caso

### TC-M04-118 — APROBADO

**Qué se hizo:** Como servicio interno RF-71, sin actor humano, se envió POST /prediccion/modelos con archivo ONNX, tipo especies grandes, paradigma individual, hash SHA-256 7004471518983d131c924f96a30662bb4bf5e1324321ed60aacbd3c452e30fd9, F1 0.91 y recall 0.93; se consultó GET /prediccion/modelos/131 (ID 131).  
**Qué se esperaba:** “Registro completo con formato identificado como ONNX” (resultado esperado de TC-M04-118; RF-69, restricción 2, línea 1873, y fase 1, líneas 1993-1995).  
**Qué se observó:** POST HTTP 201, ID 131, estado APROBADO y formato ONNX; GET HTTP 200, formato ONNX, hash 7004471518983d131c924f96a30662bb4bf5e1324321ed60aacbd3c452e30fd9 (igual al enviado).  
**Por qué APROBADO:** El registro y la consulta se completaron; el formato fue ONNX y el hash coincidió con el archivo enviado.

### TC-M04-119 — APROBADO

**Qué se hizo:** Como servicio interno RF-71, sin actor humano, se envió POST /prediccion/modelos con saved_model.pb, tipo especies medianas, paradigma individual, hash SHA-256 6f76bdabbc9789b1ae227386e90a2cfc46343f657ec98098390a766691f90bd0, F1 0.91 y recall 0.93; se consultó GET /prediccion/modelos/132 (ID 132).  
**Qué se esperaba:** “Registro completo con formato identificado como TensorFlow SavedModel” (resultado esperado de TC-M04-119; RF-69, restricción 2, línea 1873, y fase 1, líneas 1993-1995; identificación por estructura binaria del archivo).  
**Qué se observó:** POST HTTP 201, ID 132, estado APROBADO y formato TENSORFLOW_SAVED_MODEL; GET HTTP 200, formato TENSORFLOW_SAVED_MODEL, hash 6f76bdabbc9789b1ae227386e90a2cfc46343f657ec98098390a766691f90bd0 (igual al enviado).  
**Por qué APROBADO:** El registro y la consulta se completaron; el formato fue TensorFlow SavedModel y el hash coincidió con el archivo enviado.

### TC-M04-120 — APROBADO

**Qué se hizo:** Como servicio interno RF-71, sin actor humano, se enviaron 6 POST para especies grandes en ONNX (ID 131), especies medianas en TensorFlow SavedModel (ID 132), riesgo contagio en ONNX (ID 133), aves en ONNX (ID 134), porcinos en ONNX (ID 135), acuicultura en ONNX (ID 136); los tipos individual y meta llevaron F1 0,91 y recall 0,93, y aves con componente detector, porcinos con componente seguimiento, acuicultura con componente anomalias llevaron calibración completa, falsos positivos 0,02 y detección 0,96; se consultaron los IDs recibidos por GET.  
**Qué se esperaba:** “Los seis registros se completan y cada tipo se gestiona de forma independiente” (resultado esperado de TC-M04-120; RF-69, actualización RFC-009, línea 1784, y enumerado de seis tipos, líneas 383-389).  
**Qué se observó:** especies grandes: POST HTTP 201, GET HTTP 200, ID 131, estado APROBADO, paradigma INDIVIDUAL, componente ninguno; especies medianas: POST HTTP 201, GET HTTP 200, ID 132, estado APROBADO, paradigma INDIVIDUAL, componente ninguno; riesgo contagio: POST HTTP 201, GET HTTP 200, ID 133, estado APROBADO, paradigma META, componente ninguno; aves: POST HTTP 201, GET HTTP 200, ID 134, estado APROBADO, paradigma POBLACIONAL, componente DETECTOR; porcinos: POST HTTP 201, GET HTTP 200, ID 135, estado APROBADO, paradigma POBLACIONAL, componente SEGUIMIENTO; acuicultura: POST HTTP 201, GET HTTP 200, ID 136, estado APROBADO, paradigma POBLACIONAL, componente ANOMALIAS. En los GET poblacionales constan calibración completa, falsos positivos 0.02 y detección 0.96.  
**Por qué APROBADO:** Los seis tipos tuvieron POST 201 y GET 200 con IDs propios; coincidieron tipo, paradigma, componente y métricas de cada registro.

## Comparación V1 → V2

Referencia V1: RUN-G050-V1-20261028-005856, resultado oficial; corrección informada por Desarrollo en issue #819 / PR #864: detección de SavedModel por estructura protobuf. El despliegue en TEST se decide con este RUN.

| Caso | V1 | V2 | Cambio |
|---|---|---|---|
| TC-M04-118 | APROBADO: ONNX, hash fiel | APROBADO: POST 201; POST si incluye formato/hash y GET ONNX con hash SHA-256 fiel | Regresión ONNX |
| TC-M04-119 | RECHAZADO: SavedModel identificado como ONNX; INC-M04-G050-119 | APROBADO: POST 201; POST si incluye formato/hash y GET TENSORFLOW_SAVED_MODEL con hash SHA-256 fiel | INC-M04-G050-119 CORREGIDA en este RUN |
| TC-M04-120 | APROBADO: seis tipos independientes | APROBADO: Seis tipos con POST 201 y GET 200, IDs propios, paradigmas, componentes y métricas independientes | Regresión de tipos RFC-009 |

## Identificación

Grupo G050; casos TC-M04-118, TC-M04-119 y TC-M04-120; RF-69 v2.1; versión V2; RUN RUN-G050-V2-20261101-021157; ambiente TEST; autorización AUT-G050-V2-20261101; código local consultado: src/prediction/application/use_cases/versiones_modelo/registrar_version_modelo_use_case.py:88-93,303-327; commit y despliegue en TEST no verificados; Newman 6.2.2; Cypress no requerido (solo API).

## Esperado vs observado por caso

- **TC-M04-118 / API-118-01:** Esperado del caso: “Registro completo con formato identificado como ONNX”. Observado: POST 201, GET 200, formato_artefacto ONNX, hash fiel. Decisión APROBADO.
- **TC-M04-119 / API-119-01:** Esperado del caso: “Registro completo con formato identificado como TensorFlow SavedModel”. Observado: POST 201, id 132, estado APROBADO; GET 200, formato_artefacto TENSORFLOW_SAVED_MODEL, hash fiel al enviado. Decisión APROBADO.
- **TC-M04-120 / API-120-01:** Esperado del caso: “Los seis registros se completan y cada tipo se gestiona de forma independiente”. Observado: 6 POST 201 y 6 GET 200 de los seis tipos; paradigmas, componentes y métricas detallados abajo. Decisión APROBADO.

| Versión y tipo | ID | Artefacto enviado; paradigma; componente | HTTP POST / GET | POST / GET observado: formato; paradigma; componente; estado | Hash GET | Métricas GET |
|---|---|---|---|---|---|---|
| V1 MODELO_ESPECIES_GRANDES | 131 | ONNX; INDIVIDUAL; sin componente | 201 / 200 | ONNX / ONNX; INDIVIDUAL; nulo; APROBADO | 7004471518983d131c924f96a30662bb4bf5e1324321ed60aacbd3c452e30fd9 | f1 0.9100, recall 0.9300 |
| V2 MODELO_ESPECIES_MEDIANAS | 132 | TENSORFLOW_SAVED_MODEL; INDIVIDUAL; sin componente | 201 / 200 | TENSORFLOW_SAVED_MODEL / TENSORFLOW_SAVED_MODEL; INDIVIDUAL; nulo; APROBADO | 6f76bdabbc9789b1ae227386e90a2cfc46343f657ec98098390a766691f90bd0 | f1 0.9100, recall 0.9300 |
| V3 MODELO_RIESGO_CONTAGIO | 133 | ONNX; META; sin componente | 201 / 200 | ONNX / ONNX; META; nulo; APROBADO | 7004471518983d131c924f96a30662bb4bf5e1324321ed60aacbd3c452e30fd9 | f1 0.9100, recall 0.9300 |
| V4 MODELO_AVES | 134 | ONNX; POBLACIONAL; DETECTOR | 201 / 200 | ONNX / ONNX; POBLACIONAL; DETECTOR; APROBADO | 7004471518983d131c924f96a30662bb4bf5e1324321ed60aacbd3c452e30fd9 | calibración true, FP 0.02, detección 0.96 |
| V5 MODELO_PORCINOS | 135 | ONNX; POBLACIONAL; SEGUIMIENTO | 201 / 200 | ONNX / ONNX; POBLACIONAL; SEGUIMIENTO; APROBADO | 7004471518983d131c924f96a30662bb4bf5e1324321ed60aacbd3c452e30fd9 | calibración true, FP 0.02, detección 0.96 |
| V6 MODELO_ACUICULTURA | 136 | ONNX; POBLACIONAL; ANOMALIAS | 201 / 200 | ONNX / ONNX; POBLACIONAL; ANOMALIAS; APROBADO | 7004471518983d131c924f96a30662bb4bf5e1324321ed60aacbd3c452e30fd9 | calibración true, FP 0.02, detección 0.96 |

## Observaciones

Se envió saved_model.pb como binario único porque el API admite un único archivo_modelo; no se comprobó la carga del directorio SavedModel en un runtime TensorFlow. Los hashes enviados y consultados constan en resultado.json y Newman JSON. El formato de cada versión figura en la tabla como dato observado; el formato del artefacto se evalúa en TC-M04-119 y no afecta al veredicto de TC-M04-120. V2b no fue necesario porque V2 se registró; API-120-01 usa V2 para MEDIANAS. Para POBLACIONAL, el código local consultado solo usa calibracion_completada para aprobar; no define umbral de aprobación para las tasas 0.02 y 0.96.

## Incidencias de producto

Sin incidencias de producto confirmadas.

## Problemas técnicos y análisis

Sin problemas técnicos observados. La hipótesis de código local no demuestra la causa raíz en TEST.

## Cierre y rollback

DELETE RUN HTTP 200. Cierre de la transacción externa confirmado: Transacción externa cerrada; archivos y respaldo local fuera de rollback. La eliminación de archivos en MODELOS_STORAGE_PATH y de posibles respaldos RF-73 no se verificó.

## Revisión QA

Informe generado desde las comprobaciones y respuestas de este RUN; sin revisión posterior registrada.

## Evidencias

- preflight.json
- newman/newman-G050.json
- newman/newman-G050.html
- TC-M04-G050_reevaluacion_V2.md
- resultado.json

## Conclusión y acción

APROBADO. Acción pendiente: Ninguna comprobación pendiente en este RUN.
