# RF-24 — Calibración por cada especie del área · DEV-24

**Referencias:** Historia #3697 · Tareas #3788 y #3789 · Épica #3662 · RF-24 v2.0 · RFC-012.

**Estado:** criterios técnicos de DEV-24 implementados y verificados localmente. El usuario autorizó entregar código, pruebas y los dos informes en un único commit en `fix/dev24-calibracion-vision-multiespecie`. La integración hacia `dev` depende de DB-06 y su adaptación ORM de DEV-22; QA y la publicación del PR siguen pendientes. No se modificó Taiga ni se creó un PR de DEV-24.

## Alcance principal confirmado por el usuario

La ficha breve de DEV-24 es el criterio de esta entrega: `calibrar_vision_use_case.py` deja de leer `area.id_especie`, obtiene las especies presentes desde la relación N:M de DB-06 y calcula una línea base por cada par `(área, especie)`. No se agrega como requisito clasificar individuos o separar las muestras de visión por especie.

| Criterio de la tarea | Evidencia ejecutada | Resultado |
|---|---|---|
| Leer las especies de DB-06 | Repositorio real de DEV-22 sobre `modulo9.infraestructuras_especies`, creada por la migración exacta de #613 | Aprobado |
| Área con dos especies → dos líneas base | `test_dos_especies_persisten_dos_pares_recalibracion_conserva_historial` comprueba los dos pares persistidos y recuperados en PostgreSQL | Aprobado |
| Área con una especie → mismo comportamiento | `test_regresion_mono_usa_db06_sin_id_especie_en_infraestructura` y regresiones de RF-24 conservan un solo resultado y el contrato individual | Aprobado |
| No depender de la propiedad singular | La prueba unitaria elimina `id_especie` del área y verifica una, dos y tres especies desde `id_especies` | Aprobado |

La referencia de calendario (PR el miércoles 21; cierre el jueves 22 de octubre) pertenece a la planificación de la tarea. Los cambios y evidencias conservan su fecha real, 2026-10-23; no se retrofechan.

## Desvío identificado

| RF exige | Antes | Ahora |
|---|---|---|
| Obtener las especies por DB-06 | RF-24 utilizaba `area.id_especie`; DEV-22 devuelve `None` en áreas multiespecie | Lee `id_especies`, hidratado desde la puente oficial, sin elegir una especie arbitraria |
| Una identidad por área y especie | El flujo calculaba un solo resultado | Calcula, registra, publica y audita cada par |
| Compatibilidad monoespecie | Objeto individual en POST y consulta vigente | Conserva ese objeto cuando el área tiene una especie |
| Representar varias líneas | El contrato solo representaba un objeto | OpenAPI documenta unión con colección `total/items`; permite consulta por `especie_id` |
| Historial y líneas vigentes | El historial y la restricción de unicidad ya contemplaban el par | Se reutilizan; recalibrar no borra intentos anteriores |
| Transacción de la solicitud | El método de publicación confirmaba un resultado | Confirma todos los pares una vez; cualquier fallo de persistencia o auditoría revierte toda la publicación |
| Aislamiento de observaciones | Solo filtraba cámara y fechas | También filtra el área guardada en la observación, evitando muestras de otra ubicación de una cámara trasladada |

## Causa raíz

El caso de uso manual, el disparo automático, las precondiciones, la auditoría de rechazos y la consulta vigente dependían de la propiedad singular. La persistencia ya distinguía `(id_infraestructura, id_especie)`; el problema estaba en la selección y coordinación de los resultados, no en la falta de tablas de calibración.

DB-06 define `modulo9.infraestructuras_especies`, con FK a infraestructura y especie y unicidad del par. DEV-22 la expone como `Infraestructura.id_especies`. La propiedad singular se conserva en ese módulo como compatibilidad y no se utiliza como fuente de verdad en RF-24.

## Cambios implementados

### Composición, cálculo e historial

Se procesan los IDs distintos de la composición vigente, en orden estable. Una composición vacía conserva `VISION_NO_DISPONIBLE` (422). No se inventan asociaciones ni se recuperan especies de otras áreas. La puente no tiene estado ni fecha de finalización: su presencia actual corresponde a las filas existentes; `fecha_creacion` no es un historial de composición.

Se ejecuta el algoritmo RF-24 existente por cada par, conservando parámetros, etapas, ventana, calidad, origen del disparo y causa de fallo. Cada resultado tiene su registro, JSON de resultado, identificador, línea vigente y auditoría propios. No se alteraron las fórmulas, la calibración física, la ventana automática heredada de siete días ni la obligatoriedad de `modo_calibracion`.

Una recalibración crea nuevos intentos y reemplaza la línea vigente de cada par. Esta es la semántica heredada de repetición: no se añadió una clave nueva de idempotencia ni se promete reutilizar el ID de un intento anterior. La restricción única evita dos vigentes del mismo par.

### Semántica del dato de visión

**Contrato utilizado:** RF-56/M03 entrega vectores agregados por área/cámara/instante, sin `especie_id`. Cada par ejecuta el cálculo existente sobre ese contexto de visión y puede producir los mismos valores numéricos. Los resultados y su persistencia son independientes; no se toman valores de la línea de una especie para construir la de otra. DEV-24 exige dos líneas identificables para dos especies, no que sus valores deban ser distintos.

La atribución de individuos o de muestras a una especie queda fuera del alcance breve confirmado por el usuario. No se añadieron etiquetas, columnas ni parámetros al mensaje, y esa ampliación no se usa como impedimento para dar por verificados los criterios técnicos de DEV-24.

El usuario confirmó continuar según la tarea y los requerimientos suministrados. RF-20 v2.1 permite 1..N especies del mismo grupo. En RF-24, la nota RFC-012 v1.2 que propone una única línea POR ÁREA está pendiente de ratificación y no se implementó como regla vigente. Se conservó la llave por par de DEV-24/RF-24 v2.0. La nota de RF-20 aún indica pendiente de firma del Comité; no se presenta esta implementación como esa firma.

### Transacciones, concurrencia y fallos

Se calculan los resultados antes de publicarlos. Si los cálculos son exitosos, cada escritura y su auditoría participan de una sola transacción; un fallo al guardar, publicar o auditar el segundo par no deja publicado el primero.

Si el cálculo falla, se conserva el intento fallido de cada par afectado, con su estado, etapa y motivo; las líneas vigentes no cambian y la respuesta sigue siendo `LINEA_BASE_NO_CALCULADA` (422). La auditoría de rechazos conserva el mecanismo best-effort existente. No se introdujo éxito parcial.

El repositorio de calibración toma `pg_advisory_xact_lock` por área, con espacio de nombres RF24. Serializa los escritores RF-24 desde la primera publicación y se libera con commit/rollback. No requiere editar infraestructura. La prueba concurrente comprueba la espera mediante `pg_blocking_pids`, no mediante una pausa que suponga orden de ejecución. Se mantiene además el bloqueo de la fila vigente del repositorio existente.

Este bloqueo coordina calibraciones; no redefine la concurrencia ni agrega historial temporal a las modificaciones de composición de DEV-22/DB-06. La selección corresponde a la composición leída al iniciar la calibración.

### Seguridad

Se conservan JWT, RBAC del recurso `sensores`, estado de cuenta y alcance por finca. Productor recibe 403 al intentar calibrar; Ingeniero de Campo sin acceso a la finca recibe 404. El Ingeniero asignado calibra dos especies con el rol real `sgpmp_app`, incluso sin privilegio UPDATE sobre infraestructura.

La prueba detectó que `FOR UPDATE` sobre infraestructura exigiría su política de UPDATE, reservada al Administrador. Se descartó ese mecanismo y se utilizó el bloqueo transaccional del repositorio RF-24, sin cambiar políticas, propietarios, triggers o BYPASSRLS.

## Archivos modificados

Rutas relativas a `sgpmp-backend`; esta tabla describe únicamente DEV-24, no el commit base de DEV-22.

| Archivo | Cambio y justificación | Tarea |
|---|---|---|
| `src/configuration/application/use_cases/sensores/calibrar_vision_use_case.py` | Composición DB-06, cálculo manual/automático por par, publicación atómica, fallos y consulta múltiple | #3788 |
| `src/configuration/domain/repositories/calibracion_vision_repository.py` | Puerto para serializar calibraciones del área hasta finalizar la transacción | #3788 |
| `src/configuration/infrastructure/repositories/calibracion_vision_repository.py` | Bloqueo transaccional PostgreSQL sin permiso de edición de infraestructura | #3788 |
| `src/configuration/domain/repositories/observacion_vision_port.py` | Filtro opcional por área; compatible con otros consumidores | #3788 |
| `src/configuration/infrastructure/adapters/observacion_vision_m03_adapter.py` | Filtra observaciones de la ubicación solicitada | #3788 |
| `src/configuration/infrastructure/routers/calibracion_vision_router.py` | Unión de respuestas y selección explícita de especie; conserva autorizaciones | #3788 |
| `src/configuration/infrastructure/schema/calibracion_vision_schema.py` | Colección de líneas base vigentes | #3788 |
| `tests/configuration/test_inc_m09_78_g138_calibracion_vision.py` | Fixtures DB-06 y puerto ampliado conservando la regresión monoespecie | #3789 |
| `tests/configuration/test_inc_m09_75_g142_disparo_automatico_vision.py` | Compatibilidad de la consulta de observaciones del disparo automático | #3789 |
| `tests/configuration/test_dev24_vision_multiespecie.py` | Pares, repetición, fallos, consulta, aislamiento y contrato público | #3789 |
| `tests/integration/test_dev24_vision_multiespecie.py` | DB-06 y repositorios reales, HTTP/JWT/RBAC/RLS, rollback, historial y concurrencia | #3789 |

Todos los archivos de código creados/editados llevan tabla de seguimiento con fecha `2026-10-23`, autor `Leandro` leído de `git config user.name`, tarea y RF. Por instrucción posterior del usuario, los dos informes Markdown acompañan al código y las pruebas en un único commit. Los archivos temporales y las evidencias crudas de `.pytest_cache` permanecen locales.

## Migración y base de datos

DEV-24 no introduce migración ni duplica la puente. Utiliza:

| Objeto | Uso y garantías |
|---|---|
| `modulo9.infraestructuras_especies` | Puente oficial DB-06; FK a las dos entidades; unicidad del par; RLS y FORCE RLS |
| `modulo9.infraestructuras`, `especies` | Área, composición y contexto de manejo mediante el repositorio de DEV-22 |
| `modulo9.dispositivos_iot`, `tipos_dispositivo_iot` | Cámaras asociadas y activas; carga ORM de sensores/configuración remota |
| `modulo3.observaciones_vision` | Muestras de cámaras, ventana, área y calidad RF-62 |
| `modulo9.calibraciones_vision` | Historial inmutable; FK a área y especie; intentos fallidos con SQL NULL en resultado |
| `modulo9.lineas_base_vision` | Vigente por área/especie; FK al intento; unicidad del par |
| `modulo1.eventos` | Evidencia RF-10 individual por par |

Se conservaron las restricciones y los triggers existentes. PostgreSQL rechaza el DELETE del historial en la prueba de inmutabilidad.

La base aislada fue `sgpmp_dev24_test` en `127.0.0.1:55424`, PostgreSQL 18. Se aplicó la cadena Alembic hasta `e5a3c9b17d42` y, sin alterar sus fuentes, los upgrades exactos de:

- DB-06 / [PR #613](https://github.com/Arekkazu/sgpmp-backend/pull/613): `a0183109ae88`, commit `ca572ea628c41a629b80d116b8ee4a7c3223fbf0`.
- DB-07 / [PR #614](https://github.com/Arekkazu/sgpmp-backend/pull/614): `032b0b6db060`, commit `7fb4553fdf00375ee01afc9e6c3b4e1e962b3aa4`, requerido por `nivel_criticidad` del ORM base.

Las revisiones externas se ejecutaron con `MigrationContext/Operations` en transacciones separadas sobre la base local, no se copiaron a `alembic/versions` ni se creó una revisión merge ficticia. El sello Alembic del checkout sigue identificando su head; esta prueba no resuelve el grafo de despliegue de los PR dependientes.

Un clúster nuevo requiere provisionar roles y grants antes de las migraciones/requests. Se crearon roles locales NOLOGIN y se otorgaron únicamente los privilegios de lectura/escritura/secuencias necesarios en los esquemas y tablas usados por RF-24. `sgpmp_app` no es propietario, superusuario ni BYPASSRLS; no recibe UPDATE sobre infraestructura. No se desactivaron controles para obtener resultados aprobados. Los fallos iniciales de preparación se corrigieron en el entorno local, no con cambios a las migraciones ajenas.

## Contrato resultante

| Operación | Resultado |
|---|---|
| POST con un área monoespecie | 201 y el objeto `CalibracionVisionResponse` existente |
| POST con varias especies | 201 y `ListaCalibracionesVisionResponse {total, items}`; un resultado por par |
| GET historial `?area_id=...` | Lista de todos los intentos del área, incluidas especies anteriores y fallos |
| GET `/linea-base?area_id=...`, monoespecie | Objeto `LineaBaseVisionResponse` existente |
| GET `/linea-base?area_id=...`, multiespecie | `ListaLineasBaseVisionResponse {total, items}` de las vigentes existentes para especies actualmente asociadas |
| GET `/linea-base?area_id=...&especie_id=...` | Objeto individual del par solicitado; 404 si no está asociado o no tiene vigente |
| Sin líneas vigentes | 404 `LINEA_BASE_NO_ENCONTRADA` |
| Falta `modo_calibracion` | 400, conforme al manejador de validación existente |
| Sin JWT / sin permiso | 401 / 403 |

No se cambió silenciosamente el objeto monoespecie. Los consumidores que quieran operar con áreas multiespecie deben admitir la colección documentada. No se modificó el frontend dentro de esta tarea.

## Pruebas realizadas

**663 pruebas distintas aprobadas en las corridas finales: 0 fallidas y 0 omitidas.** Las corridas enfocadas/repetidas no se suman de nuevo.

| Grupo | Entorno | Aprobadas | Fallidas | Omitidas |
|---|---|---:|---:|---:|
| Suite `tests/configuration` | Unitarias, fakes y pruebas de contrato; incluye 14 nuevos casos parametrizados DEV-24, regresiones SENSOR, VISION y disparos M02 | 651 | 0 | 0 |
| `tests/integration/test_dev24_vision_multiespecie.py` | PostgreSQL 18 real, migraciones exactas DB-06/DB-07, JWT/RBAC y requests como `sgpmp_app` | 12 | 0 | 0 |

Las 12 pruebas PostgreSQL comprueban: dos pares e historial de recalibración, monoespecie, tres fallos en el segundo par (guardar/publicar/auditar), intentos fallidos sin reemplazar vigentes, aislamiento espacial de observaciones, respuesta HTTP/consulta/modo/JWT, rechazo del Productor y finca ajena, Ingeniero asignado, inmutabilidad/FORCE RLS y publicaciones concurrentes desde la primera inserción.

Evidencias locales ignoradas por Git:

- `.pytest_cache/dev24_regresion_final.xml` y `.log`: 651 aprobadas, 134.20 s.
- `.pytest_cache/dev24_pg/pruebas.xml` y `pruebas6.log`: 12 aprobadas, 24.95 s.
- `.pytest_cache/dev24_pg/dependencias.log`: aplicación de las dependencias exactas.
- `.pytest_cache/dev24_bd_oficial.json`: inspección oficial de solo lectura.
- `.pytest_cache/dev24_preparar_pg.py`, `dev24_dependencias_pg.py`, `dev24_grants_pg.py`: preparación local, fuera del código entregable.

Limitaciones: Windows requiere un shim de `fcntl` solo en el lanzador de pruebas para importar el SDK existente; no se alteró producción para ello. Se usaron temporales dentro de `.pytest_cache` y ejecución con sockets locales habilitados para TestClient/PostgreSQL. Aparece la advertencia heredada de Starlette sobre `httpx`; no hubo fallos ni omisiones finales. No se ejecutó toda la suite de los demás módulos, un broker real, cámaras físicas ni modelos IA reales. La prueba concurrente solo habilita datos confirmados en la base local desechable con ese nombre; las restantes revierten la transacción exterior.

Al terminar se detuvo el clúster local del puerto 55424 y se eliminaron exclusivamente sus datos desechables, verificando la ruta absoluta y el puerto antes de hacerlo. Se conservaron los scripts de preparación, las migraciones exactas extraídas y las evidencias de ejecución.

## Integración con `sgpmp_dev`

La inspección de `158.69.200.27:5447/sgpmp_dev` fue **READ ONLY**, con rollback, sin calibrar ni aplicar DDL/DML. El catálogo `pg_catalog`, consultado en todos los esquemas, no mostró la puente DB-06 ni equivalente. Infraestructura conserva `id_especie/capacidad_maxima` y no tiene `nivel_criticidad`. M03 no tiene atribución de especie en las observaciones. La lectura de `alembic_version` fue denegada (42501); no se inventa una revisión desplegada.

No se presenta la prueba local como integración ya desplegada en la base oficial.

## Dependencias y pendientes

| Dependencia | Verificación y pendiente |
|---|---|
| DB-06 / #613 | Relación real probada localmente. PR consultado abierto y sin merge; su autor recomienda retirarlo. El comentario no deroga por sí solo los RF suministrados por el usuario. Falta resolución/integración de despliegue |
| DEV-22 / #619 | Base de código utilizada: `851db2ba5950fd2cef550b707951c0fbe96a1572`. Aporta ORM/entidad/repositorio N:M; no está incorporada a `origin/dev` consultado |
| DB-07 / #614 | Migración exacta probada localmente; falta integrar el campo requerido por el ORM de DEV-22 |
| RFC-012 / RF-20 | Se siguió el requisito 1..N del mismo grupo que el usuario indicó. La firma de Comité citada como pendiente no se suple con código |
| RF-24 | Se mantiene v2.0 por par. La propuesta v1.2 de llave por área sigue pendiente; necesita conciliación antes de aprobar un contrato distinto |
| M09 | Flujo manual, consultas, persistencia, seguridad y regresiones probados; QA funcional pendiente |
| M02 | Los ganchos de alta/cierre y el disparo automático conservan sus regresiones. No se afirma haber validado todo M02 con DB-06 |
| DEV-28 / RF-62 | Se consume `es_apto_para_ia` existente. No se reimplementa calidad ni se afirma conformidad completa con otro contrato de visión |
| Dato de visión | Se mantiene el contrato agregado por área. Clasificar individuos o segregar muestras por especie no es un requisito adicional de DEV-24 ni una dependencia para verificar los casos 2→2 y 1→1 |
| Grafo Alembic | #613, #614 y #615 parten de la misma revisión; integrar los PR exige resolver las heads y la provisión de roles, sin modificar aquí migraciones ajenas |
| Consumidores HTTP | Monoespecie compatible; colección multiespecie publicada explícitamente, pendiente de adopción/QA por los consumidores |

Referencias de la discusión: [observaciones técnicas de #613](https://github.com/Arekkazu/sgpmp-backend/pull/613#issuecomment-6307392134), [recomendación de retiro](https://github.com/Arekkazu/sgpmp-backend/pull/613#issuecomment-6330772835). Las 23 fallas de integración mencionadas por terceros en esa discusión no son pruebas ejecutadas por esta entrega.

Los criterios técnicos de #3788/#3789 están verificados localmente conforme a la ficha de DEV-24. No se modifican los estados de #3788, #3789 ni #3697 en el gestor; siguen pendientes la integración oficial y QA. El código y las pruebas quedan listos para revisión.

## Alcance del commit y revisión contra `dev`

La entrega autorizada consiste en un único commit de DEV-24 con código, pruebas y ambos informes, publicado en `fix/dev24-calibracion-vision-multiespecie`. La rama está basada en DEV-22 `851db2ba` (un commit sobre `origin/dev` `6113a3883f7ca3a9b2991148414451323f6f9a81`). Un futuro PR hacia `dev` debe declarar la dependencia de #619 o esperar su integración para evitar atribuir sus 24 archivos a DEV-24. El PR no se ha creado.

El cambio propio comprende siete archivos de producción, cuatro de pruebas y dos informes Markdown. Se preservaron los archivos locales ajenos a la tarea, las evidencias crudas y la rama anterior de DEV-47. `git diff --check` no detectó problemas de espacios.
