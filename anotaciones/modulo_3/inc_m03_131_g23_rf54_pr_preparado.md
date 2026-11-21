# RF-54 / RF-53 — Conservar buffer_sequence_id del Edge · INC-M03-131-G23

## Desvío identificado

| RF exige | Antes | Ahora |
|---|---|---|
| Conservar la secuencia de los datos sincronizados | El DTO ignoraba buffer_sequence_id y el caso de uso no lo propagaba | Campo opcional conservado en telemetrias.metadatos.buffer_sequence_id |
| Mantener el identificador original | No quedaba disponible para el contraste de QA | Se conserva exactamente, sin generar ni renumerar |
| Mantener compatibilidad e inmutabilidad | Contratos existentes sin secuencia | Clientes anteriores compatibles; deduplicación y datos confirmados preservados |

Referencias: #686 · INC-M03-131-G23 · TC-M03-037 · RF-54 Entradas/Fases 3 y 6/Salidas §1/CA-4 · RF-53 · AIOT-DEV-03 P5/D2/D10.

Desarrollo conserva la secuencia en la ingesta. Edge/IoT genera y envía el identificador y mantiene su buffer físico.

## Causa raíz

IngerirTelemetriaDTO no declaraba el campo: Pydantic lo descartaba como extra. IngerirTelemetriaUseCase construía un subconjunto de metadatos que tampoco lo incluía.

La función SQL existente ya conserva p_metadatos JSONB, de modo que la ausencia de una columna dedicada no exige crear otra tabla ni modificar la firma acordada.

## Cambios implementados

- Campo opcional buffer_sequence_id en el DTO compartido por ingesta individual y batch.
- Validación como entero JSON no negativo de 64 bits con signo, sin coerciones.
- Propagación del valor original a metadatos antes del INSERT común.
- Ausente/null conserva la compatibilidad; cero y Long máximo se mantienen exactamente.
- Pruebas de contrato, persistencia real, deduplicación, rollback y reintento.
- Documentación de consulta QA e integración pendiente con IoT.

## Migración

No requiere migración. Se reutiliza telemetrias.metadatos JSONB y p_metadatos de fn_ingesta_telemetria, cuya firma de 19 entradas permanece intacta.

No se recrea modulo3.buffers, eliminado conforme D10. Se mantienen índices, restricciones, triggers, permisos, RLS y la head ebbb160365e5 del árbol base.

## Contrato resultante

POST /iot/telemetria y cada elemento de POST /iot/telemetria/batch admiten buffer_sequence_id opcional, entero entre 0 y 9223372036854775807. Los tipos/valores inválidos producen el error de entrada HTTP 400 existente.

El backend conserva el número en metadatos.buffer_sequence_id. Si se omite o es null no inventa una secuencia. No cambia respuestas, orden cronológico existente del batch ni la clave de deduplicación sensor/variable/captura/origen.

Una secuencia no es globalmente única. Un reintento no modifica la lectura original. Las discrepancias entre secuencia y timestamp se conservan como evidencia, sin renumeración.

## Pruebas realizadas

| Grupo | Aprobadas | Fallidas | Omitidas |
|---|---:|---:|---:|
| tests/telemetry: fakes y contratos HTTP | 733 | 0 | 0 |
| PostgreSQL real: específicas #686 | 16 | 0 | 0 |
| PostgreSQL real: regresión alta/calibración/snapshot #626 | 13 | 0 | 0 |
| **Total distinto final** | **762** | **0** | **0** |

Incluye 18 pruebas unitarias nuevas. PostgreSQL cubre HTTP, batch, función común del broker, consulta JSONB, mapeo de dominio, exactitud numérica, datos originales inmutables, deduplicación, rollback después del INSERT y reintento. Operaciones nuevas bajo sgpmp_app sin superusuario ni BYPASSRLS.

La reproducción previa falló por el descarte del campo. Una prueba inicial de autenticación necesitó configurar el token del fixture para contrastar 401 en lugar del 503 de servicio no configurado; no se cambió el contrato. Las corridas finales están verdes y no se suman repeticiones.

Evidencias locales ignoradas: .pytest_cache/g32_unit_final.xml, g32_pg_final.xml, g32_resumen_final.json y logs asociados.

## Integración con sgpmp_dev

Inspección oficial en solo lectura, con transaction_read_only=on: función, columnas, restricciones, índices, políticas y triggers. Se confirmó metadatos JSONB y la conservación de p_metadatos. RBAC y alembic_version no fueron accesibles a member_dev (42501); no se eludió la restricción ni se ejecutaron escrituras oficiales.

Validación funcional en PostgreSQL 18 local, sgpmp_g32_test migrada desde cero. Los privilegios SQL de fixtures se aprovisionaron solo allí, preservando RBAC/RLS. La base desechable se eliminó y el clúster se detuvo, conservando otras bases y evidencias.

## Dependencias y pendientes

- Desplegar el backend compatible para la recepción HTTP.
- IoT debe confirmar que firmware genera/publica el campo y broker lo conserva en p_metadatos al llamar la función existente.
- El DTO HTTP no participa en el camino MQTT directo; la prueba SQL acredita persistencia, no el productor externo.
- Repetir TC-M03-037 con evidencia de envío/ACK del Edge y contraste de la secuencia en BD.
- No se reconstruyen secuencias históricas ni se redefine la política FIFO. No se certifica firmware/MQTT real desde estas pruebas locales.

## Alcance del commit

Ocho archivos preparados: dos de producción, dos de pruebas y cuatro documentos Markdown. Cabeceras de seguimiento en los cuatro archivos de código.

El usuario autorizó commit y push de esta corrección. La publicación del PR queda pendiente. Se preservan archivos ajenos y evidencias ignoradas.

## Revisión contra dev

Rama fix/inc-m03-131-g23-secuencia-buffer-rf54, creada desde dev actualizado en 5691096b8497b9fc445abf0a7579409c8de6550f. No incorpora las ramas independientes de #681/#682/#684/#685.
