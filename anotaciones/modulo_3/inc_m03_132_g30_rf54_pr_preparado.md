# RF-54 / RF-62 — Conservar TIME_DESYNC y restringir la aptitud de la lectura · INC-M03-132-G30

## Desvío identificado

| RF exige | Antes | Ahora |
|---|---|---|
| RF-54 E9: marcar datos capturados con reloj desincronizado | La función de ingesta omitía reloj_desincronizado y persistía su default false | Se calcula antes del INSERT con evidencia por lectura o heartbeat y snapshot de procedencia |
| Conservar evidencia del buffer sin reconstruir la captura | El estado del heartbeat no se propagaba a la lectura | La señal de captura prevalece; el fallback indica expresamente estado conocido al ingerir |
| Restringir análisis sensibles y preservar DEV-02 | RF-62 no recibía la marca de reloj | La evaluación oficial excluye de IA y NIC-41 sin modificar la telemetría ni inventar descuentos |

Referencias: #687, INC-M03-132-G30, TC-M03-049, RF-54 E9, RF-53 E7 y acuerdo AIOT-DEV-03 D2 / DEV-02. El usuario confirmó señal por lectura con fallback de heartbeat y exclusión de aptitud sin alterar el índice.

## Causa raíz

modulo3.telemetrias.reloj_desincronizado ya existía, pero modulo3.fn_ingesta_telemetria no lo incluía en su INSERT. Guardar reloj_sincronizado en heartbeats no afectaba a la nueva lectura. El contrato de ingesta y los caminos manual y postcommit de RF-62 tampoco transportaban la evidencia original.

## Cambios implementados

- Campo reloj_sincronizado opcional y booleano estricto en la ingesta simple y cada registro del lote; se transporta en metadatos a la función común.
- Prioridad de señal explícita sobre el último heartbeat recibido del mismo dispositivo, con desempate por ID y exclusión de recepciones futuras. Sin evidencia se conserva el estado desconocido.
- Persistencia de reloj_desincronizado y snapshot metadatos.rf53_reloj antes del INSERT inmutable, manteniendo los otros metadatos.
- Propagación de marca y snapshot desde la lectura original a RF-62 manual y postcommit. TIME_DESYNC deja ambas aptitudes false, conservando índice y clasificación y documentando la restricción.
- Pruebas de regresión y contrato de integración IoT; referencia API actualizada.

## Migración

Nueva revisión c687132a0270, padre ebbb160365e5. Actualiza la definición vigente de la función con guardas y conserva firma de 19 argumentos, resultado, owner, permisos y atributos. No agrega tablas, columnas, índices ni permisos. Sin UPDATE histórico ni backfill.

Upgrade/downgrade/upgrade verificados en PostgreSQL 18. El downgrade elimina solo el cálculo nuevo para futuras ingestas y conserva los datos ya persistidos. No se ha aplicado en la BD oficial.

## Contrato resultante

POST /iot/telemetria y sus registros batch admiten reloj_sincronizado=true/false/null o ausente. Los clientes existentes siguen siendo compatibles; en ausencia de señal se usa heartbeat. Para SQL directo, el broker transmite p_metadatos.reloj_sincronizado sin cambiar la firma.

En buffer, un heartbeat actual no prueba el estado histórico del reloj; el snapshot lo identifica como ESTADO_CONOCIDO_AL_INGERIR. La señal explícita acredita CAPTURA_REPORTADA. Un heartbeat posterior no modifica lecturas anteriores ni elimina su restricción al reevaluarlas.

TIME_DESYNC es un código del flag y del snapshot, sin nuevo valor en el enum de estado_calidad. En la evaluación: flags_detectados.reloj_desincronizado y parametros_aplicados.restriccion_temporal explican apto_para_ia=false y apto_para_nic41=false. APTO con índice 100 y ambas aptitudes false es posible: no se agrega una penalización estadística. La aptitud oficial sigue en telemetria_calidad, conforme a DEV-02.

Se mantienen autenticación, aislamiento por finca, identidad de servicio, RLS y rechazos temporales existentes. Marcar desincronización no permite aceptar capturas futuras o datos de buffer rechazados por antigüedad.

## Pruebas realizadas

| Grupo | Aprobadas | Fallidas | Omitidas |
|---|---:|---:|---:|
| Unitarias y contrato HTTP | 727 | 0 | 0 |
| Integración en PostgreSQL 18 real | 50 | 0 | 0 |
| Total distinto | 777 | 0 | 0 |

Incluye 12 nuevas unitarias y 29 nuevas reales de #687; PostgreSQL añade 8 regresiones del motor #632 y 13 de sensores/calibración/snapshot #626. Los XML finales se contaron sin duplicados y sin sumar corridas previas.

Se verificaron precedencia, datos sin evidencia, tipos inválidos, recuperación y buffer histórico, selección de heartbeat, ingesta simple/lote, evaluación manual/postcommit, aptitudes e historial, rollback/reintento y reversibilidad. HTTP/SQL operativo bajo sgpmp_app; propietario reservado a preparación y migración. El shim fcntl de Windows se limita al lanzador de pruebas.

La reproducción previa confirmó la omisión de la marca. Evidencias temporales en .pytest_cache, excluidas del commit. Se eliminó solo la base exclusiva sgpmp_g33_test y se detuvo el clúster local conservando logs y otras bases.

## Integración con sgpmp_dev

Inspección oficial únicamente en lectura: se confirmó columna, default, función, heartbeat e índice existente; los roles de aplicación e IoT inspeccionados ya disponían de lectura de heartbeats. Las consultas restringidas de RBAC/alembic_version no se eludieron. No se ejecutaron escrituras ni se afirma un despliegue validado.

La corrección requiere desplegar la migración y el backend. No se rellenan lecturas históricas porque el heartbeat actual no permite reconstruir el reloj original.

## Dependencias y pendientes

Firmware debe conservar la señal del reloj al capturar y broker debe transmitirla. Detección y resincronización NTP permanecen en IoT. La validación backend no sustituye TC-M03-049 sobre nodo o simulador real. Ver inc_m03_132_g30_rf54_integracion_iot.md para prioridad, snapshot y procedimiento de integración.

## Alcance del commit

Alcance preparado: 12 archivos — 6 de producción contando la migración, 2 de pruebas y 4 Markdown. Cabeceras de seguimiento de INC-M03-132-G30 en los ocho Python. Sin cambios de frontend ni archivos ajenos. Commit y push autorizados por el usuario; publicación del PR pendiente.

## Revisión contra dev

Rama fix/inc-m03-132-g30-time-desync-rf54 creada desde dev actualizado, base 5691096b8497b9fc445abf0a7579409c8de6550f. No incorpora las ramas independientes #685/#686 ni sus cambios. Revisar heads de Alembic al integrar con otras migraciones y conservar los parches ya presentes en la función vigente.
