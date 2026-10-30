# TC-M04-G051 — RECHAZADO (RUN oficial [RUN-G051-V1-20261028-032158](Resultados/RUN-G051-V1-20261028-032158/TC-M04-G051_resultado.md))

Orden inicial `ORD-G051-001`; ajustes locales `ORD-G051-003` y `ORD-G051-005`; cierre documental `ORD-G051-008`. Inventario inicial: únicamente `.gitkeep`; no había ejecutor, colección, Cypress, módulos, pruebas, scripts, README, dependencias ni evidencias. Quedan un ejecutor canónico (`g051.mjs`) y una colección Newman (`G051.postman_collection.json`). Cypress no aplica a la matriz.

## Historial y estructura vigente

| Intento | Resultado |
|---|---|
| 1 · RUN-G051-V1-20261028-024835 | Preflight local, exit 2; sin peticiones a TEST ni efectos. Fallo de carga de `.env.qa` corregido en `ORD-G051-003`. |
| 2 · RUN-G051-V1-20261028-025601 | Técnico, exit 2; 121 conforme, fecha futura de 122 respondió 500 y Newman detuvo 123–127. Continuidad corregida en `ORD-G051-005`; DELETE 200. |
| 3 · [RUN-G051-V1-20261028-032158](Resultados/RUN-G051-V1-20261028-032158/TC-M04-G051_resultado.md) | RUN oficial; RECHAZADO por 122, 123 y 127; cierre DELETE 200. |

Los dos RUN técnicos se retiraron por decisión del responsable QA el 2026-10-28. Su síntesis está en «Historial de intentos» del informe oficial. La estructura vigente contiene `README.md`, `g051.mjs`, `lib/`, `G051.postman_collection.json`, `pruebas/` y únicamente `Resultados/RUN-G051-V1-20261028-032158/`.

## Oráculos y diseño

Fuente vigente: `tests/Test_Testing/Test_Modulo4/Actualizacion_Matriz_RF69_RF72/Casos_Prueba(Mod4Agrupfinal)_actualizada.csv`, fila `TC-M04-G051` (Windows-1252, `;`). Se respetan literalmente estos resultados esperados:

| Caso | Comprobación | Resultado esperado de la matriz |
|---|---|---|
| TC-M04-121 | API-121-01 | “Con variables existentes procede; con una inexistente HTTP 422 indicando el campo” |
| TC-M04-122 | API-122-01 | “Las dos primeras se registran; la futura HTTP 422 sin crear la versión” |
| TC-M04-123 | API-123-01 | “Las tres HTTP 422 indicando el catálogo admitido” |
| TC-M04-124 | API-124-01 | “Las tres HTTP 422 identificando el campo ausente” |
| TC-M04-125 | API-125-01 | “0.0 y 1.0 se aceptan; -0.01 y 1.01 HTTP 422 indicando el rango” |
| TC-M04-126 | API-126-01 | “Las seis HTTP 422 identificando el hash afectado” |
| TC-M04-127 | API-127-01 | “Las tres HTTP 422 sin crear la versión” |

La lista vacía de variables queda fuera de la matriz. El requisito es `tests/Test_Testing/Requerimientos/Especificacion-Requerimientos-Modulo4 (1).md`, RF-69 v2.1: Precondición 2 (1854-1855), Restricción 8 (1893-1897), Entradas (1954-1968), Fase 2 (2006-2028) y E2 (2142-2151); RFC-009 (1784) y RF-65 (381-390) fijan los tipos vigentes. `MODELO_ESPECIES_PEQUEÑAS` se envía como dato inválido.

El lanzador externo crea el contexto y RUN, e inyecta `QA_AUTORIZADO=SI`. El ejecutor lee `.env.qa` de la raíz del repositorio con la misma semántica de G050: líneas `CLAVE=VALOR` (mayúsculas, dígitos y guion bajo), espacios laterales y comillas simples o dobles envolventes admitidos; las variables de `process.env` prevalecen, incluso vacías. `QA_AUTORIZADO` solo se acepta desde el proceso, nunca desde el archivo. `--comprobar` verifica estructura local y no requiere credenciales. El login de Administrador es antes del RUN. Ya dentro, con eco `X-Test-Run-Id`, se lee una vez el catálogo I3P-1 y se elige un ID existente; el inexistente se calcula fuera de los IDs devueltos. Se toma un listado inicial de `GET /prediccion/modelos?tipo_modelo=MODELO_ESPECIES_GRANDES&limit=100&offset=0`. Newman hace 23 POST multipart, cada uno con UUID RF-71 nuevo, `X-RF71-Internal-Key`, ONNX mínimo generado localmente y hash SHA-256 real salvo en los datos deliberadamente inválidos. Se hace GET por cada registro aceptado, un listado final y DELETE del RUN. El listado incluye `id_proceso_rf71`, de modo que un 422 que sí cree una versión se identifica sin consultar TEST fuera del RUN.

Los cuatro registros válidos previstos por el oráculo son: variables existentes/ayer (compartido por 121 y 122), ahora menos 10 segundos, f1=0.0 y f1=1.0. El instante del cliente y la cabecera HTTP `Date` del servidor se conservan para interpretar la prueba de “ahora”. f1=0.0 se acepta como registro aunque la evaluación de umbrales deje la versión en estado `RECHAZADO` y el POST responda 200. Los otros registros válidos exigen 201. Un 5xx en un POST de dato inválido se conserva como observación de ese subcaso y contradice el HTTP 422 exigido; los casos independientes continúan. Un 5xx en un registro válido o control bloquea solo los casos dependientes. Un 403 de clave o tres 5xx consecutivos detienen los POST; no se reintenta ninguna solicitud. La colección lleva un contador en su entorno y omite las iteraciones siguientes al corte; `g051.mjs` comprueba el mismo umbral en el reporte Newman. Se quitó `--bail` y el test global de Newman que fallaba con cualquier 5xx. Ausencia de respuesta deja resultado no concluyente. Solo un RUN TEST autorizado puede producir un veredicto de producto.

Presupuesto único, máximo **33 solicitudes y 900 segundos**: 2 logins permitidos antes del RUN + 1 catálogo + 2 listados + 23 POST + 4 GET de aceptados + 1 DELETE. La ejecución normal usa un login; el segundo es margen contractual del lanzador. Límite directo: 10 (máximo real 9 con un login). Newman CLI JS se invoca con `process.execPath`, comprueba `--version` con timeout de 30 s y escribe JSON saneado y HTML propio. Solo en ensayo loopback puede recurrir a la API local de Newman si `spawn` falla con `EPERM`.

## Código consultado en lectura (`origin/test` daefc3a5)

| Hecho | Archivo:líneas |
|---|---|
| DTO multipart con `Form(...)` obligatorio y fecha UTC | `src/prediction/infrastructure/dto/registrar_version_modelo_dto.py:41-63`; `src/shared/fechas.py:33-40` |
| No se encontró comprobación de fecha futura en DTO, normalizador UTC, entidad ni secuencia de registro | DTO anterior; `src/shared/fechas.py:33-40`; `src/prediction/domain/entities/version_modelo.py:65-135`; `src/prediction/application/use_cases/versiones_modelo/registrar_version_modelo_use_case.py:67-135`. Búsqueda `git grep` en `src` sin coincidencia RF-69. |
| Hash, tipo, métricas y variables se validan antes del archivo | `src/prediction/application/use_cases/versiones_modelo/registrar_version_modelo_use_case.py:80-109,274-281,310-338,384-413` |
| Archivo se escribe en `MODELOS_STORAGE_PATH` en líneas 404-413, antes de crear entidad y confirmar BD | mismo use case `:105-159,404-413` |
| f1=0.0 puede quedar `RECHAZADO`, y el POST pasa a HTTP 200 | `src/prediction/domain/entities/version_modelo.py:16-17,127-142`; `src/prediction/infrastructure/routers/version_modelo_router.py:73-77` |
| Aviso tras commit al rechazar; destinatarios con recurso 43, acción actualizar 3, cuentas activas, excluido usuario servicio | use case `:159-189`; `src/prediction/infrastructure/adapters/aviso_version_modelo_email_adapter.py:10-24,42-58,74-106` |
| Campos Form omitidos producen `VAL_ENTRADA` con `fields[].field`, pero el manejador usa HTTP 400 por defecto si la ruta no declara `x-codigo-validacion: 422` | `src/shared/error_handlers.py:193-200,298-324`; `src/prediction/infrastructure/routers/version_modelo_router.py:47-77` |
| GET listado admite filtro `tipo_modelo`, `limit`, `offset` y devuelve `total` | router `:80-113`; `src/prediction/infrastructure/repositories/version_modelo_repository.py:175-197` |
| Respuesta de versión incluye `id_proceso_rf71` | `src/prediction/infrastructure/schema/version_modelo_schema.py:13-38,43-70` |
| RF-73 puede escribir respaldo local si falla persistencia | `src/prediction/infrastructure/repositories/evento_auditoria_m04_repository.py:260-317` |
| La tabla `modulo4.versiones_modelos` tiene trigger `BEFORE INSERT` que rechaza fecha futura con `P0408`; el modelo SQLAlchemy solo declara `DateTime(timezone=True)` | `alembic/baseline/esquema_baseline.sql:10642-10654,24692,42770-42773`; `src/prediction/infrastructure/models/version_modelo_model.py:53` |
| El repositorio hace `flush()` después de asignar fecha y traduce el error de BD; `P0408` no tiene mapeo y el caso residual es `ERROR_INTERNO` | `src/prediction/infrastructure/repositories/version_modelo_repository.py:98-108`; `src/shared/db_error_translator.py:255-283,432-435` |

**DEFECTO_FUNCIONAL_CANDIDATO, sin nuevo veredicto (TC-M04-122):** el intento 2 ya observó HTTP 500 `ERROR_INTERNO` para mañana (`2026-10-29T02:56:05.304Z`), sin ID ni versión adicional en el listado; el oráculo exige HTTP 422. La causa probable en `origin/test` `daefc3a5` es: DTO/normalizador aceptan el timestamp futuro (`registrar_version_modelo_dto.py:45`; `src/shared/fechas.py:33-40`), el caso de uso escribe el ONNX (`registrar_version_modelo_use_case.py:105-110`), el INSERT activa el trigger `P0408` (`alembic/baseline/esquema_baseline.sql:10642-10654,42770-42773`) y `raise_from_db_error` no traduce `P0408` a error de validación (`src/shared/db_error_translator.py:255-283,432-435`). Bajo ese código y esquema, un timestamp aún futuro produce el 500 de forma determinista; no se verificó el esquema ni el despliegue de TEST, por lo que no es causa confirmada. **DEFECTO_FUNCIONAL_CANDIDATO, sin veredicto (TC-M04-127):** omisión de hashes aparentemente respondida con HTTP 400 en vez del 422 de E2. API-122-01 y API-127-01 comprueban las discrepancias en el endpoint; la lectura de código no redefine los oráculos.

## Efectos para la SOL del lanzador

Conforme al oráculo se esperan cuatro versiones sujetas a rollback externo y cuatro archivos ONNX que **no** revierte el sandbox. Con el 500 observado y la ruta de código consultada se prevén cuatro versiones más **un quinto archivo ONNX huérfano**, porque `_guardar_artefacto` precede a `_repo.guardar` y al trigger que rechaza la fecha; el rollback de BD no elimina ese archivo. Si otro despliegue aceptara la fecha futura, serían cinco versiones y cinco archivos. Los rechazos por hash, tipo, métricas o variables ocurren antes de `_guardar_artefacto`; por tanto, no dejan archivo en el flujo normal consultado. Un fallo de auditoría RF-73 puede dejar respaldo local. El login anterior al RUN puede dejar sesión o auditoría. La versión con f1=0.0 queda `RECHAZADO` por umbrales y dispara **después del commit** un intento de correo a cada destinatario activo con permiso de actualizar versiones (revisores Veterinarios según el adaptador); no queda revertido por el sandbox. No se leen destinatarios ni se envían avisos en esta fase. El DELETE del RUN cierra la transacción externa, sin probar eliminación de archivos, respaldo o correo.

## Validación local

Ejecutar `node g051.mjs --capacidades`, `node g051.mjs --comprobar`, `node pruebas/g051_env.test.mjs` y `node pruebas/g051_ensayo.mjs`. La regresión usa un `.env.qa` temporal y verifica preflight con archivo presente y ausente, precedencia, autorización y ausencia de valores en la salida. En el modo `todo_ok`, el ensayo completo lee las variables desde otro `.env.qa` temporal. El ensayo usa solo `127.0.0.1`, simula diez modos y deja los resultados temporales fuera del grupo; el script los elimina al concluir. En `fecha_futura_500` verifica 23 POST, 121 y 124–126 APROBADOS, 122, 123 y 127 RECHAZADOS, dos incidencias agrupadas (MEDIA para fecha y BAJA para HTTP 400/422) y delta cuatro. Verifica `resultado.json`, informe simulado, registro QA, presupuesto y ausencia de valores de clave, secreto y token. La etiqueta OFICIAL del emulador significa únicamente que la clasificación local satisface el contrato; no es evidencia de TEST.
