# INC-M03-132-G30 · RF-53 / RF-54 / RF-62 — TIME_DESYNC (#687)

Fecha: 2026-10-27. Responsable de los cambios según git config user.name: Leandro.
Rama: fix/inc-m03-132-g30-time-desync-rf54.
Base: dev/origin/dev actualizado al iniciar, 5691096b8497b9fc445abf0a7579409c8de6550f.

## Diagnóstico y alcance confirmado

La incidencia corresponde a Desarrollo Backend: la columna modulo3.telemetrias.reloj_desincronizado existía con default false, pero la función común modulo3.fn_ingesta_telemetria no la incluía en su INSERT. Ni el DTO escalar ni la evaluación RF-62 transportaban la evidencia del reloj. Guardar el heartbeat por separado no propagaba su estado a nuevas lecturas.

Referencias: issue #687, TC-M03-049, RF-54 E9 (Requerimientos_M03_RF53-RF63.md, sección del reloj desincronizado), RF-53 E7 y reglas de ingesta; acuerdo AIOT-DEV-03 D2 y DEV-02, telemetría inmutable y aptitud oficial en telemetria_calidad. La marca no sustituye el trabajo IoT de detectar y resincronizar el reloj.

El usuario confirmó expresamente:

1. Señal opcional reloj_sincronizado por lectura y heartbeat como fallback, documentando su procedencia. En buffer, el fallback acredita solo el último estado conocido al sincronizar.
2. TIME_DESYNC excluye de IA y NIC-41 en la evaluación vigente, sin inventar un descuento al índice ni actualizar la lectura original.

## Corrección implementada

| Capa | Cambio |
|---|---|
| DTO y caso de uso de ingesta | Booleano estricto opcional; envío como metadato cuando se proporciona |
| Función SQL común | Resuelve evidencia antes del INSERT y escribe reloj_desincronizado junto con el snapshot rf53_reloj |
| Postcommit y endpoint de evaluación | Entregan a RF-62 la marca y el snapshot de la lectura persistida |
| RF-62 | Conserva índice y clasificación; fuerza ambas aptitudes false y registra flag y restricción temporal |

Prioridad: booleano explícito de la lectura; si falta o es null, último heartbeat recibido del mismo dispositivo no posterior al instante de procesamiento; si no existe, SIN_EVIDENCIA. El desempate de heartbeat usa su ID. Sin evidencia no se declara sincronización ni se marca desincronización por suposición.

El snapshot incluye fuente, estado, código TIME_DESYNC cuando procede, heartbeat utilizado, recepción e instante de decisión. No reconstruye el estado histórico de un dato del buffer. Un heartbeat de recuperación modifica la decisión para nuevas lecturas, nunca los snapshots anteriores. Reevaluar una lectura desincronizada conserva su restricción.

Las aptitudes oficiales de RF-62 deben consultarse independientemente de la clasificación: APTO con índice 100 y ambas aptitudes false es válido cuando hay TIME_DESYNC. El índice sigue representando el cálculo estadístico existente; la exclusión temporal se documenta en parametros_aplicados.restriccion_temporal y flags_detectados.reloj_desincronizado.

## Persistencia y seguridad verificadas

Antes de cambiar se inspeccionó sgpmp_dev usando transacción de solo lectura: columna y default, definición real de función, heartbeat, índices y permisos disponibles. Los roles rol_aiot, rol_app y sgpmp_app ya tenían SELECT sobre heartbeats y USAGE de modulo3. Se reutiliza idx_heartbeats_dispositivo_recepcion. La consulta de ciertas tablas de RBAC y alembic_version fue denegada por permisos; no se eludió esa protección. No se acredita por ello la versión Alembic desplegada.

En PostgreSQL local se revisaron modelos, restricciones, triggers y políticas con migraciones aplicadas. No se cambian tablas, permisos, identidad de servicio, RLS/FORCE RLS ni contratos de autenticación. HTTP y el camino SQL operativo se validaron con TEST_ROL_APP=sgpmp_app; el propietario se usó para preparar el entorno y las operaciones de migración, sin representarlo como usuario normal de la API.

## Migración

c687132a0270_time_desync_ingesta.py; revisión c687132a0270; padre ebbb160365e5. Parcha la definición vigente de la función, con guardas que exigen encontrar una sola versión de los bloques esperados. No reemplaza la función por una copia histórica. Mantiene los 19 parámetros, el resultado, owner, ACL y atributos. El downgrade retira únicamente el bloque de reloj y el par columna/valor del INSERT. No borra ni modifica snapshots persistidos.

Se probaron upgrade, downgrade y upgrade sobre PostgreSQL 18, comparando definición y atributos. La migración es necesaria para desplegar la corrección. No crea columnas, tablas, índices ni backfill. Los rechazos existentes de captura futura y buffer mayor de 72 horas permanecen.

## Pruebas y evidencias

| Grupo final | Aprobadas | Fallidas | Omitidas |
|---|---:|---:|---:|
| Unitarias y contrato HTTP de telemetría | 727 | 0 | 0 |
| PostgreSQL 18 real aislado | 50 | 0 | 0 |
| Total distinto | 777 | 0 | 0 |

La suite unitaria incluye 12 casos nuevos. PostgreSQL comprende 29 nuevos de #687, 8 de regresión del motor #632 y 13 de registro/calibración/snapshot #626. Los identificadores de testcase de ambos XML finales se comprobaron sin duplicados. No se suman las corridas preliminares.

Cobertura: prioridades y ausencia de evidencia; tipos inválidos HTTP/SQL; heartbeat de otro dispositivo o recepción futura; recuperación sin cambios retroactivos; buffer con señal histórica; trigger existente que fuerza reloj no sincronizado ante fecha futura del heartbeat; ingesta simple/lote; evaluación manual/postcommit; persistencia de aptitudes; historial de reevaluación; rollback/reintento tras fallos de commit y auditoría; rechazos temporales; reversibilidad de migración.

La reproducción anterior al cambio falló como se esperaba: 12 casos unitarios por falta del campo/parámetros y un caso real que demostró el default false con heartbeat desincronizado. Una corrida focalizada posterior detectó una preparación de asociación temporal insuficiente en el fixture de buffer de 73 horas; se ajustó solo el dato local del fixture para alcanzar el rechazo temporal esperado. La corrida final no tiene fallos.

Evidencias locales ignoradas: .pytest_cache/g33_unit_final.xml/.log, g33_pg_final.xml/.log, g33_resumen_final.json, g33_preflight.json/.log, g33_inspeccion_local.log y scripts de preparación. No se incluyen en el commit. El shim fcntl fue exclusivo del lanzador Windows. Los avisos existentes de Starlette/httpx y OperationID duplicado no impidieron completar las pruebas. El volcado periódico de faulthandler en el log unitario es diagnóstico del lanzador, no un caso fallido.

Se retiró exclusivamente sgpmp_g33_test comprobando que las demás bases locales permanecieran, y se detuvo el clúster. Evidencias: g33_cierre_bd.log, g33_cierre_cluster.log y g33_estado_cluster_final.log. La BD oficial no recibió DDL ni DML de esta tarea.

## Archivos y entrega

Seis archivos de producción: migración, DTO, caso de ingesta, caso de evaluación, procesador postcommit y router de calidad. Dos archivos de pruebas y cuatro documentos: este informe, integración IoT, PR preparado y actualización de referencia API. Total previsto: 12 archivos, con cabeceras de la tarea en los ocho Python.

No hay cambios de frontend. No se modifican lecturas históricas ni se rellena evidencia desconocida de registros anteriores. Las ramas independientes de #685 y #686 no se incorporaron; ambas y esta migración parten de dev según el estado de cada tarea. Revisar heads y componer dependencias antes de una futura integración, conservando los parches de cada función vigente.

El usuario autorizó el commit y el push de esta corrección. No se publica un PR como parte de esa autorización. Quedan pendientes despliegue autorizado, envío de la señal desde firmware/broker y ejecución conjunta de TC-M03-049 con nodo real o simulador IoT. La validación realizada demuestra backend y PostgreSQL aislados; no demuestra detección NTP ni comportamiento del firmware.

Ver [contrato IoT](inc_m03_132_g30_rf54_integracion_iot.md) y [PR preparado](inc_m03_132_g30_rf54_pr_preparado.md).
