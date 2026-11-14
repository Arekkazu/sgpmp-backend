# INC-M03-126-G27 · #681 · RF-54 — Consulta del estado reportado del buffer

Fecha: 2026-10-27. Autor de cabeceras: Leandro, verificado mediante git config user.name.

## Alcance confirmado

Referencias: issue #681, TC-M03-054, TC-M03-045, RF-54 Salidas §2 y AIOT-DEV-03 P5/D10/D11, DEV-11/AIOT-08.

El usuario confirmó implementar la consulta y ampliar opcionalmente el heartbeat, documentando la integración IoT pendiente y conservando el buffer en Edge. La rama fix/inc-m03-126-g27-estado-buffer-rf54 se creó tras actualizar dev por fast-forward a 5691096b8497b9fc445abf0a7579409c8de6550f.

## Diagnóstico

No había GET para buffer. El heartbeat solo exponía estado_local_buffer (I/A/L) y datos_pendientes_buffer. EVENTO_BUFFER informa ocupación y política al ocurrir overflow/corrupción; no es un reporte periódico completo ni puede acreditar el regreso a NORMAL. Sus datos no permiten reconstruir capacidad total/utilizada ni el último timestamp pendiente.

RF-54 Salidas §2 exige las siete métricas de la issue y define NORMAL <80 %, WARNING ≥80 % y CRITICO ≥95 %. I/A/L del heartbeat es otro catálogo y se conserva con su nombre; no se interpreta como esos niveles de ocupación.

El acuerdo P5 asigna la cola persistente al Edge. D10 ordena eliminar modulo3.buffers, decisión implementada en 1164e0abedec. El cambio conserva esa eliminación: incorpora un snapshot opcional en cada heartbeat, sin almacenar ni administrar lecturas del buffer.

## Flujo resultante

Edge mide el buffer → broker conserva metricas_buffer en su INSERT de heartbeat → PostgreSQL conserva el reporte → repositorio obtiene un único heartbeat → caso de uso de consulta → schema público.

El camino HTTP POST /iot/heartbeat admite el mismo bloque opcional y lo guarda en la transacción existente. El caso de uso mantiene commit/rollback; el repositorio utiliza flush. Los mapeos ORM ↔ dominio incluyen el campo para el procesamiento postcommit existente.

La consulta nueva es GET /iot/dispositivos/{id_dispositivo_iot}/buffer. Utiliza JWT, estado de cuenta y RBAC infraestructura_iot · Leer (recurso 35, acción 2), igual que las consultas de dispositivos. Los permisos se consultan en datos; no se impone un catálogo de roles en código. El alcance proviene de AlcanceFincaAdapter y se aplica además en la consulta SQL junto al dispositivo y su infraestructura. Dispositivo inexistente y fuera de finca producen el mismo 404 DISPOSITIVO_NO_ENCONTRADO.

## Contrato de integración

El bloque opcional metricas_buffer del heartbeat contiene:

~~~json
{
  "capacidad_total": 1000,
  "capacidad_utilizada": 800,
  "ultimo_timestamp_pendiente": "2026-10-27T13:00:00Z",
  "politica_buffer_activa": "POLITICA_RECHAZO"
}
~~~

Se conserva datos_pendientes_buffer en el nivel superior del heartbeat; no se duplica en el bloque. Capacidad total y utilizada se reportan en la misma unidad física del Edge. El backend no las convierte ni asume que sean bytes o cantidad de registros; broker/firmware deben mantener esa unidad coherente para el dispositivo. Total debe ser positivo, utilizada estar entre cero y el total, y los valores ser finitos. Las políticas aceptadas son POLITICA_RECHAZO y POLITICA_SOBRESCRITURA.

El último timestamp se conserva desde la fuente y se normaliza mediante FechaHoraUtc, conforme al patrón del proyecto. Para un buffer vacío el Edge puede informar null. El backend no lo deduce de la última telemetría recibida.

La ocupación se calcula como utilizada/total ×100. La clasificación compara las capacidades contra los límites 80 % y 95 % antes de redondear, para no adelantar una transición. Son estados de consulta; no se agregan alertas o eventos técnicos nuevos.

La respuesta incluye las siete claves de la issue, id_dispositivo_iot y metadatos de procedencia: id_heartbeat, fecha_reporte, fecha_recepcion, estado_local_buffer y metricas_disponibles. Los Decimal se serializan como cadenas, conforme a Pydantic 2.

La fuente es el último heartbeat por fecha_recepcion DESC e id_heartbeat DESC, siguiendo el criterio existente del sistema. Todas las métricas se toman de esa misma fila. No se busca un snapshot antiguo si el heartbeat más reciente omite la ampliación, ni se mezclan datos de EVENTO_BUFFER. Las fechas permiten distinguir la última información recibida de un estado físico observado en tiempo real.

Sin heartbeat, el dispositivo visible responde 200 con las métricas desconocidas en null y metricas_disponibles=false. Con heartbeat legacy, datos_pendientes y estado_local_buffer siguen disponibles, pero las nuevas métricas son null. Esto no equivale a buffer vacío o NORMAL. Un reporte completo de buffer vacío sí puede devolver cero y NORMAL.

Se mantiene el handler HTTP vigente: entrada inválida responde 400 VAL_ENTRADA; JWT ausente/inválido 401; falta de permiso 403; inexistente/fuera de finca 404. La ruta canónica pertenece a /iot; no se añade un alias /dispositivos fuera de ese router.

## Migración y preflight

Nueva revisión b68127f54a01, dependiente de ebbb160365e5 (head de dev verificada antes de implementar). Añade modulo3.heartbeats.json_metricas_buffer JSONB nullable, sin valor por defecto fabricado ni backfill. Los INSERT anteriores que omiten la columna continúan dejando NULL. El downgrade elimina esa columna y sus snapshots; no modifica las columnas anteriores.

La inspección oficial se ejecutó con SET TRANSACTION READ ONLY. Confirmó la ausencia de la columna nueva y de modulo3.buffers, tipos, FK, restricciones, índice idx_heartbeats_dispositivo_recepcion, triggers de procesamiento/reloj y funciones asociadas, y políticas. Dispositivos e infraestructuras tienen RLS y FORCE habilitados; heartbeats no tiene RLS. Por eso la consulta une la fuente al dispositivo/infraestructura y filtra por fincas autorizadas.

member_dev no pudo consultar permisos ni alembic_version (42501). No se eludió la restricción. La head y los permisos se comprobaron en Git y en PostgreSQL local migrado; no se afirma conocer el estado desplegado de migraciones oficiales. No se ejecutó DDL/DML oficial.

La base local sgpmp_g27_test se migró desde cero. Los privilegios SQL de lectura, autenticación y ejecución de los triggers de heartbeat se aprovisionaron solo allí para sgpmp_app, sin cambiar RBAC ni desactivar RLS, FORCE o restricciones. El recurso 35 ya tiene permisos de lectura en las migraciones existentes; no se crea un permiso alternativo.

## Pruebas y evidencias

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

Los errores intermedios del lanzador/fixture se conservan y se distinguen del resultado final. El shim fcntl de Windows se limita al lanzador por el SDK existente; no modifica producción. Evidencias temporales en .pytest_cache, excluidas de Git.

## Dependencias y despliegue

1. Aplicar la migración antes de desplegar el ORM y la consulta nuevos. No se aplicó en la base oficial.
2. IoT debe ampliar el payload del firmware con metricas_buffer y conservar datos_pendientes_buffer, usando la misma unidad de capacidad en ambos valores.
3. El broker, que inserta directamente, debe aceptar ese bloque y guardarlo en json_metricas_buffer. Cambiar solo el DTO HTTP no completa el camino MQTT.
4. Coordinar el despliegue según D11. El nuevo bloque es opcional para mantener los heartbeats existentes; su ausencia se hace explícita en la consulta.
5. QA debe repetir TC-M03-054 y TC-M03-045 con el nodo real, observando umbrales 80/95 y descenso de ocupación. Las pruebas locales no acreditan medición física, publicación MQTT ni firmware.

## Entrega

Se incluyen código, migración, pruebas e informes de #681. Se conservan los archivos ajenos y el frontend no se modifica. El usuario autorizó el commit y el push el 2026-10-27; no se crea ni publica un PR.

## Cierre del entorno local

Tras finalizar las pruebas se eliminó exclusivamente sgpmp_g27_test y se detuvo limpiamente el clúster local. Las otras bases y las evidencias/scripts se conservaron. Registro: .pytest_cache/g27_cierre.log. git diff --check finalizó correctamente. No se realizó despliegue ni DDL/DML en la base oficial.
