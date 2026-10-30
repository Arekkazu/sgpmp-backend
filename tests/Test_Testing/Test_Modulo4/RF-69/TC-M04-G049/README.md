# TC-M04-G049 — preparación local RF-69

Órdenes `ORD-G049-001` y `ORD-G049-004`, fase `preparar`. Grupo G049, casos TC-M04-114 a TC-M04-117. La revisión QA de `RUN-G049-V1-20261027-170142` corrige TC-M04-114 a APROBADO con evidencia TEST ya obtenida; mantiene TC-M04-115 RECHAZADO y TC-M04-116/117 APROBADOS. Esta automatización tiene un ejecutor y una colección; Cypress no aplica porque la orden es solo API.

## Oráculos

Fuente vigente: `tests/Test_Testing/Test_Modulo4/Actualizacion_Matriz_RF69_RF72/Casos_Prueba(Mod4Agrupfinal)_actualizada.csv`, fila `TC-M04-G049`, Windows-1252 y separador `;`. El responsable QA indicó que reemplaza a la matriz original pendiente de actualización. RF: `tests/Test_Testing/Requerimientos/Especificacion-Requerimientos-Modulo4 (1).md`, RF-69 v2.1.

| Caso | Esperado preservado | RF |
|---|---|---|
| TC-M04-114 | “La versión se registra con identificador único y sin intervención humana; su historial muestra el registro inicial en EN_VALIDACION (VERSION_REGISTRADA) seguido del resultado automático (APROBADO o RECHAZADO)” | Fases 1, 3 y 6, líneas 1972-2004, 2030-2043, 2089-2099 |
| TC-M04-115 | “Los tres identificadores son UUID distintos entre sí” | Descripción 1794; Salida 1, 2207 |
| TC-M04-116 | “Se persisten todos los campos de la Salida 1 con notas_validacion en nulo” | Salida 1, 2204-2223; CA-11, 2327-2331 |
| TC-M04-117 | “Con el campo, la relación es consultable; sin él, el registro procede igual” | Entrada `version_referencia`, 1965 |

En API-116-01, `id_version` debe estar presente en el GET y coincidir con el valor devuelto por el POST de V1. Su formato UUID se evalúa en TC-M04-115; si falla, API-116-01 lo registra como observación sin duplicar el rechazo. Los demás metadatos de la Salida 1 conservan su comprobación de presencia y fidelidad.

El DTO admite `version_referencia: Optional[int]`, la respuesta expone `id_version_modelo: int` y la ruta GET exige entero. El RUN autorizado confirmó la divergencia por API en TC-M04-115; el oráculo UUID sigue vigente.

## Diseño y contrato

`node g049.mjs --capacidades` publica `sigab-qa-ejecutor/1` y las cuatro comprobaciones API obligatorias. `node g049.mjs --comprobar` valida la colección y los archivos sin red, RUN ni lectura de valores de `.env.qa`. La ejecución requiere el contexto canónico del lanzador con `--operacion evaluar|reintentar|reevaluar --version --intento --run-id --autorizacion --contexto`; solo el lanzador inyecta `QA_AUTORIZADO=SI`. `contexto_operacion.json` contiene únicamente grupo, versión, intento, run_id, operación, referencia, casos y, para reevaluación, alcance y versión anterior. No hay variables manuales adicionales.

El flujo usa un login de Administrador antes del escenario, catálogo I3P-1 público dentro del RUN, tres POST multipart Newman con clave interna, hasta tres GET de versión, lectura de auditoría RF-73 para V1 y DELETE del RUN. Se usa un valor activo del catálogo, `MODELO_ESPECIES_GRANDES`, tres procesos RF-71 UUID, métricas aprobatorias, fecha pasada, hashes SHA-256 reales y un ONNX mínimo determinista. V3 referencia V2; V1 no envía referencia. El ONNX contiene un grafo Identity FLOAT[1]; no hay dependencia de descarga. Un 422 de `tipo_modelo` se informa como precondición y no consume un POST adicional: el límite de tres POST impide reintentar un cuarto sin otra autorización. La equivalencia permitida por RFC-009 se considera dato de precondición; nunca cambia el oráculo de los casos.

Presupuesto único en `lib/g049_escenario.mjs`: **máximo 2 logins, 1 catálogo, 3 POST, 3 GET de versión, 3 lecturas de auditoría y 1 DELETE = 13 solicitudes**, hasta 600 s. La implementación usa normalmente 1 login y 1 auditoría (10 solicitudes); cada solicitud directa tiene timeout de 30 s y Newman tiene límite de 300 s. Sin respuesta → NO_CONCLUYENTE; 403 de clave o 5xx → BLOQUEADO técnico; las aserciones de producto se evalúan como APROBADO/RECHAZADO solo con evidencia del RUN. La ausencia del historial/auditoría acreditable rechaza TC-M04-114, sin bloquear los casos independientes. La auditoría se consulta por `id_referencia` y requiere VERSION_REGISTRADA y VERSION_APROBADA/VERSION_RECHAZADA, ambos de actor SISTEMA, sin usuario humano y con `id_sistema` igual a `id_proceso_rf71`. El payload puede ser una foto del estado final; se registra observación cuando VERSION_REGISTRADA no muestra EN_VALIDACION. La falta de un evento, actor humano u origen distinto rechaza TC-M04-114.

Los resultados oficiales, cuando el lanzador autorizado los genere, van solo en `Resultados/RUN-G049-V1-<fecha>-<hora>/` o `EvaluacionV2/Resultados/RUN-G049-V2-<fecha>-<hora>/`: un Markdown, `resultado.json`, `preflight.json` y reportes Newman JSON/HTML saneados. La plantilla del informe incluye decisión, identificación, esperado/observado, incidencias completas, problemas técnicos, cierre y límites del rollback. La emulación local de `registro_qa` exige cierre HTTP 200, rollback del sandbox verificado, comprobaciones obligatorias y evidencias relativas existentes.

## Fuentes de código realmente consultadas en `origin/test` (`daefc3a5`)

| Hecho | Archivo y línea |
|---|---|
| POST multipart con cabecera interna; GET por entero y RBAC 43 lectura | `src/prediction/infrastructure/routers/version_modelo_router.py:47-77,80-138` |
| DTO exige métricas JSON, archivo y proceso UUID; referencia entera | `src/prediction/infrastructure/dto/registrar_version_modelo_dto.py:41-63` |
| Respuesta expone entero y nombres equivalentes de métricas/fecha | `src/prediction/infrastructure/schema/version_modelo_schema.py:13-70` |
| Tipos RFC-009, incluyendo MODELO_ESPECIES_GRANDES | `src/shared/tipo_modelo.py:19-47` |
| Catálogo público de variables activas con recurso 20 lectura | `src/configuration/infrastructure/routers/variable_ambiental_router.py:44-68` |
| Adapter valida identificadores activos en I3P-1 | `src/prediction/infrastructure/adapters/variable_i3p1_m09_adapter.py:12-23`; use case `registrar_version_modelo_use_case.py:384-402` |
| Auditoría RF-73 pública por id_referencia, recurso 46 lectura | `src/prediction/infrastructure/routers/auditoria_m04_router.py:38-105` |
| No se halló ruta pública de historial de estados en el router de versiones revisado; se usa RF-73, preservando la exigencia EN_VALIDACION | `src/prediction/infrastructure/routers/version_modelo_router.py:47-192`; `src/prediction/infrastructure/repositories/version_modelo_repository.py:124-151` |
| Clave desde entorno, historial y eventos, commits, aviso tras RECHAZADO | `src/prediction/application/use_cases/versiones_modelo/registrar_version_modelo_use_case.py:141-189,213-232` |
| Artefacto guardado en disco MODELOS_STORAGE_PATH | `src/prediction/application/use_cases/versiones_modelo/registrar_version_modelo_use_case.py:404-413` |
| Middleware de eco y secreto; sesión por RUN con savepoints; DELETE hace rollback externo | `src/shared/rollback/infraestructure/testing_middlaware.py:17-36`; `src/shared/database.py:274-337`; `src/shared/rollback/infraestructure/testing_sandbox.py:47-79`; `src/shared/rollback/presentation/test_control_router.py:11-35` |
| RF-73 puede usar respaldo local si falla la persistencia; consultar auditoría registra evento y hace commit en la sesión | `src/prediction/infrastructure/repositories/evento_auditoria_m04_repository.py:260-317`; `src/prediction/application/use_cases/auditoria/consultar_auditoria_m04_use_case.py:51-80` |

## Efectos para la autorización de ejecución

Tres versiones y sus eventos de historial/auditoría se insertan en BD y los `commit()` quedan dentro de la transacción externa del sandbox si TEST despliega ese código y el RUN lleva ambas cabeceras. El DELETE 200 acredita cierre de la transacción; no acredita ausencia de artefactos ni de respaldos locales. Se escriben **tres archivos ONNX** en `MODELOS_STORAGE_PATH`, uno por `id_proceso_rf71`; el sandbox no revierte el sistema de archivos. RF-73 puede escribir respaldo local ante falla de persistencia. Login previo puede dejar sesión o auditoría. No se espera correo con clave correcta y métricas aprobatorias; una clave rechazada puede avisar al Administrador y no se reintenta. Estos efectos requieren autorización humana específica antes de TEST; esta fase no ejecuta TEST ni crea RUN.

## Validación local

`node pruebas/g049.test.mjs` (en este sandbox `node --test` falla al crear su proceso hijo); `node g049.mjs --capacidades`; `node g049.mjs --comprobar`; `node pruebas/g049_ensayo.mjs`. El ensayo usa nueve modos loopback, incluido `snapshot_final`, y guarda artefactos temporales fuera del grupo, que elimina al terminar. Si el sandbox local impide `spawn`, el ensayo usa la API local del paquete Newman; la ejecución futura autorizada usa su CLI JS mediante `process.execPath`. La regresión verifica coherencia entre `resultado.json`, informe y registro QA, así como ausencia del valor de la clave, secreto de sandbox y password en todas las salidas.


