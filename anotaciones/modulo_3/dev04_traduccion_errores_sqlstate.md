# DEV-04 — Traducción contextual de errores SQLSTATE

Fecha: 2026-10-15. Historia #3512, épica #3503, subtareas #3566 y #3567.
RF relacionados: RF-53, RF-57 y RF-69 (integridad de predicciones RF-66).

## 1. Diagnóstico

El traductor compartido no reconocía los rechazos de los cuatro triggers.
Sus SQLSTATE de clase P0 llegan como errores internos del driver, envueltos
habitualmente en `sqlalchemy.exc.InternalError`. El traductor terminaba en
`InfrastructureError/ERROR_INTERNO/500`; el handler de SQLAlchemy también
respondía 500 si el error escapaba sin traducir. La extracción previa del
diagnóstico solo contemplaba `exc.orig`, no una excepción directa de psycopg2.

RF-53 ya hacía rollback antes de registrar los errores funcionales en
`modulo3.bitacora_ingest`. El rechazo del trigger no entraba a esa rama al
traducirse como infraestructura. No era necesario crear otra bitácora.

RF-57 validaba transiciones en dominio y PostgreSQL, pero carecía de la
traducción para una carrera que llegara al trigger. El historial de estados
debe conservar únicamente cambios efectivamente realizados: el rechazo se
audita separadamente mediante el mecanismo RF-63 existente.

### Fuentes y discrepancias verificadas

- Código de `src/shared`, casos de uso, adaptadores y routers M03/M04.
- `alembic/baseline/esquema_baseline.sql` y todas las migraciones posteriores.
- Especificaciones proporcionadas RF-53/RF-57 y RF-64–RF-73; RF-57 CA-11
  exige transiciones válidas y HTTP 422 para transiciones rechazadas.
- Convenciones existentes: `ERROR_TIEMPO` usa `ValidationError/400` en ingesta;
  M04 usa `MODELO_NO_ACTIVO/PreconditionFailedError/412` y
  `VERSION_MODELO_NO_ENCONTRADA/NotFoundError/404` al vincular versiones.
- No se encontró `gaps_m03_m04_m09_patron_transversal.md`; no se atribuyen
  decisiones a un Patrón C que no pudo inspeccionarse.
- La aplicación tolera hasta 30 segundos futuros, pero el trigger RF-53
  rechaza cualquier `timestamp_captura > now()`. Se conserva esta diferencia,
  sin debilitar el trigger ni cambiar validaciones ajenas a DEV-04. Una entrada
  a +15 segundos permite probar el rechazo real de persistencia.
- `P0413` no significa exclusivamente modelo inactivo: también identifica
  una versión inexistente. El trigger verifica `esta_produccion`; DEV-04 no
  sustituye esa regla por una comprobación diferente de `estado_version`.
- No existe repositorio/router de escritura para `modulo4.predicciones` ni
  una API para UPDATE/DELETE de telemetría en este checkout. Se verifican con
  SQL real y handlers de producción en endpoints exclusivos de las pruebas.

### Colisiones y estrategia

La búsqueda completa encontró usos adicionales:

| SQLSTATE | Contextos diferentes |
|---|---|
| P0001 | Reutilización de contraseña M01 y numerosas reglas de M06; no identifica por sí solo RF-53. |
| P0002 | Protección de auditoría RF-10, incluidos eventos archivados, además de telemetría. |
| P0005 | `ROLE_IN_USE` de M01 y transición inválida de alertas M03. |
| P0413 | Dos ramas de la misma función: versión inexistente y versión fuera de producción. |

`RAISE EXCEPTION` de estos triggers no proporciona un identificador de
constraint ni tabla/esquema en los campos estructurados del diagnóstico.
Sí proporciona `diag.context` con la función PL/pgSQL que lanzó el error.
Se combina **SQLSTATE + primera función del contexto, calificada por esquema**.
No se buscan nombres en la sentencia SQL ni en los parámetros del cliente.

Se toma la primera función incluso si no está calificada: un frame exterior
conocido no puede convertir el rechazo de una función interior desconocida en
otro error. Contextos ausentes, no reconocibles o funciones no calificadas
conservan el tratamiento desconocido. Las pruebas con PostgreSQL verifican
los contextos calificados emitidos por los cuatro triggers de las migraciones.

Para P0413, una vez confirmada la función, se distingue la etiqueta estable
`MODEL_NOT_ACTIVE` o `MODEL_NOT_FOUND`; no se compara la oración completa ni
se devuelve el mensaje PostgreSQL. Etiquetas nuevas no se traducen por suposición.

## 2. Mapeo definitivo

| SQLSTATE | Función/contexto | Error de dominio | HTTP | Auditoría |
|---|---|---|---|---|
| P0001 | `modulo3.fn_validar_timestamp_telemetria` | `ERROR_TIEMPO` (`ValidationError`) | 400 | Obligatoria en ingesta: `bitacora_ingest`, `ERROR_PROCESAMIENTO`, calidad `ERROR_TIEMPO`, después del rollback. |
| P0002 | `modulo3.fn_telemetrias_inmutable` | `TELEMETRIA_INMUTABLE` (`BusinessRuleError`) | 422 | No se define un evento de rechazo específico en RF-53; se conserva el registro original. |
| P0005 | `modulo3.fn_alerta_validar_transicion` | `TRANSICION_INVALIDA` (`BusinessRuleError`) | 422 | RF-63: `TRANSICION_ALERTA_RECHAZADA`, resultado `RECHAZADO`, componente RF57, usuario, alerta, estado solicitado y hash de integridad. |
| P0413 | `modulo4.trg_fn_predicciones_version_modelo_activo`, etiqueta `MODEL_NOT_ACTIVE` | `MODELO_NO_ACTIVO` (`PreconditionFailedError`) | 412 | No hay productor de predicciones en el backend inspeccionado; no se inventa un evento de éxito/rechazo sin su contexto. |
| P0413 | Misma función, etiqueta `MODEL_NOT_FOUND` | `VERSION_MODELO_NO_ENCONTRADA` (`NotFoundError`) | 404 | Mismo límite del productor de predicciones. |

Para inmutabilidad se incorpora un código propio y se usa 422 porque la
operación viola una invariante del dominio; no es un duplicado ni un fallo de
conectividad. No existía un HTTP específico impuesto por el flujo RF-53 para
un endpoint de modificación, ya que dicho endpoint no existe.

Las respuestas mantienen `error_code`, `message`, `fields` y `timestamp`.
Los mensajes de los nuevos mapeos son constantes controladas; no contienen
SQLSTATE, funciones, SQL, valores de parámetros ni mensajes internos del driver.

## 3. Archivos modificados

| Ruta | Responsabilidad y cambio | Justificación |
|---|---|---|
| `src/shared/db_error_translator.py` | Incorpora `traducir_rechazo_trigger`; extrae diagnóstico del driver o de `.orig`; integra los mapeos en `raise_from_db_error`. | Una única traducción contextual, compatible con las reglas existentes. |
| `src/shared/error_handlers.py` | Registra handlers DBAPIError/psycopg2 que usan el mismo traductor para los triggers conocidos. | Evita 500 cuando una excepción conocida escapa de un repositorio, conservando los handlers de conectividad 503 y el 500 seguro de desconocidos. |
| `src/telemetry/application/use_cases/ingesta/ingerir_telemetria_use_case.py` | Registra un warning controlado si falla la transacción de bitácora del rechazo. | El error de auditoría no reemplaza el error funcional ni queda completamente silenciado. |
| `src/telemetry/infrastructure/repositories/bitacora_ingest_repository.py` | `registrar_error` traduce y propaga el fallo de persistencia hacia su caso de uso. | El rollback/commit de auditoría queda a cargo de aplicación; no se oculta una sesión abortada. |
| `src/telemetry/application/use_cases/alertas/actualizar_estado_alerta_use_case.py` | Incluye la validación de dominio en el bloque transaccional e inyecta un puerto opcional de auditoría; audita `TRANSICION_INVALIDA` después del rollback. | Cubre el rechazo previo y la carrera del trigger, sin generar un historial de transición ficticio. |
| `src/telemetry/infrastructure/routers/alerta_router.py` | Inyecta el adaptador RF-63 existente al caso de uso de actualización. | Completa el flujo real sin cambiar JWT, permisos ni RBAC. |
| `src/telemetry/application/use_cases/auditoria/registrar_evento_auditoria_iot_use_case.py` | Comprueba el ID devuelto por el adaptador best-effort y registra fallos controlados. | Un evento sin ID no se considera persistido; auditoría fallida hace rollback y conserva el rechazo original. |
| `tests/shared/test_dev04_sqlstate.py` | 37 pruebas nuevas: driver, SQLAlchemy, HTTP, contexto, colisiones y desconocidos. | Cubre traducción y compatibilidad del contrato público. |
| `tests/integration/test_dev04_sqlstate.py` | 9 pruebas nuevas con triggers reales, routers RF-53/RF-57, JWT/RBAC de alertas, auditoría y rollback. | Verifica el comportamiento completo donde hay API de producto y explicita los endpoints de prueba donde no la hay. |
| `anotaciones/modulo_3/dev04_traduccion_errores_sqlstate.md` | Este informe. | Reproducción, decisiones, alcance y evidencia para desarrollo/QA. |

## 4. Transacciones y trazabilidad

El traductor no controla sesiones ni escribe auditoría. Los repositorios
traducen antes de salir de infraestructura; los casos de uso hacen rollback.
`get_db` mantiene su rollback/close defensivo para errores que escapen.

RF-53: INSERT rechazado → traducción 400 → rollback → INSERT en bitácora →
commit de bitácora → propagación del mismo `ERROR_TIEMPO`.

RF-57: transición rechazada → traducción 422 → rollback → evento RF-63 en
otra transacción → propagación del mismo `TRANSICION_INVALIDA`. El evento
incluye alerta/usuario/estado solicitado, resultado RECHAZADO y SHA-256.
No se agrega una entrada exitosa al historial de estados.

La auditoría reutiliza la política best-effort existente. Si la base o el
adaptador de auditoría falla, se revierte esa transacción y se registra un
warning sin SQL, credenciales ni parámetros; se conserva el rechazo original.
No se promete persistencia durante una caída del almacenamiento ni se añade
una cola durable nueva. Los tests cubren error SQL abortante y devolución de
evento sin ID, además de la persistencia normal de los rechazos.

El handler defensivo compartido no intenta inventar auditoría a partir de
una excepción aislada: no conoce sensor, dispositivo o actor. La auditoría
obligatoria RF-53 está integrada y probada en su flujo de ingesta.

## 5. Pruebas ejecutadas

Entorno: Windows, Python 3.13.13 y PostgreSQL 18.6 temporal, escuchando
únicamente en 127.0.0.1. Base `sgpmp_test_dev04`, migraciones existentes hasta
`3a9d5e7c1b24`. Se respetó la protección de `TEST_DATABASE_URL`: no se usó
una base compartida ni se desactivaron triggers.

Cada integración usa el `conftest.py` existente: transacción exterior y
savepoints de sesión. El rollback exterior elimina los fixtures al terminar.

| Prueba | Objetivo | Resultado final |
|---|---|---|
| P0001, 2 integraciones | Router real de ingesta; +15s alcanza el trigger; error 400, bitácora persistida o fallo de auditoría sin ocultar el rechazo. | 2 aprobadas |
| P0002, 2 integraciones | UPDATE y DELETE reales bloqueados; respuesta 422 y valor original intacto. | 2 aprobadas |
| P0005, 3 integraciones | Router real, JWT/RBAC y lectura obsoleta ACTIVA frente a fila VENCIDA; HTTP 422, estado/historial intactos; auditoría normal y dos modos de fallo. | 3 aprobadas |
| P0413, 2 integraciones | INSERT de predicción real con versión fuera de producción o inexistente; HTTP 412/404 y ausencia de persistencia. | 2 aprobadas |
| Traductor y HTTP DEV-04 | Contexto, colisiones, driver directo, envoltura, fallback pgcode y SQLSTATE desconocido. | 37 aprobadas, incluidas en el grupo de 212 |
| Shared + telemetría + taxonomía M04 | Regresión compatible con Windows, con exclusiones explícitas indicadas abajo. | 212 aprobadas, 2 deseleccionadas |
| Colisión P0005 de roles M01 | Suite existente de eliminación de roles; conserva ROL_EN_USO y sus reglas. | 6 aprobadas |
| Ingesta/vinculación existente | Suite PostgreSQL `test_inc_m09_64_g31_vinculacion_ingesta.py`. | 6 aprobadas |
| Versiones RF-69/RF-73 existentes | Registro, activación y eventos de versiones. | 2 aprobadas |
| AST y whitespace | Parseo de los 9 archivos Python y `git diff --check`. | Aprobados |
| Bandit, gate del proyecto | Siete archivos de producción modificados, umbral `-lll -iii`. | Exit 0; alta 0, media 0, baja 1 |
| Semgrep | Herramienta no disponible localmente. | No ejecutado |

**Conteo sin duplicaciones: 235 pruebas aprobadas** = 212 + 9 + 6 + 6 + 2.
De ellas, 46 son nuevas de DEV-04 (37 unitarias/HTTP + 9 PostgreSQL).
No se suman de nuevo las ejecuciones individuales o reintentos.

### Fallos y límites de la regresión

La regresión amplia inicial ejecutó dos pruebas de
`tests/shared/test_error_handlers_auditoria_m02.py` que fallan por
`ModuleNotFoundError: fcntl` en `_registrar_evento_bitacora.py` de M02.
El import y esa ruta de auditoría no fueron modificados. Se reprodujeron
los fallos aisladamente y se deseleccionaron ambas pruebas para verificar el
resto: siguen siendo **2 fallos ajenos a DEV-04**, no pruebas aprobadas.

Dos archivos no pueden recolectarse por el mismo import exclusivo de POSIX:
`tests/telemetry/test_inc_m09_77_g137_observaciones_vision.py` y
`tests/shared/test_tc_m02_65_g94_cabeceras_cuota_429.py`. No se afirma que sus
casos hayan sido ejecutados. No se cambió M02 ni se simuló `fcntl`.

La primera preparación de fixtures falló por nombres de finca con dígitos,
un enum de alerta inválido y modelos referenciados no importados. Luego se
corrigieron los fixtures conforme al esquema, incluyendo confirmar el
hardware antes del rechazo. No se alteraron reglas de producto para aprobar.
La regresión RF-69 se repitió con un basetemp exclusivo tras un error de
permisos del caché temporal de pytest. Resultado final: sus 2 pruebas pasaron.

Se observa el warning preexistente de deprecación Starlette/httpx.
La suite completa del repositorio no está certificada en Windows.

### Comandos reproducibles

Requieren una PostgreSQL **aislada**, migrada, y `TEST_DATABASE_URL` válida.
Usar un basetemp exclusivo si el caché pytest del usuario no es accesible.

```powershell
python -m pytest --confcutdir=tests/shared tests/shared tests/prediction tests/telemetry --ignore=tests/telemetry/test_inc_m09_77_g137_observaciones_vision.py --ignore=tests/shared/test_tc_m02_65_g94_cabeceras_cuota_429.py --deselect=tests/shared/test_error_handlers_auditoria_m02.py::test_400_en_activos_biologicos_registra_auditoria_fallida --deselect=tests/shared/test_error_handlers_auditoria_m02.py::test_400_sin_token_registra_auditoria_sin_usuario -q
python -m pytest --confcutdir=tests/integration tests/integration/test_dev04_sqlstate.py tests/integration/test_inc_m09_64_g31_vinculacion_ingesta.py -q
python -m pytest --confcutdir=tests/integration tests/integration/test_rf69_registro_activacion_version_e2e.py -q
python -m pytest --confcutdir=tests/identity_access tests/identity_access/test_inc_m01_03_119_eliminar_rol.py -q
```

## 6. Estado final

- #3566: completada la traducción, conexión HTTP y gestión de auditoría/rollback.
- #3567: completadas y ejecutadas las 46 pruebas nuevas y la regresión indicada.
- 10 archivos modificados/agregados; ninguna migración ni cambio de trigger.
- Base Git: `origin/dev` en `cd06a257`; rama `fix/dev04-traduccion-sqlstate`.
  El SHA del commit local se informa en la entrega; no hubo push ni despliegue.
- DEV-02 permanece independiente en `fix/rf62-dev02-aptitud-telemetria`
  (`8fc5ef9c`); no está integrado en este `origin/dev`. DEV-04 no modifica
  su fuente oficial de aptitud ni los archivos de evaluación RF-62. Su merge
  sigue siendo necesario para retirar el UPDATE obsoleto de la base dev.
- No se accedió a bases compartidas para ejecutar escrituras, DDL o tests.
- Comprobación final de la base aislada: telemetrias, alertas,
  telemetria_calidad y predicciones quedaron con 0 filas funcionales; los
  cuatro triggers revisados siguieron habilitados (`tgenabled='O'`). No se
  promete restauración de secuencias, que pueden avanzar durante pruebas.
- PostgreSQL temporal se detuvo y su base/runtime se eliminaron tras las pruebas.
- Pendientes externos: portabilidad/CI Linux para las pruebas M02 con fcntl,
  Semgrep en CI y prueba de publicación de predicciones cuando exista su
  productor/API. La ausencia de dicho productor no se presenta como una
  ejecución completa de RF-66 o del pipeline AIoT.
