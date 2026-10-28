# INC-M03-125-G12 · #680 · RF-53 / RF-63 — Trazabilidad de fallas de persistencia

Implementación y pruebas: 2026-10-26. Cierre de documentación: 2026-10-27. Autor de cabeceras: Leandro, consultado mediante git config user.name.

## Alcance confirmado y referencias

Issue #680, TC-M03-026, RF-53 R9/E12/CA-12 y catálogo RF-63. Documentos revisados: Requerimientos_M03_RF53-RF63.md, Especificacion-Requerimientos-Modulo3 (1).md y AIOT-DEV-03_Acuerdo_Consolidado_Desarrollo_AIoT (1).md.

RF-53 exige resguardo y reprocesamiento. El acuerdo AIOT-DEV-03 P5/D2 concreta que el buffer no volátil de lecturas es el del Edge, que el broker no confirma lo no persistido y que una excepción, timeout o BD caída exige retener y reintentar con backoff. AIOT-01 implementa esa interpretación en broker/firmware. Desarrollo mantiene la vía HTTP por la misma función SQL y el trabajo postcommit.

Se expuso la contradicción entre la ficha que pide una cola de lecturas en backend y el acuerdo. El usuario indicó: «Ve con el mejor, y que mas acorde vaya a lo establecido». Se conserva P5/D2. El respaldo nuevo contiene evidencia de auditoría; no contiene lecturas para ingesta ni sustituye RF-54. Un 503 no confirma entrega ni autoriza liberar el buffer del emisor.

La rama fix/inc-m03-125-g12-falla-persistencia-rf53 parte de dev actualizado, commit 18b4ce67e8d23ed57fdfd108d44e0c2601e66604. No incorpora los cambios de #678 ni modifica el frontend. El usuario autorizó el commit y el push el 2026-10-27; no se crea ni publica un PR.

## Diagnóstico y causa raíz

La respuesta 503 ante BD inaccesible es correcta. get_db realiza sus reintentos y devuelve BD_NO_DISPONIBLE con un mensaje público seguro.

RutaIngestaAuditada ya reconocía errores de SQLAlchemy/psycopg2 y emitía FALLA_PERSISTENCIA. Sin embargo, _registrar_error intentaba escribir esa evidencia en la misma BD caída. Al fallar, solo dejaba un log sin correlación individual ni respaldo recuperable.

La reproducción inicial envió veinte solicitudes con una caída simulada de conexión: obtuvo veinte 503 y falló la aserción de existencia del respaldo durable. No se usó la base oficial para esa reproducción.

La afirmación «FALLA_PERSISTENCIA no existe» requiere precisión: existe como tipo de evento RF-63 en el código y tipo_evento es varchar(80), sin catálogo enum que necesite ampliarse. No se convierte en un estado de calidad de una lectura persistida. El estado ERROR_PERSISTENCIA de bitacora_ingest y el tipo FALLA_PERSISTENCIA de auditoría son conceptos distintos.

## Recorrido y corrección

1. El token de servicio del broker se verifica como antes. Las peticiones no autorizadas no generan este respaldo.
2. Ante un error real de persistencia, la ruta construye un contexto limitado: correlación, hash SHA-256 del body, identificadores válidos y fecha de captura normalizada. Para batch conserva hasta los 500 identificadores permitidos por el contrato y la cantidad total.
3. El caso de uso genera UUID y fecha originales, clasificación NIC41/retención de 5 años y el hash existente de RF-63.
4. Un adaptador guarda ese evento en SQLite independiente del PostgreSQL principal, con synchronous=FULL, orden secuencial y transacciones cortas. No almacena Authorization, serial, valores crudos, headers arbitrarios, SQL ni mensajes internos del error.
5. La respuesta original se conserva, incluido 503 BD_NO_DISPONIBLE. No se devuelve id_telemetria ni éxito por haber respaldado una evidencia.
6. Un worker periódico de lifespan revisa pendientes. Tras recuperarse PostgreSQL, utiliza la identidad de servicio existente y un advisory lock transaccional para serializar recuperadores.
7. El caso de uso valida el hash y escribe el lote en orden FIFO. INSERT ON CONFLICT DO NOTHING conserva el UUID; el hash existente debe coincidir para aceptar un reintento.
8. Solo después del commit de PostgreSQL se confirman/eliminan los pendientes locales. Una caída entre commit y confirmación puede repetir intentos, pero no crea otra fila ni modifica evidencia existente.
9. Si falla una escritura o el commit, se revierte el lote y se conserva todo el respaldo. Si el disco también falla, se emite un log CRITICAL sin convertir la solicitud en éxito.

El temporizador respeta el apagado: espera el trabajo iniciado y conserva la cancelación aunque ese trabajo encuentre otro fallo.

## Arquitectura y contratos

Se agregan puertos de dominio para el respaldo y su destino, casos de uso separados para resguardar/sincronizar, adaptador de almacenamiento y composición en infraestructura. Los puertos transportan EventoAuditoriaIot, no modelos ORM. SQL y mapeos permanecen en infraestructura; commit/rollback de PostgreSQL pertenecen al caso de uso.

No se cambia el contrato HTTP, JWT/RBAC, token del broker, reglas SQL de ingesta, calibración, orden del batch, tratamiento de duplicados o procesamiento postcommit. Se conserva use_insertmanyvalues=False. No se inventa otra identidad de servicio ni acceso global para hacer pasar las pruebas.

La tabla privada pendientes del archivo SQLite es un mecanismo técnico de respaldo de auditoría; no sustituye una tabla de negocio ni una dependencia de migración. No existe una cola de lecturas nueva en el backend.

## Base de datos y RBAC

La inspección oficial fue SET TRANSACTION READ ONLY. Se comprobaron columnas y tipos, PK UUID, ausencia de restricción enum para tipo_evento, trigger de inmutabilidad y RLS de bitacora_auditoria_iot. Esta tabla inspeccionada no tiene RLS/FORCE habilitado; no se atribuye una protección inexistente. Se conservan los filtros por finca de la aplicación y las políticas de las tablas relacionadas.

La consulta oficial de permisos no se pudo completar con member_dev: PostgreSQL rechazó ejecutar modulo1.fn_id_rol_actual. No se alteraron roles, funciones, permisos ni datos oficiales para evitar esa restricción. Los privilegios de prueba se aprovisionaron únicamente en sgpmp_g12_test, con sgpmp_app sin superusuario ni BYPASSRLS.

No hay migración PostgreSQL nueva. Se reutilizan la PK e inmutabilidad existentes. El entorno local se migró desde cero hasta 30168ab97bd4; eso no demuestra el estado de migraciones desplegadas en otro ambiente.

## Almacenamiento y despliegue

- Ruta local predeterminada: var/auditoria_iot/fallas.sqlite3.
- Variable técnica: IOT_AUDITORIA_RESPALDO_PATH.
- En Docker: /app/storage/auditoria_iot/fallas.sqlite3, con directorio propiedad de UID 1000 y volumen sgpmp_auditoria_iot en Compose.
- IOT_AUDITORIA_RESPALDO_INTERVALO_SEG controla el intervalo técnico del worker, por defecto 5 segundos; no es un nuevo umbral funcional.
- El contexto Docker excluye los directorios de respaldo runtime. Los archivos SQLite y las evidencias de pruebas no forman parte de Git.

El despliegue debe conservar ese directorio en almacenamiento persistente. No se acredita resistencia a pérdida física del volumen ni un modo alternativo si fallan simultáneamente PostgreSQL y el disco local. La segunda falla queda visible en CRITICAL y el emisor continúa obligado a retener sus lecturas.

## Pruebas y evidencias

| Grupo | Aprobadas distintas | Fallidas | Omitidas |
|---|---:|---:|---:|
| Unitarias y contratos HTTP (fakes para PostgreSQL; SQLite real) | 665 | 0 | 0 |
| Integración con PostgreSQL 18 real y rol API | 4 | 0 | 0 |
| **Total distinto final** | **669** | **0** | **0** |

El total se consolidó por `classname + name` de los XML, sin sumar las corridas repetidas: g12_regresion.xml contiene 664; g12_durable_final.xml contiene 33, de las cuales solo una prueba del temporizador es adicional; g12_pg_definitivo.xml aporta cuatro distintas. La regresión contiene 622 casos de tests/telemetry y 42 de tests/configuration; el caso adicional del temporizador pertenece a tests/telemetry. Los resultados intermedios fallidos de reproducción y ajuste del fixture se conservan, pero no se presentan como el resultado final.

La suite específica comprueba veinte 503, correlación por intento, metadatos seguros sin secretos ni valores de lectura, batch, reapertura de SQLite, cuarenta escritores concurrentes, integridad, rollback, confirmación posterior al commit, fallos de disco, rechazo de solicitudes no autorizadas, fechas extremas, recuperación periódica y apagado del worker.

Las cuatro pruebas reales demuestran:

1. Se confirma una ingesta de control, se detiene PostgreSQL, se envían veinte solicitudes que responden 503 y se conservan veinte evidencias en SQLite. Tras reiniciar PostgreSQL, el worker periódico recupera automáticamente las veinte filas de auditoría con UUID, fecha y hash originales. No crea lecturas desde el respaldo. El emisor de prueba conserva los cuerpos y reenvía las veinte lecturas en batch desordenado: se procesan por captura, y un segundo envío produce veinte duplicados sin crear filas adicionales.
2. Un fallo de confirmación local posterior al commit no pierde el respaldo; al reabrir el adaptador se reintentan los mismos UUID y no se duplican en PostgreSQL.
3. Una restricción real de longitud en PostgreSQL (SQLSTATE 22001) revierte todo el lote y mantiene ambas evidencias locales pendientes.
4. Dos recuperadores concurrentes publican treinta eventos una sola vez.

La preparación y observación del entorno usa su propietario local. Las operaciones de la API y del recuperador usan sgpmp_app, comprobado con rolsuper=false y rolbypassrls=false, e identidad de servicio existente. No se desactivan políticas ni restricciones.

Evidencias locales ignoradas en .pytest_cache: g12_antes.log/xml (reproducción), g12_regresion.log/xml, g12_durable_final.log/xml, g12_pg_definitivo.log/xml, g12_preflight_oficial.log, g12_compose.log, g12_cierre.log y los lanzadores g12_run_unit.py/g12_run_tests.py. La integración final terminó con 4 passed en 70,49 s. El aviso de Starlette sobre httpx corresponde a una dependencia existente.

También se verificaron git diff --check y docker compose config --quiet. No se construyó ni desplegó una imagen; la validación de Compose no demuestra el montaje efectivo del volumen en un entorno desplegado.

El shim fcntl se limita a los lanzadores de Windows de pruebas por la dependencia existente del SDK. El respaldo nuevo utiliza las transacciones y bloqueos reales de SQLite, sin depender del shim.

## Verificación de TC-M03-026 y límite de alcance

El criterio se interpreta conforme a P5/D2: durante el 503 el emisor conserva las lecturas; el backend conserva la evidencia de intentos fallidos; tras recuperar BD, el worker publica la auditoría y el emisor reenvía sus lecturas con sus timestamps originales.

Enviar veinte POST y descartar sus cuerpos pese a recibir 503 no valida el buffer RF-54 ni obliga al backend a confirmar una persistencia que no ocurrió. El camino MQTT B+ escribe directamente desde el broker: las fallas que no alcanzan HTTP deben observarse en broker/Edge conforme a AIOT-01. No se declara validado ese firmware por una prueba HTTP local.

Pendiente: integrar/desplegar los cambios, ajustar la ficha de QA a la distribución de responsabilidades acordada y repetir TC-M03-026 con broker y Edge reales. No se declara aprobada una corrida oficial ni se publica un comentario o PR sin autorización.

## Procedimiento de repetición para QA

1. Usar un entorno exclusivo con token de servicio, hardware y calibración válidos; conservar los cuerpos de las veinte lecturas en el emisor.
2. Interrumpir únicamente PostgreSQL de ese entorno. Enviar las lecturas y verificar 503 sin confirmación de id_telemetria; inspeccionar las veinte evidencias locales y su correlación.
3. Recuperar PostgreSQL y mantener el mismo volumen del respaldo. Verificar que el worker publique los mismos UUID y vacíe los pendientes solo después del commit.
4. Reenviar las lecturas retenidas por el emisor con origen BUFFER_LOCAL. Verificar el orden de captura y el tratamiento de duplicados al repetir el lote.
5. Para acreditar RF-54 y AIOT-01, repetir con el broker y firmware reales, observando su buffer, backoff y confirmaciones. El emisor HTTP de integración no acredita esos componentes.

## Cierre del entorno local

Se eliminó exclusivamente sgpmp_g12_test después de las pruebas y se detuvo limpiamente el clúster local. Se conservaron las otras bases del clúster y las evidencias/scripts en .pytest_cache. No se eliminaron archivos del usuario ni se ejecutó DDL/DML en la base oficial. La evidencia del cierre está en g12_cierre.log.
