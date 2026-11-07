# [TC-M04-G052 — APROBADO (RUN oficial RUN-G052-V1-20261028-042531)](Resultados/RUN-G052-V1-20261028-042531/TC-M04-G052_resultado.md)

Órdenes `ORD-G052-001`, `ORD-G052-003`, `ORD-G052-005` y `ORD-G052-007`. Grupo de seis casos `TC-M04-129` a `TC-M04-134`, RF-69 v2.1. Fuente vigente: `tests/Test_Testing/Test_Modulo4/Actualizacion_Matriz_RF69_RF72/Casos_Prueba(Mod4Agrupfinal)_actualizada.csv`, fila `TC-M04-G052` (Windows-1252, separador `;`). Inventario inicial: solo `.gitkeep`; sin automatización ni evidencias. Se mantiene un ejecutor `g052.mjs` y una colección `G052.postman_collection.json`; Cypress no aplica porque la matriz exige solo API.

## Historial y estructura vigente

- Intento 1: `RUN-G052-V1-20261028-040338`, técnico, no oficial, exit 2. Su resumen verificable figura en el historial del informe oficial. El responsable QA autorizó eliminar sus evidencias nativas el 2026-10-28; su directorio fue retirado en `ORD-G052-007`.
- Intento 2: [RUN oficial RUN-G052-V1-20261028-042531](Resultados/RUN-G052-V1-20261028-042531/TC-M04-G052_resultado.md), seis casos APROBADOS.
- Estructura: `g052.mjs` (ejecutor), `G052.postman_collection.json` (colección), `lib/` (módulos), `pruebas/` (regresiones locales) y `Resultados/RUN-G052-V1-20261028-042531/` (único RUN conservado, con informe, JSON y reportes Newman).

## Oráculos preservados

| Caso | Comprobación API | Resultado esperado |
|---|---|---|
| 129 | API-129-01 | f1 0.91, recall 0.93: APROBADO automáticamente, sin intervención humana, con historial. |
| 130 | API-130-01 | f1 0.72, recall 0.95: RECHAZADO, mensaje de umbrales no alcanzados y aviso al Veterinario. E3 exige HTTP 200. |
| 131 | API-131-01 | f1 0.95, recall 0.70: RECHAZADO aunque f1 cumpla. |
| 132 | API-132-01 | (0.80, 0.85) APROBADO; (0.7999, 0.85), (0.80, 0.8499), (0.7999, 0.8499) RECHAZADO. |
| 133 | API-133-01 | Cada rechazo de 130, 131 y las tres fronteras identifica el umbral concreto incumplido. |
| 134 | API-134-01 | Administrador y Veterinario no alteran APROBADO→RECHAZADO ni RECHAZADO→APROBADO; no hay endpoint que fije directamente el estado. |

RF-69: umbrales 1835-1837, Restricción 4 1878-1882, Fase 3 2030-2043, historial 2089-2099, E3 2169-2175, Salida 2 2225-2229 y CA-4 2291-2295; RFC-009 línea 1784 fija el paradigma INDIVIDUAL para `MODELO_ESPECIES_GRANDES`. La nota obsoleta de la matriz sobre 201 no cambia E3. El correo no tiene confirmación de entrega por API pública en la ruta revisada; se registra como observación y no decide 130.

## Diseño y presupuesto

El lanzador externo debe crear el contexto y RUN y pasar `QA_AUTORIZADO=SI`; este ejecutor no crea un RUN oficial. `--comprobar` y `--capacidades` no consultan red. Se carga `.env.qa` de la raíz con `leerEnv`, sin imprimir valores. Login de Administrador y Veterinario antes de la primera solicitud con eco de RUN. Dentro: catalogo I3P-1, siete POST multipart por Newman con ONNX minimo y hashes reales, un GET de listado y hasta siete GET por id, una lectura RF-73 filtrada por la versión 129, 12 intentos de estado (tres por versión y rol), 12 GET posteriores y DELETE de cierre. En 134 se envía únicamente `estado_version` a PATCH de notas, PUT directo y PATCH directo, sobre una versión aprobada y otra rechazada por rol. No se llama a `/activar` ni se envían notas válidas. Una aceptación del campo extra puede guardar notas y se documenta como efecto sujeto al sandbox. Cada caso conserva su decisión independiente; tres 5xx consecutivos o 403 de clave se clasifican como impedimento técnico.

`PRESUPUESTO` es la constante única: 2 logins + 1 catalogo + 7 POST + 1 listado + 7 GET por id + 1 auditoria + 12 intentos + 12 GET + 1 DELETE = **44 solicitudes maximas**; maximo 1200 segundos, 120 segundos por POST de registro y 30 segundos por las demas solicitudes (inactividad sandbox: 180 segundos). Si no hay cuenta Veterinario verificable, se ejecutan solo los seis intentos del Administrador y sus seis GET: **31 solicitudes maximas**; 134 queda `NO_CONCLUYENTE` porque el oráculo exige ambos roles. La variable `QA_VETERINARIO_EMAIL` y la contraseña común `QA_COMMON_PASSWORD` están presentes por nombre en `.env.qa`; no se leyeron sus valores durante la preparación.

## Hallazgos de código leído en `origin/test` (`daefc3a5`)

- `src/prediction/infrastructure/routers/version_modelo_router.py:47-84`: POST 201 por defecto; si la entidad es RECHAZADO, cambia a 200. `:87-179` publica GET, GET por id, PATCH notas y POST activar; no registra PUT, PATCH ni DELETE directos sobre `/{id}`, por lo que FastAPI debe responder 405 para esas rutas si no hay otra ruta superpuesta. No se presume respuesta de TEST.
- `src/prediction/domain/entities/version_modelo.py:127-148`: comparación estricta por debajo de 0.80 y 0.85, con detalle que nombra `f1_score_global` y `recall_clase_riesgo_alto` según corresponda.
- `src/prediction/infrastructure/dto/registrar_notas_version_dto.py:1-5`: `notas_validacion` requerido. `src/shared/base_dto.py:13-21`: configuración Pydantic sin `extra='forbid'`; el campo adicional se ignora si el requerido está presente. La solicitud de 134 omite notas, por lo que se espera 422 por campo requerido, más GET que confirme el estado.
- `src/prediction/application/use_cases/versiones_modelo/registrar_version_modelo_use_case.py:145-191`: registra historial y eventos RF-73 como SISTEMA con fuente `id_proceso_rf71`; avisa el rechazo después del commit, best effort.
- `src/prediction/infrastructure/routers/auditoria_m04_router.py:38-102`: GET `/prediccion/auditoria` permite `id_referencia`. No se encontró una ruta de notificación in-app para la entrega de E3 en el router ni en el caso de uso consultados.
- `src/prediction/infrastructure/adapters/aviso_version_modelo_email_adapter.py:43-112`: consulta destinatarios activos con permiso recurso 43, acción 3, excluye cuenta de servicio y llama `send_email` una vez por destinatario. Incluye quien tenga ese permiso, potencialmente Veterinarios y Administradores; no se consultó la lista real de TEST.

## Efectos que deben constar en la autorización del lanzador

Si los siete registros se crean: siete versiones de BD sujetas al rollback externo y siete archivos ONNX en `MODELOS_STORAGE_PATH` que el sandbox no revierte. Cinco registros quedan RECHAZADO (130, 131 y tres fronteras), así que se intenta **5 correos por cada usuario activo** con permiso 43/3 distinto de la cuenta de servicio: `5 × N` intentos, donde `N` es el número de destinatarios reales de TEST, no observable sin consulta autorizada. Esos correos son irreversibles; entrega no demostrada. Los intentos de 134 podrían guardar notas si el endpoint acepta un campo extra; la BD quedaría sujeta al rollback. Los dos logins anteriores al RUN pueden dejar sesión o auditoría. El cierre DELETE no prueba eliminación de ONNX ni entrega/reversión de correos. Esta preparación no envía ninguno.

## Validación local

Ejecutar `node g052.mjs --capacidades`, `node g052.mjs --comprobar`, `node pruebas/g052_env.test.mjs` y `node pruebas/g052_ensayo.mjs`. El ensayo usa exclusivamente `127.0.0.1`, un directorio temporal y una etiqueta `OFICIAL_LOCAL` que significa solo que pasa el clasificador emulado de registro QA; no es evidencia de TEST ni crea RUN oficial en el grupo. Los catorce modos cubren seis discrepancias aisladas, archivo `.env.qa` temporal, 403, 5xx sistémico, un 5xx limitado a 130 y ausencia de respuesta. Se comprueban informe y `resultado.json` temporales, presupuesto, saneamiento y codificación. Ningún resultado local constituye veredicto de producto.

## Correcciones tecnicas ORD-G052-003 y ORD-G052-005

Los POST sin respuesta no se reintentan. Tras los siete POST se consulta una vez `GET /prediccion/modelos?tipo_modelo=MODELO_ESPECIES_GRANDES&limit=100&offset=0`. Se recupera la version solo si `id_proceso_rf71` coincide de forma unica y se verifica estado y detalle por GET individual. El HTTP del POST queda no verificable para E3 y se anota. Si falta la version tras un POST sin respuesta, el caso es `NO_CONCLUYENTE`. 132 exige las cuatro combinaciones; 133 evalua el detalle de cada version que efectivamente quedo RECHAZADO. Si un defecto ya atribuido con evidencia a 130, 131 o 132 impidio ese estado, 133 registra la exclusion con la incidencia del subcaso. Un POST sin respuesta no conciliado o un GET no verificable mantiene 133 en `NO_CONCLUYENTE`; tampoco se aprueba sin ninguna version rechazada evaluable. `resultado.json` y el informe generado listan las versiones evaluadas, excluidas y pendientes. Cada duracion POST se mide en ms y se guarda en resultado e informe. Si supera 5 s se cita RF-69 RNF-01 (lineas 2350-2352) solo como observacion: incluye correo y no aisla Fases 2-3.

En `origin/test` (`daefc3a5`), `registrar_version_modelo_use_case.py:181-190` llama al aviso tras el commit y antes de retornar. `aviso_version_modelo_email_adapter.py:74-81,101-104` recorre destinatarios y llama `send_email` una vez por cada uno, sin cola visible. `src/shared/email.py:37-38,68-81` fija un timeout SMTP de 8 s por conexion. Esto es una hipotesis del tiempo de respuesta, no una causa comprobada en TEST. Los POST de 130, 131 y 132-b del intento 1 probablemente ya enviaron aviso por correo; no se reintentan y el correo no es reversible.
