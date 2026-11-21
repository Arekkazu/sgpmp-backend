# TC-M04-G050 — preparación local RF-69

## Reevaluación V2 preparada (ORD-G050-007)

El RUN V1 oficial `RUN-G050-V1-20261028-005856` rechazó TC-M04-119 porque la API registró `saved_model.pb` como ONNX; TC-M04-118 y TC-M04-120 aprobaron. Desarrollo informó la corrección por estructura protobuf en issue #819 / PR #864. El despliegue en TEST queda por comprobar en un RUN V2 autorizado por el lanzador externo. Esta preparación no accedió a TEST ni creó RUN.

El oráculo V2 exige POST 201 y GET 200, formato ONNX para 118 y `TENSORFLOW_SAVED_MODEL` para 119, con SHA-256 fiel; si el POST incluye formato o hash, también se comparan. Para 120 se comprueban los seis tipos RFC-009 con POST 201, GET 200, ID propio, tipo, paradigma, componente y métricas. El formato de cada versión queda como dato observado en la tabla del informe y se evalúa en 119, sin afectar el veredicto de 120. El informe V2 se genera solo dentro de `EvaluacionV2/Resultados/RUN-G050-V2-<timestamp>/TC-M04-G050_reevaluacion_V2.md`, con comparación V1 → V2 y referencia a issue #819 / PR #864. Si 119 aprueba, se registra `INC-M04-G050-119 CORREGIDA` en ese RUN. El archivo `saved_model.pb` se valida como binario; esta prueba no carga un directorio en un runtime TensorFlow.

Las pruebas locales replican la detección del backend consultado en `src/prediction/application/use_cases/versiones_modelo/registrar_version_modelo_use_case.py:88-93,303-327`: solo campos protobuf 1 y 2, con el primer `meta_graphs` empezando por `0x0a`. El ensayo loopback incluye `v2_corregido`, `v2_defecto` y el modo histórico `tf_como_onnx`; no representa evidencia de TEST. Se conservan la colección, los dos artefactos y el presupuesto de 18 solicitudes.

## Contexto de preparación V1

Orden `ORD-G050-001` y `ORD-G050-002`, fase `preparar`. Casos TC-M04-118, TC-M04-119 y TC-M04-120, solo API. La carpeta contenía únicamente `.gitkeep`; no había ejecutor, colección, spec, módulos, tests, scripts, README, dependencias ni evidencias que consolidar. Quedan un ejecutor canónico (`g050.mjs`) y una colección Newman (`G050.postman_collection.json`). Cypress no aplica porque la matriz indica solo API. No se creó RUN ni informe en esta fase.

## Oráculos y requisito

Fuente vigente: `tests/Test_Testing/Test_Modulo4/Actualizacion_Matriz_RF69_RF72/Casos_Prueba(Mod4Agrupfinal)_actualizada.csv`, fila `TC-M04-G050`, Windows-1252, separador `;`. Conserva estos resultados esperados: “Registro completo con formato identificado como ONNX”; “Registro completo con formato identificado como TensorFlow SavedModel”; “Los seis registros se completan y cada tipo se gestiona de forma independiente”. La nota de TC-M04-119 exige detectar por firma binaria y no por extensión. RF: `tests/Test_Testing/Requerimientos/Especificacion-Requerimientos-Modulo4 (1).md`, RF-69 Restricción 2, líneas 1872–1873; entrada archivo_modelo, 1960; verificación de formato, 1993–1995; RNF-09, 2390–2392; RFC-009, 1784; RF-65, 381–390 y 486–487.

| Caso | Comprobación API |
|---|---|
| TC-M04-118 | API-118-01: POST ONNX 201; GET con `formato_artefacto=ONNX` y hash igual al enviado. |
| TC-M04-119 | API-119-01: POST `saved_model.pb` real 201; GET con `formato_artefacto=TENSORFLOW_SAVED_MODEL` y hash igual. HTTP 422 o identificación ONNX rechaza el caso solo en un RUN TEST autorizado. |
| TC-M04-120 | API-120-01: seis tipos registrados y consultados con tipo, paradigma, componente y métricas fieles. Si V2 SavedModel se rechaza por artefacto, V2b registra MEDIANAS con ONNX y un nuevo UUID; solo V2b representa MEDIANAS en este caso. |

## Artefactos deterministas

`artefactos/g050.onnx` (84 bytes, inicio `08 09 12 07 71 61 2d 67`) es ModelProto con grafo Identity FLOAT[1], opset 19; SHA-256 `7004471518983d131c924f96a30662bb4bf5e1324321ed60aacbd3c452e30fd9`. `artefactos/saved_model.pb` (155 bytes, inicio `08 01 12 96 01 0a 07 22`) es SavedModel protobuf con `saved_model_schema_version=1` (campo 1, wire 0) y `meta_graphs` (campo 2, wire 2). El MetaGraphDef lleva `MetaInfoDef.tags=['serve']`, un GraphDef Placeholder→Identity FLOAT y `signature_def['serving_default']` con entrada `x:0`, salida `y:0` y método `tensorflow/serving/predict`; SHA-256 `6f76bdabbc9789b1ae227386e90a2cfc46343f657ec98098390a766691f90bd0`. Los campos siguen `tensorflow/core/protobuf/saved_model.proto` y `tensorflow/core/protobuf/meta_graph.proto`; el codificador y lector de campos están en `lib/artefactos.mjs`. La regresión verifica estructura y bytes sin TensorFlow ni descargas. No se añadió `0a` artificial al inicio. El API admite un solo binario `archivo_modelo`, por lo que se envía `saved_model.pb` sin directorio SavedModel; esta limitación se documenta como observación del caso. No se ha hecho una carga en un runtime TensorFlow.

## Flujo y contrato

`node g050.mjs --capacidades` publica `sigab-qa-ejecutor/1`, contexto canónico `contexto_operacion.json` y las tres comprobaciones API sin UI. `node g050.mjs --comprobar` valida sin red, RUN ni lectura de `.env.qa`. En evaluación futura, solo el lanzador inyecta `QA_AUTORIZADO=SI` y argumentos `--operacion --version --intento --run-id --autorizacion --contexto`. El login Administrador ocurre antes del RUN; dentro se consulta una variable activa I3P-1, se ejecutan V1 GRANDES ONNX, V2 MEDIANAS SavedModel, V3 RIESGO_CONTAGIO ONNX, V4 AVES ONNX DETECTOR, V5 PORCINOS ONNX SEGUIMIENTO y V6 ACUICULTURA ONNX ANOMALIAS; cada POST va seguido de GET por id cuando el registro produce uno. Solo si V2 se rechaza por formato o artefacto sin id, se ejecutan POST y GET V2b MEDIANAS ONNX con un nuevo `id_proceso_rf71`; API-119-01 permanece sobre V2 SavedModel y API-120-01 usa V2b. El cierre usa DELETE del RUN. No hay dependencia entre los seis tipos; 403 por clave detiene sin reintentar, 5xx bloquea y sin respuesta queda no concluyente.

INDIVIDUAL/META llevan siete métricas (`f1_score_global=0.91`, `recall_clase_riesgo_alto=0.93`, precisión, accuracy, ROC AUC, recall por clase y matriz). POBLACIONAL lleva `calibracion_completada=true`, tasa de falsos positivos 0.02 y tasa de detección 0.96; además se envían f1 y recall. El dominio de `origin/test` exige f1 ≥ 0.80 y recall ≥ 0.85 para INDIVIDUAL/META. Para POBLACIONAL solo la calibración completa determina APROBADO; las tasas deben ser numéricas en `[0,1]`, sin umbrales de aprobación definidos. Así se evita un RECHAZADO previsto y su correo.

Presupuesto único: hasta **2 logins antes del RUN + 1 catálogo + 7 POST + 7 GET + 1 DELETE = 18 solicitudes**, máximo 600 s. El séptimo POST/GET solo ocurre por rechazo de artefacto de V2. Newman usa CLI JS por `process.execPath`, verifica `--version` en 30 s y genera JSON saneado y HTML propio. El fallback API local solo aplica si `spawn` falla con EPERM en el ensayo loopback. `RF71_INTERNAL_KEY` se usa por nombre y como cabecera, nunca como valor en salida; tampoco se conservan token, password o secreto de sandbox. Se guarda un Markdown oficial, `resultado.json`, `preflight.json` y `newman/` solo dentro del RUN que cree el lanzador: V1 `Resultados/RUN-G050-V1-<fecha>-<hora>/`, V2 `EvaluacionV2/Resultados/RUN-G050-V2-<fecha>-<hora>/`.

## Código consultado en lectura (`origin/test`, daefc3a5)

| Hecho | Archivo:líneas |
|---|---|
| Taxonomía y componentes RFC-009 | `src/shared/tipo_modelo.py:19-47` |
| DTO multipart: JSON, proceso UUID, archivo y componente | `src/prediction/infrastructure/dto/registrar_version_modelo_dto.py:41-63` |
| Schema GET expone formato, paradigma, componente, métricas poblacionales y hash | `src/prediction/infrastructure/schema/version_modelo_schema.py:14-25,47-54` |
| POST con cabecera interna y GET por id | `src/prediction/infrastructure/routers/version_modelo_router.py:47-77,112-138` |
| Detección por primer byte `08→ONNX`, `0a→TF` | `src/prediction/application/use_cases/versiones_modelo/registrar_version_modelo_use_case.py:40-41,250-270` |
| Validación de tasas y componente | mismo use case `:340-380`; POBLACIONAL se ramifica en `:93-99` |
| Umbrales INDIVIDUAL/META y ausencia de umbral de tasas POBLACIONAL | `src/prediction/domain/entities/version_modelo.py:16-17,127-142` |
| Almacenamiento fuera de BD y aviso tras RECHAZADO | use case `:104-110,181-189,404-413` |
| Respaldo local RF-73 ante falla de persistencia | `src/prediction/infrastructure/repositories/evento_auditoria_m04_repository.py:260-317` |
| Sandbox de sesión con savepoints y rollback externo | `src/shared/rollback/infraestructure/testing_sandbox.py:47-79` |

**Hallazgo de preparación V1, posteriormente confirmado en el RUN oficial:** el `saved_model.pb` válido comienza `08 01` porque `saved_model_schema_version` es varint. El código local revisado en esa preparación interpretaba cualquier primer byte `08` como ONNX. La discrepancia se acreditó después por API en `RUN-G050-V1-20261028-005856`; la lectura de código y el ensayo loopback por sí solos no constituyeron ese rechazo.

## Efectos que requiere documentar el lanzador antes de TEST

Se registrarían hasta siete versiones y eventos sujetos al rollback de la transacción externa si TEST usa el código consultado y envía las cabeceras del RUN. Se escribirían hasta siete archivos de artefacto ONNX/PB en `MODELOS_STORAGE_PATH`, **no revertidos por el sandbox**. RF-73 puede escribir respaldo local si falla la persistencia. El login anterior al RUN puede dejar sesión o auditoría. No se espera correo de versión rechazada con estas métricas y clave correcta; si se rechaza una versión, el use case intenta avisar. DELETE 200 cierra la transacción externa, sin demostrar borrado de archivos ni de respaldo. Esta preparación no ejecutó TEST ni creó RUN.

## Validación local

Ejecutar `node pruebas/g050.test.mjs`, `node g050.mjs --capacidades`, `node g050.mjs --comprobar` y `node pruebas/g050_ensayo.mjs`. El ensayo usa diez modos loopback; guarda su contexto y resultados temporales fuera del grupo y los elimina al concluir. Verifica `resultado.json`, informe simulado, registro QA, presupuesto y ausencia de secretos. La etiqueta OFICIAL del ensayo significa clasificación del emulador local; no es un veredicto de TEST.
