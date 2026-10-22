# DEV-05 — Ingesta B+ y procesamiento posterior al commit

Fecha: 2026-10-17, America/Bogota. Historia #3523; épica #3503.
Subtareas #3598–#3602. Base de desarrollo: `origin/dev`, `cd06a257`.
Rama independiente: `fix/dev05-ingesta-bplus-postcommit`.

## 1. Estado de la entrega

Se implementó la parte de aplicación: ingesta HTTP por la función común,
procesamiento durable por etapas, recuperación de heartbeats y eliminación de
la bitácora duplicada de éxito. **No está habilitado el cierre integral de QA**:
faltan DB-02, la integración de DEV-02 en la base de la rama y la publicación
de los umbrales de heartbeat de Análisis/DEV-14. No se hicieron despliegues ni push.

La separación de responsabilidades sigue el reparto suministrado: Samuel es
responsable de DB-02 y de las migraciones; DEV-05 implementa la aplicación.
El acuerdo consolidado agrupa originalmente cambios SQL y de aplicación bajo
DEV-05, pero el reparto posterior los separa explícitamente. Se aplicó esta
última asignación; no se copió la solución SQL a Python.

## 2. Diagnóstico confirmado

### Código anterior

`IngerirTelemetriaUseCase` repetía las reglas de tiempo, unidades, rangos,
duplicados y calibración en Python, insertaba mediante ORM y llamaba a
`registrar_exito`. El trigger de RF-53 también escribía el éxito. La función
SQL usada por el broker y HTTP podían producir resultados diferentes.

RF-61/RF-62/semáforo solo se intentaban durante el request HTTP, después del
primer commit, sin una recuperación durable común para MQTT. Una falla podía
quedar únicamente en logs. La recepción HTTP de heartbeats también contenía
procesamiento que no se ejecutaba para una inserción del broker.

### Verificación de la base oficial de desarrollo

Se confirmó `current_database() = sgpmp_dev`, usuario `member_dev` y
`transaction_read_only = on`. El nombre real incluye la segunda `p`.
Se consultaron definiciones, columnas y triggers; **no se ejecutaron funciones
de ingesta, DML, migraciones ni pruebas con escrituras en DEV**.

Hallazgos verificables:

- `fn_ingesta_telemetria` mantiene su firma de 19 entradas y retorno
  `(id_telemetria, estado_calidad, mensaje)`.
- Conserva la aproximación de rango físico `× 5`, la selección de umbral con
  `LIMIT 1`, latencia fija de 2000 ms, valor ajustado crudo sin calibración y
  retornos de rechazo sin insertar su bitácora. DB-02 aún es una dependencia.
- SHA-256 de la definición recuperada:
  `aa7c6aa0fba267cbdc86093efe70ac9a59eb430d60d8099505114de87c725c79`.
- Están habilitados los triggers RF-53 de timestamp, no UPDATE, no DELETE y
  bitácora de persistencia; también los de cache de sensor y heartbeat.
- `telemetria_calidad` dispone de aptitudes, estado y referencia a evaluación
  superada. No se necesita una nueva tabla para almacenar calidad.
- `configuraciones_globales` publica frecuencia y heartbeat; no dispone de
  umbrales de batería/RSSI. El reparto también los deja pendientes de Análisis.
- La consulta de `alembic_version` fue denegada por permisos. No se afirma una
  revisión de migraciones ni un SHA de aplicación desplegado en DEV.

El `.env` local apuntaba a otra base (`integrador`); no se utilizó como sustituto
de DEV. Las credenciales no se incorporaron a código, documentación ni evidencias.

### Dependencias de código

DEV-02 (`8fc5ef9c`), DEV-04 (`49644a91`) y DEV-17 (`fa41e8e3`) existen en ramas
independientes, pero no estaban integrados en `origin/dev` durante el análisis.
No se mezclaron sus commits ni sus archivos en esta entrega.

## 3. Flujo implementado

```text
HTTP: DTO + credencial existente → fn_ingesta_telemetria → commit → respuesta
MQTT: broker → misma función SQL → commit
                                ↓
             procesador del backend consulta filas confirmadas
                                ↓
       RF-61 / RF-62 / RF-17, o estado / alertas de heartbeat
                                ↓
             efectos de cada etapa + evidencia RF-63 atómicos
```

### HTTP y errores de la función

Se conserva el DTO y la forma de las respuestas públicas. El catálogo I3P-1
traduce el nombre público de variable a su identificador/categoría SQL; no
repite sus reglas por fila. Se conserva la validación de la credencial HTTP
existente hasta DEV-06. Una credencial rechazada se registra sin incluirla en
el payload de bitácora.

| Prefijo de retorno sin ID | HTTP | Código funcional |
|---|---:|---|
| `ERROR_DUPLICADO` | 409 | `ERROR_DUPLICADO` |
| `ERROR_ESTRUCTURA` | 400 | `ERROR_ESTRUCTURA` |
| `ERROR_AUTENTICACION` | 401 | `ERROR_AUTENTICACION` |
| `ERROR_TIEMPO` | 400 | `ERROR_TIEMPO` |
| `ERROR_UNIDAD` | 400 | `ERROR_UNIDAD` |
| `ERROR_SENSOR` | 422 | `ERROR_SENSOR` |

Un rechazo normal de la función confirma la transacción antes de responder,
para conservar la evidencia que debe escribir DB-02. No se reproduce esa
bitácora en Python. Un retorno desconocido o inconsistente produce
`INGESTA_NO_CONFIRMADA`/503 y rollback. Un ID solo permite confirmar cuando
acompaña a uno de los tres estados persistidos y a su timestamp almacenado.
Los detalles internos SQL no se incorporan a los mensajes públicos.

Batch mantiene el orden cronológico, la aceptación parcial y el conteo de
duplicados. La indisponibilidad o un error inesperado no se convierte en un
acuse funcional exitoso. Los ítems confirmados antes de una falla conservan
su commit; el reenvío se apoya en la unicidad de la función/base.

### Progreso, concurrencia y recuperación

Se reutiliza `modulo3.bitacora_auditoria_iot`, con eventos
`POSTCOMMIT_<ETAPA>_COMPLETADO` y `POSTCOMMIT_<ETAPA>_FALLIDO`, hash RF-63,
ID de origen y tipo de fuente. Las etapas son:

- `RF61`, `RF62` y `RF17` para lecturas; RF-17 espera la etapa RF-61.
- `HEARTBEAT_ESTADO` y `HEARTBEAT_ALERTAS`, independientes de la calidad escalar.
  Las alertas esperan la etapa de estado del mismo heartbeat.

La existencia de una evaluación no excluye una lectura de las otras etapas.
El selector considera evidencia por responsabilidad y un enfriamiento de
reintento. Una fila fallida no detiene las siguientes ni las otras etapas.
El proceso se reconstruye desde PostgreSQL tras un reinicio, sin callback del
broker, cola volátil ni tabla de transporte adicional.

Cada etapa usa una conexión fijada a una transacción externa y sesiones con
`join_transaction_mode='create_savepoint'`. Los commits de los casos de uso
existentes liberan savepoints; el commit externo confirma efectos y evidencia
juntos. Una falla de la evidencia revierte también los efectos de la etapa.
El evento de fallo se intenta en otra transacción después del rollback.
Una falla de auditoría deja el trabajo pendiente y se informa en logs.

Se usan locks de fila `FOR UPDATE SKIP LOCKED` y un advisory lock transaccional
por dispositivo, namespace 3505. La evidencia se vuelve a consultar después
del lock. No se mantiene el lock durante comunicaciones externas.
Los selectores usan expresiones parametrizadas SQLAlchemy Core.

El lifespan ejecuta el ciclo fuera del event loop mediante un hilo; cada unidad
abre y cierra sus propias sesiones. Al apagar espera la unidad en curso.
En producción declara la identidad de servicio existente, sin BYPASSRLS.

### Calidad y semáforo

Las consultas nuevas de lectura excluyen los flags obsoletos de `telemetrias`.
La aptitud se obtiene exclusivamente de una evaluación `VIGENTE` de
`telemetria_calidad` que ninguna posterior señale como superada; el orden de
desempate es determinista.

La integración usa el caso de uso RF-62 existente. Mientras su puerto conserve
`actualizar_flags_aptitud`, la etapa informa `RF62_DEV02_PENDIENTE` y se reintenta:
no intenta el UPDATE ni captura P0002 para simular una evaluación completada.
Una evaluación oficial ya existente puede reutilizarse.

RF-61 reutiliza su caso de uso y evita crear otra vinculación vigente. El
semáforo reutiliza el cálculo RF-17, reconstruye el cache desde la mayor captura
válida cuando llegan datos tardíos y conserva la prioridad de comunicación,
mantenimiento y alertas. Si falta contexto/umbral, usa GRIS; no acredita VERDE
sin una clasificación. Las filas históricas originales no se modifican.

Se mantiene la limitación previa de RF-61: el adaptador M02 resuelve la ocupación
actual del área, no su historial completo. DEV-05 no introduce una reconstrucción
histórica de ubicaciones ni de umbrales.

### Heartbeats

La recepción HTTP autentica y guarda; MQTT conserva su inserción existente.
El trigger sigue siendo dueño del contacto y la reconexión. El procesamiento
posterior no inserta otro heartbeat ni duplica el historial inicial de alertas
o las transiciones que ya registran triggers.

Se procesa el buffer `A`/`L` del último heartbeat por fecha de recepción/ID,
preservando mantenimiento y evitando despertar estados sin señal por reproceso.
La transición a BUFFER_ACTIVO utiliza la causa existente `FALLO_CONECTIVIDAD`,
necesaria para el período obligatorio que abre el trigger. También se corrigió
el repositorio de alertas para enviar su `fecha_registro` obligatoria.

Las alertas de batería/RSSI reutilizan una única lógica y deduplican por
dispositivo, causa y estado vigente. Sus límites provienen de un puerto de
parámetros. **No hay valores predeterminados de negocio inventados**: el
adaptador de producción informa `PARAMETROS_HEARTBEAT_NO_DISPONIBLES` mientras
Análisis/DEV-14 no publique la fuente M09. El heartbeat y su buffer permanecen
almacenados y recuperables. Las pruebas numéricas utilizan parámetros de prueba
inyectados; no acreditan configuración oficial disponible en DEV.

## 4. Archivos y justificación

| Archivo | Responsabilidad y cambio |
|---|---|
| `main.py` | Registra el ciclo postcommit en el lifespan existente. |
| `.env.example` | Documenta lote, intervalo y espera técnicos; no contiene umbrales de negocio. |
| `src/telemetry/application/use_cases/ingesta/ingerir_telemetria_use_case.py` | Delega la fila a SQL, interpreta retorno/commit y conserva batch. Mantiene la constante importada por visión. |
| `src/telemetry/application/use_cases/ingesta/procesar_postcommit_use_case.py` | Orquesta etapas, reintentos y aislamiento de fallas. |
| `src/telemetry/application/use_cases/ingesta/procesar_lectura_confirmada_use_case.py` | Reutiliza RF-61/RF-62/RF-17 y hace visible la dependencia DEV-02. |
| `src/telemetry/application/use_cases/infraestructura/recibir_heartbeat_use_case.py` | Separa recepción y procesamiento de la fila confirmada, sin duplicar triggers. |
| `src/telemetry/domain/entities/evento_auditoria_iot.py` | Añade el tipo de entidad HEARTBEAT al dominio; la columna SQL existente es varchar. |
| `src/telemetry/domain/repositories/ingesta_telemetria_port.py` | Contrato y resultado del puerto de ingesta común. |
| `src/telemetry/domain/repositories/postcommit_port.py` | Etapas y contrato de unidad transaccional. |
| `src/telemetry/domain/repositories/parametros_heartbeat_port.py` | Parámetros de batería/RSSI sin fijar constantes de negocio. |
| `src/telemetry/domain/repositories/alerta_repository.py` | Operación de búsqueda de alerta técnica vigente por dispositivo/causa. |
| `src/telemetry/infrastructure/repositories/ingesta_telemetria_repository.py` | Ejecuta la función de firma intacta; recupera tiempos sin leer aptitud obsoleta. |
| `src/telemetry/infrastructure/repositories/postcommit_repository.py` | Selectores, locks, transacción externa y evidencia RF-63 obligatoria. |
| `src/telemetry/infrastructure/repositories/lectura_postcommit_repository.py` | Consultas de fuente oficial, vinculación y cache derivado. |
| `src/telemetry/infrastructure/repositories/alerta_repository.py` | Deduplicación técnica y fecha de registro obligatoria. |
| `src/telemetry/infrastructure/adapters/parametros_heartbeat_pendientes_adapter.py` | Informa la dependencia pendiente de M09 sin simular configuración. |
| `src/telemetry/infrastructure/workers/postcommit_worker.py` | Compone adaptadores existentes y ciclo asíncrono. |
| `src/telemetry/infrastructure/workers/__init__.py` | Declara el paquete de infraestructura del procesador. |
| `src/telemetry/infrastructure/routers/telemetria_router.py` | Compone la ingesta SQL conservando rutas y respuestas. |
| `src/telemetry/infrastructure/routers/infraestructura_iot_router.py` | Compone la recepción de heartbeat sin procesamiento duplicado. |
| `tests/telemetry/test_dev05_ingesta_bplus.py` | Contrato de retorno, commit, errores, credenciales y batch. |
| `tests/integration/test_dev05_ingesta_bplus_postcommit.py` | PostgreSQL real, recuperación, concurrencia, calidad vigente, heartbeat, cache e inmutabilidad. |
| `anotaciones/modulo_3/api_reference_m03_telemetria_iot.md` | Aclara confirmación de persistencia y procesamiento posterior. |
| `anotaciones/modulo_3/dev05_validacion.json` | Evidencias sanitizadas y resultados por caso/contexto. |
| `anotaciones/modulo_3/dev05_ingesta_bplus_postcommit.md` | Diagnóstico, decisiones y límites de esta entrega. |

## 5. Pruebas y evidencia de ejecución

Las escrituras utilizaron PostgreSQL 18.4 local efímero, Python 3.13.13 y
Alembic hasta `3a9d5e7c1b24`. Las pruebas ordinarias usaron el fixture existente
de transacción externa/savepoints; las pruebas con dos conexiones confirmaron
sus fixtures solo en esa base aislada. No se desactivaron triggers. Los fixtures
confirmados de hardware se desactivaron lógicamente; la instancia efímera se
retiró al terminar. No se ejecutaron pruebas destructivas en `sgpmp_dev`.

| Grupo distinto | Aprobadas | Pendientes conocidas | Evidencia |
|---|---:|---|---|
| Telemetría, incluida ingesta DEV-05 | 46 | Un archivo de visión no colectable en Windows | `--confcutdir=tests/telemetry`, excluyendo el archivo indicado abajo |
| Shared: traductor, handlers globales, RLS, reconexión y FK | 73 | Ninguna en la selección ejecutada | Cinco archivos seleccionados de `tests/shared` |
| Integración DEV-05 | 28 | 1 skip DEV-02; 2 xfail estrictos DB-02 | Archivo de integración DEV-05 |
| Regresión PostgreSQL RF-61 | 6 | Ninguna | `test_inc_m09_64_g31_vinculacion_ingesta.py` |
| Escenario condicional DEV-02 + DEV-05 | 1 | Requiere integrar DEV-02 en la rama base | Serie de 21 lecturas, solo en validación temporal combinada |

En la rama independiente: **153 aprobadas, 0 fallos inesperados, 1 omitida y
2 incumplimientos conocidos (`xfail`, no aprobaciones)**. La prueba omitida
también se ejecutó en un contexto temporal con los siete archivos productivos
del commit DEV-02 existente: aprobó sin UPDATE y con ambas aptitudes oficiales.
No se volvió a contar como dos casos: hay **154 casos distintos con aprobación
en alguno de los contextos**, de los cuales uno es condicional; los otros dos
casos contractuales siguen pendientes. El detalle está en el JSON de evidencia.

La superposición temporal no forma parte de la entrega. Una restauración tuvo
un bloqueo transitorio de Windows; se restauraron y verificaron contra HEAD
los siete archivos originales, que no aparecen en el diff final DEV-05.

Cobertura relevante:

- Paridad HTTP/función para hardware equivalente, con y sin calibración, y una
  única bitácora de éxito por lectura. Es paridad con la función vigente, no
  aprobación de las reglas pendientes DB-02.
- Rechazos, duplicados, batch parcial, desconocidos, fallo de escritura/commit
  y ausencia de credenciales en los parámetros persistidos.
- Recuperación aunque calidad ya exista; evaluación no superada; excepción
  individual sin detener otra fila; enfriamiento y recuperación del reintento.
- Rollback de efectos aunque el caso de uso interno haya hecho commit si falla
  la evidencia obligatoria; hash RF-63 verificable después de recuperar el evento.
- Dos conexiones disputando el mismo origen; una fila no confirmada permanece
  invisible para el procesador. No se acredita una prueba de carga sostenida.
- Heartbeat HTTP con autenticación y heartbeat SQL; buffer activo/lleno,
  mantenimiento, límites numéricos inyectados, deduplicación e historial inicial único.
- Cache con lectura tardía, conectividad de la captura mayor, ausencia de VERDE
  sin contexto y prioridad de alerta/estado operativo.
- UPDATE y DELETE reales siguen siendo rechazados por RF-53 con P0002.

### Comandos reproducibles

Definir `DATABASE_URL` y `TEST_DATABASE_URL` únicamente hacia una base aislada
permitida por `tests/integration/conftest.py`, migrada con el esquema del proyecto.
No usar DEV como destino de estos comandos.

```powershell
.venv/Scripts/python.exe -m pytest --confcutdir=tests/telemetry tests/telemetry --ignore=tests/telemetry/test_inc_m09_77_g137_observaciones_vision.py -q
.venv/Scripts/python.exe -m pytest --confcutdir=tests/shared tests/shared/test_db_error_translator.py tests/shared/test_error_handlers_globales.py tests/shared/test_contexto_rls.py tests/shared/test_database_reintentos.py tests/shared/test_orm_foreign_keys_resolvibles.py -q
.venv/Scripts/python.exe -m pytest --confcutdir=tests/integration tests/integration/test_dev05_ingesta_bplus_postcommit.py tests/integration/test_inc_m09_64_g31_vinculacion_ingesta.py -q
.venv/Scripts/python.exe -m pytest --confcutdir=tests/integration tests/integration/test_dev05_ingesta_bplus_postcommit.py::test_serie_20_lecturas_evalua_rf62_cuando_dev02_esta_integrado -q
.venv/Scripts/python.exe -m compileall -q src/telemetry main.py
git diff --check
```

El último escenario de pytest requiere DEV-02 integrado; de lo contrario omite
la ejecución expresamente. Los dos xfail son estrictos: cuando DB-02 los corrija,
el resultado XPASS obligará a retirar la marca y acreditar la nueva implementación.

Se intentó la colección del archivo de visión excluido: importa `main`, que
importa M02 y falla por `ModuleNotFoundError: fcntl` en Windows. Sus casos no se
ejecutaron. La aplicación completa y su lifespan no se arrancaron en este entorno.
El aviso de deprecación Starlette/httpx no impidió las suites ejecutadas.

Bandit, control `-lll -iii`, aprobó los archivos productivos cambiados: cero
hallazgos altos. Su inventario completo conserva un hallazgo medio previo en
`main.py` por el bind de uvicorn `0.0.0.0`; esa línea no se modificó. Los nuevos
selectores no requieren SQL interpolado ni supresiones `nosec`.
Semgrep no se ejecutó localmente; se conserva el control CI configurado.

## 6. Configuración y riesgos operativos

| Variable técnica | Valor predeterminado |
|---|---:|
| `IOT_POSTCOMMIT_LOTE` | 50 filas por etapa/ciclo |
| `IOT_POSTCOMMIT_INTERVALO_SEG` | 5 segundos |
| `IOT_POSTCOMMIT_REINTENTO_SEG` | 60 segundos |

Los defaults son límites técnicos de ejecución, no umbrales funcionales.
Cada unidad fija límites locales de sentencia y espera de lock. Las credenciales
y la identidad de servicio se resuelven por la infraestructura existente.

Antes del despliegue conjunto:

1. Integrar DB-02 manteniendo firma/códigos y comprobar rechazo con bitácora,
   ajuste NULL sin calibración, umbral por especie/área, límites físicos y latencia M09.
2. Integrar DEV-02; repetir la suite escalar sin superposición temporal.
3. Publicar el contrato y la fuente M09 de umbrales de heartbeat; sustituir el
   adaptador pendiente por el adaptador real y repetir las pruebas numéricas.
4. Verificar grants y asociaciones de fincas de la identidad de servicio en el
   entorno de despliegue. No se verificó una carga real bajo el rol productivo.
5. Probar el broker real/BRK-01 y su ACK según D2: los tests SQL no sustituyen
   una sesión MQTT real. Edge, buffer SQLite y tópicos se mantienen fuera del cambio.
6. Medir el selector sobre el volumen real. Se reutilizan los índices RF-63
   existentes; cualquier índice adicional debe coordinarse con DBA. No se
   acreditó rendimiento a escala ni se introdujo DDL para anticiparlo.
7. Conservar accesible la evidencia de finalización durante la vida de las
   fuentes RF-53; el archivado/retención de RF-63 no debe eliminar marcadores
   todavía necesarios para la idempotencia. No se implementó borrado ni archivado nuevo.

DEV-04 es la corrección separada del traductor de triggers; esta rama conserva
el traductor existente. No se duplicó. DEV-17 tampoco se modifica: el procesador
no envía paquetes al motor de inferencia ni cambia su estado.

## 7. Subtareas y cierre

| Subtarea | Estado técnico |
|---|---|
| #3598 — HTTP por función común | Implementada en aplicación; contrato integral condicionado a DB-02. |
| #3599 — Postcommit telemetría | Implementado por etapas; RF-62 nuevo queda pendiente hasta integrar DEV-02. Compatibilidad combinada comprobada. |
| #3600 — Postcommit heartbeat | Persistencia, buffer, recuperación y lógica de alertas implementados. Activación numérica pendiente de parámetros oficiales. |
| #3601 — Bitácora de éxito única | Implementada y verificada: se conserva el trigger y se elimina la invocación duplicada. |
| #3602 — Pruebas de paridad | Automatizadas y ejecutadas en PostgreSQL aislado. Cierre completo pendiente de dependencias y broker real. |

No hay migraciones, modificaciones a triggers, nuevos tópicos, buffers paralelos,
cambios RF-17 de comandos ni contratos IA simulados. Los cambios funcionales
aplican a la ingesta y sus derivados; el frontend permanece fuera del alcance.

Se prepara un commit local convencional en la rama indicada. El identificador
efectivo se informa en la entrega y puede consultarse con `git log -1 --oneline`.
No se publica una PR ni se realiza push desde esta tarea.

## 8. Referencias utilizadas

- `AIOT-DEV-03_Acuerdo_Consolidado_Desarrollo_AIoT.md`: P1–P7, D2 y dependencia de parámetros.
- `DEV-Reparto_Tareas_Integracion_AIoT.md`: DEV-05 #3523, DB-02 #3507, DEV-14 y responsabilidades de broker/DBA.
- Prompt DEV-05 adjunto: subtareas #3598–#3602 y restricción de escrituras compartidas.
- Código, migraciones existentes y definiciones consultadas en DEV; las
  diferencias constatadas se documentan arriba, sin asumir despliegues de otras ramas.
