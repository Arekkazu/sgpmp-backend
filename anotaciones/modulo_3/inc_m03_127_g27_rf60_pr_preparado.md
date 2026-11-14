# RF-54 / RF-60 — Conservar BUFFER_ACTIVO hasta confirmar vaciado · INC-M03-127-G27

## Desvío identificado

| RF exige / decisión confirmada | Antes | Ahora |
|---|---|---|
| Mantener BUFFER_ACTIVO con el último reporte de buffer pendiente | El contacto reciente tenía prioridad y devolvía ACTIVO sin confirmar vaciado | Buffer confirmado tiene prioridad en dominio, evaluador y postcommit |
| Salir del buffer cuando se confirme su vaciado | El trigger forzaba ACTIVO ante cualquier heartbeat y el procedimiento SQL repetía esa prioridad | Ambos escritores SQL conservan el buffer pendiente y respetan el reporte vigente |
| Consulta de estado limitada a las fincas autorizadas | Un Ingeniero con permiso de lectura podía obtener estado/historial de otra finca | GET /estado comprueba el alcance antes de consultar y devuelve 404 fuera de él |
| Historial y períodos coherentes | Podían producirse transiciones contradictorias y cierres prematuros | Se conserva el trigger como fuente única; repetir un reporte pendiente no genera otra transición |

Referencias: #682, grupo G27, RF-54, RF-60 Fases 4/5, Restricción 12 y CA-2, AIOT-DEV-03 P5/D10. Se expuso la contradicción de RF-60 entre contacto reciente y salida al vaciar; el usuario confirmó conservar BUFFER_ACTIVO hasta confirmar vaciado.

## Causa raíz

EstadoDispositivoIoT.evaluar_transicion resolvía ACTIVO antes de considerar el buffer. El adaptador no transportaba la cantidad pendiente y el postcommit utilizaba el indicador del heartbeat procesado en lugar de releer la fuente vigente bajo bloqueo.

Además, fn_procesar_heartbeat forzaba ACTIVO y sp_clasificar_estado_dispositivo priorizaba contacto reciente. Corregir solo Python dejaba escritores contradictorios.

## Cambios implementados

- Regla de dominio compartida que prioriza buffer A/L pendiente y conserva un BUFFER_ACTIVO confirmado hasta un reporte de vaciado. Mantenimiento mantiene prioridad.
- Cantidad pendiente opcional añadida al final de ParametrosComunicacionHeartbeat, preservando constructores anteriores.
- Adaptador que lee estado y pendientes del mismo último heartbeat por recepción e ID.
- Evaluador y postcommit aplican la misma regla; postcommit revalida la fuente después del bloqueo.
- Trigger y procedimiento SQL alineados con la prioridad confirmada y el advisory lock existente (3505, dispositivo).
- El trigger conserva el ID de la fuente vigente, la causa primaria requerida por el período y evita cierres prematuros.
- Filtro por finca en GET /iot/dispositivos/{id}/estado y su historial incluido, usando el alcance y el puerto existentes. Ampliación autorizada expresamente tras reproducir la brecha en las pruebas; el endpoint independiente /historial no forma parte de este cambio.
- Pruebas nuevas y expectativas anteriores actualizadas para la decisión de #682, con cabeceras de seguimiento.

## Migración

Nueva revisión c68227f60a01, dependiente de ebbb160365e5. Reemplaza únicamente fn_procesar_heartbeat y sp_clasificar_estado_dispositivo. Conserva las definiciones anteriores para downgrade.

No agrega tablas, columnas, enums, permisos o políticas, ni modifica datos históricos. La causa utiliza el tipo real modulo3.enum_causa_inactividad. Debe desplegarse junto a la aplicación; no se ejecutó en la base oficial.

## Contrato resultante

Se conservan rutas y DTO/schema público. GET /estado devuelve 404 para un dispositivo fuera del alcance de finca, antes de leer su estado e historial; mantiene JWT y RBAC. Los campos existentes estado_local_buffer y datos_pendientes_buffer bastan para #682.

Un reporte A/37 o L/37 mantiene BUFFER_ACTIVO, incluso con contacto reciente y tras ciclos sin mensajes nuevos. Un BUFFER_ACTIVO ya confirmado no se libera mientras siga habiendo pendientes. Un reporte con cero pendientes permite ACTIVO si el contacto es reciente. Sin datos suficientes no se inventa que la cola se vació. Sin buffer se conservan los umbrales de comunicación y la tolerancia existentes.

La recepción de un heartbeat anterior no sustituye el reporte vigente. El historial sigue en los triggers existentes y el cierre del período ocurre al confirmar la recuperación correspondiente.

## Pruebas realizadas

| Grupo | Aprobadas | Fallidas | Omitidas |
|---|---:|---:|---:|
| tests/telemetry (fakes y contratos HTTP) | 750 | 0 | 0 |
| PostgreSQL real local exclusivo | 83 | 0 | 0 |
| **Total de casos distintos, resultado final** | **833** | **0** | **0** |

La suite de telemetría contiene 35 casos específicos de #682; PostgreSQL incluye 11 casos nuevos de esta incidencia y 72 de regresión DEV-05/27/42. No se suman de nuevo las repeticiones.

La corrida conjunta de PostgreSQL tuvo 82 aprobadas y un fallo en una prueba previa de reintento: asumía que el resto del worker terminaba antes de un segundo. Se estabilizó únicamente la comprobación inmediata con el instante de fallo registrado; la recuperación sigue usando el reloj real y la consulta real de PostgreSQL. Esa prueba se repitió y aprobó (1/1). El resultado final anterior consolida cada caso una sola vez, sin ocultar el fallo inicial. Evidencias: .pytest_cache/g28_regresion_final.xml, g28_pg_final.xml, g28_reintento.xml y g28_resumen_final.json.

Evidencias locales ignoradas en .pytest_cache. No se acredita firmware ni MQTT real mediante HTTP/SQL local.

## Integración con sgpmp_dev

La inspección oficial fue de solo lectura: columnas, restricciones, índices, funciones, triggers y políticas. member_dev no obtuvo filas del dispositivo 513/historial y no pudo consultar permisos ni alembic_version (42501). No se reconstruyó la corrida original ni se eludieron esas restricciones.

Las pruebas funcionales utilizan PostgreSQL local exclusivo, con API bajo sgpmp_app sin superusuario ni BYPASSRLS. Los privilegios de fixtures se aprovisionan solo en esa base; no se desactivan restricciones, RLS o FORCE.

La base local sgpmp_g28_test se eliminó al terminar y el clúster local quedó detenido. Se comprobó que las otras bases locales permanecieron intactas. Logs y scripts se conservan ignorados en .pytest_cache/g28_cierre_bd.log, g28_cierre_cluster.log y g28_estado_cluster_final.log.

## Dependencias y pendientes

- Desplegar aplicación y migración de forma coordinada.
- No depende del endpoint o las métricas nuevas de #681 ni requiere ampliar firmware para A/37.
- #681 tiene una revisión paralela que también parte de ebbb160365e5. Al integrar ambas ramas, revisar Alembic heads y preparar el merge de revisiones; esta rama no incorpora ni modifica #681.
- Repetir QA en un entorno autorizado. No se enviaron mensajes ni se modificó el dispositivo oficial.

## Alcance del commit

Contenido preparado: 8 archivos de producción/migración, 3 de pruebas y 3 documentos Markdown. Código, pruebas e informes de #682; sin cambios del frontend.

El usuario autorizó commit y push de esta corrección. La publicación del PR queda pendiente. Se excluyen AGENTS.md, notas ajenas, .pytest_cache y credenciales.

## Revisión contra dev

Rama fix/inc-m03-127-g27-buffer-activo-rf60, creada desde dev actualizado, base 5691096b8497b9fc445abf0a7579409c8de6550f. Los archivos locales ajenos permanecen preservados.
