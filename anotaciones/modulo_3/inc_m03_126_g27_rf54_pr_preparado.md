# RF-54 — Consultar el estado reportado del buffer Edge · INC-M03-126-G27

## Desvío identificado

| RF exige | Antes | Ahora |
|---|---|---|
| Consultar las siete métricas del buffer (TC-M03-054) | No existía una ruta de consulta ni una fuente completa de métricas | GET /iot/dispositivos/{id_dispositivo_iot}/buffer expone el último reporte y sus datos disponibles |
| Observar NORMAL / WARNING / CRITICO (TC-M03-045) | I/A/L del heartbeat no expresaba niveles de ocupación | Clasificación del snapshot recibido: NORMAL <80 %, WARNING ≥80 %, CRITICO ≥95 % |
| Identificar información desconocida | Los mensajes actuales no incluyen capacidad ni último timestamp pendiente | Campos null y metricas_disponibles=false cuando el reporte no tiene esas métricas |

Referencias: issue #681, TC-M03-054, TC-M03-045, RF-54 Salidas §2 y AIOT-DEV-03 P5/D10/D11. El usuario confirmó implementar backend y documentar la ampliación pendiente de broker/firmware.

## Causa raíz

El contrato vigente recibe estado_local_buffer y datos_pendientes_buffer por heartbeat; EVENTO_BUFFER solo avisa overflow/corrupción. Ninguno aporta todas las métricas requeridas para consultar el buffer ni permite observar su vuelta a NORMAL.

P5/D10 mantiene el buffer en Edge y elimina modulo3.buffers. Se conserva esa decisión y se agrega un snapshot opcional del reporte, sin administrar la cola física desde backend.

## Cambios implementados

- Entidad de dominio para métricas y clasificación de ocupación, puerto de consulta, caso de uso, repositorio SQLAlchemy y schema público.
- GET protegido por JWT, estado de cuenta, RBAC infraestructura_iot · Leer (35/2) y alcance por finca. Los permisos siguen siendo dinámicos.
- Ampliación opcional metricas_buffer en POST /iot/heartbeat, con capacidades coherentes, valores finitos, política válida y timestamp normalizado a UTC.
- Persistencia del snapshot junto al heartbeat y mapeo ORM ↔ dominio, manteniendo commit/rollback en el caso de uso.
- Lectura de una única fila por fecha_recepcion DESC, id_heartbeat DESC. No se mezclan métricas antiguas con el último heartbeat ni con eventos de incidentes.
- Exposición de timestamps e id_heartbeat para identificar la procedencia del reporte. Sin datos se conserva null; un cero solo se informa cuando proviene de la fuente.
- Cabeceras de seguimiento con la identidad Git verificada y preservación de cambios ajenos.

## Migración

Nueva revisión b68127f54a01, dependiente de ebbb160365e5. Añade heartbeats.json_metricas_buffer JSONB nullable. Los heartbeats anteriores y los INSERT que omiten el campo conservan NULL.

No restaura modulo3.buffers ni modifica roles, permisos, RLS o triggers. El downgrade elimina el campo y sus snapshots. Debe aplicarse antes del código nuevo y coordinarse con IoT; no se aplicó DDL/DML oficial.

## Contrato resultante

Ruta canónica: GET /iot/dispositivos/{id_dispositivo_iot}/buffer.

Devuelve capacidad_total, capacidad_utilizada, porcentaje_ocupacion, datos_pendientes, ultimo_timestamp_pendiente, estado_buffer y politica_buffer_activa. Incluye id_dispositivo_iot, id_heartbeat, fecha_reporte, fecha_recepcion, estado_local_buffer y metricas_disponibles.

Las métricas de capacidad usan la misma unidad reportada por Edge; el backend no asume bytes ni registros. El bloque opcional de entrada contiene capacidad_total, capacidad_utilizada, ultimo_timestamp_pendiente y politica_buffer_activa; datos_pendientes_buffer permanece en el nivel superior del heartbeat.

Sin heartbeat o sin ampliación disponible, las métricas desconocidas son null. Un heartbeat legacy posterior no hereda un snapshot anterior. La consulta representa el último reporte recibido; no acredita el estado físico actual de un nodo desconectado.

Entrada inválida conserva el handler general 400 VAL_ENTRADA. JWT ausente/inválido: 401; falta de permiso: 403; dispositivo inexistente o fuera de finca: 404 DISPOSITIVO_NO_ENCONTRADO.

## Pruebas realizadas

| Grupo | Aprobadas distintas | Fallidas | Omitidas |
|---|---:|---:|---:|
| Unitarias y contratos HTTP de telemetría | 749 | 0 | 0 |
| PostgreSQL 18 real: casos nuevos y regresión de heartbeat/postcommit | 29 | 0 | 0 |
| **Total distinto final** | **778** | **0** | **0** |

El total se consolidó por classname + name de los XML: g27_regresion.xml contiene 748; g27_contrato.xml contiene 34, de las que solo una prueba de OpenAPI es adicional; g27_pg_definitivo.xml aporta 11; g27_heartbeat_pg.xml aporta 18. No se suman las corridas repetidas.

Los once casos nuevos de PostgreSQL comprueban transiciones ascendentes y descenso a NORMAL, persistencia del snapshot HTTP, lectura del INSERT directo del broker, heartbeat legacy posterior sin mezcla de métricas, ausencia de heartbeat, buffer vacío reportado, JWT/RBAC y finca con Ingeniero asignado, rechazo de entrada inválida sin escritura, desempate por ID, rollback y esquema nullable. Incluyen downgrade y upgrade reales preservando una fila legacy y manteniendo RLS/FORCE. Las solicitudes usan sgpmp_app y verifican rolsuper=false/rolbypassrls=false.

Las 18 regresiones reales verifican el heartbeat extendido y procesamiento postcommit existente. Las unitarias/HTTP cubren límites 80/95 sin redondeo, métricas inválidas, normalización temporal, transacción y rollback, datos desconocidos, permisos, identificadores, fuente inválida y OpenAPI opcional.

Evidencias y lanzadores en .pytest_cache: g27_regresion.log/xml, g27_contrato.log/xml, g27_pg_definitivo.log/xml, g27_heartbeat_pg.log/xml, g27_preflight.log, g27_preparar_bd.log, g27_grants.log, g27_run_unit.py y g27_run_tests.py. Se conservan los intentos intermedios: primero se corrigieron el directorio temporal del lanzador, las expectativas HTTP frente al handler vigente y los privilegios locales que exigía el trigger existente. No se presentan como defectos de producción ni se ocultan del registro.

Avisos existentes: deprecación de httpx en Starlette y Operation ID duplicado en auditoria_iot_router al generar OpenAPI del conjunto del proyecto. No se ampliaron esos cambios ajenos al alcance.

Evidencias temporales en .pytest_cache; no forman parte del commit. Las pruebas HTTP no acreditan MQTT ni firmware reales.

## Integración con sgpmp_dev

Inspección oficial de solo lectura: columnas, FK, restricciones, índice del último heartbeat, triggers y funciones, ausencia de la columna nueva y de modulo3.buffers, y políticas RLS. Dispositivos e infraestructuras conservan RLS/FORCE; heartbeats no tiene RLS, por lo que la consulta enlaza al dispositivo y aplica el alcance autorizado.

member_dev no pudo consultar permisos ni alembic_version (42501). No se eludió esa restricción ni se alteraron datos o permisos oficiales. Las verificaciones funcionales y de migración se ejecutaron en sgpmp_g27_test local, con operaciones de API bajo sgpmp_app sin superusuario ni BYPASSRLS.

## Dependencias y pendientes

- Aplicar la migración antes del ORM nuevo.
- Firmware: medir y reportar metricas_buffer, conservar datos_pendientes_buffer y utilizar una unidad de capacidad coherente.
- Broker: ampliar su payload e INSERT directo a json_metricas_buffer. Modificar solo el DTO HTTP no completa el canal MQTT.
- Coordinar despliegue de migración/backend/broker/firmware conforme al patrón D11.
- QA: repetir TC-M03-054 y TC-M03-045 con Edge real, incluyendo subida y descenso de ocupación. No se declara aprobada una corrida oficial.

## Alcance del commit

Contenido de la entrega: 13 archivos de producción/migración, 2 de pruebas y 3 documentos Markdown (referencia API e informes). El usuario autorizó el commit y el push el 2026-10-27. Este documento prepara el contenido del PR; no se crea ni publica un PR.

Se excluyen AGENTS.md, notas ajenas, .pytest_cache, credenciales y cualquier cambio del frontend.

## Revisión contra dev

Rama fix/inc-m03-126-g27-estado-buffer-rf54, creada después de actualizar dev mediante fast-forward a 5691096b8497b9fc445abf0a7579409c8de6550f. No incluye la rama de #680 como dependencia adicional. Los cambios ajenos previos permanecen conservados.

## Cierre del entorno local

Tras finalizar las pruebas se eliminó exclusivamente sgpmp_g27_test y se detuvo limpiamente el clúster local. Las otras bases y las evidencias/scripts se conservaron. Registro: .pytest_cache/g27_cierre.log. git diff --check finalizó correctamente. No se realizó despliegue ni DDL/DML en la base oficial.
