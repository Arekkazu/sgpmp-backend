# [TC-M04-G056 — APROBADO (RUN oficial RUN-G056-V1-20261028-051318)](Resultados/RUN-G056-V1-20261028-051318/TC-M04-G056_resultado.md)

## Historial de intentos

- Intento 1, `RUN-G056-V1-20261028-050237`: ejecución técnica con DELETE 200 y exit 0; registro QA `INCIERTO/ABIERTO_PENDIENTE` por contrato de `resultado.json`. Sus falsos rechazos de 147 y 149 se corrigieron en ORD-G056-005. La evidencia nativa se eliminó por autorización QA del 2026-10-28; el resumen consta en el informe oficial.
- Intento 2, `RUN-G056-V1-20261028-051318`: registro QA `OFICIAL`, cuatro casos APROBADOS y DELETE 200. Evidencias e informe en el enlace del título.

## Preparación local de RF-69 v2.1

Órdenes `ORD-G056-001`, `ORD-G056-002` y corrección local `ORD-G056-003`. Casos `TC-M04-146` a `TC-M04-149`. Fuente vigente: `tests/Test_Testing/Test_Modulo4/Actualizacion_Matriz_RF69_RF72/Casos_Prueba(Mod4Agrupfinal)_actualizada.csv`, fila `TC-M04-G056`, Windows-1252 y separador `;`. Inventario inicial de G056: solo `.gitkeep`; no ejecutor, colección, Cypress, pruebas, duplicados ni evidencias previas. Se usa un ejecutor `g056.mjs`, una colección `G056.postman_collection.json` para los cuatro registros RF-71 y pruebas locales en `pruebas/`. Cypress no aplica porque la matriz pide solo API. Se revisaron en solo lectura `TC-M04-G052/g052.mjs`, `lib/{contrato_ejecutor,seguridad,artefactos,g052_escenario}.mjs`, `G052.postman_collection.json`, `pruebas/{g052_ensayo,g052_env.test,registro_qa}.mjs` y `README.md`; no se alteraron ni sus evidencias.

## Oráculos y comprobaciones

| Caso | API | Oráculo de la matriz |
|---|---|---|
| 146 | API-146-01 | Las notas quedan asociadas y consultables; el estado no cambia al registrarlas; ambos roles pueden hacerlo. |
| 147 | API-147-01 | Puede consultar métricas e historial; no puede modificar el estado, activar ni intervenir el historial. |
| 148 | API-148-01 | Permanece en APROBADO, no se activa sola y sigue disponible para activación. |
| 149 | API-149-01 | Se devuelven estado y métricas completas y los filtros acotan correctamente el resultado. |

Interpretación operativa de 147: se comparan las transiciones y el estado de V2 antes y después; las consultas `HISTORIAL_CONSULTADO` añadidas por GET no constituyen intervención. En 149, el listado sin filtro se revisa por estado y bloque de métricas del paradigma; las cuatro versiones del RUN deben tener las siete métricas completas. Las métricas nulas y tipos nulos de datos preexistentes se registran como observación, conservando el oráculo literal de la matriz.

El RF especifica el ciclo humano en `Especificacion-Requerimientos-Modulo4 (1).md:1792`, transiciones en `:1822-1832`, notas en `:1968`, revisión en `:2045-2068`, E4 en `:2177-2181`, historial append-only en `:1890-1891` y CA-8 en `:2313-2315`, y RBAC en `:2369-2376`. Para 148 prevalece la lista cerrada de transiciones: no existe APROBADO→DEPRECADO. No se cambió el oráculo para ajustarlo al código.

## Código leído en `origin/test` (`daefc3a5`)

- `src/prediction/infrastructure/routers/version_modelo_router.py:47-179`: POST interno con `X-RF71-Internal-Key`, GET listado y detalle (permiso 43/2), PATCH notas (43/3), POST activar (43/5). El router no declara PUT/PATCH directos de versión. `:91-94` expone `tipo_modelo`, `estado`, `limit` y `offset`. El comentario inicial `:14-17` documenta Admin/Vet, pero los grants reales de TEST no se verificaron.
- `src/prediction/infrastructure/routers/auditoria_m04_router.py:56-161`: GET listado con `id_referencia`, exportación y detalle; no declara PUT/PATCH/DELETE de auditoría. Su comentario `:13-17` indica lectura Veterinario desde DB-08; el permiso efectivo requiere comprobación pública.
- `src/prediction/infrastructure/schema/version_modelo_schema.py:27-37,58-68`: campos de las siete métricas, estado, notas y `esta_produccion` en respuesta.
- `src/prediction/infrastructure/repositories/version_modelo_repository.py:175-195`: ambos filtros se aplican a consulta y conteo; no se infiere resultado de TEST.
- `src/prediction/domain/entities/version_modelo.py:150-180`: activar RECHAZADO produce `ConflictError` antes de exigir notas, y solo APROBADO pasa a ACTIVO. `:196-211`: notas vacías se rechazan; una nota previa produce `NOTAS_INMUTABLES`; no hay restricción por estado en este método.
- `src/prediction/application/use_cases/versiones_modelo/registrar_notas_version_use_case.py:25-59`: llama al método de dominio, actualiza versión, hace commit y registra auditoría con `id_usuario`; usa `VERSION_APROBADA` como tipo de evento incluso para una nota. El autor no figura en `VersionModeloResponse`, pero puede figurar en auditoría.
- `src/prediction/application/use_cases/versiones_modelo/activar_version_modelo_use_case.py:29-96`: actualización de versión, historial y auditoría en BD; en esta ruta consultada no se observan llamadas OTA, MQTT ni Edge.
- `src/prediction/application/use_cases/versiones_modelo/registrar_version_modelo_use_case.py:140-190,404-414`: registra versión e historial, avisa rechazo tras commit, y escribe el ONNX en `MODELOS_STORAGE_PATH` (o `/tmp/sgpmp_modelos`). `src/prediction/infrastructure/adapters/aviso_version_modelo_email_adapter.py:74-81,101-104` envía una vez por destinatario activo con permiso 43/3; número real de destinatarios no se consultó. `src/prediction/infrastructure/repositories/evento_auditoria_m04_repository.py:260-318` puede escribir respaldo local si falla persistencia.

La matriz exige que ambos roles puedan registrar notas, pero no exige sobrescribir una nota ya registrada sobre la misma versión. Tampoco incluye PATCH de notas entre los intentos del caso 147. La corrección local usa V1 y V1b para los permisos de 146 y omite ese PATCH sobre V2. Para 148 se usa V1 si conserva una nota comprobada; de lo contrario, V1b si conserva la nota del Administrador. Si ninguna versión APROBADA tiene evidencia de nota registrada, 148 queda `NO_CONCLUYENTE`. La versión elegida queda en las observaciones del resultado. Solo un RUN autorizado en TEST podría confirmar veredictos.

## Flujo y presupuesto para autorización externa

El lanzador debe proporcionar contexto de RUN y `QA_AUTORIZADO=SI`. El ejecutor valida el contrato antes de acceder a red. Dos logins ocurren antes de la primera solicitud con eco de RUN. Dentro del RUN: catálogo I3P-1, V1, V1b y V2 por Newman con ONNX mínimo y hashes, notas y consultas de 146, intentos y lecturas de 147, V3 por Newman, consulta de 148 y ocho listados de 149; finalmente DELETE de cierre. La colección usa la ruta canónica; el resto de la API se ejecuta desde el ejecutor. No se reintenta un POST sin respuesta. Los subcasos se deciden por separado; un fallo de clave o 5xx sistémico bloquea técnicamente y la falta sistémica de respuesta deja `NO_CONCLUYENTE`.

`PRESUPUESTO` en `lib/g056_escenario.mjs` es la fuente única: **2 logins + 1 catálogo + 4 POST + 4 solicitudes 146 + 20 solicitudes 147 + hasta 1 GET 148 + 8 listados 149 + 1 DELETE = 41 solicitudes máximas**. Duración máxima 900 s; timeout por registro 120 s y por las demás solicitudes 30 s. Dos logins y el DELETE se cuentan aunque estén fuera de la ventana del RUN. No hay UI obligatoria.

Efectos a declarar en la SOL: hasta cuatro versiones y notas en BD sujetas al sandbox; cuatro archivos ONNX en `MODELOS_STORAGE_PATH` no revertidos por el sandbox; posible respaldo local RF-73; un aviso por correo irreversible **por destinatario activo** de la única V2 RECHAZADA (cantidad real desconocida); dos logins previos que pueden dejar sesión o auditoría. Si V2 se activara indebidamente, su cambio de BD queda sujeto al sandbox, sin OTA según la ruta de código leída. DELETE con HTTP 200 informa cierre; no acredita por sí solo reversión de ONNX ni correo, ni rollback de BD sin comprobación pertinente.

## Validación local

Corrección `ORD-G056-005`: `resultado.json` usa `cierre.run.cierre_http`, `cierre.rollback.{verificado,motivo}`, comprobaciones `ASSERT`, `cypress.total_pruebas=0` y evidencias relativas. `pruebas/registro_qa.mjs` reproduce la validación del registro QA de G052 con el nombre de G056. El ensayo cubre 17 modos, incluidos consultas de auditoría adicionales, datos heredados y una transición alterada. La clasificación `OFICIAL_LOCAL` solo valida el contrato en loopback; no acredita TEST ni un RUN real. El intento 1 se resume en el informe oficial y su carpeta técnica se elimina conforme a ORD-G056-007.

`node g056.mjs --capacidades`, `node g056.mjs --comprobar`, `node pruebas/g056_env.test.mjs` y `node pruebas/g056_ensayo.mjs`. El ensayo usa exclusivamente `127.0.0.1`, crea artefactos reales en temporal y los retira. `OFICIAL_LOCAL` es solo la decisión del clasificador emulado; no acredita TEST. En esta corrección no se creó RUN ni informe. Las variables de `.env.qa` se cargan por nombre sin mostrar valores; los artefactos se sanean antes de conservarse.
