# RF-54 / RF-60 — Alertar por capacidad del buffer · INC-M03-129-G27

## Desvío identificado

| RF exige / definición confirmada | Antes | Ahora |
|---|---|---|
| Recibir BUFFER_CAPACITY_WARNING | El enum solo admitía overflow/corrupción | D10 ampliado admite el aviso de capacidad |
| Aviso al 80 % y condición crítica al 95 % | No se generaba la alerta preventiva | Alerta LEVE; desde 95 %, CRITICO |
| Consolidar un incidente abierto | Sin regla de escalamiento para capacidad | Mismo ID, incremento de frecuencia y severidad máxima |
| Visibilidad técnica por rol/finca | El aviso no llegaba al listado técnico | Se consulta por el contrato existente de alertas técnicas, conservando permisos y alcance |

Referencias: #684 · INC-M03-129-G27 · TC-M03-045/G27 · RF-54 Fase 4/E1/Salidas §2 · AIOT-DEV-03 P2/P5/D10 · DEV-11/AIOT-08.

El usuario confirmó ampliar D10 para este evento, con alerta LEVE y escalamiento de la misma alerta a CRITICO desde 95 %, documentando el envío pendiente en firmware/broker.

## Causa raíz

EventoBuffer rechazaba BUFFER_CAPACITY_WARNING y el caso de uso solo gestionaba BUFFER_OVERFLOW y BUFFER_DATA_CORRUPTION. El acuerdo D10 original también limitaba el catálogo a esos dos eventos; RF-54 contempla el aviso preventivo.

## Cambios implementados

- Ampliación del enum público del DTO y su OpenAPI.
- Clasificación del aviso de capacidad y escalamiento mediante SeveridadAlerta existente.
- Reutilización del advisory lock (3505, dispositivo) antes de buscar/crear/consolidar, evitando alertas duplicadas en avisos concurrentes.
- Conservación de ACTIVA/EN_ATENCION y de la severidad máxima; un incidente cerrado permite otro.
- Protección de ultima_ocurrencia frente a reportes atrasados. Metadatos iniciales preservados y evidencia de cada nuevo aviso con severidad_alerta.
- Pruebas unitarias/HTTP, integración PostgreSQL, cabeceras de seguimiento y documentación de integración IoT.

## Migración

No requiere migración. alertas.tipo_variable es VARCHAR(50) y las severidades ya existen. El enum SQL enum_tipo_alerta_tecnica no tiene columnas dependientes en el catálogo inspeccionado y no es el tipo utilizado por este flujo.

Se conservan tablas, políticas, triggers de historial/inmutabilidad y la cadena Alembic existente.

## Contrato resultante

POST /iot/eventos-buffer admite BUFFER_CAPACITY_WARNING con el sobre D10 existente. Devuelve HTTP 201 y los mismos campos: id_alerta, es_duplicado, tipo_alerta_tecnica y severidad.

- Reporte al 80 %: LEVE.
- Reporte al 95 % o superior: CRITICO.
- Misma alerta abierta: mismo ID y frecuencia incrementada; la severidad no se rebaja.
- El umbral del aviso es configurable en Edge: no se introduce un rechazo adicional por porcentajes menores a 80 en un aviso ya emitido.
- OVERFLOW conserva MODERADO; DATA_CORRUPTION conserva CRITICO.

GET /iot/alertas-tecnicas conserva JWT, permiso 36/Leer y alcance por finca. El Productor no accede a la bandeja técnica y el listado operativo excluye estas alertas. CRITICO es la severidad; el ciclo de atención mantiene ACTIVA/EN_ATENCION.

## Pruebas realizadas

| Grupo | Aprobadas | Fallidas | Omitidas |
|---|---:|---:|---:|
| tests/telemetry: fakes y contratos HTTP | 744 | 0 | 0 |
| PostgreSQL real: específicas #684 | 19 | 0 | 0 |
| PostgreSQL real: regresión DEV-49 | 11 | 0 | 0 |
| **Total distinto final** | **774** | **0** | **0** |

La suite de telemetría incluye 29 casos nuevos de #684. La integración comprueba límites 80/95, consolidación 80→95→80, estados ACTIVA/EN_ATENCION/terminales, metadatos originales y reportes atrasados, token de broker, JWT, RBAC, alcance por finca, separación técnica/operativa, auditoría real y fallos inyectados de evidencia con rollback real. Dos pruebas coordinan conexiones concurrentes bajo el lock del dispositivo y verifican una alerta con severidad máxima.

Corridas exploratorias: una falló antes del cambio por el enum (reproducción esperada); la primera focalizada tuvo una aserción nueva que exigía rechazar un datetime sin zona, corregida al contrato UTC compartido; la primera integración obtuvo 18/19 por ordenar auditoría con timestamp_registro transaccional y UUID, corregido en la prueba para ordenar por fecha_hora. Las corridas finales completas aprobaron 744/744 y 30/30. No se suman las repeticiones.

Evidencias: .pytest_cache/g30_antes.xml, g30_foco.xml, g30_pg_foco.xml, g30_unit_final.xml, g30_pg_final.xml, g30_resumen_final.json y sus logs. Se mantienen las advertencias preexistentes de Starlette/httpx y Operation ID duplicado de auditoría.

La siembra usa el propietario local; las nuevas operaciones HTTP/concurrentes comprueban sgpmp_app sin superusuario ni BYPASSRLS. Los privilegios SQL de fixtures se aprovisionan solo en la base exclusiva. El shim fcntl se limita a los lanzadores de Windows.

## Integración con sgpmp_dev

Inspección oficial de solo lectura: tipos, columnas, FK, restricciones, índices, políticas y triggers. member_dev no pudo consultar permisos ni alembic_version (42501); no se eludió la restricción ni se ejecutaron escrituras oficiales.

La validación funcional se ejecutó en sgpmp_g30_test local. No acredita firmware/MQTT reales ni el entorno desplegado de QA.

La base local sgpmp_g30_test se eliminó al terminar y el clúster quedó detenido. Se comprobó que las otras bases se conservaron. Logs y scripts permanecen ignorados en .pytest_cache/g30_cierre_bd.log, g30_cierre_cluster.log y g30_estado_cluster_final.log.

## Dependencias y pendientes

- Desplegar primero el backend compatible y coordinar la ampliación del broker/firmware de AIOT-08.
- Firmware debe emitir el aviso de capacidad y reportar el cruce de 95 %. Broker debe admitir el código, añadir serial y reenviarlo con token de servicio.
- Una ocupación aislada en el heartbeat no ejecuta este flujo. #681 / PR #806 consulta snapshots y permanece separado.
- Mantener el buffer en Edge conforme P5/D10. No se agrega recuperación automática ni otro canal de notificación.
- Repetir TC-M03-045 con Edge real en un entorno autorizado.
- La auditoría RF-57 obligatoria revierte cambios si falla; la evidencia RF-54 conserva su comportamiento best-effort después del commit de la alerta.

## Alcance del commit

Contenido preparado: 2 archivos de producción, 3 de pruebas y 4 documentos Markdown; 9 archivos en total. Se preservan frontend, AGENTS.md, notas ajenas y evidencias ignoradas.

El usuario autorizó commit y push de esta corrección. La publicación del PR queda pendiente.

## Revisión contra dev

Rama fix/inc-m03-129-g27-alerta-capacidad-buffer-rf54, creada desde dev actualizado: 5691096b8497b9fc445abf0a7579409c8de6550f. La rama no incorpora los cambios de #681 ni #682.
