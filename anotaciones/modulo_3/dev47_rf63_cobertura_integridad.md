# RF-63 — Cobertura de auditoría IoT y detección de alteraciones · DEV-47

Historia **#3703** · Épica **#3667** · Tareas **#3804, #3805 y #3806**.

Fecha de desarrollo: 2026-10-22. Rama: `fix/dev47-auditoria-iot-integridad`.

## Diagnóstico

| Flujo | Estado encontrado | Corrección |
|---|---|---|
| RF-53 | La función de ingesta registraba resultados en `bitacora_ingest`, sin proyectarlos obligatoriamente a RF-63 | Etapas recuperables por resultado y por lectura confirmada, también para la persistencia utilizada por MQTT |
| RF-56 | Se persistían paquetes y cambios de estado sin evidencia central | Evidencia en la misma transacción del paquete; no se modifica la semántica del motor |
| RF-57 | Creación, consolidación y atención no emitían todos sus eventos centrales | Instrumentación de los repositorios existentes, sin crear historial adicional |
| RF-60 | Había auditoría de mantenimiento, pero faltaban heartbeats y transiciones realizadas directamente por PostgreSQL | Proyección del heartbeat y del historial confirmado; eliminación de una escritura histórica redundante del evaluador |
| RF-61 | La base DEV-44 ya auditaba vinculación automática/manual, corrección y traslados | Se conserva esa implementación y se ejecuta su regresión; no se agrega un segundo emisor |
| E6 | Solo existía POST; se emitía un incidente repetido, atribuido a RF-62, y se silenciaban sus errores | GET estático protegido, POST compatible, incidente externo idempotente, marca consultable y recuperación del aviso |
| DB-11 | Revisión oficial encontrada en otra rama; no integrada en la rama de trabajo ni visible en los triggers oficiales consultados | Incorporación de la revisión original y una revisión de unión con DB-13 |

Fuentes revisadas: implementación real, `Especificacion-Requerimientos-Modulo3.md` (RF-63 y catálogos RF-53/56/57/60/61), migraciones, modelos y metadatos de `sgpmp_dev`. La consulta oficial fue de solo lectura sobre el destino correcto `158.69.200.27:5447`, base `sgpmp_dev`.

DB-11 es `97ecff4d7d0c`, procedente del commit `a43f26f6` de `origin/fix/seguridadMoudulo03`. Define inmutabilidad, no una columna `comprometido`, un almacén de incidentes o un catálogo de notificación RF-14. No se presupusieron esas estructuras.

## Implementación

### #3804 — Ingesta, paquetes y alertas

`registrar_evidencia` construye el evento, aplica la clasificación/retención existente y utiliza exactamente `_calcular_hash`. No confirma transacciones. Si no obtiene el identificador persistido, falla y deja al llamador revertir la operación.

El worker DEV-05 incorpora `RF53_LECTURAS` y `RF53_AUDITORIA`. La primera recupera lecturas confirmadas incluso si faltó el log SQL auxiliar; la segunda proyecta resultados y rechazos de `bitacora_ingest`. Ambas comparten el bloqueo por dispositivo y comprueban si la lectura ya tiene evidencia. Las fuentes, los eventos y los marcadores de progreso tienen responsabilidades distintas: un marcador `POSTCOMMIT_*` no se presenta como sustituto del evento funcional.

El lote HTTP conserva el resultado individual. Se registran `TELEMETRIA_VALIDADA`, `TELEMETRIA_RECHAZADA`, `DUPLICADO_DETECTADO`, `ERROR_AUTENTICACION_DISPOSITIVO` y los demás tipos aplicables del catálogo. La calidad original se conserva; una lectura persistida con calidad distinta de `LECTURA_VALIDA` utiliza resultado `ADVERTENCIA`. Auditarla no la convierte en apta ni genera una alerta funcional.

Los rechazos estructurales anteriores al caso de uso se capturan únicamente en las rutas de ingesta. Mantienen HTTP 400 y se escriben mediante una sesión de auditoría independiente. Se conserva solo la ruta y la cantidad de errores, sin cuerpo, credenciales, valores de campos ni cabeceras. Los errores SQL de infraestructura pueden dejar `FALLA_PERSISTENCIA`; un rechazo de negocio no se reclasifica como fallo SQL. Si la propia base está caída, queda diagnóstico seguro en log: no se afirma una persistencia imposible ni se construye otro buffer.

Los paquetes generan `PAQUETE_INFERENCIA_GENERADO`, `CONTEXTO_INCOMPLETO` cuando procede y `PAQUETE_ENVIADO_IA` o `FALLO_ENVIO_PAQUETE` cuando existe un resultado de envío real. El stub conserva `PENDIENTE`, cero intentos y ninguna confirmación ficticia. Reconsolidar el mismo evento conserva el paquete y no registra un nuevo envío.

Las alertas generan `ALERTA_GENERADA`, `DUPLICADO_ALERTA_CORRELACIONADO` y eventos de reconocimiento, resolución, descarte o vencimiento según la operación real. La evidencia y el cambio se confirman juntos. Un fallo de evidencia impide confirmar la alerta. No se modifica la deduplicación RF-57 ni se escriben filas históricas desde los emisores nuevos.

### #3805 — Heartbeats, transiciones y vinculaciones

`HEARTBEAT_AUDITORIA` registra `HEARTBEAT_RECIBIDO` sin depender de que los adaptadores de diagnóstico pendientes completen sus etapas. `RF60_TRANSICIONES` consume `historico_transiciones_dispositivos` y conserva estados, dispositivo, actor disponible, causa e instante original.

La reconexión SQL existente puede insertar dos filas históricas con la misma transición y `now()`. Se conserva la fuente y se proyecta una evidencia por dispositivo/estados/instante, serializada por dispositivo. El evaluador periódico deja de insertar de nuevo una transición ya garantizada por `fn_log_transicion_dispositivo`; no se retira el trigger ni sus campos.

Se conservan `DISPOSITIVO_SIN_SEÑAL`, `DISPOSITIVO_INACTIVO`, `DISPOSITIVO_RECONECTADO`, `MANTENIMIENTO_INICIADO`, `MANTENIMIENTO_COMPLETADO` y `ESTADO_CAMBIADO` según el cambio real. La auditoría de la operación manual preexistente sigue siendo evidencia de la acción del usuario, diferenciada de la proyección del cambio de estado.

La cobertura RF-61 procede de DEV-44: `VINCULACION_AUTOMATICA`, `VINCULACION_MANUAL`, `CORRECCION_VINCULACION`, condiciones sin vinculación y `TRASLADO_PROCESADO`. No se cambia el estado de vínculos históricos ni se modifica telemetría para auditar.

### #3806 — Integridad y aviso al Administrador

`GET /iot/auditoria/verificar-integridad` y el POST compatible conservan JWT/RBAC del recurso 39, acción 5. La ruta estática se registra antes de `/{id_evento}`.

Un hash distinto genera `INTEGRIDAD_COMPROMETIDA`, resultado `FALLIDO`, severidad `CRITICAL`, con el UUID original y ambos hashes en `accion_detallada.compromiso`. Este evento es el marcador externo durable. El original no recibe UPDATE ni DELETE. Listado y detalle exponen `integridad_comprometida`, calculado desde esos marcadores; no es una nueva columna ni se incorpora al hash original.

El incidente se identifica por UUID y pareja de hashes. Un bloqueo transaccional por registro evita duplicarlo entre verificadores concurrentes. Una nueva alteración distinta puede originar otro incidente. El propio incidente tiene un hash válido, por lo que no genera recursión. Los registros sin hash y los marcados incompletos se informan separadamente; un fallo de consulta no se presenta como alteración.

Se conserva la función SHA-256 y su serialización. Para registros HTTP escritos en UTC y leídos mediante TIMESTAMPTZ en la zona de la sesión, se comprueba también la representación UTC equivalente, sin reemplazar hashes históricos. La clave del incidente utiliza una representación UTC estable.

El incidente se confirma antes del aviso. El aviso y su confirmación RF-63 forman otra transacción: una falla revierte solo esa entrega, deja `notificaciones_pendientes` y permite volver a verificar. Un aviso confirmado no se repite. El marcador de confirmación reutiliza el tipo existente y lo diferencia mediante `aviso_incidente` y `notificacion=REGISTRADA_RF14`; significa registro interno, no entrega de correo/push.

El adaptador M01 consulta el tipo real, su clasificación RF-10, el canal interno existente y las cuentas activas cuyo rol está protegido. No utiliza nombres ni identificadores de rol fijos. Correlaciona el evento M01 por UUID de incidente, evitando asociar avisos de incidentes concurrentes distintos.

**Bloqueo confirmado:** el catálogo oficial no tiene un tipo de integridad IoT compatible con RF-14. Tampoco está incorporado en la clasificación de eventos M01 disponible. No se reutiliza el evento de inconsistencia de M02, el fallo de archivado o un login. El adaptador informa `CONTRATO_AVISO_INTEGRIDAD_PENDIENTE`; no se presenta el aviso real como completado.

## Archivos modificados

| Archivo | Responsabilidad y cambio | Tarea |
|---|---|---|
| `src/telemetry/application/use_cases/auditoria/evidencia_iot.py` | Emisión obligatoria, hash existente y transacción del llamador | #3804–#3806 |
| `src/telemetry/application/use_cases/auditoria/verificar_integridad_bitacora_use_case.py` | Detección, incidente externo, concurrencia y recuperación del aviso | #3806 |
| `src/telemetry/application/use_cases/infraestructura/evaluar_estado_dispositivos_use_case.py` | Retira la transición histórica duplicada por el trigger | #3805 |
| `src/telemetry/domain/entities/evento_auditoria_iot.py` | Marca de integridad derivada, sin columna ni cambio de hash | #3806 |
| `src/telemetry/domain/repositories/bitacora_auditoria_iot_repository.py` | Contrato para bloqueo, incidentes y confirmación de aviso | #3806 |
| `src/telemetry/domain/repositories/aviso_integridad_port.py` | Puerto de notificación interna transaccional | #3806 |
| `src/telemetry/domain/repositories/postcommit_port.py` | Nuevas etapas de recuperación de evidencia | #3804/#3805 |
| `src/telemetry/infrastructure/repositories/bitacora_auditoria_iot_repository.py` | Consulta de marcadores, bloqueo por UUID y marca externa | #3806 |
| `src/telemetry/infrastructure/repositories/evidencia_fuentes_iot.py` | Proyección de lecturas, rechazos, heartbeat e historial | #3804/#3805 |
| `src/telemetry/infrastructure/repositories/alerta_repository.py` | Evidencia atómica de creación, consolidación y estados | #3804 |
| `src/telemetry/infrastructure/repositories/paquete_inferencia_repository.py` | Evidencia de paquete y resultado real de envío | #3804 |
| `src/telemetry/infrastructure/repositories/postcommit_repository.py` | Fuentes adicionales, identificadores nulos y progreso idempotente | #3804/#3805 |
| `src/telemetry/infrastructure/workers/postcommit_worker.py` | Conexión de etapas al worker real | #3804/#3805 |
| `src/telemetry/infrastructure/adapters/aviso_integridad_m01_adapter.py` | Integración RF-14 sin inventar catálogo o simular aviso | #3806 |
| `src/telemetry/infrastructure/routers/ruta_ingesta_auditada.py` | Rechazos previos al caso de uso; sesión independiente | #3804 |
| `src/telemetry/infrastructure/routers/telemetria_router.py` | Aplica captura únicamente a ingesta | #3804 |
| `src/telemetry/infrastructure/routers/auditoria_iot_router.py` | GET estático y POST compatible, ambos protegidos | #3806 |
| `src/telemetry/infrastructure/schema/bitacora_auditoria_iot_schema.py` | Marca externa, incidentes y avisos pendientes en respuesta | #3806 |
| `alembic/versions/97ecff4d7d0c_fix_seguridadmodulo03.py` | Integra DB-11 original, con seguimiento | Dependencia |
| `alembic/versions/ab47d0630022_merge_db11_db13.py` | Unión de heads oficiales; sin DDL adicional | Dependencia |
| `tests/telemetry/test_dev47_auditoria_integridad.py` | Hash, incidentes, avisos, RBAC y categorías de error | #3804–#3806 |
| `tests/integration/test_dev47_auditoria_integridad.py` | Persistencia, rollback, API, triggers y concurrencia | #3804–#3806 |
| `tests/integration/test_dev05_ingesta_bplus_postcommit.py` | Exige los eventos nuevos sin debilitar la idempotencia anterior | #3804/#3805 |
| Este informe | Diagnóstico, evidencia, límites y propuesta de PR | #3703 |

## Base de datos y migraciones

Se utiliza `modulo3.bitacora_auditoria_iot` como bitácora central. `telemetrias`, `bitacora_ingest`, `heartbeats` e `historico_transiciones_dispositivos` son fuentes confirmadas para recuperación; `alertas`, `paquetes_inferencia` y los vínculos existentes conservan sus repositorios y transacciones.

No se crea una tabla de auditoría, incidentes, transporte o buffer. La marca de compromiso utiliza la estructura JSONB existente. La única migración con DDL incorporada es DB-11 oficial: protege UPDATE/DELETE en las bitácoras M03 y M04. `ab47d0630022` une DB-11 con DB-13 sin agregar esquema. Alembic queda con un único head.

Las pruebas utilizan PostgreSQL 18 local en puerto 55447, con migraciones reales, savepoints y bases desechables para commits/concurrencia. La simulación de corrupción inserta una copia con hash inconsistente; no desactiva DB-11 para alterar una fila protegida. También se comprueba que UPDATE y DELETE reales sean rechazados. No se escribieron pruebas ni migraciones en `sgpmp_dev`.

Al finalizar se detuvo y eliminó exclusivamente el clúster temporal DEV-47, tras comprobar su ruta y puerto. Los XML, logs y consultas de evidencia permanecen en `.pytest_cache`.

## Pruebas y evidencia

**1.232 pruebas distintas aprobadas. 0 fallidas y 0 omitidas** al consolidar las últimas ejecuciones por caso: **1.151 unitarias y 81 de integración PostgreSQL**. La regresión unitaria conjunta aprobó 1.147; la focalizada de cierre aprobó 43 (17 unitarias. 21 PostgreSQL DEV-47 y 5 de auditoría M04). Trece de esas unitarias ya estaban en la regresión y no se vuelven a sumar. Se conservan además 55 regresiones PostgreSQL DEV-05/DEV-44 aprobadas en la ejecución amplia. Los intentos exploratorios con fallos de fixtures/aserciones no se cuentan como casos adicionales.

La ejecución amplia de integración tuvo una aserción incorrecta sobre el tipo de excepción de auditoría; el cierre focalizado repitió y aprobó todos los casos DEV-47 tras corregirla. El consolidado reemplaza el archivo de pruebas DEV-47 por su última ejecución completa, incluida la prueba renombrada de independencia del consumo de bitácora. No se afirma que una sola invocación haya ejecutado las 1.232 pruebas.

Controles finales: **23 archivos Python** con AST y seguimiento válidos; **0 hallazgos alta/alta y 0 errores de análisis de Bandit**; `git diff --check` sin errores; head Alembic único `ab47d0630022`. Semgrep y Bearer no se ejecutaron localmente.

| Verificación | Evidencia y alcance |
|---|---|
| Resultado por lectura y batch | HTTP real contra aplicación de pruebas; función PostgreSQL usada por MQTT |
| Recuperación independiente del consumo del log auxiliar | Lectura confirmada por INSERT controlado; evento recuperado antes de procesar su bitácora SQL, sin modificarla |
| Paquetes | Stub real pendiente; puertos dobles para entrega positiva/negativa; persistencia real |
| Alertas | Creación/estado/consolidación y rollback real de negocio/evidencia |
| Heartbeats y transiciones | Triggers reales, reconexión y evidencia idempotente |
| RF-61 | Regresión DEV-44 de vínculos, correcciones, traslados y sus eventos |
| Integridad | Hash inconsistente, marca externa, repetición sin nuevo incidente y permisos HTTP |
| Concurrencia | Dos sesiones PostgreSQL: un incidente y una confirmación; recuperación por lectura una vez |
| Aviso | Puerto doble para éxito/recuperación; adaptador M01 real detecta el contrato ausente |
| DB-11/M04 | Inmutabilidad real y regresión de auditoría M04 |
| Controles | Alembic, sintaxis, seguimiento, Bandit y `git diff --check` |

Los ensayos iniciales detectaron precondiciones incompletas de pruebas: cuenta activa mal representada, causa obligatoria de inactividad y lectura/bitácora sintéticas conservadas por pruebas de concurrencia anteriores. Se corrigieron fixtures y se limitaron los conteos al dispositivo o al intento correspondiente. Una prueba esperaba el RuntimeError interno, pero el repositorio lo traduce correctamente a InfrastructureError público: se comprueba esa traducción y el rollback. Las aserciones antiguas DEV-05 se ampliaron para exigir los nuevos eventos, incluyendo su cardinalidad; no se eliminaron validaciones funcionales.

Evidencia local ignorada por Git en `.pytest_cache`: `dev47_unit_final.xml`/`.log`, `dev47_pg_final.xml`/`.log`, `dev47_cierre.xml`/`.log`, `dev47_resultados_consolidados.json`, `dev47_archivos.json`, `dev47_bandit.json`, `dev47_migraciones.log`, `dev47_oficial_esquema.json` y `dev47_oficial_notificaciones.json`. No contienen credenciales incorporadas al repositorio.

### Comandos ejecutados

```powershell
.venv/Scripts/python.exe -m alembic upgrade head
.venv/Scripts/python.exe -m alembic heads
.venv/Scripts/python.exe -m pytest tests/telemetry tests/shared tests/configuration tests/prediction -q --import-mode=importlib
.venv/Scripts/python.exe -m pytest tests/telemetry/test_dev47_auditoria_integridad.py tests/integration/test_dev47_auditoria_integridad.py tests/integration/test_dev05_ingesta_bplus_postcommit.py tests/integration/test_dev44_vinculacion_contexto.py -q --import-mode=importlib
.venv/Scripts/python.exe -m pytest tests/telemetry/test_dev47_auditoria_integridad.py tests/integration/test_dev47_auditoria_integridad.py tests/integration/test_dev03_auditoria_m04_enum_integration.py -q --import-mode=importlib
.venv/Scripts/python.exe -m bandit -r src/telemetry -lll -iii
git diff --check
```

En Windows se ejecutó pytest mediante `pytest.main(...)`, con puente de `fcntl` exclusivo del ejecutor y archivos XML/log. Se habilitó el socket local que necesita TestClient/AnyIO. No se modificó código productivo para resolver la diferencia con Unix. Los bloqueos PostgreSQL sí se ejercitaron realmente. La preparación utiliza el propietario de la base aislada: no acredita una regresión específica de RLS con el rol de aplicación. En el endpoint RF-63 se controlan identidad y consulta de permisos con dobles para comprobar 403/200; la regresión RF-61 conserva sus casos JWT y permisos persistidos. No se presenta el endpoint RF-63 como una prueba JWT extremo a extremo.

## Dependencias y pendientes

| Área / dependencia | Estado y acción pendiente | Tarea |
|---|---|---|
| BD / DB-11 | Integrada y probada localmente; coordinar despliegue oficial. La consulta oficial no mostraba sus triggers | #3804–#3806 |
| DEV-44 / DB-13 | La rama se apoya en la implementación RF-61 existente; integrar su PR/base antes de evaluar el diff final contra dev | #3805 |
| M01 / RF-10/RF-14 | Aprobar e incorporar el tipo de integridad IoT, su clasificación y semilla oficiales; comprobar avisos internos reales con cuentas autorizadas | #3806 |
| Broker / AIoT | Validar entrega MQTT extremo a extremo. La función de persistencia es real; no se dispuso de un broker de pruebas en esta validación | #3804/#3805 |
| Motor IA | La entrega positiva/negativa se verifica con un doble de puerto. No acredita entrega a un motor real; el stub sigue pendiente | #3804 |
| QA | Verificar los contratos en el entorno con dependencias desplegadas y repetir E6 con notificación disponible | #3703 |

Solicitud técnica preparada para M01/BD: confirmar el tipo aprobado para el aviso de integridad IoT y proporcionar su incorporación a `modulo1.tipos_eventos` y al contrato de clasificación RF-10. No se requiere una tabla nueva ni un identificador fijo. Tras integrarlo, verificar que un incidente genere avisos internos para las cuentas administrativas activas, que repetir la verificación no repita avisos y que un fallo de notificación conserve el incidente. No se enviaron mensajes a terceros.

Discrepancias funcionales conservadas explícitamente: la especificación menciona publicación por broker persistente y un hash de todos los campos; el repositorio utiliza recuperación DEV-05 y una canonicalización histórica que cubre un subconjunto. Este cambio conserva esa fórmula y no afirma una garantía de broker, latencia inferior a dos segundos ni detección de alteraciones en campos que esa fórmula no cubre. Ampliar la canonicalización exige un contrato/versionado de hashes; no se recalculó evidencia histórica.

| Tarea | Estado |
|---|---|
| #3804 | Implementada y verificada en los componentes disponibles; MQTT extremo a extremo y motor real no acreditados |
| #3805 | Cobertura conectada y regresión RF-61; depende de integrar la base DEV-44/DB-13 |
| #3806 | Parcial: detección, incidente y marca externa implementados; aviso RF-14 bloqueado por catálogo/clasificación |
| #3703 | No cerrar hasta completar el aviso y las validaciones de integración pendientes |

## Estado Git

Rama `fix/dev47-auditoria-iot-integridad`, creada desde `80f8e92b` de DEV-44. `origin/dev` consultado: `6113a388`. El diff contra dev incluye las dependencias DB-13/DEV-44 hasta que se integren. Los cambios DEV-47 se mantienen en esta rama, separados de los archivos de pendientes previos. Los documentos de pendientes anteriores y `AGENTS.md` se conservaron fuera del alcance.

## Propuesta de PR

**Título:** RF-63 — Cobertura de auditoría IoT e integridad con incidentes idempotentes · DEV-47

**Referencias:** #3703, #3804, #3805, #3806. Entrega parcial mientras RF-14 carezca del contrato de aviso; no usar cierre automático de toda la historia.

### Desvío

| RF exige | Antes | Ahora |
|---|---|---|
| Evidencia central de operaciones IoT | Resultados repartidos entre bitácoras específicas | Eventos RF-63 con hash y recuperación post-commit |
| Paquetes y alertas trazables | Cambios persistidos sin toda su evidencia | Evento y cambio comparten transacción |
| Heartbeats y transiciones auditados | Los cambios SQL no siempre llegaban a RF-63 | Proyección recuperable desde fuentes confirmadas |
| Detectar y marcar alteraciones | Incidentes repetidos, sin marca durable ni aviso | CRITICAL idempotente y marca externa; aviso preparado pero pendiente de M01 |

### Causa raíz

Los emisores funcionales no utilizaban sistemáticamente la bitácora central. El verificador escribía un evento best-effort por cada consulta, lo atribuía a RF-62 y no mantenía identidad del incidente ni progreso del aviso.

### Cambios

- Evidencia obligatoria reutilizando el hash existente, sin commits implícitos.
- Recuperación por lectura y resultado de ingesta, HTTP/batch y persistencia MQTT.
- Auditoría transaccional de paquetes y alertas, conservando el stub pendiente.
- Heartbeats/transiciones desde el worker DEV-05 y cobertura RF-61 existente.
- GET de integridad protegido, POST compatible, marca externa y control concurrente.
- Integración de DB-11 oficial y unión con DB-13, sin tabla adicional.

### Pruebas realizadas

1.232 pruebas distintas aprobadas (1.151 unitarias y 81 PostgreSQL), sin fallidas ni omitidas en el consolidado final; no se suman reejecuciones. PostgreSQL y los triggers son reales; motor, aviso positivo y transporte MQTT extremo a extremo no se presentan como integraciones reales.

### Contrato resultante

Los cambios confirmados tienen evidencia con hash; los errores post-commit conservan la telemetría y se recuperan. Un hash inconsistente genera un incidente CRITICAL sin editar el original. Repetir la verificación no duplica el incidente. Los avisos pendientes se informan explícitamente y pueden recuperarse cuando exista su contrato RF-14.

### Compatibilidad y pendientes

Se conservan autenticación/RBAC, estados de paquetes, reglas de calidad y deduplicación, historial de alertas y canonicalización SHA-256. Requiere desplegar DB-11 e integrar DEV-44/DB-13. Falta el tipo/clasificación RF-14 y la validación con broker y canales reales.

### Revisión contra dev

Rama `fix/dev47-auditoria-iot-integridad`; base de trabajo `80f8e92b`. El commit de DEV-47 debe revisarse desde esa base para separar las dependencias. Revisar el diff propio desde esa base, o esperar a integrar las dependencias antes de apuntar a `dev`.
