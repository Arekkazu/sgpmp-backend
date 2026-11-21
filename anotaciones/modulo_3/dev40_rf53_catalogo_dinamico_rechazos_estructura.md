# DEV-40 — RF-53: catálogo dinámico M09 y rechazos de estructura

Fecha: 2026-10-21. Responsable: Leandro Estiven Ramirez.
Historia #3695, épica #3667. Subtareas #3783 y #3784.
Rama: `fix/dev40-catalogo-m09-rechazos-estructura`.
Base: `origin/dev`, `6113a388`. No incluye los cambios independientes de DEV-49.

## 1. Diagnóstico y contraste funcional

Se revisaron RF-53 de `Requerimientos_M03_RF53-RF63.md`, RF-17 de
`Requerimientos_M09_RF15-RF32.md` y G-06/G-08 de los documentos de reparto.
RF-53 define identificadores públicos de variables, categorías AMBIENTAL/ANIMAL/
HIDRICA y valor escalar decimal. Exige consulta dinámica del catálogo. RF-17
reserva la gestión del catálogo al sistema; no se agrega un CRUD para usuarios.

Hechos confirmados antes de modificar el flujo:

| Componente | Estado anterior | Causa / corrección |
|---|---|---|
| Entidad `telemetria.py` | `CATALOGO_I3P1` contenía IDs, categorías y unidades | Se retira la constante; el dominio no consulta SQL |
| Ingesta escalar | Traducía `tipo_variable` a ID con el diccionario | Se inyecta el puerto de catálogo existente |
| Adaptador M09 | Usaba el mismo diccionario y solo consultaba rangos | Ahora lee todos los metadatos desde M09 |
| Catálogo persistido | Nombre, unidad, rangos, activo y criticidad | Faltaban código público y categoría requeridos por RF-53 |
| Pydantic | Valida antes del endpoint/caso de uso | La excepción no llegaba a la escritura de bitácora |
| Handler compartido | Ya devuelve 400 `VAL_ENTRADA` | Se reutiliza sin modificarlo globalmente |
| Bitácora | FK a sensor/dispositivo/telemetría y enums propios | Se conservan referencias solo cuando existen |
| Ingesta B+ | PostgreSQL valida unidad, rangos, tiempo y duplicados | Se conserva como única regla para esas validaciones |

La consulta oficial de solo lectura a `sgpmp_dev` del 2026-10-21, con
`transaction_read_only=on`, confirmó que el esquema no tiene código/categoría.
Se consultó `pg_catalog`, no solo el modelo ORM. La evidencia saneada está en
`.pytest_cache/dev40_bd_oficial.json`; no contiene credenciales.

Las únicas dependencias ejecutables de `CATALOGO_I3P1` eran la ingesta y el
adaptador M09. El adaptador anterior no estaba conectado a la ingesta B+.
Los rangos legados ajenos a esta resolución y las reglas de calidad RF-62 no se
refactorizaron como parte de DEV-40.

## 2. Archivos modificados

| Ruta | Cambio / justificación | Tarea |
|---|---|---|
| `src/telemetry/domain/entities/telemetria.py` | Elimina `CATALOGO_I3P1`; conserva las entidades sin acceso a infraestructura | #3783 |
| `src/telemetry/domain/repositories/variable_catalogo_port.py` | Define lectura de metadatos, separada de validación de mediciones | #3783 |
| `src/telemetry/infrastructure/adapters/variable_catalogo_m09_adapter.py` | Consulta M09 sin caché ni IDs fijos; detecta catálogo ambiguo/incompleto | #3783 |
| `src/telemetry/application/use_cases/ingesta/ingerir_telemetria_use_case.py` | Usa catálogo; comprueba referencia/categoría y conserva pipeline SQL | #3783 |
| `src/telemetry/infrastructure/dto/ingerir_telemetria_dto.py` | Valida categoría reconocida y añade referencia opcional `id_variable` | #3783 |
| `src/configuration/infrastructure/models/variable_ambiental_model.py` | Mapea las dos columnas y sus restricciones; no cambia respuestas públicas M09 | #3783 |
| `alembic/versions/f40c53a37834_dev40_rf53_catalogo_dinamico.py` | Persiste metadatos que el esquema no tenía y conserva compatibilidad histórica | #3783 |
| `src/telemetry/infrastructure/routers/telemetria_router.py` | Inyecta catálogo real y ruta auditada | Ambas |
| `src/telemetry/infrastructure/routers/ruta_ingesta_auditada.py` | Captura validación estructural en las dos rutas escalares; sanea contexto y abre sesión independiente | #3784 |
| `src/telemetry/application/use_cases/ingesta/registrar_rechazo_estructura_use_case.py` | Confirma o revierte exclusivamente la bitácora del rechazo | #3784 |
| `src/telemetry/infrastructure/repositories/bitacora_ingest_repository.py` | Evita que referencias inválidas del body impidan escribir por FK | #3784 |
| `tests/telemetry/test_dev40_catalogo_rechazos.py` | 22 casos aislados de catálogo, HTTP, privacidad, rollback y fallos | Ambas |
| `tests/integration/test_dev40_catalogo_rechazos.py` | 18 casos con PostgreSQL y rutas reales, más fallo real de conexión controlado | Ambas |
| `tests/telemetry/test_dev05_ingesta_bplus.py` | Inyecta explícitamente el doble del nuevo puerto; conserva sus 16 verificaciones | #3783 |
| `anotaciones/modulo_3/dev40_rf53_catalogo_dinamico_rechazos_estructura.md` | Diagnóstico, evidencia, despliegue y propuesta de PR | #3695 |

Los 14 Python creados/editados llevan una sola fila DEV-40 RF-53 por archivo,
fecha real y `Leandro`, obtenido de `git config user.name`.

## 3. Implementación del catálogo — #3783

`VariableCatalogoM09Adapter` implementa el puerto existente. Consulta columnas
de las filas activas en cada operación; no usa caché ni identity-map para resolver
metadatos. Se aceptan el código persistido o el nombre normalizado (mayúsculas,
sin tildes y separadores convertidos a `_`). No hay otro diccionario en ejecución.

La ingesta recibe el ID real de la fila, su categoría y unidad/rangos oficiales.
La validación de unidad y rangos sigue en `fn_ingesta_telemetria`, sin duplicarla
en Python ni habilitar conversiones de unidad que el pipeline no tenía.

Se preservan los nombres anteriores, incluidos `TEMP_CORPORAL`/
`TEMPERATURA_CORPORAL`, `ACTIVIDAD`/`ACTIVIDAD_MOVIMIENTO` y
`TDS`/`CONDUCTIVIDAD_ELECTRICA`: código y nombre proceden de la misma fila.
No se necesita una tabla ni una columna adicional de alias.

`tipo_variable` sigue siendo obligatorio. `id_variable` es opcional; si se envía,
debe corresponder al tipo resuelto. `categoria_variable` continúa siendo opcional
en el sobre: el backend obtiene su valor oficial de M09 y comprueba que coincida
cuando el cliente lo proporciona. Una categoría reconocida pero incompatible es
un rechazo funcional; una categoría fuera del enum es un error de estructura.

El tipo primitivo de `valor` continúa siendo `Decimal`, validado por Pydantic.
M09 no contiene una columna de tipo primitivo: no se inventó una. CRUDO/AGREGADO
mantienen el contrato previo de `valor_agregado`.

| Situación | Respuesta / tratamiento |
|---|---|
| Variable inexistente o inactiva | 404 `VARIABLE_NO_ENCONTRADA`; sin telemetría |
| ID o categoría incompatible con la variable | 400 `VARIABLE_INCOMPATIBLE`; sin telemetría |
| Unidad incompatible | 400 `ERROR_UNIDAD`, generado y auditado por SQL |
| Código/nombre ambiguo | 503 `CATALOGO_AMBIGUO`; no elige una fila arbitrariamente |
| Categoría sin configurar | 503 `CATALOGO_INCOMPLETO`; no infiere una categoría |
| Error de conectividad | 503 `BD_NO_DISPONIBLE` mediante el traductor existente |
| Otros errores de persistencia | Conservan el error de infraestructura correspondiente |

Los rechazos de referencia/categoría usan la clasificación existente
`ERROR_SENSOR` en bitácora, con `codigo_rechazo` en JSON para distinguirlos.
No se agregan estados de calidad ni se clasifican como `ERROR_ESTRUCTURA`.

## 4. Bitácora de estructura — #3784

Rutas reales afectadas:

```http
POST /iot/telemetria
POST /iot/telemetria/batch
```

`RutaIngestaAuditada` captura `RequestValidationError` antes del endpoint y llama
al handler existente para conservar 400, `VAL_ENTRADA`, `fields` y `timestamp`.
Solo registra errores del body de esas dos rutas. No modifica el handler
global, la autenticación del broker, la ruta de visión ni otros módulos.

La sesión de bitácora es nueva, usa la identidad de servicio existente y no
confirma la transacción de ingesta. La evidencia persiste aunque el request
revierta su sesión. La validación completa del lote ocurre antes de procesar
sus elementos: un lote estructuralmente inválido no persiste ni sus filas válidas.

Correspondencia con el esquema real:

- `estado_calidad = ERROR_ESTRUCTURA`.
- `tipo_evento = ERROR_PROCESAMIENTO`: el enum de esta columna no incluye
  ERROR_ESTRUCTURA; se utiliza la clasificación oficial de la columna anterior.
- `fecha_evento`: fecha/hora UTC del rechazo.
- `descripcion_text`: descripción fija de la operación rechazada.
- `payload_recibido`: endpoint, operación, resultado RECHAZADO, correlación UUID,
  tipos de error, nombres de campos conocidos e índices del lote.
- `id_sensor` e `id_dispositivo_iot`: solo referencias existentes y visibles en
  la sesión independiente. Los IDs recibidos estrictamente enteros y positivos
  permanecen en el JSON saneado aunque no existan.
- `id_telemetria`: NULL.

No se copian body completo, serial, access_key, checksum, idempotency_key, headers,
tokens, `input`, `msg` ni `ctx` de los errores. Los nombres de campos desconocidos
se sustituyen por una etiqueta fija. Se limitan errores a 50 y referencias de
lote a 20; la cantidad total recibida queda registrada. La correlación de entrada
solo se conserva si es UUID válido; en otro caso se genera un UUID técnico.

Se produce un evento por intento HTTP rechazado. Reintentos HTTP distintos pueden
producir eventos distintos aunque compartan correlación; no hay doble escritura
del mismo rechazo desde varias capas. La correlación no es una nueva clave de
idempotencia de ingesta.

## 5. Base de datos y migración necesaria

Revisión `f40c53a37834`, padre `e5a3c9b17d42`, head único en esta rama.

La ampliación mínima de `modulo9.variables_ambientales` agrega:

| Columna | Tipo | Propósito |
|---|---|---|
| `codigo_telemetria` | VARCHAR(40), nullable, UNIQUE y CHECK de formato | Nombre público de RF-53 y compatibilidad con códigos anteriores |
| `categoria_variable` | VARCHAR(20), nullable, CHECK de las tres categorías | Fuente persistida de la clasificación obligatoria de telemetría |

No se crean tablas duplicadas ni columnas en `bitacora_ingest`. La migración
completa solo los dos metadatos nuevos de las once variables ya utilizadas por
el catálogo anterior, identificándolas por sus nombres verificados, sin asumir
sus IDs. Esa fotografía de inicialización está confinada a la migración; no es
una lista de variables permitidas durante la ejecución.

No cambia nombres, unidades, rangos, IDs, activo ni criticidad existentes, ni
crea variables. El test de reversibilidad compara esas definiciones antes y
después. El downgrade elimina únicamente las dos columnas y sus restricciones.

Una variable nueva se registra por el mecanismo administrativo autorizado de
M09, con categoría y unidad/rangos válidos. El código es opcional si se usa su
nombre normalizado. La ingesta no crea ni completa variables automáticamente.
Si una instalación renombró variables antes de la migración, debe configurar
sus nuevos metadatos explícitamente: no se infiere ni se sobrescribe su definición.

Se aplicaron todas las migraciones desde cero en PostgreSQL 18 local desechable,
se probó downgrade/upgrade de DEV-40 y se generó SQL offline UTF-8. La base oficial
se consultó exclusivamente en modo de solo lectura. **La nueva migración debe
desplegarse junto con el código; no está aplicada en bases compartidas.**
El clúster desechable se detuvo y eliminó al terminar; los reportes locales de
pruebas y la evidencia de verificación se conservaron.

## 6. Pruebas ejecutadas

| Ejecución | Resultado | Evidencia local |
|---|---|---|
| Telemetría disponible en Windows | 215 aprobadas: 193 previas y 22 nuevas DEV-40 | `.pytest_cache/dev40_telemetry.xml` |
| DEV-40 PostgreSQL final | 18 aprobadas | `.pytest_cache/dev40_postgresql_final.xml` |
| Regresión PostgreSQL | 85 aprobadas | `.pytest_cache/dev40_postgresql.xml`, excluyendo sus 16 casos DEV-40 repetidos |
| Migraciones desde cero y reversibilidad | Correctas en base aislada | `.pytest_cache/dev40_migrations.log` y test de migración |
| SQL offline | Correcto, sin conexión ni aplicación a DEV | `.pytest_cache/dev40_migracion_offline.sql` |
| Sintaxis y seguimiento | 14 Python correctos | AST y comprobación de cabeceras ejecutados |
| Diff | Correcto | `git diff --check` |
| Bandit, severidad media/alta | 0 hallazgos | `.pytest_cache/dev40_bandit.txt` |
| Bandit completo | 1 B110 bajo preexistente en `registrar_exito` | `.pytest_cache/dev40_bandit_completo.json` |

**Total sin contar repeticiones: 318 pruebas distintas aprobadas, 0 fallidas y
0 omitidas por pytest en las ejecuciones finales.** Son 22 pruebas nuevas
aisladas/HTTP y 18 nuevas PostgreSQL. El ensayo dirigido inicial de 37 pruebas
se solapa con telemetría; no se suma. Las 16 DEV-40 de la ejecución conjunta
de 101 se sustituyen por las 18 de la última ejecución; no se suman dos veces.

La primera ejecución PostgreSQL detectó un fallo real: la bitácora no se
confirmaba con IDs que no existían en su transacción independiente. Se corrigió
la resolución de FK y se verificaron IDs inexistentes y referencias confirmadas.
Ese fallo inicial no se oculta ni se cuenta como una prueba final aprobada sin
su reevaluación.

| Escenarios obligatorios | Evidencia de comportamiento |
|---|---|
| TC-01 / TC-13 | Lectura con catálogo existente conserva ingesta HTTP y persistencia SQL |
| TC-02 / TC-17 | Inserción de nueva variable y reconocimiento por el mismo adaptador, sin reiniciar |
| TC-03 / TC-04 | Referencia inexistente y categoría/ID incompatibles: error controlado sin telemetría |
| TC-05 | Unidad incorrecta: ERROR_UNIDAD del pipeline SQL, sin falso ERROR_ESTRUCTURA |
| TC-06 / TC-15 | Fallo real del driver contra conexión local no disponible: HTTP 503; sin bitácora estructural |
| TC-07 / TC-08 | Body individual inválido: 400 y una fila persistida ERROR_ESTRUCTURA |
| TC-09 / TC-10 | Lote inválido: 400 y una fila persistida ERROR_ESTRUCTURA |
| TC-11 / TC-12 | Ninguna lectura nueva; bitácora visible desde otra conexión después del rollback |
| TC-14 | Errores funcionales conservan su clasificación |
| TC-16 | Un registro por intento; reconfirmación de la deduplicación de lecturas en batch |
| TC-18 | DEV-05, DEV-04, DEV-17, RF-62, visión y catálogo RF-17 aprobados |

La prueba de indisponibilidad inyecta la conexión del adaptador a un puerto
local no disponible; conserva router, caso de uso, SQLAlchemy, psycopg2 y handler
reales. No simula una caída de la base oficial. Los tests aislados con dobles de
puertos no se presentan como integración real.

Regresiones PostgreSQL: DEV-05 (32), DEV-04 (8), DEV-17 (16), RF-62 (12),
DEV-07 visión (15) y RF-17 catálogo (2): 85 pruebas distintas.

### Comandos principales

```powershell
& .venv/Scripts/python.exe -m pytest --confcutdir=tests/telemetry tests/telemetry `
  --ignore=tests/telemetry/test_dev06_token_servicio_broker.py `
  --ignore=tests/telemetry/test_dev11_eventos_buffer.py `
  --ignore=tests/telemetry/test_inc_m09_77_g137_observaciones_vision.py `
  -q --tb=short --junitxml=.pytest_cache/dev40_telemetry.xml

# Exclusivamente PostgreSQL local desechable:
$env:DATABASE_URL = 'postgresql+psycopg2://postgres@127.0.0.1:55440/sgpmp_dev40_test'
$env:ALEMBIC_DATABASE_URL = $env:DATABASE_URL
$env:TEST_DATABASE_URL = $env:DATABASE_URL
& .venv/Scripts/python.exe -X utf8 -m alembic upgrade head
& .venv/Scripts/python.exe -m pytest --confcutdir=tests/integration `
  tests/integration/test_dev40_catalogo_rechazos.py `
  tests/integration/test_dev05_ingesta_bplus_postcommit.py `
  tests/integration/test_dev04_sqlstate.py `
  tests/integration/test_rf56_dev17_paquetes_pendientes.py `
  tests/integration/test_rf62_dev02_aptitud_telemetria.py `
  tests/integration/test_dev07_vision_d4.py `
  tests/integration/test_rf17_variables_ambientales.py `
  -q -rs --tb=short --junitxml=.pytest_cache/dev40_postgresql.xml

# Reevaluación final de DEV-40 con dos escenarios adicionales:
& .venv/Scripts/python.exe -m pytest --confcutdir=tests/integration `
  tests/integration/test_dev40_catalogo_rechazos.py `
  -q -rs --tb=short --junitxml=.pytest_cache/dev40_postgresql_final.xml
& .venv/Scripts/python.exe -X utf8 -m alembic upgrade e5a3c9b17d42:head --sql
git diff --check
```

## 7. Limitaciones y pendientes de despliegue

- Completar QA en el entorno desplegado con la revisión Alembic y los permisos
  del rol PostgreSQL de aplicación. Las pruebas locales usan conexión administrativa;
  la sesión de auditoría sí declara la identidad de servicio existente.
- Ejecutar los tres módulos excluidos y la suite general en Linux: importan
  `main.py` y la dependencia preexistente `fcntl` de M02 impide la colección en
  Windows. No se modificaron ni se contabilizan como aprobados.
- Semgrep y Bearer no se ejecutaron localmente; permanecen en el pipeline.
- Bandit detecta el `except/pass` preexistente de `registrar_exito`; la nueva
  auditoría de rechazos registra advertencias ante fallos. No se amplió el alcance
  para cambiar el camino antiguo de éxitos.
- Si la base de bitácora está caída, se conserva el 400 y se emite warning conforme
  al patrón best-effort existente. No se promete persistencia durable durante una
  caída de BD ni se crea un nuevo buffer de auditoría.
- La instalación inicial sin elevación no pudo inicializar WAL por restricciones
  del sandbox; se utilizó una instancia local aislada fuera de ese sandbox.
  Las pruebas HTTP también se ejecutaron fuera de las restricciones que bloqueaban
  TestClient. No se modificaron sus aserciones para resolver esas limitaciones.
- G-06 menciona también checksum, pero el reparto DEV-40 y las subtareas #3783/
  #3784 asignan catálogo y bitácora estructural. No se inventó un algoritmo ni se
  afirma haber implementado la validación de checksum.

## 8. Estado final y propuesta de PR

| Tarea | Estado de implementación |
|---|---|
| #3783 — Catálogo leído desde M09 | Implementada y probada; requiere desplegar la migración incluida |
| #3784 — Rechazos estructurales en bitácora | Implementada y probada en PostgreSQL |
| #3695 | Desarrollo listo para revisión; cierre funcional sujeto a despliegue y QA |

Los archivos previos de pendientes y AGENTS.md
permanecen fuera de DEV-40. La base oficial no recibió escrituras.

Título propuesto:

`fix(rf53): consultar catálogo dinámico M09 y auditar rechazos estructurales (DEV-40)`

Descripción:

```markdown
# RF-53 — DEV-40: Catálogo dinámico M09 y bitácora de rechazos estructurales

## Desvío identificado

La ingesta dependía de IDs/categorías de CATALOGO_I3P1 y los rechazos de Pydantic
no llegaban al caso de uso que escribe bitacora_ingest.

Refs: #3695, #3783 y #3784.

## Causa raíz

El catálogo persistido no tenía código público ni categoría. El adaptador M09
todavía dependía del diccionario y no estaba conectado a la ingesta B+.
La validación estructural ocurría antes del endpoint.

## Cambios

- Retira CATALOGO_I3P1 y conecta el puerto existente a metadatos reales de M09.
- Valida referencias y categorías sin aceptar IDs inexistentes ni inferir categorías.
- Conserva unidad/rango/calibración y deduplicación en el pipeline PostgreSQL.
- Registra ERROR_ESTRUCTURA para POST individual y batch en una sesión independiente.
- Conserva 400 VAL_ENTRADA y registra solo contexto saneado, sin credenciales/body completo.
- Evita fallos de FK al registrar IDs de payloads inválidos.

## Migración

f40c53a37834, sobre e5a3c9b17d42: agrega codigo_telemetria y categoria_variable
en variables_ambientales. Inicializa únicamente esos nuevos metadatos para
compatibilidad; conserva las definiciones físicas y no crea variables.
Debe desplegarse con el código. No se aplicó en bases compartidas.

## Pruebas

318 pruebas distintas aprobadas: 215 telemetría y 103 PostgreSQL, incluyendo
40 casos nuevos DEV-40. Migración desde cero y downgrade/upgrade verificados.
Nueva variable y cambios de metadatos reconocidos sin reiniciar; rechazos
persistidos después del rollback; ninguna telemetría derivada de body inválido.
Bandit: cero hallazgos medios/altos; un B110 bajo preexistente documentado.

## Dependencias y pendientes

Desplegar la migración y validar en QA con el rol de aplicación. Tres módulos y
la regresión general requieren Linux/fcntl. Semgrep/Bearer quedan para CI.
La auditoría conserva el patrón best-effort existente ante caída de BD.
```
