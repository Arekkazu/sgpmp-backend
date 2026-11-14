# DEV-41 — RF-53: alertas críticas RF-57 desde telemetría confirmada

Fecha: 2026-10-21. Historia #3698; tareas #3790 y #3791; épica #3667.

Rama: `fix/dev41-alertas-telemetria-critica`, creada desde `origin/dev`
(`6113a3883f7ca3a9b2991148414451323f6f9a81`). Los cambios de DEV-27 permanecen
en su rama independiente.

## 1. Diagnóstico

Se inspeccionaron la ingesta individual y batch, la función SQL de B+, las etapas
DEV-05, RF-17, RF-57, RF-61/RF-62, el endpoint Edge, modelos, migraciones, triggers
y pruebas. Se contrastaron RF-53 postcondición 5/CA-16, RF-57 E2/E4 y los contratos
RF-17 presentes en los requerimientos actualizados de M03/M09.

| Componente | Hecho confirmado en la base de la rama | Acción |
|---|---|---|
| Ingesta HTTP | `POST /iot/telemetria` y `/iot/telemetria/batch` persisten mediante `fn_ingesta_telemetria` | Conservar contrato y commit |
| MQTT B+ | El broker escribe mediante la frontera SQL; el backend procesa filas confirmadas, sin consumidor MQTT propio | Reutilizar esa misma persistencia y el worker |
| DEV-05 | Etapas RF61, RF62 y RF17; evidencia durable RF-63, reintentos y locks por dispositivo | Agregar RF57 después de los requisitos |
| RF-17 | `ReclasificarSemaforoUseCase` usa `SemaforoCalculator.calcular_por_niveles` y umbrales M09 | Exponer la operación por lectura sin duplicar el clasificador |
| Proyección RF-58 | El cache representa el último dato y puede tener prioridad por alertas existentes | No usar ese color como clasificación del origen |
| RF-57 | `GenararAlertaUseCase` genera ACTIVA y deduplica por sensor/variable | Reutilizarlo para BACKEND y conservar Edge |
| Deduplicación | Ventana de 30 minutos, basada en fecha de generación; búsqueda y actualización sin un bloqueo común de condición | Conservar la ventana y serializar la condición |
| Historial inicial | El caso de uso insertaba una fila adicional a `trg_rf57_02_historico_inicial` | Dejar la creación histórica al trigger |
| DEV-40/DEV-49 | Sus ramas no están integradas en `origin/dev` | No incorporar sus soluciones completas ni otro parámetro |

La causa raíz de G-09 era la ausencia de una etapa RF-57 tras la ingesta:
persistir y proyectar el semáforo no invocaba el generador de alertas.

## 2. Implementación de #3790

### Etapa y orden

Se agregó `EtapaPostcommit.RF57` al worker existente. Requiere evidencia de
RF17 y RF62 completadas para el mismo `id_telemetria`; RF17 conserva su requisito
RF61. El resto de las etapas mantiene su comportamiento.

```text
Ingesta SQL común a HTTP/broker → COMMIT
    → RF61 / RF62
    → RF17
    → RF57: clasificar origen → generar/consolidar
    → confirmar efectos y evidencia RF-63 juntos
```

No se invoca el generador desde el endpoint antes del commit y no se crea un
worker paralelo. Una sesión del worker solo puede ver la ingesta confirmada.

El mecanismo recupera también lecturas anteriores que ya cumplan los requisitos
y aún no tengan evidencia RF57, conservando su fecha de captura original. No se
inventó una fecha de corte ni se marcaron históricos como procesados sin ejecutar
la etapa. QA debe considerar este procesamiento pendiente al validar el despliegue.

### Clasificación oficial por origen

`ReclasificarSemaforoUseCase.clasificar_lectura` utiliza los mismos puertos de
especie/umbral y el mismo `SemaforoCalculator.calcular_por_niveles` que ya usaba
RF-17. Su método `execute` conserva la actualización de la proyección RF-58.
La nueva operación permite clasificar el `id_telemetria` exacto sin sobrescribir
el cache del último dato.

Se mantiene el uso de `valor_ajustado`, con el respaldo al valor crudo que ya
define RF-17. Sus bandas inclusivas, límites y tratamiento ROJO fuera de todas
las bandas siguen siendo responsabilidad del clasificador existente.

Esto evita dos errores: perder una lectura crítica tardía porque el último dato
ya es normal, y generar una alerta crítica porque el cache está rojo debido a
otra alerta en lugar de a la medición.

### Calidad y contexto

- Un estado RF-53 diferente de `LECTURA_VALIDA` produce una decisión técnica
  `EXCLUIDA_POR_CALIDAD`, sin alerta operativa.
- RF62 debe haber persistido una evaluación vigente. No se leen las columnas
  obsoletas de aptitud de `telemetrias`.
- `apto_para_ia=false` no se convierte en veto a una alerta local válida: aptitud
  para IA y clasificación de calidad RF-53 son contratos distintos.
- Una vinculación RF61 pendiente o ambigua deja la etapa pendiente de reintento
  con `CONTEXTO_ALERTA_PENDIENTE`, para no inventar una especie o umbral.
- Si RF-17 no ofrece clasificación por falta de umbral/especie resoluble, se
  conserva su resultado sin alerta y se registra `SIN_CLASIFICACION_RF17`.
- Un fallo real de consulta/clasificación se propaga al mecanismo técnico de
  reintento; no se transforma en lectura normal ni en éxito ficticio.

### Generación y correlación

`GenerarAlertaTelemetriaUseCase` transforma exclusivamente ROJO en un evento
RF-57 BACKEND con severidad CRITICO. Invoca `GenararAlertaUseCase`, conservando
tipo de alerta, estado ACTIVA, frecuencia inicial, SLA y deduplicación existentes.

El contexto utiliza las relaciones reales:

```text
telemetrias → sensor / dispositivo / variable
dispositivo → infraestructura → finca
vinculaciones_lecturas → activo biológico → especie
umbrales_ambientales → niveles_alerta_ambientales
```

La alerta nueva conserva la referencia `id_telemetria`. Sus metadatos incluyen
sensor, dispositivo, variable, finca, especie, captura, unidad, valor crudo y
evaluado, umbral, versión y bandas aplicadas.

Al consolidar se conserva el contenido original de la alerta, incluida su primera
referencia de telemetría. La evidencia RF-63 de **cada** lectura registra el
`id_alerta` resultante y su propio snapshot RF-17. Así, una segunda lectura no
sobrescribe la trazabilidad de la primera ni depende del valor futuro del umbral.

## 3. Implementación de #3791

### Deduplicación y concurrencia

Se reutiliza la búsqueda RF-57 por sensor y variable, con estados ACTIVA o
EN_ATENCION y la ventana existente de **30 minutos**. La segunda lectura distinta
actualiza `ultima_ocurrencia` e incrementa `frecuencia_evento` mediante el mismo
caso de uso. Se conserva su política de escalamiento de severidad.

`AlertaRepository.bloquear_condicion` introduce un advisory lock transaccional
por sensor e identidad de variable, utilizado por el generador común. No es un
bloqueo global y protege también el encuentro entre Edge y BACKEND. La búsqueda
y la actualización de la alerta aplican bloqueo de fila y recarga de estado.

La identidad de la variable se consulta en M09. Cuando `codigo_telemetria` está
disponible, tiene precedencia; para el esquema anterior se reutilizan únicamente
los alias públicos ya existentes, sin copiar ni crear otro catálogo de variables.
El respaldo de nombre sigue la normalización usada por DEV-40. Esto permite,
por ejemplo, consolidar CONDUCTIVIDAD_ELECTRICA y TDS de la misma variable.
Un catálogo ambiguo o inaccesible produce un error explícito.

Esta compatibilidad no implementa DEV-40: la ingesta base todavía depende de su
catálogo previo hasta integrar esa tarea. Las pruebas de la forma futura del
catálogo son unitarias con dobles y se distinguen de las consultas PostgreSQL
efectuadas sobre el esquema actual.

### Idempotencia y atomicidad

La idempotencia por lectura pertenece a DEV-05: reclama la fila, conserva su
lock por dispositivo y consulta la evidencia durable antes de ejecutar RF57.
Dos lecturas distintas se consolidan; dos ejecuciones de la misma lectura no
incrementan otra vez la frecuencia.

La alerta o incremento y `POSTCOMMIT_RF57_COMPLETADO` se confirman en la misma
transacción externa. Los commits del generador siguen siendo savepoints dentro
de esa unidad. Si falla la alerta o la evidencia, ambos efectos se revierten y
el mecanismo existente registra un fallo recuperable. La telemetría previamente
confirmada permanece intacta.

No se agrega un identificador aleatorio de entrega ni una tabla de transporte.

### Historial y flujo Edge

Se retiró exclusivamente el insert histórico inicial redundante del generador
compartido. `trg_rf57_02_historico_inicial` conserva esa escritura atómica. La
consolidación de frecuencia no crea una transición de estado adicional.

El endpoint `POST /iot/eventos-edge` conserva su generador. Se verificó que un
evento Edge equivalente consolide con una alerta originada por telemetría,
incluyendo persistencia de su evento y el flujo RF-56 existente. Esto no constituye
una entrega real al motor IA ni una prueba del transporte MQTT externo.

## 4. Archivos modificados

| Archivo | Cambio y justificación | Tarea |
|---|---|---|
| `src/telemetry/domain/repositories/postcommit_port.py` | RF57 y requisitos RF17/RF62; detalle opcional de resultado | #3790 |
| `src/telemetry/infrastructure/repositories/postcommit_repository.py` | Requisitos conjuntos y correlación en la evidencia RF-63 existente | #3790/#3791 |
| `src/telemetry/application/use_cases/ingesta/procesar_postcommit_use_case.py` | Confirma detalle de la etapa junto con sus efectos | #3790/#3791 |
| `src/telemetry/infrastructure/workers/postcommit_worker.py` | Inyecta los componentes reales y conecta RF57 | #3790 |
| `src/telemetry/application/use_cases/monitoreo/reclasificar_semaforo_use_case.py` | Comparte clasificación exacta sin duplicar reglas ni cambiar la proyección existente | #3790 |
| `src/telemetry/application/use_cases/alertas/generar_alerta_telemetria_use_case.py` | Orquesta calidad, contexto, criticidad y generador RF-57 | #3790 |
| `src/telemetry/infrastructure/repositories/lectura_postcommit_repository.py` | Obtiene contexto M09, infraestructura y finca | #3790 |
| `src/telemetry/infrastructure/adapters/variable_alerta_m09_adapter.py` | Identidad M09 y compatibilidad de alias entre canales | #3791 |
| `src/telemetry/domain/repositories/alerta_repository.py` | Contrato de bloqueo por condición | #3791 |
| `src/telemetry/infrastructure/repositories/alerta_repository.py` | Bloqueo, equivalencia de alias y actualización con fila bloqueada | #3791 |
| `src/telemetry/application/use_cases/alertas/generar_alerta_use_case.py` | Bloquea la condición y delega el historial inicial al trigger | #3791 |
| `tests/telemetry/test_dev41_alertas_telemetria.py` | 25 pruebas unitarias de clasificación, calidad, catálogo y reutilización | Ambas |
| `tests/integration/test_dev41_alertas_telemetria.py` | 21 pruebas PostgreSQL de commit, SQL B+, HTTP/Edge, consolidación y concurrencia | Ambas |
| `tests/integration/test_dev05_ingesta_bplus_postcommit.py` | Incluye RF57 y comprueba decisión de exclusión e idempotencia | #3790/#3791 |
| `anotaciones/modulo_3/dev41_rf53_alertas_criticas_postcommit.md` | Diagnóstico, pruebas, alcance y propuesta de PR | Ambas |

Los 14 archivos Python llevan seguimiento de la tarea, fecha real y autor obtenido
de `git config user.name`: `Leandro`. Los archivos preexistentes de pendientes y
`AGENTS.md` sin seguimiento Git se conservaron sin incorporarlos a esta tarea.

## 5. Base de datos

Se reutilizan `modulo3.telemetrias`, `telemetria_calidad`, `vinculaciones_lecturas`,
`alertas`, `historico_estados_alertas`, `bitacora_auditoria_iot`, las tablas M09 de
variables, umbrales, niveles, dispositivos e infraestructura, y la especie M02.

Se utiliza la función existente `modulo3.fn_ingesta_telemetria`. El procedimiento
SQL heredado `sp_generar_alerta` existe en el baseline, pero no se encontró una
invocación desde el backend inspeccionado; DEV-41 utiliza el caso de uso vigente,
no agrega una segunda vía de generación SQL.

No fue necesaria una migración: las etapas RF-63, relaciones de alerta y snapshots
JSONB ya soportan este cambio. No se alteran triggers ni la inmutabilidad RF-53.
Las garantías de consolidación verificadas corresponden al generador común de
los caminos backend/Edge implementados, no a escrituras SQL externas que lo omitan.

## 6. Pruebas ejecutadas

PostgreSQL 18 efímero local, puerto 55441, base `sgpmp_dev41_test`. Se aplicaron
las migraciones existentes hasta `e5a3c9b17d42`. Los escenarios concurrentes usan
conexiones y commits reales exclusivamente en esa base aislada. No se efectuaron
escrituras en bases oficiales o compartidas.

### Resultados finales sin duplicar casos

| Suite seleccionada | Aprobadas | Fallidas | Omitidas |
|---|---:|---:|---:|
| `tests/telemetry` | 259 | 0 | 0 |
| `tests/configuration` | 616 | 0 | 0 |
| Integraciones PostgreSQL seleccionadas | 95 | 0 | 0 |
| **Total** | **970** | **0** | **0** |

Duración: 102.67 s. Las **25 unitarias y 21 PostgreSQL propias de DEV-41** están
incluidas en esos totales. No se suman otra vez ejecuciones dirigidas anteriores.

| Escenario | Evidencia de ejecución |
|---|---|
| Normal y precaución | No generan alerta crítica; se conserva clasificación RF-17 |
| Crítica por SQL B+ | ACTIVA/CRITICO, frecuencia inicial 1 y relaciones persistidas |
| Segunda lectura distinta | Una alerta, frecuencia 2 y correlación individual RF-63 |
| Redelivery SQL | Ingesta duplicada sin nueva lectura ni incremento de frecuencia |
| Lectura crítica tardía | Genera alerta aunque el último dato sea normal |
| ERROR_CALIBRACION | Registro técnico de exclusión, sin alerta operativa |
| Aptitud IA falsa | No sustituye la regla de calidad de alertas locales |
| Umbral no disponible | Sin clasificación/alerta, conforme al resultado RF-17 |
| Fallo RF62 | RF57 no se adelanta; se recupera después de completar calidad |
| Fallo al guardar alerta | Rollback de efectos y reintento, sin perder telemetría |
| Fallo al registrar evidencia | Revierte también la alerta aunque el generador haya hecho commit del savepoint |
| Fallo durante consolidación | No se conserva el incremento fallido ni se duplica al reintentar |
| Fuera de ventana | Nueva alerta, conservando el contrato temporal RF-57 |
| HTTP individual y batch | Persistencia/idempotencia conservadas; alertas solo después del worker |
| Endpoint Edge existente | Evento persistido y consolidación con BACKEND |
| Dos workers simultáneos | Una alerta y frecuencia 2 para dos lecturas |
| Generadores Edge/BACKEND simultáneos | Comparten la condición bloqueada y una sola alerta |
| Antes del commit / rollback de ingesta | Otra conexión del worker no ve la lectura ni produce alerta |
| Historial | Una fila inicial por alerta; sin insert adicional por consolidación |

Las pruebas de ausencia de umbral físico/configuración, propagación de errores,
límites inclusivos y compatibilidad del catálogo posterior DEV-40 incluyen dobles
de puertos; no se presentan como despliegue real de esa dependencia.

### Comandos y evidencia

Suite ejecutada con variables `DATABASE_URL` y `TEST_DATABASE_URL` apuntando a la
base aislada anterior:

```text
tests/telemetry
tests/configuration
tests/integration/test_dev41_alertas_telemetria.py
tests/integration/test_dev05_ingesta_bplus_postcommit.py
tests/integration/test_dev12_heartbeat_extendido.py
tests/integration/test_dev14_parametros_dinamicos.py
tests/integration/test_inc_m09_64_g31_vinculacion_ingesta.py
```

Comando real en Windows:

```powershell
.venv/Scripts/python.exe -c "import sys,types; sys.modules['fcntl']=types.SimpleNamespace(LOCK_EX=2,LOCK_NB=4,LOCK_UN=8,flock=lambda *a:None); import pytest; sys.exit(pytest.main(['tests/telemetry','tests/configuration','tests/integration/test_dev41_alertas_telemetria.py','tests/integration/test_dev05_ingesta_bplus_postcommit.py','tests/integration/test_dev12_heartbeat_extendido.py','tests/integration/test_dev14_parametros_dinamicos.py','tests/integration/test_inc_m09_64_g31_vinculacion_ingesta.py','--import-mode=importlib','--basetemp=.pytest_cache/dev41_final_tmp','-q','--tb=short','--junitxml=.pytest_cache/dev41_cierre.xml']))"
```

El puente de importación `fcntl` permite cargar el `conftest` de M02 en Windows;
no valida sus bloqueos de archivos. No se modificó ese módulo. En Linux puede
usarse `python -m pytest` con las mismas rutas y opciones, sin ese puente.

Los intentos iniciales detectaron dos requisitos del fixture M02: catálogo ACTIVO
e identidad de auditoría. Se prepararon explícitamente usando el modelo y la
función existentes. También se actualizó la expectativa antigua de tres etapas
para comprobar la cuarta etapa y su decisión de exclusión, sin debilitar las
comprobaciones de integridad/idempotencia. La ejecución final no tiene fallos.

Evidencias locales ignoradas por Git:

```text
.pytest_cache/dev41_cierre.xml
.pytest_cache/dev41_resumen_validacion.json
.pytest_cache/dev41_bandit.txt
.pytest_cache/dev41_migrations.log
```

AST y seguimiento: 14 archivos correctos. `git diff --check`: sin errores.
Bandit sobre los 11 archivos de producción afectados: 0 hallazgos medios/altos.
Una advertencia preexistente corresponde a la deprecación de httpx/TestClient.
No se ejecutó una suite de todo el backend ni una prueba desplegada en DEV/TEST.

## 7. Alcance MQTT y dependencias

| Dependencia | Estado verificado |
|---|---|
| DEV-05 | Disponible en la rama y utilizado por la nueva etapa |
| RF-17 | Puertos/calculador reales reutilizados; se conserva la limitación previa de consultar el umbral activo, sin vigencias históricas aún publicadas por M09 |
| RF-57 | Generador, repositorios, estados, frecuencia y triggers disponibles |
| DEV-14 | Parámetros RF62/confianza disponibles; la instalación necesita sus valores válidos para completar esas evaluaciones |
| DEV-40 | No integrado en `origin/dev`; identidad de alertas preparada para el código persistido, sin reproducir sus migraciones ni su ingesta |
| DEV-49 | No integrado en `origin/dev`; se mantiene temporalmente la ventana 30 min permitida por DEV-41, sin agregar otro parámetro |
| DEV-17 | Adaptador del motor no integrado conserva el paquete pendiente; no se simula entrega real a IA |
| MQTT externo | No se dispuso de broker ni de su repositorio/consumidor de pruebas en el entorno inspeccionado |

**MQTT extremo a extremo no ejecutado:** las pruebas invocan la función SQL real
de la frontera B+ y el worker real, con PostgreSQL. No usan un socket MQTT ni
prueban publicación, ACL, ACK o reenvío del broker. La recepción HTTP Edge sí se
prueba a través de su endpoint existente y token de servicio de pruebas.

## 8. Estado final y pendientes

| Tarea | Estado |
|---|---|
| #3790 | Implementada y verificada con PostgreSQL: etapa productiva, clasificación oficial, calidad, correlación y rollback |
| #3791 | Deduplicación, frecuencia, idempotencia y concurrencia implementadas/verificadas; prueba MQTT externa extremo a extremo pendiente |
| #3698 | Preparada para revisión de código/QA; no se declara cierre de toda la historia sin la validación MQTT externa |

Pendientes verificables para integración/QA:

1. En un broker de pruebas autorizado, publicar dos lecturas críticas distintas
   del mismo sensor/variable; comprobar una alerta ACTIVA con frecuencia 2.
   Reentregar una lectura y reiniciar el worker: la frecuencia debe seguir en 2.
2. Confirmar en ese entorno la configuración RF62 y las relaciones RF61/umbrales
   RF17 necesarias. Una vinculación sin resolver permanece pendiente de reintento.
3. Cuando se integre DEV-49, verificar su ventana persistida desde el mismo
   generador RF-57. DEV-41 no define otro nombre de parámetro ni regla temporal.
4. Al integrar DEV-40, ejecutar la regresión conjunta con su migración y códigos
   reales. La compatibilidad futura probada con dobles no sustituye ese despliegue.

No se solicitó un cambio de BD ni se creó una migración.
Los cambios permanecen en la rama indicada, con tablas de seguimiento completas.

## 9. Propuesta de Pull Request

**Título:** `RF-53 — Alertas críticas RF-57 desde la ingesta post-commit (DEV-41)`

### Desvío identificado

La ingesta persistía telemetría crítica sin invocar RF-57; el worker terminaba sus
etapas de vinculación, calidad y semáforo sin generar la alerta operativa.

### Causa raíz

Faltaba una etapa RF57 en DEV-05. La proyección del último semáforo no representa
necesariamente la criticidad de cada lectura y el generador necesitaba serializar
la creación/consolidación entre Edge y backend.

### Cambios

- Agrega RF57 después de RF17/RF62, reutilizando el worker y su evidencia durable.
- Reutiliza la clasificación oficial del origen, incluyendo lecturas tardías.
- Invoca el generador RF-57 para crear ACTIVA/CRITICO o incrementar frecuencia.
- Comparte identidad de variable y bloqueo por condición entre los canales.
- Delega historial inicial al trigger y confirma alerta/evidencia juntas.
- Conserva telemetría inmutable y recuperación ante fallos post-commit.

### Contrato resultante

| Situación | Resultado |
|---|---|
| Primera lectura válida crítica | Alerta ACTIVA, frecuencia 1 |
| Otra lectura equivalente dentro de la ventana | Misma alerta, frecuencia incrementada |
| Reintento de la misma telemetría | Sin repetición de efectos |
| Lectura normal/precaución o excluida | Sin alerta crítica indebida |
| Fallo post-commit | Telemetría conservada, efectos revertidos y etapa recuperable |
| Edge y BACKEND equivalentes | Consolidación compartida sin distinguir únicamente por origen |

### Pruebas

970 aprobadas, 0 fallidas, 0 omitidas. Incluyen 25 unitarias y 21 PostgreSQL de
DEV-41; HTTP/batch, endpoint Edge, concurrencia, commit, rollback y reintentos.
Sin migración. Bandit, AST, seguimiento y diferencias Git verificados.

### Dependencias y pendientes

Se conserva la ventana RF-57 de 30 minutos hasta integrar DEV-49. DEV-40 permanece
en su rama y no se incorpora su solución completa. La frontera SQL del broker B+
se probó con componentes reales; la publicación MQTT extremo a extremo queda
pendiente de un broker de pruebas externo. No se afirma una integración MQTT
externa ni una entrega IA real verificadas.

Referencias: #3698, #3790 y #3791.
