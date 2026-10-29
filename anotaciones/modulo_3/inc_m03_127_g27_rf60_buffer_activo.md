# INC-M03-127-G27 · #682 · RF-54 / RF-60 — Conservar BUFFER_ACTIVO hasta confirmar vaciado

Fecha: 2026-10-27. Autor de cabeceras: Leandro, consultado mediante git config user.name.

## Alcance y decisión confirmada

Issue #682, grupo G27, RF-54 y RF-60 Fases 4/5, Restricción 12 y CA-2; AIOT-DEV-03 P5/D10. Se contrastaron los RF descargados, código, migraciones y definiciones SQL oficiales en lectura.

Se encontró una contradicción: Fase 4/Restricción 12 prioriza ACTIVO por contacto reciente, mientras Fase 5 define BUFFER_ACTIVO → ACTIVO al completar sincronización y vaciar el buffer. Se expuso al usuario, que confirmó: «Conservar BUFFER_ACTIVO hasta confirmar vaciado». No se interpreta una nueva comunicación o un ciclo del evaluador como prueba de que se vació la cola.

Durante las pruebas se reprodujo además una brecha previa de alcance en GET /iot/dispositivos/{id}/estado: un Ingeniero con permiso de lectura, pero sin pertenencia a la finca, obtenía el estado y su historial. El usuario autorizó incluir el filtro por finca y su regresión. La consulta ahora verifica el alcance existente antes de leer ambos recursos y devuelve el mismo 404 de estado no encontrado fuera del alcance. El endpoint independiente /historial queda fuera de esta corrección.

Rama fix/inc-m03-127-g27-buffer-activo-rf60, creada después de actualizar dev desde origin/dev, base 5691096b8497b9fc445abf0a7579409c8de6550f. No incorpora #681 ni depende de su endpoint o su snapshot.

## Causa raíz y reproducción

EstadoDispositivoIoT.evaluar_transicion evaluaba primero tiempo_sin_contacto ≤ umbral_activo. Por ello, con el último reporte A y pendientes, un ciclo periódico o postcommit podía sustituir BUFFER_ACTIVO por ACTIVO sin un mensaje que confirmara el vaciado.

El caso se reprodujo con una prueba unitaria antes de modificar producción: BUFFER_ACTIVO, contacto hace 3 segundos y estado A devolvía ACTIVO. Evidencia: .pytest_cache/g28_antes.log/xml, una prueba fallida esperada.

Había además dos escritores SQL incoherentes con la decisión confirmada: fn_procesar_heartbeat forzaba ACTIVO en cada heartbeat (salvo mantenimiento), y sp_clasificar_estado_dispositivo priorizaba diez minutos de contacto sobre el buffer pendiente. Arreglar solo Python dejaba oscilaciones al recibir heartbeats repetidos o al ejecutar ese procedimiento.

El adaptador temporal solo transportaba el indicador de buffer, sin su cantidad pendiente. El postcommit utilizaba el indicador del heartbeat procesado incluso si, después de comprobar que era el último, entraba un reporte más reciente.

## Corrección y recorrido

1. El DTO y las columnas existentes se conservan. No se agrega un reporte, permiso, identidad o tabla nueva.
2. El trigger utiliza el advisory lock transaccional existente (3505, id_dispositivo), compartido con el repositorio de estados. Conserva mantenimiento, determina el buffer con el reporte vigente y evita cerrar el período de buffer por un heartbeat que todavía declara pendientes. Conserva FALLO_CONECTIVIDAD como causa de esa condición, usando el enum real modulo3.enum_causa_inactividad para satisfacer la restricción del período.
3. La consulta del adaptador transporta estado y cantidad del mismo último heartbeat, ordenados por fecha_recepcion DESC e id_heartbeat DESC, en una única sentencia.
4. ParametrosComunicacionHeartbeat añade una cantidad opcional al final del constructor para preservar los consumidores anteriores.
5. El dominio prioriza A/L con pendientes sobre el contacto reciente. Un BUFFER_ACTIVO ya confirmado se conserva mientras siga habiendo pendientes, aunque un reporte desactive el indicador; solo una cantidad cero permite liberar ese estado. Si un consumidor anterior no conoce la cantidad, no se inventa que el buffer se vació.
6. El evaluador periódico y el postcommit utilizan esa misma regla. El postcommit relee la fuente vigente después de obtener el bloqueo del dispositivo, para no imponer un heartbeat anterior sobre un reporte concurrente.
7. Un reporte con cero pendientes permite ACTIVO si hay contacto reciente; sin buffer se conservan los umbrales y la tolerancia existentes. EN_MANTENIMIENTO conserva su prioridad.
8. El procedimiento SQL heredado aplica la misma prioridad y utiliza el bloqueo compartido. Conserva sus umbrales preexistentes; no introduce otros defaults.
9. Los triggers existentes siguen siendo la fuente única del historial. El evaluador no agrega registros manuales ni duplica períodos. El commit/rollback se mantiene en los casos de uso y unidades transaccionales existentes.

No se amplía el criterio de observación a la cola física: el backend utiliza el reporte del Edge y no reconstruye su buffer. Tampoco se agrega un timeout que declare vacía una cola pendiente sin evidencia.

## Migración

Nueva revisión c68227f60a01, dependiente de ebbb160365e5. Reemplaza únicamente fn_procesar_heartbeat y sp_clasificar_estado_dispositivo. Conserva las definiciones anteriores completas para downgrade; no modifica tablas, enums, permisos, políticas, triggers de inmutabilidad ni datos históricos.

El trigger conserva el ID del heartbeat utilizado como fuente del estado; una recepción anterior que termina más tarde no reemplaza el reporte vigente. Los locks son transaccionales, sin conceder privilegios de edición sobre infraestructura ni desactivar RLS.

La migración debe desplegarse junto al cambio de aplicación. No se aplicó en la base oficial. Como #681 tiene otra revisión que también parte de ebbb160365e5, al integrar ambas ramas se debe revisar Alembic heads y preparar el merge de revisiones correspondiente; esta rama no asume que #681 esté fusionada ni altera su migración.

## PostgreSQL oficial, seguridad y límites

La inspección se ejecutó con SET TRANSACTION READ ONLY. Se verificaron tipos, FK, restricciones, índices, triggers, funciones y políticas relacionadas. Las funciones obtenidas se conservaron como referencia de la migración.

La consulta con member_dev no devolvió filas para el dispositivo 513 ni su historial; no se reconstruyó la corrida original ni se afirma haber inspeccionado las transacciones 1384/1385/1390/1391. Eso no invalida el defecto reproducido localmente. Las consultas de permisos y alembic_version devolvieron 42501, sin eludir la restricción.

No se enviaron heartbeats ni se alteraron datos, configuración, estados o permisos oficiales. Las pruebas funcionales usan sgpmp_g28_test local. Los privilegios SQL necesarios de fixtures se aprovisionan solo allí, sin desactivar RLS/FORCE ni modificar RBAC. API y operaciones específicas de corrección se comprueban bajo sgpmp_app sin superusuario ni BYPASSRLS. La siembra/observación local usa el propietario del entorno exclusivo.

## Pruebas y evidencias

| Grupo | Aprobadas | Fallidas | Omitidas |
|---|---:|---:|---:|
| tests/telemetry (fakes y contratos HTTP) | 750 | 0 | 0 |
| PostgreSQL real local exclusivo | 83 | 0 | 0 |
| **Total de casos distintos, resultado final** | **833** | **0** | **0** |

La suite de telemetría contiene 35 casos específicos de #682; PostgreSQL incluye 11 casos nuevos de esta incidencia y 72 de regresión DEV-05/27/42. No se suman de nuevo las repeticiones.

La corrida conjunta de PostgreSQL tuvo 82 aprobadas y un fallo en una prueba previa de reintento: asumía que el resto del worker terminaba antes de un segundo. Se estabilizó únicamente la comprobación inmediata con el instante de fallo registrado; la recuperación sigue usando el reloj real y la consulta real de PostgreSQL. Esa prueba se repitió y aprobó (1/1). El resultado final anterior consolida cada caso una sola vez, sin ocultar el fallo inicial. Evidencias: .pytest_cache/g28_regresion_final.xml, g28_pg_final.xml, g28_reintento.xml y g28_resumen_final.json.

Cobertura específica: heartbeat A/37 y L/37; varios ciclos sin mensajes; worker postcommit repetido; nuevo reporte con cero pendientes; recepción fuera de orden; mantenimiento; procedimiento SQL heredado; historial único y períodos; rollback; heartbeats concurrentes y bloqueo del vaciado; JWT, RBAC y consulta fuera de finca. Se verifica upgrade desde una base vacía, downgrade/upgrade y conservación de políticas y privilegios del rol API.

Comandos finales (mediante lanzadores locales de pruebas):

```text
python .pytest_cache/g28_run_unit.py tests/telemetry -q --junitxml=.pytest_cache/g28_regresion_final.xml
python .pytest_cache/g28_run_tests.py tests/integration/test_inc_m03_127_g27_buffer_activo.py tests/integration/test_dev05_ingesta_bplus_postcommit.py tests/integration/test_dev27_heartbeat_parametros.py tests/integration/test_dev42_heartbeat_flujos.py -q --junitxml=.pytest_cache/g28_pg_final.xml
python .pytest_cache/g28_run_tests.py tests/integration/test_dev05_ingesta_bplus_postcommit.py::test_reintento_despues_de_fallo_recupera_solo_la_etapa_pendiente -q --junitxml=.pytest_cache/g28_reintento.xml
```

Durante la validación se corrigieron dos errores de la migración: causa nula incompatible con el período y cast al nombre histórico del enum. También se completaron privilegios SQL de los fixtures locales para el worker y el trigger de sensores; no se modificaron privilegios oficiales. Una corrida previa que coincidió con una reaplicación de migración se interrumpió y no cuenta como evidencia final. Los resultados finales se informan sobre la reconstrucción limpia.

Los lanzadores de Windows usan el shim fcntl únicamente por la dependencia existente del SDK; producción no se modifica por esa limitación. Evidencias y scripts permanecen fuera del commit en .pytest_cache. La base local exclusiva se retira al concluir la validación. El prefijo técnico g28 distingue esta corrida de la corrección anterior del mismo grupo G27.

La base local sgpmp_g28_test se eliminó al terminar y el clúster local quedó detenido. Se comprobó que las otras bases locales permanecieron intactas. Logs y scripts se conservan ignorados en .pytest_cache/g28_cierre_bd.log, g28_cierre_cluster.log y g28_estado_cluster_final.log.

## Contratos y dependencias

Se conservan las rutas, DTO de entrada, schemas HTTP y catálogo público. GET /estado incorpora el filtro de finca autorizado: fuera del alcance devuelve 404, sin exponer el estado ni el historial incluido. Se conservan JWT, estado de cuenta, permisos dinámicos, alcance por finca, auditoría y separación de capas. use_insertmanyvalues=False permanece intacto.

#682 utiliza estado_local_buffer y datos_pendientes_buffer ya existentes: no necesita la ampliación de métricas de #681 ni una modificación de firmware para el caso A/37. Queda pendiente desplegar aplicación/migración y repetir el escenario de QA en un entorno autorizado. No se acredita firmware o MQTT real por las pruebas HTTP/SQL locales.

## Entrega

Código, migración, pruebas y documentación de #682. Archivos ajenos y frontend preservados. El usuario autorizó commit y push de esta corrección. La publicación del PR queda pendiente.
