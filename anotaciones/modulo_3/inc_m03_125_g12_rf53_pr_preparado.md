# RF-53 / RF-63 — Resguardar la evidencia de fallas de persistencia · INC-M03-125-G12

## Desvío identificado

| RF exige | Antes | Ahora |
|---|---|---|
| Trazar FALLA_PERSISTENCIA aun si PostgreSQL no responde | La ruta intentaba auditar en la misma BD caída; quedaba solo un log genérico | Cada intento HTTP fallido conserva un evento de auditoría durable en SQLite independiente |
| Conservar la evidencia hasta poder persistirla | No había recuperación posterior | El worker recupera en FIFO y confirma el respaldo después del commit |
| No confirmar lecturas sin persistencia | 503 correcto | Se conserva 503; el emisor retiene y reintenta sus lecturas conforme al acuerdo |

Referencias: issue #680, TC-M03-026, RF-53 R9/E12/CA-12, RF-63 y AIOT-DEV-03 P5/D2; AIOT-01 para el broker/Edge. El usuario confirmó seguir la definición más acorde al acuerdo. P5/D2 asigna el buffer no volátil de lecturas a Edge: este cambio respalda auditoría, sin crear una segunda cola de lecturas en backend.

## Causa raíz

RutaIngestaAuditada identificaba FALLA_PERSISTENCIA, pero escribía su auditoría mediante la misma conexión lógica a PostgreSQL que estaba indisponible. El fallo de esa segunda escritura se reducía a un log, sin evidencia individual recuperable. FALLA_PERSISTENCIA ya existe como tipo RF-63; no falta un enum o un estado de calidad nuevo.

## Cambios implementados

- Puertos de dominio, casos de uso de resguardo/sincronización y adaptador SQLite transaccional independiente.
- Contexto seguro por intento: UUID, fecha, correlación, hash del body e identificadores/timestamps válidos; batch con trazas acotadas. No se conservan valores crudos, token, serial, SQL ni mensajes internos.
- Recuperación periódica con identidad de servicio existente, advisory lock transaccional, UUID estable e inserción idempotente. Una repetición exige el mismo hash.
- Confirmación local únicamente después del commit. Un error de escritura o commit revierte el lote sin borrar los pendientes. Un fallo posterior al commit permite repetir sin duplicar.
- Log CRITICAL si también falla el almacenamiento local. Se mantiene la respuesta original al emisor.
- Directorio Docker con UID 1000, volumen persistente de Compose y exclusión de archivos runtime del contexto de construcción.
- Cabeceras de seguimiento con la identidad Git consultada y conservación de las filas previas.

## Migración

No hay migración PostgreSQL ni cambios a RLS, permisos o triggers. Se reutilizan la PK UUID y el trigger de inmutabilidad de modulo3.bitacora_auditoria_iot. La tabla privada de pendientes SQLite se inicializa por el adaptador y solo contiene evidencia de auditoría.

La base local exclusiva se migró desde cero hasta 30168ab97bd4. Esto no acredita migraciones desplegadas en DEV/TEST.

## Contrato resultante

POST /iot/telemetria y POST /iot/telemetria/batch conservan sus contratos. Durante la caída no se entrega id_telemetria ni éxito; se conserva 503 BD_NO_DISPONIBLE. El respaldo no supone recepción definitiva de las lecturas. El emisor debe conservarlas y reenviarlas por RF-54 cuando se recupere la persistencia.

El worker publica las evidencias pendientes en modulo3.bitacora_auditoria_iot, manteniendo UUID, fecha y hash originales. Las lecturas se procesan solo al recibir el reintento normal del emisor; se conservan el orden por captura y la deduplicación existentes.

## Pruebas realizadas

| Grupo | Aprobadas distintas | Fallidas | Omitidas |
|---|---:|---:|---:|
| Unitarias / contratos HTTP; SQLite real y PostgreSQL con fakes | 665 | 0 | 0 |
| PostgreSQL 18 real, rol sgpmp_app sin superusuario ni BYPASSRLS | 4 | 0 | 0 |
| **Total final sin duplicar corridas** | **669** | **0** | **0** |

La integración real cubre: veinte 503 durante la caída, veinte evidencias durables, recuperación automática del worker, reenvío del emisor en orden y deduplicación; interrupción entre commit y confirmación; rollback completo ante una restricción real de PostgreSQL; y recuperadores concurrentes.

Las pruebas unitarias/HTTP cubren además batch, reapertura del respaldo, cuarenta escritores SQLite concurrentes, integridad, fallos de disco, autorización, metadatos seguros, fechas extremas, temporizador y apagado del worker.

Evidencias ignoradas en .pytest_cache: g12_regresion.xml (664), g12_durable_final.xml (33, solo una adicional) y g12_pg_definitivo.xml (4). La reproducción inicial fallida se conserva en g12_antes.log/xml. git diff --check y docker compose config --quiet fueron correctos. No se construyó ni desplegó la imagen Docker.

## Integración con sgpmp_dev

La base oficial se inspeccionó únicamente en lectura. Se comprobaron columnas, PK, tipo_evento varchar(80), trigger de inmutabilidad y estado de RLS. La tabla de auditoría inspeccionada no tiene RLS/FORCE; no se atribuye esa protección. Se preserva el aislamiento por finca de las consultas y las políticas relacionadas.

La comprobación oficial de permisos quedó limitada por el rechazo de member_dev al ejecutar modulo1.fn_id_rol_actual. No se eludió la restricción ni se modificaron roles o datos oficiales. Las pruebas funcionales usaron PostgreSQL local exclusivo. Tras completarlas se eliminó solo sgpmp_g12_test y se detuvo el clúster local, conservando otras bases y evidencias.

## Dependencias y pendientes

- Desplegar con IOT_AUDITORIA_RESPALDO_PATH en almacenamiento persistente; Compose define /app/storage/auditoria_iot/fallas.sqlite3 y volumen sgpmp_auditoria_iot. El intervalo técnico del worker es configurable, 5 s por defecto.
- Conservar ese volumen entre reinicios. No se acredita resistencia a pérdida física del volumen ni resguardo si también falla el disco.
- Adaptar TC-M03-026 a P5/D2 y repetir con broker/Edge reales. AIOT-01 debe retener/reintentar sin confirmar lo no persistido, también en el camino MQTT B+ que escribe directamente desde el broker.
- Las pruebas HTTP no acreditan firmware, MQTT, backoff del Edge ni una corrida oficial de QA.

## Alcance del commit

Contenido preparado: 11 archivos de producción/configuración, 3 archivos de pruebas y 2 informes Markdown. Incluye main.py, ruta auditada, repositorio de auditoría, puertos/casos de uso/adaptador/worker y configuración del volumen Docker.

El usuario autorizó el commit y el push de esta entrega el 2026-10-27. Este documento prepara el contenido del PR; no se crea ni publica un PR. Se excluyen AGENTS.md, notas ajenas, .pytest_cache, archivos SQLite, credenciales y cualquier cambio del frontend.

## Revisión contra dev

Rama fix/inc-m03-125-g12-falla-persistencia-rf53 creada desde dev actualizado, base 18b4ce67e8d23ed57fdfd108d44e0c2601e66604. Los cambios de #678 no forman parte de esta entrega. Los archivos ajenos previos permanecen conservados.
