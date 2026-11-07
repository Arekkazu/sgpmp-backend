# RF-62 — Regenerar evaluaciones explícitas y conservar la vigente · INC-M03-133-G170

## Desvío identificado

| RF exige | Antes | Ahora |
|---|---|---|
| Restricción 9 / CA-16: crear nuevas evaluaciones con parámetros corregidos | Marcaba SUPERADA y devolvía evaluaciones_creadas=0 | Recalcula con el motor y crea las sustitutas en la misma transacción |
| Conservar historial y una vigente por lectura | El rango podía quedar sin evaluación VIGENTE | Nueva VIGENTE enlazada a la anterior; rollback completo si falla el lote |
| Auditoría completa RF-63 | Se ejecutaba después del commit, sin parámetros completos y con errores silenciados | Evidencia obligatoria antes del commit, con usuario, causa, parámetros, IDs y conteos |

Referencias: #688 · INC-M03-133-G170 · TC-M03-G170 / TC-324, TC-325 y TC-326 · RF-62 Restricción 9, CA-15/CA-16 y RNF-07/RNF-08 · AIOT-DEV-03 DEV-02.

## Causa raíz

SolicitarReevaluacionUseCase no invocaba el motor ni utilizaba sus dependencias de telemetría y parámetros. Solo superaba las evaluaciones seleccionadas y confirmaba esa operación. No existía un proceso diferido que generara las nuevas filas. La auditoría posterior tampoco garantizaba trazabilidad atómica.

## Cambios implementados

- Reutilización del motor RF-62 con confirmación individual deshabilitada durante el lote y un solo commit al finalizar.
- Correcciones locales de calibración y parámetros estadísticos, validadas sin escribir configuración M09 ni telemetría original.
- Nuevas evaluaciones con motivo_reevaluacion, id_evaluacion_superada y version_evaluacion reproducible; conservación de causas de creación de reevaluaciones históricas.
- Bloqueos por lectura en orden ascendente, compartidos con la evaluación manual/postcommit. Se relee la vigente después de esperar el bloqueo.
- Auditoría individual y global obligatoria antes de confirmar. Fallos de cálculo, escritura, auditoría o commit revierten el lote.
- Restricción de la ruta masiva al Administrador protegido, además de JWT y RBAC dinámico 38/E. El Ingeniero conserva su permiso de evaluación individual.
- Contexto RF-60 y alertas reales en la composición de la ruta; errores de persistencia traducidos mediante el mecanismo compartido.

## Migración

No requiere migración: las columnas, snapshots y FK necesarias ya existen. Se conservan tablas, índices, triggers, RLS/FORCE RLS e identidad de servicio. Los repositorios usan flush; el caso de uso confirma la transacción.

## Contrato resultante

Se conserva POST /iot/calidad/reevaluar con HTTP 200 y ambos contadores finales:

```json
{"evaluaciones_superadas":6,"evaluaciones_creadas":6}
```

El rango mantiene su selección por timestamp_evaluacion de las vigentes, con extremos inclusivos. No se cambia a timestamp_captura. Se mantiene el dict opcional parametros_correctos; admite offset/ganancia y parámetros del motor, rechazando claves desconocidas, valores no finitos y ventanas inválidas con 422 PARAMETROS_REEVALUACION_INVALIDOS.

La versión rf62:<sha256> identifica los componentes aplicados, persistidos también en parametros_aplicados.version_evaluacion_componentes. Las versiones históricas no disponibles quedan null. No es un contador de ejecuciones: los IDs y enlaces distinguen la cadena.

Si una lectura debe omitirse por inactividad, la solicitud devuelve 422 y conserva el lote anterior. Auditoría no disponible devuelve 503 y revierte todas las sustituciones. Las lecturas y aptitudes legacy de telemetrias permanecen inmutables; la aptitud oficial sigue en telemetria_calidad.

Por alcance confirmado, el evento global registra los avisos a M04/M06 como pendientes con los IDs nuevos, con resultado PARCIAL. No se afirma una notificación efectiva. El procesamiento asíncrono de RNF-08 queda como pendiente separado, conservando el contrato HTTP actual.

## Pruebas realizadas

| Grupo | Aprobadas | Fallidas | Omitidas |
|---|---:|---:|---:|
| Unitarias y contrato HTTP | 731 | 0 | 0 |
| Integración PostgreSQL 18 real, incluida concurrencia | 42 | 0 | 0 |
| Total distinto | 773 | 0 | 0 |

Incluye 16 pruebas unitarias nuevas y 21 reales de #688. Las regresiones PostgreSQL añaden 8 del motor de #632, 12 de aptitud oficial DEV-02 y una de omisión normal por inactividad. Los XML se contaron sin duplicados ni sumar corridas preliminares.

Se verificaron seis sustituciones con eliminación del drift falso, consulta de la vigente, snapshots, fuente inmutable, parámetros locales sin cambios M09, causas históricas, JWT/RBAC, rechazos, rollback/reintento de los caminos afectados y dos lotes concurrentes. HTTP y lotes concurrentes usan sgpmp_app; la concurrencia emplea parámetros M09 de prueba con motor, repositorios y locks reales.

El caso inicial reprodujo una superada y cero creadas. Las evidencias están en .pytest_cache y no forman parte del commit. El shim fcntl se limita al lanzador Windows.

No se ejecutó Newman ni se declara aprobada toda G170. El supuesto rechazo de preferencias de TC-325d devolvía SIN_EVALUACIONES_EN_RANGO tras vaciar las vigentes; no probaba CA-17. No se introducen heurísticas de texto libre. Los extremos iguales pueden coincidir con una evaluación exacta, conservando el filtro inclusivo existente.

## Integración con sgpmp_dev

Inspección oficial únicamente en lectura: columnas, restricciones, índices, triggers, políticas y privilegios disponibles. Consultas restringidas de RBAC y alembic_version denegadas con 42501, sin eludirlas. El RBAC se verificó en PostgreSQL local migrado.

No se ejecutó DDL/DML oficial ni se validó un despliegue. Las bases desechables de la tarea se retiraron y el clúster local se detuvo, conservando evidencias y otras bases.

## Dependencias y pendientes

Quedan pendientes integración efectiva con M04/M06, diseño asíncrono RNF-08, proveedor histórico de límites M09 y definición formal para validar preferencias CA-17. El usuario confirmó resolver el lote atómico y auditar las notificaciones pendientes.

Las evaluaciones huérfanas generadas antes de esta corrección requieren inventario y reparación autorizada; no se reconstruyen automáticamente ni se modifican datos oficiales desde esta rama.

## Alcance del commit

Alcance preparado: 10 archivos — cinco de producción, dos de pruebas y tres Markdown. Cabeceras INC-M03-133-G170 en los siete Python. Sin cambios de frontend ni archivos ajenos. Commit y push autorizados por el usuario; publicación del PR pendiente.

## Revisión contra dev

Rama fix/inc-m03-133-g170-reevaluacion-rf62 creada desde dev actualizado, base 5691096b8497b9fc445abf0a7579409c8de6550f. No incorpora otras ramas independientes. Al integrar cambios superpuestos del motor, conservar la propagación de reloj de #687 si se fusiona junto con esta corrección.
