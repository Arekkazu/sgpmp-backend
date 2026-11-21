# INC-M03-131-G23 / #686 — Conservar la secuencia original del buffer Edge

Fecha: 2026-10-27. Rama: `fix/inc-m03-131-g23-secuencia-buffer-rf54`.
Base: dev actualizado, `5691096b8497b9fc445abf0a7579409c8de6550f`.

## Responsabilidad y alcance

Sí corresponde a Desarrollo admitir y conservar la secuencia recibida. RF-54 Entradas define buffer_sequence_id como Long/Integer; Fase 3 lo asigna en Edge y Salidas §1 exige que la secuencia acompañe los datos sincronizados. IoT conserva la generación, el envío FIFO, los reintentos y la liberación local por ACK.

Referencias: [#686](https://github.com/Arekkazu/sgpmp-backend/issues/686), INC-M03-131-G23, TC-M03-037, RF-53/RF-54 y AIOT-DEV-03 P5/D2/D10. El acuerdo elimina modulo3.buffers y mantiene el almacenamiento físico del buffer en Edge. Esto no elimina la trazabilidad de una lectura ya sincronizada.

## Causa raíz y punto de pérdida

El DTO no declaraba buffer_sequence_id. BaseDTO usa el comportamiento por defecto de Pydantic para campos extra, por lo que el dato se ignoraba. El caso de uso además construía metadatos solo con gateway_id, checksum y frecuencia_muestreo.

La función común ya admite p_metadatos JSONB y lo copia a telemetrias.metadatos. ORM y entidad ya transportan ese diccionario. Por tanto, la ausencia de una columna dedicada no bloquea conservar ni consultar la secuencia; no se necesita otra tabla o migración.

Flujo resultante: DTO → IngerirTelemetriaUseCase → IngestaTelemetriaPort → SqlAlchemyIngestaTelemetriaRepository → fn_ingesta_telemetria(p_metadatos) → INSERT inmutable → metadatos consultables por SQL y por la entidad de dominio existente.

## Corrección mínima

- Campo opcional buffer_sequence_id en IngerirTelemetriaDTO, también utilizado por cada registro del batch.
- Entero JSON no negativo, hasta 9223372036854775807, sin coerción de booleanos, flotantes ni cadenas. Los valores mal formados conservan el error de entrada HTTP 400.
- El caso de uso añade la clave a metadatos solo si el valor no es None; conserva 0 y números grandes exactamente.
- Ausente/null: no se añade ni se inventa una secuencia. Clientes anteriores mantienen su comportamiento.
- Firma SQL de 19 entradas y respuestas HTTP sin cambios. No se toca el puerto, repositorio, ORM, entidad, función SQL, índices, permisos ni triggers porque el contrato de metadatos ya permite el recorrido.
- No se reconstruye la secuencia histórica ni se actualizan lecturas. El commit/rollback sigue perteneciendo al caso de uso.

## FIFO, idempotencia y límites

El batch conserva su orden cronológico existente por timestamp_captura, definido también en RF-54 CA-4/Postcondiciones. La corrección no cambia prioridades de RFC-016 ni supone una secuencia global entre dispositivos. La Fase 6 del RF expresa secuencia/captura en la preparación del envío en Edge: guardar el dato permite contrastarlo, no demuestra esa ejecución física.

buffer_sequence_id se mantiene como evidencia recibida, no como nueva clave única. Se conserva la deduplicación por sensor/variable/captura/origen. Un reintento con otro número no reemplaza el original. Dos dispositivos pueden usar la misma secuencia. Si secuencia y timestamp discrepan, ambos se conservan: no se renumera para aparentar FIFO.

No se agregan endpoints ni campos a las respuestas. La consulta SQL y el contrato broker están en [integración IoT](inc_m03_131_g23_rf54_integracion_iot.md). El broker MQTT directo debe incluir la secuencia en p_metadatos; el DTO HTTP no participa en ese camino. No se inspeccionó ni modificó firmware/broker externos.

## Base de datos, seguridad y migraciones

La inspección oficial fue de solo lectura y confirmó current_database=sgpmp_dev, current_user=member_dev y transaction_read_only=on. Se verificaron columnas, restricciones, índices, RLS/políticas, triggers y la definición de la función. telemetrias.metadatos ya es JSONB NOT NULL y la función conserva p_metadatos sin reconstruirlo.

El usuario de lectura no pudo consultar RBAC ni alembic_version (42501); se respetó la restricción. No se ejecutó DDL/DML oficial ni se asumieron migraciones desplegadas a partir de Git.

Para integración se creó exclusivamente sgpmp_g32_test en PostgreSQL 18 local, puerto 55429. Alembic desde cero dejó una única head ebbb160365e5. No hay una migración propia. El esquema local conserva restricciones, triggers y RLS/FORCE; los privilegios SQL de fixtures se aprovisionaron solo allí, sin modificar RBAC.

Los padres de prueba se siembran con el propietario local; las operaciones HTTP y el camino SQL equivalente al broker usan sgpmp_app sin superusuario ni BYPASSRLS y la identidad de servicio existente. Se mantiene el token de servicio y no se inventan identidades.

## Pruebas y evidencias

| Grupo | Aprobadas | Fallidas | Omitidas |
|---|---:|---:|---:|
| tests/telemetry: unitarias/fakes y contratos HTTP | 733 | 0 | 0 |
| PostgreSQL real: específicas #686 | 16 | 0 | 0 |
| PostgreSQL real: regresión alta/calibración/snapshot #626 | 13 | 0 | 0 |
| **Total distinto final** | **762** | **0** | **0** |

La suite unitaria incluye 18 casos nuevos. Se verifican ausencia/null/0/Long máximo, tipos inválidos, OpenAPI opcional, propagación por registro y compatibilidad del metadato anterior.

Integración: HTTP individual, batch, consulta JSONB con cast bigint, lectura ORM→dominio, función compartida del broker, deduplicación sin alterar originales, scope de secuencias por dispositivo, rollback real después del INSERT y reintento, token requerido y discrepancia secuencia/timestamp sin renumerar.

La reproducción previa g32_antes tuvo 16 fallidas y 2 aprobadas, mostrando el campo descartado. g32_foco aprobó los 18 nuevos más 16 regresiones de ingesta. La primera corrida PostgreSQL aprobó 14 y falló una aserción de autenticación porque ese fixture no configuraba el token y el contrato devolvía 503; se corrigió el fixture para probar 401 con servicio configurado. La corrida final aprobó los 29 casos PostgreSQL. No se cuentan repeticiones.

Evidencias ignoradas: g32_unit_final.xml/log, g32_pg_final.xml/log, g32_resumen_final.json, g32_preflight.json/log, g32_inspeccion_local.log y lanzadores en .pytest_cache. Shim fcntl solo en el lanzador Windows. Persisten las advertencias previas Starlette/httpx y Operation ID de auditoría.

Se eliminaron únicamente los datos de sgpmp_g32_test; se comprobó que las otras bases se conservaron. El clúster se detuvo al finalizar. Logs g32_cierre_bd.log y g32_cierre_cluster.log.

## Pendientes de integración y alcance Git

IoT debe confirmar que el firmware publica el identificador y que el broker lo reenvía intacto a p_metadatos. TC-M03-037 integral requiere evidencia del nodo/broker y contraste con la BD en un entorno autorizado. Estas pruebas locales no certifican MQTT, el buffer físico ni un despliegue de QA.

Ocho archivos: dos de producción, dos de pruebas y cuatro Markdown (referencia API, informe, contrato IoT y PR preparado). Cabeceras con fecha real e identidad Git verificada Leandro. Se preservan AGENTS.md, notas ajenas, frontend y evidencias ignoradas. La rama no incorpora #681/#682/#684/#685. El usuario autorizó commit y push de esta corrección. La publicación del PR queda pendiente.
