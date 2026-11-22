# RF-53 / RF-62 — Completar la marca de frecuencia y validar drift · INC-M03-130-G16

## Desvío identificado

| RF exige / alcance confirmado | Antes | Ahora |
|---|---|---|
| Marcar frecuencia anómala sin rechazar la lectura | El intervalo de 1 minuto ya se marcaba con configuración 10; el de 60 minutos no | Se mantienen los casos rápidos y se detectan los lentos |
| Conservar el muestreo aplicado | frecuencia_muestreo_min se insertaba en NULL | Snapshot del valor M09 aplicado para las consultas posteriores de RF-62 |
| Consultar drift calculado sin modificar el origen | El reporte confundía el campo inicial FALSE con el resultado de RF-62 | Se valida el recorrido hasta la evaluación vigente y se documenta su fuente |

Referencias: #685 · INC-M03-130-G16 · TC-M03-034 / TC-M03-068 · RF-53 E13/E17 · RF-62 Fases 1/4/5/7 · AIOT-DEV-03 DEV-02.

Se conserva la decisión confirmada: drift en RF-62 y telemetría original inmutable.

## Causa raíz

La revisión 15cb081c4835 ya calculaba frecuencia rápida buscando vecinos a menos de medio intervalo. No contemplaba frecuencia lenta y el INSERT conservaba NULL en el muestreo aplicado.

El motor RF-62 sí calcula posible_drift y lo guarda en telemetria_calidad. El campo inicial de telemetrias no representa esa evaluación posterior. No se duplica el algoritmo en SQL.

## Cambios implementados

- Migración reversible de la función vigente de ingesta, compartida por HTTP y broker.
- Búsqueda del vecino anterior/posterior más cercano del mismo sensor y variable, contemplando BUFFER_LOCAL fuera de orden.
- Conservación del límite inferior existente de 0,5 intervalos; detección de intervalos superiores a 2, coherente con la consistencia temporal RF-62. Los límites exactos no se marcan.
- Persistencia del muestreo configurado en la nueva lectura, sin recalcular lecturas previas.
- Exclusión de EVENTO_EDGE como muestra periódica y como vecino.
- Pruebas PostgreSQL de ingesta, drift, inmutabilidad, snapshot y reversibilidad; referencia API e informe técnico.

## Migración

Nueva revisión c685130a0260, padre ebbb160365e5, con una única head.

Parchea únicamente el bloque de frecuencia y el valor del snapshot en fn_ingesta_telemetria. Conserva firma de 19 entradas, retorno, propietario, ACL, atributos, validaciones, multiespecie y snapshot de calibración. Falla explícitamente si no encuentra una única versión del bloque esperado.

No crea tablas, columnas, índices ni permisos. No modifica datos históricos. Downgrade restituye la regla anterior para nuevas ingestas y conserva datos existentes.

## Contrato resultante

Sin cambios en rutas, DTO, códigos HTTP ni respuestas.

Con muestreo M09 de 10 minutos:

- 1 minuto: frecuencia_anomala = TRUE.
- 5, 10 o 20 minutos: FALSE.
- Más de 20 minutos, incluido 60: TRUE.
- Primera lectura sin vecino: FALSE.

La anomalía no rechaza la lectura. La frecuencia declarada por el cliente no sustituye M09. Se conservan los valores de las lecturas ya almacenadas.

El drift se consulta mediante GET /iot/calidad/{id_telemetria}, en flags_detectados.posible_drift de la evaluación vigente. El 201 de ingesta confirma persistencia RF-53 y puede preceder a la evaluación postcommit. Sin calibración no se inventa drift.

## Pruebas realizadas

| Grupo | Aprobadas | Fallidas | Omitidas |
|---|---:|---:|---:|
| tests/telemetry: fakes y contratos HTTP | 715 | 0 | 0 |
| PostgreSQL real: específicas #685 | 35 | 0 | 0 |
| PostgreSQL real: regresión motor #632 | 8 | 0 | 0 |
| PostgreSQL real: regresión alta/snapshot #626 | 13 | 0 | 0 |
| **Total distinto final** | **771** | **0** | **0** |

Evidencias finales: .pytest_cache/g31_unit_cierre.xml, g31_pg_core_final.xml, g31_pg_snapshot_cierre.xml y g31_resumen_final.json, con sus logs. Las ejecuciones unitarias iniciales interrumpidas por espera prolongada no se cuentan; la corrida final completa aprobó 715/715.

Los 35 casos específicos verifican los límites de frecuencia mediante HTTP, batch y SQL, latencia independiente, buffer desordenado, muestreo histórico, configuración M09 frente al dato del cliente, eventos no periódicos, drift con/sin calibración, consulta vigente e inmutabilidad. La migración se prueba con downgrade/upgrade y conservación de atributos/privilegios.

Las regresiones existentes cubren motor RF-62 y el flujo alta → asociación → calibración → ingesta → evaluación, además de rollback, historial y JWT/RBAC. Operaciones nuevas con sgpmp_app sin superusuario ni BYPASSRLS. Los privilegios de fixtures se aprovisionaron exclusivamente en la base local.

Las corridas exploratorias detectaron y corrigieron precondiciones de fixtures: privilegios SQL, nombre offset_calibracion y relación heartbeat ≥ muestreo. Las reproducciones previas de frecuencia lenta y snapshot fallaron como se esperaba. No se suman repeticiones al total final.

## Integración con sgpmp_dev

La conexión oficial de solo lectura agotó el tiempo de espera. No se pudo comprobar la función ni las migraciones desplegadas; no se realizaron escrituras oficiales.

La validación funcional utiliza PostgreSQL 18 local y la base exclusiva sgpmp_g31_test, migrada desde cero. No acredita broker/firmware reales ni despliegue de QA.

Al terminar se eliminó exclusivamente sgpmp_g31_test, se comprobó que las otras bases locales se conservaron y se detuvo el clúster. Evidencias: .pytest_cache/g31_cierre_bd.log y g31_cierre_cluster.log.

## Dependencias y pendientes

- Aplicar c685130a0260 mediante el procedimiento autorizado del entorno.
- Comprobar 15cb081c4835, el snapshot 8d13c7e9a624 y la función efectiva si QA aún ve FALSE en la lectura de un minuto.
- Repetir TC-M03-034 y TC-M03-068 con configuración y calibración verificables, consultando el resultado vigente de RF-62.
- No requiere ampliar el contrato MQTT ni el firmware.
- No se incorporan ramas independientes de #681, #682 o #684.

## Alcance del commit

Cambios preparados en cinco archivos: una migración, un archivo de integración y tres documentos Markdown. Cabeceras de seguimiento incluidas en ambos archivos de código.

El usuario autorizó commit y push de esta corrección. La publicación del PR queda pendiente. Se preservan archivos ajenos y evidencias ignoradas.

## Revisión contra dev

Rama fix/inc-m03-130-g16-marcas-calidad-rf53, creada desde dev actualizado en 5691096b8497b9fc445abf0a7579409c8de6550f.
