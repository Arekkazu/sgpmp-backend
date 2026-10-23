# RF-53/62 DEV-28 — Sobre D4, calidad ponderada y ventanas sin detección

Historia **#3701** · Tareas **#3798, #3799 y #3800** · Fecha **2026-10-22**.

**Estado: implementación parcial verificable; no cerrar #3701.** El DTO normativo, el oráculo ponderado, la configuración persistente y el diagnóstico post-commit están implementados. La persistencia del sobre normativo y la sustitución productiva del cálculo legado dependen de DB-09 y de las decisiones detalladas al final. No se ejecutaron escrituras en la base oficial.

## 1. Desvío identificado

| Componente | Antes | Resultado implementado y límite |
|---|---|---|
| Sobre D4 | Rechazaba los campos nuevos por `extra=forbid` | DTO normativo publica y exige `tipo_dato`, `n_individuos_observados` y `origen`; no permite extras ni decisiones de aptitud del cliente |
| Persistencia | Solo esquema DB-03 y catálogos antiguos | Legado conservado; sobre normativo responde `503 CONTRATO_VISION_PENDIENTE` después de comprobar identidad y área, sin guardar ni descartar campos |
| Índice | Fórmula heredada, sin la política ponderada vigente | Oráculo RF-62 con pesos persistidos y contexto decimal propio; todavía no sustituye el cálculo productivo legado |
| Modificadores | Estados SQL `CALIBRADA/DEGRADADA/SIN_DETECCION` | Oráculo acepta `CALIBRADO/EN_CALIBRACION/SIN_LINEA_BASE`; no inventa equivalencias históricas |
| Clasificación | `APTO/APTO_CON_RESERVA/NO_APTO` | Oráculo devuelve `OPTIMA/DEGRADADA/NO_APTA` usando umbrales configurados; falta persistencia DB-09 |
| Flags | Sin columnas DB-09 para flags y confianza | Resultado de cálculo incluye los cuatro flags documentados, snapshot y confianza; no se afirma su persistencia |
| Aptitud | Visión excluida de NIC41 | Se conserva `apto_para_nic41=false`; `SIN_LINEA_BASE` fuerza `NO_APTA` en el oráculo |
| Ventanas | Sin etapa DEV-05 para secuencias de visión | Etapa productiva `VISION_DETECCION`, diagnóstico RF-63 persistido e idempotente, sin insertar alertas de dispositivo |

## 2. Diagnóstico y evidencia de la base oficial

Se revisaron el DTO, la ingesta, el repositorio de observaciones, el worker DEV-05, la auditoría RF-63, DEV-14, los parámetros de DEV-27 y las migraciones del repositorio.

La conexión correcta fue **158.69.200.27:5447 / sgpmp_dev**, usuario **member_dev**. Las consultas se ejecutaron en una transacción **READ ONLY**. El servidor confirmó `current_database()=sgpmp_dev` y el usuario indicado. Su dirección y puerto internos son diferentes del acceso externo; no se utilizó localhost para esta comprobación.

Resultado confirmado en `information_schema` y catálogos PostgreSQL:

| Elemento de `modulo3.observaciones_vision` | Estado observado |
|---|---|
| `fecha_inicio_ventana`, `json_version_cascada` | Presentes: DB-03 sí está aplicada |
| `n_individuos_observados`, `origen` | Ausentes |
| `json_flags_detectados`, `es_confianza_baja` | Ausentes |
| `tipo_dato` | Ausente; se necesita confirmar si será discriminador persistido o constante derivada de esta tabla |
| `indice_calidad` | `SMALLINT NOT NULL`; no conserva resultados como `91.6` |
| `cantidad_tracks` | `INTEGER NOT NULL`; incompatible con omitir `n_tracks` sin resolver P-5 |
| Estado de calibración | CHECK con `CALIBRADA`, `DEGRADADA`, `SIN_DETECCION` |
| Clasificación | CHECK con `APTO`, `APTO_CON_RESERVA`, `NO_APTO` |
| Deduplicación | UNIQUE por cámara y fecha; no permite distinguir `origen` según el contrato normativo |

No se encontró una migración DB-09 en la rama ni en las referencias remotas examinadas. La lectura del catálogo oficial de parámetros no encontró los pesos ni las claves de detección de DEV-27 sembradas; la coincidencia existente era `ventana_retroalimentacion_dias=90`. No se deduce una revisión Alembic aplicada: la consulta de `public.alembic_version` no permitió verificarla.

La causa del bloqueo no es DB-03: el esquema oficial sigue siendo anterior al contrato DB-09. No se crearon columnas paralelas ni se adaptaron pruebas mediante un esquema ficticio que ocultara esa diferencia.

## 3. Fuentes funcionales y discrepancias

Se utilizaron `Especificacion-Requerimientos-Modulo3.md` —RF-53, RF-60 y RF-62, incluida la integración de AIOT-SPEC-01 del 2026-10-16—, el prompt DEV-28 y los documentos `DEV-Reparto_Tareas_RFC012-016_y_Gaps.md` / `DEV-Tareas_RFC012-016_y_gaps_M03_M04_M09.md`.

Decisiones aplicadas:

- `n_individuos_observados` es obligatorio, entero estricto y admite cero. No se deriva de `n_tracks`. El DTO normativo permite transportar `n_tracks` si llega, sin convertirlo en obligatorio mientras P-5 permanece sin resolver; no puede persistirse todavía bajo el esquema actual.
- El literal `VECTOR_COMPORTAMIENTO` tiene **21 caracteres**, aunque la tabla de la ficha indica `varchar(20)`. Se conserva el literal funcional completo y se documenta la discrepancia para el contrato físico; no se trunca.
- No se traduce `CALIBRADA` a `CALIBRADO`, ni clases antiguas a nuevas, sin una migración oficial que defina la transición de datos históricos.
- RF-62 exige evaluación asíncrona. El cálculo legado sigue siendo el del contrato anterior; el nuevo oráculo no se conecta a una ingesta síncrona para simular que se completó el cambio.
- RF-62 aún menciona procedencia de calibración por `(area_id, especie_id)`, pero la aclaración posterior RFC-012 v1.2 del 2026-10-19 establece la línea base del área y visión agregada agnóstica de especie. Se toma esa aclaración como referencia vigente: no se crea una especie ficticia. Falta conectar el estado normativo con la fuente RF-24 y su persistencia, sin inventar equivalencias con los estados SQL anteriores.
- El sobre aporta cobertura redondeada, no el conteo original de `frames_procesados`. El oráculo conserva ese dato como `null`, calcula `frames_esperados` con FPS y duración y no reconstruye un conteo supuestamente exacto multiplicando la cobertura redondeada.
- `tracking_inestable` se activa al alcanzar o superar la tolerancia, cuando se agota el factor de continuidad de la fórmula. `fps_insuficiente` compara contra FPS configurado y `cobertura_baja` usa el mínimo persistido de DEV-27. Se documenta esta interpretación para revisión funcional, sin introducir otro umbral.

## 4. Implementación

### 4.1. DTO y compatibilidad (#3798)

El endpoint `POST /iot/telemetria/vision` publica tres alternativas explícitas: sobre D4 normativo, sobre D4 legado y lote legado. Mantiene token de servicio, resolución de cámara por serial y asociación con área. El serial por sí solo no autentica.

El DTO normativo mantiene aliases no ambiguos, ventanas con zona horaria y orden temporal, componentes y versiones estructurados. Exige los tres metadatos nuevos, rechaza decisiones de aptitud enviadas por el cliente y mantiene `extra='forbid'`.

Un sobre normativo estructuralmente válido llega al caso de uso. La falta comprobada de persistencia DB-09 se informa con HTTP 503; no se convierte a un DTO antiguo que pierda campos. Un sobre normativo incompleto devuelve HTTP 400. El legado conserva su HTTP 201, persistencia, deduplicación y consumo RF-24.

### 4.2. Oráculo ponderado y política (#3799)

```text
I = 100 × (w1 × cobertura
         + w2 × min(1, fps_efectivo / fps_configurado)
         + w3 × (1 − min(1, n_tracks_perdidos / tracks_perdidos_tolerables)))
indice_final = I × factor_calibracion
```

`CALIBRADO` aplica 1; `EN_CALIBRACION`, el factor configurado; `SIN_LINEA_BASE`, 0 y prohibición explícita de aptitud incluso si el umbral inferior se configura en cero. El oráculo usa `Decimal`, precisión aritmética 28 y contexto local con `ROUND_HALF_EVEN`; no cuantiza el índice a entero ni define así la precisión de persistencia pendiente.

Los tramos usan `>= umbral_optima`, `>= umbral_degradada` y el tramo inferior. Con valores de referencia 80/40, `79.99` sigue siendo degradada y `80` es óptima. Solo degradada marca confianza baja. NIC41 permanece falso.

El resultado conserva los cuatro flags y los parámetros efectivos, estado, factor y duración utilizados. Esa trazabilidad está disponible como resultado de aplicación; **su almacenamiento y consulta posterior siguen bloqueados**.

### 4.3. Parámetros persistidos DEV-14 / DEV-27

| Clave | Valor de siembra D | Validación |
|---|---:|---|
| `w1` | 0.40 | 0–1; suma exacta de los tres pesos igual a 1 |
| `w2` | 0.35 | 0–1 |
| `w3` | 0.25 | 0–1 |
| `tracks_perdidos_tolerables` | 5 | Entero 1–50 |
| `umbral_optima` | 80 | 0–100, mayor que el degradado |
| `umbral_degradada` | 40 | 0–100 |
| `factor_en_calibracion` | 0.70 | 0–1; clave técnica DEV-14 para el factor D documentado |
| `ventanas_consecutivas_sin_deteccion` | Reutiliza DEV-27 | Entero 1–20 |
| `cobertura_minima_deteccion_valida` | Reutiliza DEV-27 | 0.05–0.90 |
| `duracion_ventana_observacion` | Reutiliza DEV-27 | Entero 10–300 s |

Los defaults D solo se usan al solicitar una siembra explícita. Los lectores no recurren a ellos cuando falta configuración. El adaptador recupera la política completa en una consulta, sin caché local. FPS procede de la configuración RF-23 que debe entregar el llamador, con validación de entero positivo y sin divisor de sustitución.

El caso de uso administrativo valida el snapshot resultante de cambios parciales antes de escribir. Reutiliza el lock y la transacción de DEV-14. Un conjunto de pesos inválido no deja cambios parciales.

El script admite `--sembrar-vision`, simulación por defecto, confirmación explícita con `--aplicar` y conservación de valores existentes. Actualizar valores existentes requiere además un archivo explícito y `--actualizar-existentes`. No se modifican parámetros MLOps ajenos.

### 4.4. Ventanas consecutivas, idempotencia y recuperación (#3800)

`VISION_DETECCION` se integra en el worker DEV-05. Solo procesa observaciones persistidas con inicio de ventana verificable. No agrega un worker, tabla de transporte, contador en memoria ni alerta de dispositivo.

La secuencia usa la misma cámara y área, duración configurada y contigüidad exacta entre cierres e inicios. Una cobertura igual o superior al mínimo interrumpe la secuencia. Una ventana ausente, superpuesta o un lote legado sin inicio verificable también la interrumpe. No se cuentan reintentos como ventanas nuevas.

El repositorio reconstruye las últimas N ventanas de la cámara. Una llegada tardía puede completar la secuencia actual. Al cumplirse la condición, se registra `SIN_DETECCION_VALIDA` en RF-63 con cámara, área, IDs de ventanas, coberturas y parámetros. Es un diagnóstico técnico por cierre de ventana que cumple la condición; nuevos cierres pueden producir nueva evidencia. No representa pérdida de comunicación y no modifica estados del dispositivo.

Los locks de DEV-05 serializan procesamiento por dispositivo. La consulta de evidencia existente evita repetir el diagnóstico del mismo cierre. Diagnóstico y marca de etapa completada se confirman en una sola transacción. Si falla la evidencia, se revierte el efecto de la etapa, se registra el fallo recuperable y se conserva la observación ya confirmada. El registro de auditoría best-effort no se acepta como éxito cuando devuelve un evento sin identificador persistido.

## 5. Archivos modificados

| Ruta | Cambio y justificación | Tarea |
|---|---|---|
| `src/configuration/domain/entities/parametros_vision.py` | Claves, límites y política completa; defaults solo para siembra | #3799 |
| `src/configuration/application/use_cases/configuracion_global/configurar_parametros_mlops_use_case.py` | Validación de pesos y umbrales antes de confirmar cambios | #3799 |
| `scripts/configurar_parametros_dev14.py` | Siembra explícita e idempotente de política de visión | #3799 |
| `src/telemetry/domain/entities/calidad_vision.py` | Fórmula, calibración, clases, flags y snapshot reproducible | #3799 |
| `src/telemetry/domain/entities/secuencia_vision.py` | Secuencias de ventanas reales por cámara y área | #3800 |
| `src/telemetry/domain/repositories/parametros_vision_port.py` | Puerto de política sin acceso SQL desde el dominio | #3799 / #3800 |
| `src/telemetry/domain/repositories/ventanas_vision_port.py` | Puerto de ventanas y evidencia existente | #3800 |
| `src/telemetry/domain/repositories/postcommit_port.py` | Nueva etapa dentro del contrato DEV-05 | #3800 |
| `src/telemetry/application/use_cases/calidad/evaluar_calidad_vision_use_case.py` | Orquestación del oráculo; sin simular persistencia DB-09 | #3799 |
| `src/telemetry/application/use_cases/calidad/evaluar_ventanas_vision_use_case.py` | Diagnóstico RF-63, sin repositorio de alertas ni commits propios | #3800 |
| `src/telemetry/application/use_cases/ingesta/ingerir_observaciones_vision_use_case.py` | Conserva legado e informa bloqueo normativo explícito | #3798 |
| `src/telemetry/infrastructure/adapters/parametros_vision_mlops_adapter.py` | Lectura real, dinámica y consistente de DEV-14 | #3799 / #3800 |
| `src/telemetry/infrastructure/dto/observacion_vision_d4_dto.py` | Contrato normativo y legado separados, validación estricta | #3798 |
| `src/telemetry/infrastructure/repositories/ventanas_vision_repository.py` | Ventanas DB-03 y consulta de idempotencia RF-63 | #3800 |
| `src/telemetry/infrastructure/repositories/postcommit_repository.py` | Selección, reclamación y evidencia de observaciones de visión | #3800 |
| `src/telemetry/infrastructure/routers/telemetria_router.py` | Publicación de contratos en OpenAPI | #3798 |
| `src/telemetry/infrastructure/workers/postcommit_worker.py` | Composición productiva de la etapa de detección | #3800 |
| `tests/telemetry/test_dev28_vision_calidad.py` | Oráculo, DTO, límites, configuración y secuencias | Todas |
| `tests/integration/test_dev28_vision_calidad.py` | HTTP, PostgreSQL, configuración dinámica, rollback, concurrencia y CLI | Todas |
| `tests/telemetry/test_dev07_vision_d4.py` | Mantiene explícitas las pruebas del contrato legado | #3798 |
| `tests/integration/test_dev07_vision_d4.py` | Conserva regresión legado; aísla los commits de la prueba concurrente | #3798 / #3800 |
| `tests/integration/conftest.py` | BD efímera local por prueba concurrente; no deja observaciones en otras pruebas | #3800 |
| `anotaciones/modulo_3/dev28_rf53_rf62_vision_calidad_ventanas.md` | Diagnóstico, evidencia, pendientes y propuesta de PR | Todas |

Los archivos de código incorporan o actualizan su tabla de seguimiento con `git config user.name = Leandro`, fecha 2026-10-22. Los documentos de pendientes y `AGENTS.md` que ya estaban sin seguimiento en Git no forman parte de esta implementación.

## 6. Base de datos y procedimiento

Se reutilizan `modulo4.parametros_mlops` —valores JSONB—, `modulo3.observaciones_vision`, la configuración de cámaras en `modulo9.dispositivos_iot` y `modulo3.bitacora_auditoria_iot`. No se modifican tablas de telemetría inmutable ni triggers. No se crea migración DEV-28.

Las pruebas usan PostgreSQL efímero en `127.0.0.1:55428`, base `sgpmp_dev28_test`, con las migraciones reales del repositorio hasta `e5a3c9b17d42`. Las pruebas con commits concurrentes y CLI crean una base local independiente, aplican esas mismas migraciones y la eliminan al finalizar. Nunca usan la base oficial como destino de escritura.

Al terminar se verificaron la ruta temporal, `PG_VERSION`, las opciones y el puerto del cluster DEV-28; se detuvo y retiró únicamente ese cluster. Las evidencias de ejecución se conservaron en `.pytest_cache`.

Procedimiento de configuración para el administrador, pendiente de autorización en DEV/TEST compartidos:

```powershell
# DEV14_DATABASE_URL debe estar configurada con el destino autorizado.
# Primero simular; sustituir ID_ADMIN_VALIDO por el identificador real.
.venv/Scripts/python.exe scripts/configurar_parametros_dev14.py --sembrar-vision --id-usuario ID_ADMIN_VALIDO
# Solo con autorización de escritura:
.venv/Scripts/python.exe scripts/configurar_parametros_dev14.py --sembrar-vision --id-usuario ID_ADMIN_VALIDO --aplicar
```

Las tres claves de detección se configuran mediante el mecanismo de DEV-27; no se duplican en la siembra de calidad. Los valores D requieren calibración en sitio y no se presentan como mediciones de hardware.

## 7. Pruebas y evidencia

### 7.1. Resultados finales sin duplicar reejecuciones

| Conjunto | Aprobadas | Fallidas | Omitidas | Evidencia |
|---|---:|---:|---:|---|
| Unitarias de `tests/telemetry` y `tests/configuration` | 965 | 0 | 0 | `.pytest_cache/dev28_regresion_unit.xml` y `.log` |
| Integración PostgreSQL DEV-28/07/27/05/12/14 | 115 | 0 | 0 | `.pytest_cache/dev28_pg_final.xml` y `.log` |
| **Total de pruebas distintas en esas ejecuciones** | **1080** | **0** | **0** | No suma las ejecuciones exploratorias |

De ellas, **88 son específicas de DEV-28**: 71 unitarias y 17 de integración. Las 115 integradas se distribuyen en DEV-28: 17; DEV-07: 15; DEV-27: 15; DEV-05: 32; DEV-12: 18; DEV-14: 18.

Se repitió además `test_pesos_persistidos_cambian_oraculo_sin_reinicio` después de hacer explícita la lectura del FPS real de la cámara: **1 aprobada**, evidencia `.pytest_cache/dev28_fps.xml`. Es la misma prueba y no se suma de nuevo al total de 1080.

| Escenario | Verificación y resultado |
|---|---|
| Oráculo y modificadores | Con política de referencia: 91.6 calibrado, 64.12 en calibración y 0/no apto sin línea base |
| Fronteras | 0, 39.99, 40, 40.01, 79.99, 80, 80.01 y 100; compara antes de cualquier cuantización |
| Determinismo | Mismo resultado aunque cambie el contexto decimal del llamador |
| Política | Pesos fuera de dominio, suma distinta de 1, divisor cero, parámetros faltantes e inconsistencias rechazados |
| HTTP/OpenAPI | Metadatos normativos obligatorios, cero individuos válido, extras prohibidos, incompletos 400 y persistencia no disponible 503 explícito |
| Compatibilidad y seguridad | Legado 201, ventanas y versiones preservadas, token obligatorio, área verificada, deduplicación, rollback y consumidor RF-24 |
| Lectura dinámica real | Cambiar pesos y umbral en M04 cambia índice/clase en el mismo consumidor; cambiar N cambia detección en el mismo worker |
| Secuencias | N/N−1, igualdad con mínimo, ventana válida, brecha, superposición, separación por cámara/área y llegada fuera de orden |
| Evidencia persistida | `SIN_DETECCION_VALIDA` recuperable con IDs, hash y política; observaciones originales iguales y cero alertas de dispositivo |
| Recuperación | Configuración ausente conserva observaciones; fallo posterior al diagnóstico revierte efectos de etapa; reintento aplica evidencia una sola vez |
| Concurrencia | Dos workers reales sobre PostgreSQL local no duplican el diagnóstico; ingesta concurrente legado mantiene una observación |
| CLI real | Simulación sin escrituras, siembra confirmada y segunda ejecución conserva los pesos modificados |

La primera ejecución exploratoria PostgreSQL obtuvo 31 aprobadas y un fallo del fixture CLI: sobrescribía la variable del administrador con el usuario usado para configurar datos de prueba. Se corrigió esa variable, manteniendo intacta la comprobación de autorización del script. La ejecución final anterior pasa; no se suma el resultado exploratorio al total ni se oculta como fallo de producción.

Se observó un aviso de deprecación de Starlette sobre su cliente HTTP de pruebas. No se añadió una dependencia para silenciarlo. Bandit se ejecutó en el alcance productivo afectado con el filtro `-ll -ii`: **0 hallazgos medios/altos**, dos avisos de severidad baja fuera del filtro. AST, tablas de seguimiento y espacios finales: **22 archivos Python correctos**. `git diff --check` no detectó errores; Git solo avisó de conversión LF/CRLF en el DTO.

### 7.2. Comandos ejecutados

Variables de conexión para pruebas exclusivamente locales:

```powershell
$env:DATABASE_URL='postgresql+psycopg2://postgres@127.0.0.1:55428/sgpmp_dev28_test'
$env:TEST_DATABASE_URL=$env:DATABASE_URL
```

Runner unitario realmente utilizado:

```powershell
.venv/Scripts/python.exe -u -c "import sys,types;sys.modules['fcntl']=types.SimpleNamespace(LOCK_EX=2,LOCK_NB=4,LOCK_UN=8,flock=lambda *a:None);import pytest;sys.exit(pytest.main(['tests/telemetry','tests/configuration','-q','--import-mode=importlib','--basetemp=.pytest_cache/dev28_regresion_unit','--tb=short','--junitxml=.pytest_cache/dev28_regresion_unit.xml']))"
```

Runner integrado realmente utilizado:

```powershell
.venv/Scripts/python.exe -u -c "import sys,types;sys.modules['fcntl']=types.SimpleNamespace(LOCK_EX=2,LOCK_NB=4,LOCK_UN=8,flock=lambda *a:None);import pytest;sys.exit(pytest.main(['tests/integration/test_dev28_vision_calidad.py','tests/integration/test_dev07_vision_d4.py','tests/integration/test_dev27_heartbeat_parametros.py','tests/integration/test_dev05_ingesta_bplus_postcommit.py','tests/integration/test_dev12_heartbeat_extendido.py','tests/integration/test_dev14_parametros_dinamicos.py','-q','--import-mode=importlib','--basetemp=.pytest_cache/dev28_pg_final','--tb=short','--junitxml=.pytest_cache/dev28_pg_final.xml']))"
```

Además se ejecutó `alembic upgrade head` sobre el cluster local, Bandit con `-ll -ii`, análisis AST de los archivos Python modificados/nuevos y `git diff --check`. Evidencias locales ignoradas por Git: `.pytest_cache/dev28_migraciones.log`, `.pytest_cache/dev28_bandit.txt` y `.pytest_cache/dev28_oficial_esquema.json` —este último contiene metadatos, no credenciales—.

### 7.3. Límites de la evidencia

No se ejecutaron pruebas de persistencia del nuevo sobre y resultados DB-09, consulta posterior de flags/confianza, sustitución asíncrona completa RF-62, broker MQTT/cámara reales ni calibración de hardware. Esos escenarios **no se cuentan como aprobados**; tampoco son tests omitidos automáticamente del runner: son criterios pendientes de implementación/integración. El índice se prueba como oráculo de dominio/aplicación con configuración PostgreSQL real, sin afirmar que está almacenado en DB-09.

El runner Windows utiliza un puente de `fcntl` únicamente para importar dependencias de pruebas; los locks PostgreSQL, autenticación HTTP y validaciones de producción permanecen activos. No constituye validación del mecanismo de bloqueo de archivos Linux.

## 8. Dependencias y pendientes para cierre

| Dependencia | Estado confirmado | Pendiente |
|---|---|---|
| DB-03 | Aplicada en la base oficial y reutilizada en pruebas | Ninguno para los campos DB-03 inspeccionados |
| DB-09 | No integrada en esquema oficial ni rama inspeccionada | Campos normativos, flags, confianza, catálogos, nulabilidad de tracks y precisión del índice |
| DEV-14 | Almacén, repositorio, locks y validación disponibles | Sembrar política en ambientes compartidos con autorización |
| DEV-27 | Integrada en la base de rama `a218a3d9`; claves y worker disponibles | Sembrar/verificar claves de detección en DEV/TEST; P-1 conserva su alcance provisional |
| P-5 / Análisis-AIoT | No se encontró resolución aprobada | Definir si `n_tracks` debe enviarse y su contrato; no equipararlo con individuos |
| RF-62 | Oráculo y parámetros implementados y comprobables | Integrar evaluación asíncrona, persistencia, lectura posterior y consumidores con DB-09 |
| RF-60 | Diagnóstico por ventanas conectado a DEV-05 | Validar en integración conjunta con el sobre normativo y broker/cámara reales |

### Solicitud técnica mínima para DB-09 — preparada, no enviada

**Responsable de esquema: Samuel, tarea DB-09.** Confirmar la migración oficial y su referencia antes de adaptar el modelo ORM/repo:

1. En `modulo3.observaciones_vision`, proporcionar los campos asignados por DB-09: `n_individuos_observados`, `origen`, `json_flags_detectados`, `es_confianza_baja`, con sus tipos, restricciones y tratamiento de históricos.
2. Confirmar cómo se conserva `tipo_dato=VECTOR_COMPORTAMIENTO`: columna oficial o discriminador constante recuperable del recurso. No se solicita una columna duplicada sin esa decisión.
3. Publicar los nuevos estados de calibración y clases, con la estrategia aprobada de migración/convivencia histórica. Desarrollo no debe inventar correspondencias.
4. Resolver junto con Análisis la precisión y redondeo del índice. `SMALLINT` no representa los resultados fraccionarios del oráculo; no basta con añadir los cuatro campos.
5. Alinear la nulabilidad de `cantidad_tracks` con P-5. La ausencia de tracks no puede suplirse con el conteo de individuos ni con cero inventado.
6. Definir la persistencia del estado de evaluación y parámetros aplicados para soportar RF-62 asíncrono sin habilitar consumidores antes de evaluar, sin borrar versiones históricas ni actualizar indebidamente datos inmutables.
7. Confirmar la clave normativa de deduplicación RFC-015 C4 con `origen`; el UNIQUE legado por cámara/fecha no debe cambiarse por una interpretación unilateral. Considerar también la discrepancia entre `varchar(20)` de la ficha y el literal de 21 caracteres.

**Criterio de recepción:** el sobre normativo con cero individuos y tracks omitidos cuando corresponda debe poder guardarse y consultarse sin pérdida; un resultado fraccionario, sus flags, confianza y política efectiva deben recuperarse fielmente; el flujo asíncrono debe distinguir pendiente de evaluado y conservar idempotencia.

### Pendientes de Análisis / AIoT / integración

- Resolver P-5 y la procedencia exacta de `frames_procesados`; no se exige un nuevo campo de transporte sin acuerdo.
- Confirmar política de redondeo y correspondencias históricas; conectar la calibración con la línea base del área conforme a RFC-012 v1.2, sin introducir atribución por especie.
- Revisar la interpretación de activación de `tracking_inestable` documentada en este informe.
- Integrar el repositorio DB-09, evaluación asíncrona y consumidores RF-24/RF-56/RF-71; reemplazar el cálculo legado únicamente al completar esa transición.
- Ejecutar aceptación de persistencia normativa y consulta de flags/snapshot. No están aprobadas mediante un esquema ficticio.
- Verificar broker MQTT y cámara reales, latencia RF-55 y calibración en hardware. Las pruebas actuales no demuestran esas integraciones.

## 9. Estado de tareas y Git

| Tarea | Estado |
|---|---|
| #3798 | Parcial: DTO/OpenAPI/validación implementados; persistencia bloqueada por DB-09 |
| #3799 | Parcial: fórmula, configuración y oráculo implementados; sustitución productiva y almacenamiento asíncrono pendientes |
| #3800 | Implementada sobre ventanas DB-03 en el worker existente; aceptación conjunta del nuevo sobre y hardware pendiente |
| #3701 | No cerrar mientras permanezcan los criterios de persistencia y contratos anteriores |

Rama: `fix/dev28-vision-calidad-ventanas`. Base: `a218a3d9`, que contiene DEV-27. `origin/dev` observado en `6113a388`. El identificador del commit de entrega se consulta en el historial Git de esta rama. La revisión contra `dev` deberá separar la dependencia DEV-27 si aún no está integrada; no mezclarla silenciosamente como trabajo nuevo DEV-28.

## 10. Propuesta de Pull Request

### Título

`fix(RF-53/62): preparar D4 normativo y calidad ponderada; detectar ventanas sin cobertura (DEV-28)`

### Desvío identificado

| RF | Antes | Ahora |
|---|---|---|
| RF-53 | DTO sin metadatos de la ficha | Sobre normativo estricto y OpenAPI; bloqueo DB-09 explícito sin pérdida silenciosa |
| RF-62 | Cálculo legado sin política ponderada configurable | Oráculo ponderado determinista con DEV-14; integración productiva pendiente de persistencia |
| RF-60 | Sin detección consecutiva de visión | Diagnóstico técnico idempotente en DEV-05, sin alertas de dispositivo |

Referencias: historia #3701; tareas #3798, #3799 y #3800. **No usar `Closes` mientras DB-09/P-5 y los criterios pendientes no estén resueltos.**

---

### Causa raíz

El contrato y esquema existentes pertenecen a la etapa DB-03: faltan metadatos y resultados DB-09, los catálogos son anteriores y el índice es SMALLINT. La fórmula vigente requiere pesos/tramos configurables y una evaluación asíncrona que el legado no proporciona. El worker tampoco reconstruía secuencias de visión.

### Cambios implementados

- DTO normativo con metadatos obligatorios y contrato legado separado; conserva autenticación y autorización de área.
- Oráculo RF-62 ponderado, modificadores, tramos configurables, flags, confianza y exclusión NIC41; snapshot de política leído en una consulta.
- Claves, validación completa y siembra explícita e idempotente mediante DEV-14, sin migraciones ni fallback silencioso.
- Etapa `VISION_DETECCION` en DEV-05, reconstrucción temporal, RF-63 durable, locks por dispositivo, rollback y recuperación.
- 1080 pruebas distintas aprobadas: 965 unitarias y 115 de integración PostgreSQL; 88 específicas DEV-28. Cero fallidas y cero omitidas en las ejecuciones finales. AST y seguimiento correctos en 22 archivos Python; Bandit sin hallazgos medios/altos.

### Contrato resultante

| Situación | Resultado |
|---|---|
| Sobre normativo incompleto o inválido | HTTP 400, sin observación |
| Sobre normativo válido con esquema actual | HTTP 503 `CONTRATO_VISION_PENDIENTE`, sin fingir persistencia |
| Contrato D4 legado válido | HTTP 201 y comportamiento previo conservado |
| N ventanas reales consecutivas de cobertura baja | `SIN_DETECCION_VALIDA` en RF-63; cero alertas de dispositivo |
| Reintento o workers concurrentes | Un diagnóstico por cierre lógico |
| Error post-commit | Observación conservada y etapa recuperable |

### Pruebas, dependencias y pendientes

Consultar secciones 7 y 8. Integración real MQTT/cámara y persistencia normativa DB-09 no verificadas. Los cambios de parámetros y pruebas persistentes se ejecutan exclusivamente en PostgreSQL local aislado. La base oficial solo se inspeccionó en lectura.

### Revisión contra dev

Rama `fix/dev28-vision-calidad-ventanas`, dependiente de DEV-27. Este PR debe describirse como avance parcial hasta integrar DB-09 y completar los criterios pendientes; no acredita cierre de #3701.
