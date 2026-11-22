# DEV-49 — RF-57: historial, auditoría del 403 y eventos técnicos

Fecha: 2026-10-21. Responsable: Leandro Estiven Ramirez.
Historia #3693, épica #3667. Tareas #3778, #3779 y #3780.
Rama: `fix/dev49-alertas-historial-auditoria`.
Base verificada: `origin/dev`, `6113a388`.

## 1. Resumen y estado

Se eliminaron tres escrituras redundantes de historial, se preservaron sus
motivos mediante los triggers existentes, se implementó auditoría de los 403
en las rutas operativas y se registran los diagnósticos de calidad y fallos del
motor sin modificar las garantías previas de los paquetes de inferencia.

**DEV-49 no está cerrado integralmente:** la ventana configurable de #3779
depende del contrato de DEV-14, todavía no integrado. No se inventaron claves,
semillas ni otra fuente de configuración para ocultar esa dependencia.

| Tarea | Estado | Alcance |
|---|---|---|
| #3778 | Implementada y probada en PostgreSQL aislado | Historial único en creación y transición, con actor, motivo y rollback |
| #3779 — bitácora del 403 | Implementada y probada | GET listado/detalle y PATCH operativos, incluso rechazo dentro del endpoint |
| #3779 — deduplicación dinámica | Bloqueada por contrato DEV-14 | La ventana de 30 min continúa en el flujo existente; no se presenta como corregida |
| #3780 | Implementada y probada en el alcance backend | Exclusión por calidad, motor no integrado, indisponibilidad y otros fallos de entrega |

El commit de DEV-30 no está integrado en
la base de esta rama y no se copió su solución: permisos de descarte, CERRADA y
VENCIDA siguen correspondiendo a DEV-30. La auditoría de ruta captura también
un 403 emitido desde el endpoint, para facilitar su integración posterior.

## 2. Diagnóstico confirmado

### Historial duplicado

Se encontraron INSERT explícitos en:

1. `GenararAlertaUseCase.execute`: creación ACTIVA → ACTIVA.
2. `ActualizarEstadoAlertaUseCase.execute`: transición manual.
3. `EvaluarEstadoDispositivosUseCase.execute`: creación de alerta técnica.

La consulta directa a `sgpmp_dev` confirmó que ya están activos:

- `trg_rf57_02_historico_inicial`: registra la creación con el estado inicial.
- `trg_rf57_03_validar_transicion`: valida la transición y registra estado
  anterior/nuevo, fecha y actor dentro de la misma transacción.

El trigger de transición conservaba el motivo de DESCARTADA y el diagnóstico
de RESUELTA, pero no el motivo enviado para EN_ATENCION. El motivo libre de
RESUELTA tampoco se transportaba al trigger. Borrar únicamente los INSERT de
Python habría eliminado información que antes estaba en la fila redundante.

### Rechazos de autorización

El permiso se comprueba antes de entrar al caso de uso. Los handlers compartidos
construyen el error HTTP, pero no insertan un evento RF-63 por esos rechazos.
La auditoría de transiciones inválidas ya existía; se conserva.

### Deduplicación

`GenararAlertaUseCase` sigue llamando a `buscar_activa_duplicada` con
`ventana_min=30`. El puerto y repositorio también tienen ese valor predeterminado.
DEV-14 solo proporciona en el puerto de alertas el umbral de confianza Edge/IA.
La ventana de confirmación de una regla y la ventana temporal del motor son
parámetros distintos; no se reutilizaron como deduplicación global.

### Calidad y motor

- El caso de generación ya excluía FUERA_DE_RANGO y ERROR_CALIBRACION, pero solo
  devolvía un motivo; no registraba el diagnóstico RF-57 en bitácora.
- El stub ya lanza `MotorInferenciaNoIntegradoError`, preserva el paquete en
  PENDIENTE y registra un warning de aplicación. Faltaba el evento persistido.
- El puerto diferencia True como entrega confirmada y False como intento de
  entrega fallido. No representa un diagnóstico clínico negativo ni demuestra
  que una inferencia ya se haya calculado.
- Reconsolidar un evento que ya tiene paquete devuelve ese mismo paquete sin
  volver a enviar. Se conserva esa semántica y su bloqueo por evento.

## 3. Archivos modificados

| Archivo | Cambio y justificación | Tarea |
|---|---|---|
| `src/telemetry/application/use_cases/alertas/generar_alerta_use_case.py` | Elimina el INSERT histórico de creación y registra la exclusión por calidad con campos conocidos | #3778 / #3780 |
| `src/telemetry/application/use_cases/alertas/actualizar_estado_alerta_use_case.py` | Elimina el INSERT histórico de transición y conserva commit, rollback y auditoría de rechazo existentes | #3778 |
| `src/telemetry/application/use_cases/infraestructura/evaluar_estado_dispositivos_use_case.py` | Elimina el tercer INSERT redundante y conserva motivo/estado operativo en metadatos de la alerta técnica | #3778 |
| `src/telemetry/infrastructure/repositories/alerta_repository.py` | Transporta el motivo como contexto local antes del autoflush; no escribe en el historial | #3778 |
| `alembic/versions/6af49e8c2d10_dev49_rf57_motivo_historial_unico.py` | Adapta las dos funciones de trigger para conservar los motivos al eliminar la segunda fila | #3778 |
| `src/telemetry/infrastructure/routers/ruta_alerta_auditada.py` | Captura el 403 de dependencias o endpoint y reutiliza RF-63 después del rollback, sin cambiar RBAC compartido | #3779 |
| `src/telemetry/infrastructure/routers/alerta_router.py` | Instala la ruta auditada y captura identidad antes del permiso; conecta bitácora de calidad | #3779 / #3780 |
| `src/telemetry/application/use_cases/inferencia/consolidar_paquete_inferencia_use_case.py` | Distingue y registra los fallos del motor después de persistir el estado correspondiente | #3780 |
| `src/telemetry/application/use_cases/inferencia/recibir_evento_edge_use_case.py` | Propaga el repositorio de bitácora a consolidación y alertas; hace visible el fallo best-effort de generación | #3780 |
| `src/telemetry/infrastructure/routers/evento_edge_router.py` | Inyecta el repositorio RF-63 real en el flujo Edge | #3780 |
| `tests/telemetry/test_dev49_alertas_historial_auditoria.py` | 17 casos con dobles de puertos y HTTP: autorización, calidad, disponibilidad y fallos de persistencia/auditoría | Todas |
| `tests/integration/test_dev49_alertas_historial_auditoria.py` | 11 casos con JWT/broker, repositorios y triggers reales en PostgreSQL exclusivo | Todas salvo configuración pendiente |
| `anotaciones/modulo_3/dev49_rf57_historial_auditoria_deduplicacion.md` | Evidencia, límites, dependencia y propuesta de PR | #3693 |

Todos los Python creados/editados incluyen la tabla de seguimiento con la fecha
y el valor real de `git config user.name`: `Leandro`. Se mantienen las firmas
de los ensambladores existentes; los repositorios de historial ya no reciben
llamadas de escritura desde los casos de uso de telemetría.

## 4. Implementación

### Historial único y motivos

El trigger es el único escritor del historial durante estas operaciones. La
alerta y su fila histórica se confirman o revierten juntas.

La revisión Alembic `6af49e8c2d10`, sobre `e5a3c9b17d42`, es necesaria para
conservar información, no para habilitar estados ni eliminar protecciones:

- En transición, el repositorio fija `app.rf57_motivo_transicion` con
  `set_config(..., true)` antes de modificar el ORM. El trigger usa ese motivo
  cuando está presente y conserva sus motivos anteriores como alternativa.
- El contexto es local a la transacción y se limpia cuando no hay motivo.
  Se verificó que una operación posterior no hereda el motivo anterior.
- El actor sigue obteniéndose de los campos existentes de atención/resolución.
- En creación técnica, el motivo `Dispositivo en estado ...` se conserva en
  `metadato_evento.motivo_generacion` y lo recoge el trigger inicial. Las demás
  creaciones conservan su motivo anterior basado en el origen.
- El downgrade restaura las dos funciones previas. No crea tablas, columnas,
  permisos ni estados, y no reintroduce los INSERT de Python.

El despliegue debe incorporar esta migración junto con el código para preservar
todos los motivos. No se aplicó en la base oficial ni se limpiaron históricos
duplicados existentes; la corrección evita duplicados en operaciones nuevas.
La instancia PostgreSQL desechable se detuvo y retiró al terminar; se conservaron
los reportes locales de ejecución.

### Auditoría del 403

`RutaAlertaAuditada` se limita al router operativo. Captura la identidad y la
sesión autenticadas antes de RBAC. Cuando se produce un 403:

1. Conserva la excepción y su respuesta HTTP.
2. Revierte la transacción de negocio.
3. Usa `RegistrarEventoAuditoriaIotUseCase` para registrar el rechazo en una
   transacción nueva, siguiendo el patrón ya existente de RF-63.

El evento `ACCESO_DENEGADO` contiene
usuario, fecha, operación, ruta parametrizada, recurso, acción, alerta cuando
corresponde, resultado RECHAZADO y hash de integridad. No se copian headers,
tokens, query strings ni el cuerpo de la petición. Un indicador de request evita
registrar el mismo 403 dos veces dentro de esa ejecución.

Los 400, 401, 404 y 422 conservan sus contratos. Los demás routers no utilizan
esta clase y su política global de autorización no cambia.

### Calidad E2

FUERA_DE_RANGO y ERROR_CALIBRACION producen `LECTURA_EXCLUIDA_RF57` en la bitácora
RF-63, clasificado TECNICO y con resultado RECHAZADO. Se conserva estado de
calidad, sensor, dispositivo, variable, valor, unidad, fecha y referencias de
telemetría/Edge/paquete disponibles, sin copiar metadatos arbitrarios.

No se consulta deduplicación ni se genera una alerta funcional en ese camino.
La telemetría original no se actualiza. La respuesta previa del endpoint se
conserva: resultado sin `id_alerta`, bajo el HTTP 201 existente del receptor.

Los registros RF-53 de ingesta y este diagnóstico RF-57 representan operaciones
distintas; no se duplica la misma evaluación de calidad ni se modifican aptitudes.

### Motor E3

Se reutiliza la bitácora existente; `tipo_evento` es texto de hasta 80 caracteres,
no un catálogo SQL cerrado. Los nuevos diagnósticos son identificadores explícitos
de esta implementación, no tipos de catálogo que se afirme que ya existían.

| Resultado del puerto | Paquete | Evento técnico | Resultado del evento |
|---|---|---|---|
| Stub sin integración | PENDIENTE, cero intentos | MOTOR_INFERENCIA_NO_INTEGRADO | ADVERTENCIA |
| Timeout, conexión o ServiceUnavailableError | FALLIDO, un intento | MOTOR_INFERENCIA_NO_DISPONIBLE | FALLIDO |
| Retorno False | FALLIDO, un intento | ENVIO_INFERENCIA_NO_CONFIRMADO | FALLIDO |
| Otra excepción técnica | FALLIDO, un intento | ERROR_ENVIO_INFERENCIA | FALLIDO |
| Retorno True | ENVIADO, un intento | Sin evento de indisponibilidad | No aplica |
| Reconsolidación del mismo evento | Conserva ID y estado previos | Sin nuevo evento ni nuevo envío | No aplica |

El diagnóstico se inserta después del commit del paquete/estado. La prueba HTTP
Edge → paquete → alerta comprueba PENDIENTE, flag de inferencia no disponible,
severidad MODERADO tomada del Edge y una sola fila histórica de creación.

No se implementó transporte IA-1 ni se presentaron dobles de entrega como una
inferencia real. No se alteró el comportamiento previo de reintentos.

## 5. Dependencia DEV-14 y deduplicación pendiente

Se revisaron el código, las migraciones, el informe DEV-14 y **la base oficial**
`sgpmp_dev`, con `member_dev` y `transaction_read_only=on`. La reverificación
del 2026-10-21 a las 15:54 UTC confirmó:

- `modulo9.configuraciones_globales` solo tiene ID, frecuencia_muestreo,
  heartbeat, usuario, fecha y es_activo. No existe una columna de deduplicación.
- La consulta a `modulo4.parametros_mlops` no devuelve parámetros de
  deduplicación/alertas/confianza. Esa tabla no tiene RLS, por lo que ese resultado
  no proviene de una política que oculte filas al usuario consultado.
- El puerto `ParametrosAlertasPort` solo declara `obtener_confianza_edge_ia`.
- `anotaciones/modulo_9/dev14_solicitud_samuel.md` propone
  `ventana_deduplicacion_alertas_min`, entero positivo en minutos, en M09 global.
  El propio documento dice que los nombres finales dependen de revisión DBA.
  Es una propuesta, no un contrato desplegado/aprobado que pueda asumirse.

Se solicitó al usuario confirmar ese contrato o identificar su ubicación vigente.
No se creó otra tabla, una clave MLOps alternativa ni una semilla ficticia.

**Lo que sigue pendiente:** confirmar nombre, ubicación, unidades y validaciones;
integrar lectura mediante DEV-14; eliminar la constante y los defaults del flujo
operativo; probar cambios persistidos sin reiniciar el consumidor y los casos de
configuración ausente/inválida. Los escenarios obligatorios TC-08, TC-09 y TC-10
no se presentan como implementados ni ejecutados.

La ventana actual de 30 minutos permanece como comportamiento previo explícito,
no como un fallback nuevo ni como una solución definitiva de DEV-49.

## 6. Pruebas ejecutadas y evidencia

### Resultados sin duplicados

| Ejecución | Objetivo | Resultado | Evidencia local |
|---|---|---|---|
| Telemetría disponible en Windows | Regresión y 17 casos nuevos de aplicación/HTTP | 210 aprobadas | `.pytest_cache/dev49_telemetry.xml` |
| DEV-49 PostgreSQL | 11 casos nuevos con triggers, JWT y broker | 11 aprobadas | Parte de `.pytest_cache/dev49_postgresql_final.xml` |
| DEV-04 SQLSTATE y DEV-17 PostgreSQL | Regresión de errores, paquetes y reconsolidación | 24 aprobadas | Mismo XML, ejecución conjunta: 35 aprobadas |
| Alembic | Construcción desde cero y downgrade/upgrade de DEV-49 | Correcto en base exclusiva | `.pytest_cache/dev49_migrations.log` y test de migración |
| Bandit | Análisis de los nueve archivos de aplicación creados/editados | Sin hallazgos, 1368 líneas analizadas | `.pytest_cache/dev49_bandit_final.txt` |
| SQL offline | Generación del upgrade entre la base y la revisión DEV-49 | Correcta, sin conexión ni aplicación a DEV | `.pytest_cache/dev49_migracion_offline.sql` |
| AST y seguimiento | Sintaxis y cabeceras de los 12 Python creados/editados | Correcto | Comprobación ejecutada contra `git config user.name` |
| Diff | Espacios y conflictos de edición | Correcto | `git diff --check` |
| Base oficial | Contratos y triggers vigentes, solo lectura | Consulta correcta; dependencia DEV-14 confirmada | `.pytest_cache/dev49_bd_oficial.json` |

**Total: 245 pruebas distintas aprobadas; 0 fallidas y 0 omitidas por pytest en
estas ejecuciones finales.** Los ensayos dirigidos iniciales de 28/45 y los de
10/34 pruebas PostgreSQL se solapan con las ejecuciones finales y no se suman.
Los tres escenarios de parametrización pendientes no son pruebas aprobadas ni
se han añadido como tests vacíos con skip.

### Casos relevantes

| Caso | Resultado observado |
|---|---|
| TC-01 / TC-02 | Una fila inicial y una fila adicional por transición; actor y motivo correctos |
| TC-03 | Transición inválida: 422 sin modificación de alerta ni nuevo historial |
| TC-04 | Fallo inducido en commit: rollback de alerta e historial, sin filas huérfanas |
| TC-05 / TC-06 / TC-07 | GET listado/detalle y PATCH sin permiso: 403, un evento persistido y ningún cambio de alerta |
| TC-08 / TC-09 / TC-10 | Pendientes del contrato DEV-14; no ejecutados |
| TC-11 | Lectura válida: creación HTTP y transición autorizada conservadas |
| TC-12 / TC-13 | Dos clasificaciones inválidas: lectura intacta, registro TECNICO y ninguna alerta funcional |
| TC-14 / TC-15 | Stub real: evento técnico persistido, paquete PENDIENTE y alerta local con flag |
| TC-16 | Reconsolidación: mismo paquete, ningún nuevo envío ni diagnóstico duplicado |
| TC-17 | Flujos HTTP completos y regresiones disponibles aprobados, con los límites de entorno indicados |

También se probaron retorno False, timeout, excepción inesperada, fallo de
persistencia, fallo de auditoría, 403 dentro del endpoint y aislamiento del motivo
entre operaciones. Los resultados del motor distintos del stub usan dobles del
puerto; no prueban comunicación real con IA.

### Comandos principales

```powershell
& .venv/Scripts/python.exe -m pytest --confcutdir=tests/telemetry tests/telemetry `
  --ignore=tests/telemetry/test_dev06_token_servicio_broker.py `
  --ignore=tests/telemetry/test_dev11_eventos_buffer.py `
  --ignore=tests/telemetry/test_inc_m09_77_g137_observaciones_vision.py `
  -q --tb=short --junitxml=.pytest_cache/dev49_telemetry.xml

# Solo contra PostgreSQL desechable, nunca contra sgpmp_dev:
$env:DATABASE_URL = 'postgresql+psycopg2://postgres@127.0.0.1:55439/sgpmp_dev49_test'
$env:ALEMBIC_DATABASE_URL = $env:DATABASE_URL
$env:TEST_DATABASE_URL = $env:DATABASE_URL
& .venv/Scripts/python.exe -m alembic upgrade head
& .venv/Scripts/python.exe -X utf8 -m alembic upgrade e5a3c9b17d42:head --sql
& .venv/Scripts/python.exe -m alembic downgrade e5a3c9b17d42
& .venv/Scripts/python.exe -m alembic upgrade head
& .venv/Scripts/python.exe -m pytest --confcutdir=tests/integration `
  tests/integration/test_dev49_alertas_historial_auditoria.py `
  tests/integration/test_dev04_sqlstate.py `
  tests/integration/test_rf56_dev17_paquetes_pendientes.py `
  -q -rs --tb=short --junitxml=.pytest_cache/dev49_postgresql_final.xml
git diff --check
```

## 7. Regresiones y límites

- Los tres módulos excluidos importan `main.py`, que carga la dependencia Linux
  `fcntl` de M02. Esa limitación fue comprobada previamente en este entorno y
  sigue presente. No se modificaron esas pruebas ni se simularon sus resultados;
  falta ejecutarlas, junto con la suite general, en Linux.
- Las pruebas HTTP PostgreSQL usan el router, handlers y JWT reales; la conexión
  de prueba es administrativa. No equivalen a desplegar el sistema con RLS y el
  rol PostgreSQL de aplicación en DEV/TEST.
- En la creación técnica se aíslan los puertos de estados y períodos; la
  persistencia de la alerta y sus triggers sí se ejecutan contra PostgreSQL.
- Se observó la advertencia preexistente Starlette/httpx; no produjo fallos.
- La primera generación de SQL offline falló por la salida cp1252 de Windows y
  la flecha del mensaje existente del trigger. Se verificó correctamente con
  `python -X utf8`, sin cambiar el mensaje ni las reglas del trigger.
- No se ejecutaron Semgrep ni Bearer localmente.
- RF-63 es best-effort. Si falla la bitácora se conserva el 403 o el paquete ya
  confirmado y se emite un warning. No se agregó un buffer paralelo ni se promete
  una recuperación durable nueva de eventos de auditoría.
- La reconsolidación idempotente se refiere al mismo evento persistido. No se
  implementó una nueva clave de idempotencia de recepción HTTP Edge.
- La eliminación de INSERT evita duplicados nuevos; no elimina ni reescribe
  históricos existentes.

## 8. Pendientes de cierre

1. Confirmar e integrar el contrato persistente de la ventana RF-57 en DEV-14.
2. Implementar su consumo y ejecutar TC-08, TC-09 y TC-10 con cambios reales de BD
   sin reiniciar el consumidor. Hasta entonces #3779 y #3693 siguen parciales.
3. Desplegar la revisión `6af49e8c2d10` junto con el código mediante el proceso
   habitual y verificarlo con QA. No se aplicó a bases compartidas.
4. Completar la regresión dependiente de Linux y la validación del rol PostgreSQL
   de aplicación cuando el entorno lo permita.

No se modificaron frontend, permisos, reglas de calidad/aptitud ni contratos de
transporte IA. Los archivos AGENTS.md y los documentos previos de pendientes
continúan fuera del cambio. El commit se limita a los 13 archivos de DEV-49 y
se publica únicamente esta rama, sin crear un PR remoto.

## 9. Propuesta de Pull Request

### Título

`fix(rf57): evitar historial duplicado y auditar rechazos y fallos técnicos (DEV-49)`

### Descripción

```markdown
## Desvío identificado

RF-57 duplicaba el historial de creación/transición mediante INSERT de Python
y triggers. Los 403 no dejaban bitácora RF-63; las lecturas excluidas por calidad
y la falta de motor tampoco conservaban el diagnóstico requerido.

Refs: #3693, #3778, #3779 y #3780.

## Causa raíz

La aplicación repetía una responsabilidad de PostgreSQL y la autorización fallaba
antes del caso de uso. El motor distinguía estados de entrega, pero solo dejaba
un warning cuando no estaba integrado. El motivo de algunas transiciones solo
existía en la fila histórica redundante.

## Cambios

- Tres INSERT históricos redundantes eliminados; un único escritor por trigger.
- Migración 6af49e8c2d10 conserva motivos de transiciones y creaciones técnicas.
- Auditoría de 403 limitada al router operativo, con rollback previo y patrón RF-63.
- Registro técnico de FUERA_DE_RANGO y ERROR_CALIBRACION sin generar alertas.
- Diagnósticos diferenciados de motor no integrado, indisponible y entrega fallida.
- Persistencia previa de paquetes y reconsolidación idempotente conservadas.

## Pruebas

245 pruebas distintas aprobadas: 210 de telemetría y 35 PostgreSQL, incluyendo
DEV-04 y DEV-17. Sin fallos en esas ejecuciones. Bandit y git diff --check correctos.
Upgrade/downgrade probado exclusivamente en PostgreSQL desechable.

Tres módulos requieren Linux/fcntl y no están incluidos en ese conteo.
La entrega real al motor IA no se probó: se verificaron el stub y dobles del puerto.

## Dependencias y pendientes

La parametrización de deduplicación sigue pendiente de DEV-14: la base oficial
sgpmp_dev todavía no tiene el campo de ventana y el puerto no publica su lectura.
El nombre documentado es una propuesta pendiente de confirmación; se conserva
explícitamente la ventana actual de 30 minutos, sin presentarla como corregida.
TC-08, TC-09 y TC-10 quedan pendientes. No se cierra integralmente #3693.

Se requiere desplegar la migración junto con el código y reevaluar en QA.
No se modificaron bases compartidas ni se mezclaron los cambios de DEV-30.
```

No se utiliza `Closes` mientras siga pendiente la parte configurable de #3779.
