# RF-61 — Estados, causas, contexto histórico y traslados · DEV-44

Historia #3702 · tareas #3801, #3802 y #3803 · épica #3667.

Fecha: 2026-10-22. Responsable: Leandro Estiven Ramirez. Identidad Git consultada: `Leandro`.

## Estado de entrega

Implementación parcial preparada para revisión. La historia no puede cerrarse todavía: faltan la integración efectiva de avisos RF-61/RF-57, las definiciones de edad y estado sanitario histórico y la comprobación contra el contrato definitivo de DEV-23. La entrega se prepara en la rama `fix/dev44-vinculacion-contexto-traslados`.

## Desvío y causa raíz

| RF-61 exige | Antes | Resultado implementado |
|---|---|---|
| Estados oficiales DB-13 | `VINCULADA` y `CORREGIDA` en aplicación y funciones SQL | `CONFIRMADA`, `PENDIENTE_REVISION` y `SUPERADA`; se conservan `AMBIGUA` y `SIN_VINCULAR` del catálogo |
| E1/E2 diferenciados | Ausencia de candidatos sin causa persistida | `CONFIGURACION_INCOMPLETA` frente a `SIN_ACTIVOS_EN_ESTRUCTURA`, con evidencia RF-63 |
| Ambigüedad revisable | Sin contexto suficiente para revisar | Candidatos persistidos; no se elige por orden de consulta |
| A4 histórico | Consulta sin snapshot biológico persistido | Fuentes históricas a la captura, fase, peso con unidad y referencias de origen; datos no disponibles explícitos |
| Traslados coherentes | RF-48 no cerraba vinculaciones RF-61 | Cierre del origen como `SUPERADA` dentro de la transacción RF-48; el destino se vincula al recibir sus propias lecturas |
| E1/E3 con avisos reales | Sin integración confirmada | Etapa recuperable y destinatarios autorizados preparados; falta conectar un proveedor aprobado |

La entidad y el ORM conservaban literales anteriores a DB-13. RF-61 no distinguía la falta de asociación RF-22 de una estructura identificada sin activos. RF-48 persistía ubicación y movimiento sin actualizar RF-61. La consulta de candidatos no reconstruía el contexto biológico temporal.

## Dependencias verificadas

| Dependencia | Evidencia y estado |
|---|---|
| DB-13 | Encontrada en `origin/fix/VinculacionRF61`, commit `626abdf1948edc0fcf46e925b17f1cf28a2f82ac`; revisión `04cdc3f4d54a`, padre `e5a3c9b17d42`. La rama de trabajo parte de ese commit. |
| Base oficial | Consulta de solo lectura a `158.69.200.27:5447/sgpmp_dev`, usuario `member_dev`. El enum consultado conserva los cuatro estados anteriores; no aparecen `causa` ni `contexto_activo`. No se ejecutaron escrituras oficiales. |
| RF-57 | Hay infraestructura de alertas técnicas; no se encontró regla de catálogo para `SENSOR_SIN_ESTRUCTURA` ni severidad aprobada en RF-61. No se inventó una. |
| Notificaciones M01 | El catálogo consultado no tiene evento RF-61 de ambigüedad. El servicio disponible no ofrece por sí solo el contrato necesario para acreditar registro/entrega idempotente de este evento. |
| RF-48 | Se integró el caso de uso existente. No se modificaron sus reglas de especie, capacidad ni fecha. |
| DEV-23 | No integrado en la base de esta rama; falta referencia definitiva de Daniel para verificar compatibilidad. No se reconstruyó su implementación. |
| DEV-05 | Se reutilizan worker, transacciones, evidencia, bloqueos y recuperación existentes. No se crea una cola o worker paralelo. |
| DEV-41 y otros ajustes | No se incorporan ramas ajenas a DEV-44 para afirmar una integración que no está en la base. |

## Archivos modificados

La descripción indica la responsabilidad y el motivo del cambio. Las cabeceras registran una fila DEV-44 por archivo, con la identidad Git consultada.

| Archivo | Cambio y justificación | Tarea |
|---|---|---|
| `alembic/versions/04cdc3f4d54a_fixactualizacionescatalogovinculaciones.py` | DEV-44 RF-61: preserva vistas dependientes al aplicar DB-13 | #3801 |
| `src/biological_assets/application/use_cases/gestion/registrar_transferencia_use_case.py` | DEV-44 RF-48/61: integra vinculaciones en la misma transaccion | #3803 |
| `src/biological_assets/domain/repositories/vinculacion_traslado_port.py` | DEV-44 RF-48/61: puerto transaccional del traslado | #3803 |
| `src/biological_assets/infrastructure/routers/activo_biologico_router.py` | DEV-44 RF-48/61: inyecta integracion transaccional de traslado | #3803 |
| `src/telemetry/application/use_cases/infraestructura/corregir_vinculacion_use_case.py` | DEV-44 RF-61: correccion SUPERADA conserva periodo y contexto | #3803 |
| `src/telemetry/application/use_cases/infraestructura/evidencia_vinculacion.py` | DEV-44 RF-61: evidencia obligatoria en la transaccion de vinculacion | #3803 |
| `src/telemetry/application/use_cases/infraestructura/procesar_avisos_vinculacion_use_case.py` | DEV-44 RF-61: avisos recuperables sin confirmar envios ficticios | #3802 |
| `src/telemetry/application/use_cases/infraestructura/resolver_vinculacion_use_case.py` | DEV-44 RF-61: resuelve pendientes con contexto y alcance | #3803 |
| `src/telemetry/application/use_cases/infraestructura/vincular_lectura_activo_use_case.py` | DEV-44 RF-61: estados, causas, snapshot e idempotencia | #3801 |
| `src/telemetry/application/use_cases/ingesta/procesar_lectura_confirmada_use_case.py` | DEV-44 RF-61: clasifica capturas con su contexto historico cerrado | #3803 |
| `src/telemetry/domain/entities/vinculacion_lectura.py` | DEV-44 RF-61: estados DB-13 y contexto historico | #3801 |
| `src/telemetry/domain/repositories/activo_biologico_dependency_port.py` | DEV-44 RF-61: contrato de contexto y candidatos historicos | #3803 |
| `src/telemetry/domain/repositories/avisos_vinculacion_port.py` | DEV-44 RF-61: contrato de avisos con clave idempotente | #3802 |
| `src/telemetry/domain/repositories/postcommit_port.py` | DEV-44 RF-61: separa progreso de vinculo y avisos requeridos | #3802 |
| `src/telemetry/domain/repositories/vinculacion_lectura_repository.py` | DEV-44 RF-61: lectura vigente y configuracion temporal | #3801 |
| `src/telemetry/infrastructure/adapters/activo_biologico_m02_adapter.py` | DEV-44 RF-61: resuelve ubicacion y contexto a la captura | #3803 |
| `src/telemetry/infrastructure/adapters/destinatarios_vinculacion_m01_adapter.py` | DEV-44 RF-61: destinatarios por permisos y finca sin roles quemados | #3802 |
| `src/telemetry/infrastructure/adapters/vinculacion_traslado_m03_adapter.py` | DEV-44 RF-48/61: cierra origen sin inventar lecturas de destino | #3803 |
| `src/telemetry/infrastructure/models/vinculacion_lectura_model.py` | DEV-44 RF-61: mapea columnas oficiales DB-13 | #3801 |
| `src/telemetry/infrastructure/repositories/lectura_postcommit_repository.py` | DEV-44 RF-61: excluye vinculaciones SUPERADA del consumo vigente | #3802 |
| `src/telemetry/infrastructure/repositories/postcommit_repository.py` | DEV-44 RF-61: recupera avisos sin duplicar vinculacion | #3802 |
| `src/telemetry/infrastructure/repositories/vinculacion_lectura_repository.py` | DEV-44 RF-61: guarda contexto y serializa vinculaciones | #3801 |
| `src/telemetry/infrastructure/routers/vinculacion_router.py` | DEV-44 RF-61: mantiene alcance en modificaciones manuales | #3803 |
| `src/telemetry/infrastructure/schema/vinculacion_lectura_schema.py` | DEV-44 RF-61: expone causa y snapshot DB-13 | #3801 |
| `src/telemetry/infrastructure/workers/postcommit_worker.py` | DEV-44 RF-61: conecta evidencia y reintento de avisos | #3802 |
| `tests/integration/test_dev05_ingesta_bplus_postcommit.py` | DEV-44 RF-61: explicita asociacion RF-22 en fixture de ingesta | #3801 / #3802 / #3803 |
| `tests/integration/test_dev44_vinculacion_contexto.py` | DEV-44 RF-61: verifica DB-13, contexto, avisos y traslados reales | #3801 / #3802 / #3803 |
| `tests/integration/test_inc_m09_64_g31_vinculacion_ingesta.py` | DEV-44 RF-61: fixtures temporales RF-22 y estados DB-13 | #3801 / #3802 / #3803 |
| `tests/telemetry/test_dev44_vinculacion_contexto.py` | DEV-44 RF-61: estados, causas, avisos y rollback | #3801 / #3802 / #3803 |
| `tests/telemetry/test_inc_m09_106_g31_reclasificar_semaforo_rf17.py` | DEV-44 RF-61: adapta dobles al catalogo y bloqueo de lectura | #3801 / #3802 / #3803 |

## Implementación

### Estados, causas y candidatos — #3801

La asociación RF-22 se resuelve por sensor, dispositivo y período que contiene la captura. Solo una estructura inequívoca permite consultar candidatos. Si falta esa configuración, se conserva la infraestructura real disponible y se registra E1; no se confirma un activo. Sin ninguna infraestructura real, la FK obligatoria de DB-13 impide crear la fila: se informa `VINCULACION_SIN_ESTRUCTURA_PENDIENTE`, sin inventar una estructura.

Los activos se consultan según ubicación y estado aplicables en `timestamp_captura`, con intervalo `inicio <= captura < fin`. Una asociación directa de wearable solo resuelve si identifica exactamente un candidato elegible. Varios candidatos conservan sus IDs y pasan a revisión. Un historial incompleto no se declara estructura vacía. Modelos de manejo incompatibles producen un error explícito, sin elegir el primero.

La lectura se bloquea antes de vincular. El último vínculo de esa lectura permite reconocer reintentos aunque su período ya esté cerrado. Los activos candidatos se bloquean y se vuelven a consultar antes de persistir para coordinarse con traslados.

### Avisos — #3802, integración pendiente

Se añadió `RF61_AVISOS` como efecto recuperable dependiente del núcleo RF-61. El estado, causa y snapshot se conservan aunque el aviso falle. Un fallo no confirma la etapa de avisos ni pierde telemetría previamente confirmada.

El puerto recibe una clave estable por vínculo y clase de aviso. El futuro adaptador debe reutilizar RF-57/M01 y garantizar idempotencia también si la entrega ocurrió antes de un fallo de confirmación local. La clave estable no sustituye esa garantía del proveedor.

Los destinatarios se consultan por cuenta activa, permisos y finca: recurso de vinculaciones y lectura de activos para ambigüedad; rol protegido y lectura de alertas técnicas para E1. No se comparan nombres ni IDs de roles en producción. La selección se prueba con permisos explícitos en PostgreSQL aislado; no acredita permisos desplegados de Productor/Veterinario en la base oficial.

Sin proveedor, destinatarios o confirmación contractual, se devuelve un error recuperable. No se implementó un stub que confirme entregas ni se afirma que exista una alerta `SENSOR_SIN_ESTRUCTURA` persistida.

### Contexto histórico — #3803

`contexto_activo` JSONB conserva captura, candidato/activo, ubicación histórica, fase y su identificador, peso anterior a la captura con unidad y referencia del evento, referencia de snapshot y datos ausentes. No usa mediciones posteriores. El snapshot persiste con el vínculo y no se recompone al consultar usando valores actuales.

Se conserva la fecha de nacimiento del snapshot, pero `edad_dias` queda explícitamente no disponible: falta una regla aprobada de calendario/redondeo. La fase se resuelve desde `gestiones_fases.id_ciclos_productivo_biologico`, distinguiendo la fase biológica del ciclo productivo. El último evento sanitario se conserva como referencia mínima; un diagnóstico no equivale a un estado sanitario normalizado y no se expone su texto. `estado_sanitario_vigente` permanece no disponible hasta disponer de fuente/contrato histórico.

Resolver y corregir requieren fuente histórica para comprobar elegibilidad, además de los permisos del router y alcance por finca. Una corrección cierra el registro anterior y crea uno nuevo con referencia al reemplazado; no sobrescribe su contexto.

### Traslados RF-48 — #3803

El adaptador se ejecuta después de guardar el movimiento y antes del commit de RF-48, usando la misma sesión. Cierra períodos confirmados de origen como `SUPERADA` y registra evidencia RF-63. Si falla, el traslado completo debe revertirse. Repetir el mismo movimiento no repite el efecto.

La tabla DB-13 modela vínculos **por lectura**, con `id_telemetria` obligatorio. No se reutiliza una lectura de A para inventar un vínculo de B. El destino se evalúa con la primera lectura real correspondiente y conserva las reglas ordinarias E1/E2/E3. Una apertura independiente de lectura requeriría otra definición formal, no una FK ficticia.

RF-48 existente registra `fecha_transferencia` como fecha de negocio, pero abre/cierra su historial de ubicación con la hora efectiva de ejecución. El puente utiliza esa misma hora para mantener coherencia; la semántica de traslados retroactivos debe coordinarse con DEV-23.

Cuando el worker mantiene el bloqueo de dispositivo, el traslado devuelve `TRANSFERENCIA_CONCURRENTE` y se revierte para permitir reintento, evitando una espera circular con la FK del activo. Los bloqueos son por activo/dispositivo, no globales.

Una lectura de buffer capturada antes del traslado conserva el activo y período históricos, cerrado como `SUPERADA`. No aparece como vínculo vigente; RF-17 puede consultar explícitamente su contexto histórico para clasificar la captura sin reabrir el período.

## Base de datos y migración

Se reutiliza la migración oficial DB-13; no se creó una revisión duplicada. En PostgreSQL aislado se reprodujo su bloqueo al cambiar el enum debido a `vw_m03_telemetria_contextualizada`. Se corrigió esa misma revisión para retirar/recrear vistas dependientes conservando definición, propietario, opciones, comentarios y grants. No usa `CASCADE`, ni desactiva triggers o RLS. Vistas materializadas o grants por columna requieren un plan específico y abortan explícitamente.

También se actualizan los literales del procedimiento `sp_corregir_vinculacion`; los triggers de unicidad y sustitución utilizan los estados nuevos. La inmutabilidad de vínculos cerrados permanece activa. El downgrade oficial elimina `causa` y `contexto_activo` y traduce revisión pendiente a `AMBIGUA`: no es una recuperación sin pérdida de información.

Tablas principales: `modulo3.vinculaciones_lecturas`, `telemetrias`, `bitacora_auditoria_iot`; `modulo2.activos_biologicos`, `historial_infraestructura_activo`, `historicos_estados_activos`, `historial_activos`, `gestiones_fases`, `eventos_activos`, `eventos_crecimeinto`, `eventos_sanitarios`, `movimientos`; asociaciones RF-22, wearable, ciclos y ámbito de M09; usuarios, cuentas, roles, recursos y permisos de M01.

## Pruebas y evidencia

Resultados finales de PostgreSQL: **79 aprobadas, 0 fallidas y 0 omitidas**. Incluyen 23 casos DEV-44 y 56 regresiones RF-61/DEV-05/DEV-14. La cifra no suma las reejecuciones focalizadas. **Regresión unitaria final: 1.312 aprobadas, 0 fallidas y 0 omitidas** en telemetría, activos biológicos y configuración. Total entre ambas suites: **1.391 pruebas distintas**, sin sumar reejecuciones. Los intentos dentro del sandbox se interrumpieron tras diagnosticar la espera de `socketpair` de TestClient/AnyIO en Windows; la ejecución final habilitó sockets locales y conservó las mismas pruebas, sin modificar código productivo por este problema del entorno.

| Verificación | Resultado / evidencia |
|---|---|
| Regresión unitaria M03/M02/M09 | 1.312 aprobadas; `dev44_unit_validado.xml` |
| Regresión PostgreSQL | 79 aprobadas; `dev44_pg_final.xml` |
| Estados, causas, snapshots, candidatos y correcciones | PostgreSQL real, dentro de las 23 DEV-44 |
| Traslados y rollback | Caso de uso/repositorios reales; infraestructura M09 controlada en la prueba |
| Concurrencia | Dos sesiones para idempotencia; conflicto de traslado recuperable frente al bloqueo de dispositivo |
| Avisos y recuperación | Puerto de entrega doble; estado/evidencia/reintento en PostgreSQL |
| HTTP/JWT/RBAC/finca | 401, 403, 404 y 200 con JWT y permisos persistidos del entorno aislado |
| Migración | Bases nuevas desde cero y downgrade/upgrade con vista filtrada, owner, opciones, grants y comentarios |
| Alembic heads | Un único head: `04cdc3f4d54a` |
| AST y seguimiento | 30 archivos Python con sintaxis válida y una fila DEV-44 |
| Bandit | 0 hallazgos alta/alta y 0 errores de análisis en M03/M02 |

Evidencia local de ejecución (ignorada por Git): `.pytest_cache/dev44_unit_validado.xml` y `.log`, `dev44_pg_final.xml` y `.log`, `dev44_bandit_alta.json`, `dev44_archivos.json`. Semgrep y Bearer no se ejecutaron localmente; quedan a sus jobs de CI. Las consultas oficiales de solo lectura se conservaron en `dev44_oficial_esquema.json` y `dev44_oficial_catalogos.json`, sin credenciales.

Durante la preparación se detectaron fallos de fixtures: reloj de captura frente al reloj transaccional, asociación RF-22 ausente, período de ubicación duplicado, grants no preparados, relación de fase obligatoria y nombre de permiso faltante. Se corrigieron las precondiciones conservando triggers, restricciones y aserciones funcionales. El fallo de la migración por vista dependiente sí exigió la reparación descrita. Los resultados exploratorios no se contabilizan como pruebas adicionales.

La última comprobación focalizada de auditoría/traslados aprobó 3 casos ya incluidos en los 79; se reejecutaron tras ajustar el tipo de entidad del evento de movimiento y no se suman de nuevo. Evidencia: `dev44_pg_auditoria_final.xml`.

La integración usa PostgreSQL 18 local en puerto 55444, con migraciones reales y bases desechables para las pruebas que hacen commits y ciclos de migración. Las pruebas normales usan transacción externa/savepoints. Al finalizar se detuvo y eliminó exclusivamente el clúster temporal DEV-44; la evidencia XML/log permanece en `.pytest_cache`. No se escriben datos de prueba en `sgpmp_dev`.

El ejecutor Windows sustituye únicamente el módulo `fcntl` de bloqueo de archivo del arnés de pruebas; los bloqueos PostgreSQL, triggers y transacciones se ejecutan realmente. Esto no acredita bloqueo de archivos en Linux. La sesión de preparación/verificación es privilegiada: se comprueban JWT, RBAC y alcance de aplicación, pero no se presenta como una regresión específica de políticas RLS con `SET ROLE sgpmp_app`.

Se distinguen:

- Unitarias: dobles de puertos, sin acreditar infraestructura real.
- PostgreSQL: persistencia, causas, snapshots, períodos, corrección, traslados, rollback, concurrencia y recuperación reales.
- Avisos: proveedor doble; no acredita correo, push, notificación M01 ni alerta RF-57 real.
- RF-48: caso de uso y repositorios reales, puertos de infraestructura/parámetros controlados en la prueba.
- MQTT y hardware: no se verificó una entrega extremo a extremo con broker real para DEV-44.

## Comandos reproducibles de verificación

Sobre una instancia PostgreSQL **aislada**, con `DATABASE_URL` y `TEST_DATABASE_URL` apuntando a ella:

```powershell
.venv/Scripts/python.exe -m alembic upgrade head
.venv/Scripts/python.exe -m alembic heads
.venv/Scripts/python.exe -m pytest tests/telemetry tests/biological_assets tests/configuration -q --import-mode=importlib
.venv/Scripts/python.exe -m pytest tests/integration/test_dev44_vinculacion_contexto.py tests/integration/test_inc_m09_64_g31_vinculacion_ingesta.py tests/integration/test_dev05_ingesta_bplus_postcommit.py tests/integration/test_dev14_parametros_dinamicos.py -q --import-mode=importlib
.venv/Scripts/python.exe -m bandit -r src/telemetry src/biological_assets -lll -iii
```

En este Windows, las invocaciones de pytest se ejecutaron mediante `pytest.main(...)`, registrando antes el puente de `fcntl` descrito, `--basetemp` aislado y `--junitxml` en `.pytest_cache`. No se cambió código productivo para conseguir compatibilidad con ese módulo Unix.

## Estado por tarea

| Tarea | Estado | Condición de cierre |
|---|---|---|
| #3801 | Implementada en código; verificación aislada | Integrar/aplicar DB-13 en el destino antes de desplegar la aplicación |
| #3802 | Parcial y bloqueada para entrega real | Severidad aprobada, catálogo/canal y adaptador real; pruebas de alerta/notificación persistidas y deduplicación del proveedor |
| #3803 | Parcial | Edad/estado sanitario históricos y compatibilidad DEV-23; el puente RF-48 existente y el contexto disponible sí están implementados |
| #3702 | Abierta | Completar los criterios pendientes de #3802/#3803 y validación QA con dependencias integradas |

## Pendientes concretos por área

| Área | Necesario para cerrar | Tarea |
|---|---|---|
| BD / Samuel | Revisar e integrar DB-13 con reparación de vistas/procedimiento y desplegar bajo su procedimiento; confirmar columnas/enum en el destino | #3801 |
| Análisis / RF-57 | Severidad y configuración aprobada de `SENSOR_SIN_ESTRUCTURA`; política de deduplicación reutilizable | #3802 |
| M01 / notificaciones | Evento/canal RF-61 aprobado, registro/entrega confirmable e idempotencia por clave; conectar el adaptador con la etapa preparada | #3802 |
| Análisis / M02 | Regla de edad y fuente histórica de estado sanitario; no basta un diagnóstico ni el valor actual | #3803 |
| RF-48 / Daniel | Referencia DEV-23, fecha efectiva/retroactividad y confirmación del punto de integración; apertura de destino por lectura según DB-13 | #3803 |
| QA | Validación final con DB-13 desplegado y canales reales, incluyendo roles efectivos y regresión de las ramas integradas | #3702 |

Estas solicitudes quedan documentadas; no se enviaron mensajes a terceros.

## Estado Git y controles finales

- 30 archivos Python del alcance y este informe; cabeceras de seguimiento verificadas con `Leandro` y fecha 2026-10-22.
- Sintaxis AST válida, `git diff --check` sin errores y un único head Alembic.
- Los archivos de pendientes previos y `AGENTS.md` se conservan fuera del commit de DEV-44.
- Los logs/XML/metadata de pruebas quedan ignorados en `.pytest_cache`; no se incorporaron credenciales.
- Las integraciones funcionales sin proveedor/contrato no equivalen a tests omitidos de pytest: siguen siendo criterios de aceptación pendientes aunque las suites ejecutadas tengan cero skips.

## Propuesta de PR

**Título:** RF-61 — Estados DB-13, causas y contexto histórico con traslados · DEV-44

**Referencias:** #3702, #3801, #3802, #3803. El PR debe describirse como entrega parcial mientras persistan los bloqueos anteriores; no usar cierre automático de toda la historia.

### Desvío

RF-61 utilizaba estados anteriores a DB-13, no persistía causas diferenciadas ni contexto biológico temporal y no reaccionaba a los traslados RF-48. Se incorporan estados oficiales, evidencia y coordinación transaccional sin modificar la telemetría original.

### Cambios

- Enum/ORM/esquemas alineados con DB-13; causas E1/E2 y candidatos persistidos.
- Consultas históricas, snapshots, elegibilidad manual y alcance por finca.
- Puente RF-48 con cierre `SUPERADA`, evidencia, rollback e idempotencia.
- Recuperación separada de avisos y selección de destinatarios; proveedor pendiente.
- Reparación de dependencias de vistas y procedimiento en la revisión oficial DB-13.

### Pruebas realizadas

Regresión unitaria: 1.312 aprobadas. PostgreSQL aislado: 79 aprobadas, sin fallidas ni omitidas; evidencia y límites descritos arriba. No acredita una entrega real de avisos.

### Contrato resultante

Las vinculaciones nuevas confirmadas usan `CONFIRMADA`; ambigüedad no resuelta utiliza `PENDIENTE_REVISION`; los períodos sustituidos usan `SUPERADA`. El historial queda consultable. Los fallos de aviso no se informan como entregas exitosas.

### Compatibilidad y pendientes

Se conservan endpoints, JWT/RBAC, inmutabilidad y worker existente. La prueba HTTP usa JWT firmado y permisos persistidos del entorno aislado: comprueba 401 sin sesión, 403 sin permiso, 404 fuera de finca y 200 con permiso y finca. Requiere DB-13 antes de desplegar el código. Faltan canal/severidad de avisos, edad y estado sanitario históricos, y comprobación DEV-23. No hay validación real de entrega MQTT, correo o push en este cambio.

### Revisión contra dev

Rama: `fix/dev44-vinculacion-contexto-traslados`. Base: `626abdf1` de DB-13, no una rama de DEV-28. `origin/dev` consultado: `6113a388`. Hasta que DB-13 se integre, el diff contra dev incluye ese commit dependiente. El commit de DEV-44 contiene exclusivamente los cambios de esta tarea y su informe.
