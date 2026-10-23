# DEV-27 — RF-60: parámetros de heartbeat, diagnóstico y cadena canónica

Fecha: 2026-10-21. Historia #3696; tareas #3785, #3786 y #3787.

Rama: `fix/dev27-heartbeat-parametros-canonicos`, basada en `origin/dev`
(`6113a388`). Los pendientes de configuración y despliegue se detallan en la sección 8.

## 1. Diagnóstico y fuentes

Se contrastó el código con `Requerimientos_M03_RF53-RF63.md` (RF-60,
apartado 1.4 y Restricción 12), `Requerimientos_M09_RF15-RF32.md` (RF-18),
`DEV-Tareas_RFC012-016_y_gaps_M03_M04_M09.md` (P-1/G-11), el reparto de tareas
y el acuerdo consolidado AIoT. No se encontró un archivo independiente
AIOT-SPEC-01 ni una aprobación formal posterior de P-1 entre las fuentes disponibles.

| Componente | Estado anterior confirmado | Corrección |
|---|---|---|
| Estado del dispositivo | Límites Python de 300/1800/86400 s; prioridad que hacía inaccesible INACTIVO | Parámetros y algoritmo de dominio compartido |
| Parámetros del worker | Adaptador pendiente que respondía 503 | Adaptador real por sesión y etapa |
| Diagnóstico | Política térmica/firmware sin implementación por defecto | Lectura real de DEV-14, conservando dobles inyectables |
| RF-18 | Validaba `heartbeat >= frecuencia`, sin intervalo ni margen RF-60 | Validación conjunta en POST/PATCH y carga administrativa |
| Alerta de inactividad | MODERADO y dependía de no existir un período abierto | CRITICO; deduplicación por código técnico, independiente del período |
| Historial y períodos | El evaluador escribía además de los triggers; cerraba el período al recuperar contacto | Triggers conservan apertura/historial; aplicación conserva cierre y alertas |
| Persistencia M04 | `valor_actual` y `valor_por_defecto` JSONB, nombre único, límites opcionales, autor y fecha | Reutilizada; sin migración |

Los valores de batería, señal, temperatura e inactividad citados como ejemplos
en los RF no se convirtieron en defaults. Los únicos cinco defaults sembrables
automáticamente son los marcados expresamente como D en la documentación.

## 2. Ubicación provisional P-1 y contrato de parámetros (#3785)

Se aplica la propuesta de Desarrollo indicada por la tarea: parámetros RF-60
en `modulo4.parametros_mlops`, mediante DEV-14. No se agregan columnas a
`modulo9.configuraciones_globales`, tablas ni endpoints. La incorporación formal
de estos parámetros a la ficha RF-18 continúa siendo responsabilidad de Análisis.
No hace falta una modificación de esquema de Samuel para este desarrollo.

Las siguientes claves se incorporan a `_LIMITES` mediante `LIMITES_HEARTBEAT`.
El script existente utiliza las mismas validaciones, sin un catálogo paralelo.

| Clave JSONB | Tipo/unidad | Validación | Default sembrable |
|---|---|---|---|
| `intervalo_heartbeat_camara` | Entero, segundos | 30–600 y cadena canónica | 120 |
| `intervalos_heartbeat_por_tipo` | Objeto categoría → segundos enteros | No vacío; valores positivos; categoría en mayúsculas; CAMARA usa su clave canónica | Sin default |
| `margen_tolerancia` | Entero, segundos | Positivo; `>= max(I,F/2)` | Sin default |
| `tiempo_inactividad_extendida` | Entero, segundos | Positivo | Sin default |
| `umbral_bateria_aviso` | Número, % | Finito, 0–100 | Sin default |
| `umbral_bateria_critica` | Número, % | Finito, 0–100 y no superior a aviso | Sin default |
| `umbral_rssi` | Número, dBm | Finito | Sin default |
| `umbral_snr` | Número, dB | Finito | Sin default |
| `version_minima_firmware` | Texto | No vacío; hasta 50 caracteres, conforme al almacenamiento del heartbeat | Sin default |
| `umbral_temperatura_maxima` | Número, °C | Finito | Sin default |
| `umbral_temperatura_critica` | Número, °C | Finito, no inferior a máxima | Sin default |
| `ventanas_consecutivas_sin_deteccion` | Entero, ventanas | 1–20 | 3 |
| `cobertura_minima_deteccion_valida` | Número, proporción | 0.05–0.90 | 0.30 |
| `duracion_ventana_observacion` | Entero, segundos | 10–300 | 60 |
| `presupuesto_latencia_ventana` | Número, porcentaje | 50–95 | 80 |

La resolución de tipo usa `modulo9.tipos_dispositivo_iot.categoria`, cuyo contrato
actual distingue SENSOR/CAMARA. No utiliza IDs de tipos quemados. SENSOR requiere
su intervalo explícito en el objeto; no se presupone un valor. Margen, inactividad,
batería, señal, firmware y temperatura son globales en esta propuesta de almacenamiento;
no se inventan jerarquías por modelo, familia o sensor.

Las cuatro claves de detección/observación/latencia quedan administrables en
DEV-14. El consumo por Edge/firmware pertenece a su integración correspondiente;
este cambio no implementa un nuevo transporte ni afirma que el nodo ya las reciba.

## 3. Validación temporal y algoritmo (#3787)

RF-18 conserva minutos en `frecuencia_muestreo` y `heartbeat`, alias deprecado de
`umbral_sin_senal`. RF-60 trabaja en segundos. Se convierte antes de validar:

```text
I <= F/2 <= F <= T
margen >= max(I, F/2)

activo   = max(I, F)
sin_senal = activo + margen
inactivo = sin_senal + inactividad_extendida
```

POST/PATCH RF-18 rechazan una cadena incompatible con HTTP 400. Se conserva el
error previo `HEARTBEAT_MENOR_FRECUENCIA` cuando T < F; para la nueva restricción
se utiliza `CADENA_HEARTBEAT_INVALIDA`. La carga administrativa devuelve un error
de validación 400 `PARAMETRO_MLOPS_INVALIDO`, antes de guardar cualquier parámetro.

Las escrituras de RF-18 y DEV-14 comparten el advisory lock transaccional existente
de configuración. Se mantienen RBAC, control de concurrencia, auditoría y contrato
público de RF-18. Sin claves RF-60 previamente configuradas, RF-18 conserva su
validación anterior y permite preparar la configuración necesaria para la siembra.

El timeout T de RF-18 se valida en la cadena. El límite efectivo de clasificación
RF-60 se calcula con F y margen, como exige la fórmula; no se fuerza una igualdad
adicional entre ese cálculo y el campo independiente T de RF-18. Esta distinción
debe quedar explícita en la formalización de P-1, para evitar que una interfaz
presente ambos valores como una misma configuración independiente.

El algoritmo utiliza `fecha_ultimo_contacto` de la persistencia, incluyendo el
contacto confirmado por telemetría válida. ACTIVO incluye la igualdad; luego se
considera buffer A; durante la tolerancia se conserva el estado anterior; al
superar `sin_senal` se distingue SIN_SEÑAL de INACTIVO según el límite extendido.
EN_MANTENIMIENTO se conserva. Buffer L no se interpreta como buffer A.

### Contradicción documental identificada

La aclaración de RF-60 exige detenerse en el primer paso aplicable, pero su paso 3
(`t > sin_senal`) también abarca todo el paso 4 (`t > inactivo`). Aplicar literalmente
esa salida anticipada haría INACTIVO inalcanzable, en contradicción con #3787.
Se preserva la prioridad ACTIVO → BUFFER y se divide el fallo de comunicación
en intervalos excluyentes: SIN_SEÑAL hasta el límite extendido; INACTIVO después.
Esta decisión satisface el criterio explícito de DEV-27 y queda expuesta para
corrección de la redacción por Análisis, sin declarar que exista aprobación formal.

## 4. Adaptadores y procesamiento (#3786)

`ParametrosHeartbeatMLOpsAdapter` consulta M04 y la configuración activa de M09.
No carga una copia estática al arrancar ni usa defaults ocultos. Obtiene los
umbrales de batería/RSSI/SNR y resuelve la política temporal del dispositivo.

`DiagnosticoHeartbeatMLOpsAdapter` obtiene temperatura máxima/crítica y firmware
mínimo. Las versiones numéricas separadas por puntos se comparan por segmentos
enteros y ceros finales: 1.10.0 > 1.9.0. No se afirma soporte SemVer, prereleases
ni otra convención FW-06 no confirmada. Dos versiones idénticas no se consideran
inferiores; formatos distintos no comparables producen
`VERSION_FIRMWARE_NO_COMPARABLE` y dejan la etapa pendiente de reintento.

El worker construye los adaptadores con la sesión de cada etapa. No se comparte
una sesión administrativa con la transacción post-commit. Se conserva la sustitución
por puertos de prueba y la separación de las etapas de sensores, temperatura,
firmware y batería/señal. Una configuración realmente ausente o inválida sigue
siendo un error explícito, no un resultado exitoso.

El evaluador periódico y el worker utilizan el mismo algoritmo y los mismos
efectos de transición. SIN_SEÑAL/INACTIVO registran `FALLO_CONECTIVIDAD`, requerido
por los períodos, y generan alertas técnicas deduplicadas
`DISPOSITIVO_SIN_SEÑAL`/`DISPOSITIVO_INACTIVO`, con severidad LEVE/CRITICO.
Los triggers abren períodos y escriben historial; no se repite esa escritura.
Al recuperar ACTIVO se cierran los períodos abiertos mediante el repositorio
existente, conservando la recuperación por telemetría además de heartbeat.

La alerta y la evidencia RF-63 se confirman con la transacción de la etapa.
Un fallo de persistencia revierte estado, historial y períodos, y conserva el
mecanismo de reintento de DEV-05. No se modificaron broker, tópicos ni firmware.

## 5. Script de siembra y activación DEV/TEST

`scripts/configurar_parametros_dev14.py` mantiene el modo administrativo anterior
y agrega `--sembrar-heartbeat`. Requiere URL explícita en `DEV14_DATABASE_URL`
y un usuario Administrador real. Por defecto ejecuta una simulación de solo
lectura. `--aplicar` confirma una sola transacción.

Las claves existentes se conservan. `--actualizar-existentes`, junto con un
archivo explícito, permite actualizar solamente las claves de ese archivo;
los defaults D no sobrescriben valores configurados. El valor inicial
`valor_por_defecto` se conserva al actualizar. No se imprimen credenciales.

Procedimiento por entorno, con una URL autorizada configurada fuera del repositorio:

```powershell
# Consultar previamente el usuario Administrador real y revisar la configuración RF-18.
# RF-18 debe permitir I=120 s para la cámara: F no inferior a 4 minutos.
.venv/Scripts/python.exe scripts/configurar_parametros_dev14.py `
  --sembrar-heartbeat --archivo parametros_heartbeat_aprobados.json `
  --id-usuario $idAdministrador

# Aplicar después de revisar la simulación y los valores autorizados de ese entorno.
.venv/Scripts/python.exe scripts/configurar_parametros_dev14.py `
  --sembrar-heartbeat --archivo parametros_heartbeat_aprobados.json `
  --id-usuario $idAdministrador --aplicar
```

El archivo debe contener los valores operativos aprobados que faltan, incluido
el intervalo SENSOR cuando aplique. No se agrega un archivo de producción con
valores de prueba. El script tampoco altera automáticamente F/T para hacer pasar
la validación: una configuración RF-18 incompatible bloquea la siembra de forma
explícita y atómica.

**Estado externo:** los intentos de conexión de solo lectura a `sgpmp_dev` en el
puerto 5447 agotaron el tiempo de espera durante esta ejecución. No se pudo
confirmar su configuración actual ni ejecutar allí la siembra. Tampoco se dispone
del destino TEST confirmado ni de todos los valores operativos aprobados.
La siembra real en DEV/TEST permanece pendiente; la implementación del script y
su idempotencia sí se verificaron en PostgreSQL local aislado.

## 6. Archivos modificados

| Archivo | Responsabilidad y cambio | Tarea |
|---|---|---|
| `src/configuration/domain/entities/parametros_heartbeat.py` | Claves, tipos, límites, defaults D y regla temporal compartida | #3785/#3787 |
| `src/configuration/application/use_cases/configuracion_global/configurar_parametros_mlops_use_case.py` | Amplía `_LIMITES`, validación conjunta y siembra conservadora | #3785 |
| `scripts/configurar_parametros_dev14.py` | Simulación/aplicación idempotente y actualización explícita | #3785 |
| `src/configuration/application/use_cases/configuracion/validar_cadena_heartbeat.py` | Traduce incumplimientos de cadena a validación 400 | #3787 |
| `src/configuration/application/use_cases/configuracion/crear_configuracion_use_case.py` | Valida cadena y serializa configuración | #3787 |
| `src/configuration/application/use_cases/configuracion/actualizar_configuracion_use_case.py` | Valida cadena en PATCH conservando concurrencia | #3787 |
| `src/configuration/infrastructure/routers/configuracion_global_router.py` | Inyecta repositorio real de parámetros | #3787 |
| `src/telemetry/domain/repositories/parametros_heartbeat_port.py` | Contrato temporal y umbral SNR | #3786 |
| `src/telemetry/domain/repositories/diagnostico_heartbeat_port.py` | Documenta implementación real y límite de comparación FW | #3786 |
| `src/telemetry/infrastructure/adapters/parametros_heartbeat_mlops_adapter.py` | Lectura persistida, resolución por categoría y diagnóstico | #3786 |
| `src/telemetry/infrastructure/workers/postcommit_worker.py` | Composición real por transacción/etapa | #3786 |
| `src/telemetry/domain/entities/estado_dispositivo_iot.py` | Algoritmo único sin umbrales por defecto en Python | #3787 |
| `src/telemetry/application/use_cases/infraestructura/recibir_heartbeat_use_case.py` | Aplica política temporal y batería/RSSI/SNR al origen persistido | #3786/#3787 |
| `src/telemetry/application/use_cases/infraestructura/evaluar_estado_dispositivos_use_case.py` | Evaluación periódica dinámica, alertas y recuperación | #3787 |
| `src/telemetry/application/use_cases/infraestructura/transicion_comunicacion.py` | Comparte alertas y cierre de períodos entre ambos consumidores | #3787 |
| `main.py` | Inyecta política real al evaluador periódico | #3786/#3787 |
| `tests/telemetry/test_dev27_heartbeat_parametros.py` | Pruebas unitarias de parámetros, cadena y dominio | Todas |
| `tests/integration/test_dev27_heartbeat_parametros.py` | PostgreSQL/HTTP/worker/script reales y rollback | Todas |
| `tests/integration/test_dev05_ingesta_bplus_postcommit.py` | Configuración explícita de prueba y nueva prioridad canónica | #3786/#3787 |
| `tests/integration/test_dev12_heartbeat_extendido.py` | Regresión con el contrato real de configuración ausente | #3786 |
| `anotaciones/modulo_3/dev27_rf60_parametros_heartbeat_cadena_canonica.md` | Diagnóstico, evidencia, operación y pendientes | Todas |

Los 20 archivos Python llevan tabla de seguimiento con la identidad Git
consultada (`Leandro`) y la fecha real. No se modificaron los documentos de
pendientes ni `AGENTS.md` previamente presentes como archivos sin seguimiento.

## 7. Pruebas y verificaciones

Entorno: PostgreSQL 18 local efímero, puerto 55427, base `sgpmp_dev27_test`.
Se aplicó el historial Alembic existente hasta `e5a3c9b17d42`; no se creó migración.
Las inserciones del canal MQTT se representan mediante SQL/funciones reales;
esto no constituye una prueba del broker ni del firmware externos.

### Comando reproducible

En Linux, con `TEST_DATABASE_URL` y `DATABASE_URL` apuntando a PostgreSQL aislado:

```bash
python -m pytest tests/telemetry tests/configuration \
  tests/integration/test_dev27_heartbeat_parametros.py \
  tests/integration/test_dev05_ingesta_bplus_postcommit.py \
  tests/integration/test_dev12_heartbeat_extendido.py \
  tests/integration/test_dev14_parametros_dinamicos.py \
  --import-mode=importlib --basetemp=.pytest_cache/dev27_cierre_tmp \
  -q --tb=short --junitxml=.pytest_cache/dev27_cierre.xml
```

En esta máquina Windows, `tests/conftest.py` importa `fcntl` del módulo M02,
que no está disponible. Para ejecutar exclusivamente estas suites M03/M09 se
utilizó un puente de importación temporal en el proceso de prueba:

```powershell
.venv/Scripts/python.exe -c "import sys,types; sys.modules['fcntl']=types.SimpleNamespace(LOCK_EX=2,LOCK_NB=4,LOCK_UN=8,flock=lambda *a:None); import pytest; sys.exit(pytest.main(['tests/telemetry','tests/configuration','tests/integration/test_dev27_heartbeat_parametros.py','tests/integration/test_dev05_ingesta_bplus_postcommit.py','tests/integration/test_dev12_heartbeat_extendido.py','tests/integration/test_dev14_parametros_dinamicos.py','--import-mode=importlib','--basetemp=.pytest_cache/dev27_cierre_tmp','-q','--tb=short','--junitxml=.pytest_cache/dev27_cierre.xml']))"
```

No se modificó M02 ni se verificaron sus bloqueos de archivos; este puente no
valida concurrencia del buffer M02. `--basetemp` evita un directorio temporal de
Windows sin permisos; `--import-mode=importlib` evita colisiones entre nombres
de pruebas existentes en carpetas distintas.

| Verificación | Resultado / evidencia |
|---|---|
| Suite conjunta final | **977 aprobadas, 0 fallidas, 0 omitidas**, en 76.60 s; `.pytest_cache/dev27_cierre.xml` y `dev27_resumen_validacion.json` |
| Desglose sin duplicar casos | 278 de telemetría + 616 de configuración + 83 de integración PostgreSQL; las 59 dirigidas DEV-27 están incluidas en esos totales |
| Casos dirigidos DEV-27 previos al cierre | 59 aprobados (44 unitarios + 15 PostgreSQL), `.pytest_cache/dev27_dirigidas_final.xml` |
| Cadena inválida en PATCH | HTTP 400; valores originales conservados |
| Cadena válida en PATCH | HTTP 200; nueva configuración persistida |
| Heartbeat HTTP/SQL con batería crítica | Alerta CRITICO y etapa ALERTAS completada; reintento sin duplicación |
| Cambio persistido de batería | El mismo worker cambia de BATERIA_BAJA a BATERIA_CRITICA sin reinicio |
| Parámetro ausente y posterior carga | Etapa fallida trazable; tras configurar se recupera sin perder heartbeat |
| Ausencia de contacto | SIN_SEÑAL y posterior INACTIVO CRITICO según umbrales persistidos |
| Recuperación con telemetría válida | Conserva el contacto más reciente y cierra períodos al recuperar ACTIVO |
| Rollback de alerta | Estado, historial y períodos revertidos |
| Script real en subprocess | Simulación, aplicación, segunda ejecución conservadora y actualización explícita verificadas |
| AST y seguimiento | 20 archivos Python válidos, sin cabeceras faltantes |
| `git diff --check` | Sin errores |
| Bandit de archivos afectados | Gate alta severidad/alta confianza aprobado; informe `.pytest_cache/dev27_bandit_gate.txt` |
| Bandit nivel medio | Un B104 preexistente en `main.py` por bind 0.0.0.0, confirmado en HEAD; sin cambio en esa línea |

Se documentan los intentos iniciales: fallos de preparación por `fcntl`, nombres
de módulos repetidos y directorio temporal sin permisos; fixtures corregidos por
JSON literal interpretado como bind, identidad de cuenta activa incorrecta y
mezcla de sesiones del doble de prueba. La regresión adicional detectó una causa
de conectividad ausente al reclasificar un heartbeat antiguo, ya corregida junto
con sus pruebas. Los resultados finales sustituyen esos intentos, sin sumar
varias veces los mismos casos. No se presenta una suite de todo el backend como
ejecutada ni una integración desplegada como validada.

## 8. Estado y pendientes

| Tarea | Estado |
|---|---|
| #3785 | Claves y script implementados/verificados en PostgreSQL aislado; falta siembra efectiva DEV/TEST |
| #3786 | Adaptadores y composición reales implementados/verificados; activación externa exige configuración válida |
| #3787 | Umbrales, cadena 400 e INACTIVO CRITICO implementados/verificados en entorno aislado |
| #3696 | Implementación disponible para revisión; cierre pendiente de configuración y validación DEV/TEST |

Pendientes concretos:

1. Restablecer acceso a la base oficial DEV y confirmar destino TEST. Consultar su
   configuración real antes de aplicar el script.
2. Proporcionar valores aprobados para las diez claves sin default, según los
   tipos de dispositivo presentes; comprobar compatibilidad con F/T antes de sembrar.
3. Ejecutar simulación y siembra idempotente en ambos entornos; verificar allí el
   heartbeat crítico, etapa post-commit completada y transición por falta de contacto.
4. Formalizar P-1 en RF-18 y corregir la superposición de pasos 3/4 en RF-60.
5. Confirmar con FW-06 cualquier convención de versiones distinta de segmentos
   numéricos. Actualmente esos casos no se comparan de forma ficticia.

Las demás alertas G-11 (por ejemplo HEARTBEAT_AUSENTE, BUFFER_PROLONGADO y cierre
automático de alertas al reconectar) corresponden a su tarea específica y no se
presentan como implementadas por DEV-27. No se altera ese alcance.

## 9. Propuesta de PR

**Título:** `fix(rf60): parametrizar heartbeat y aplicar la cadena canónica (DEV-27)`

**Descripción:**

### Desvío y causa raíz

RF-60 clasificaba dispositivos con tiempos fijos y los adaptadores pendientes
impedían completar diagnósticos post-commit. RF-18 no contrastaba su configuración
con los intervalos y márgenes de heartbeat, e INACTIVO no escalaba a CRITICO.

### Cambios

- Amplía DEV-14 sobre JSONB con claves RF-60 y siembra idempotente; sin migración.
- Conecta adaptadores reales de parámetros y diagnóstico por etapa transaccional.
- Centraliza umbrales y orden canónico para worker/evaluador periódico.
- Valida la cadena y el margen con HTTP 400, también en POST/PATCH RF-18.
- Genera INACTIVO CRITICO y conserva deduplicación, historial transaccional y
  cierre de períodos al recuperar contacto.
- Incorpora pruebas HTTP, PostgreSQL, script, reintentos y regresiones M03/M09.

### Validación

977 pruebas aprobadas, 0 fallidas y 0 omitidas; incluyen 44 unitarias y 15 de
integración propias de DEV-27. PostgreSQL 18 aislado con las migraciones existentes.
AST, cabeceras de seguimiento y `git diff --check` correctos. Gate Bandit de alta
severidad aprobado; B104 medio preexistente de `main.py` documentado. En Windows
se utilizó el puente de importación `fcntl` descrito en este informe; no se probó
la exclusión de archivos de M02.

### Dependencias y pendientes de despliegue

Se utiliza la propuesta P-1 de Desarrollo. Falta aplicar la configuración aprobada
en DEV/TEST por indisponibilidad de acceso DEV, destino TEST no confirmado y
valores operativos sin default. No se afirma una siembra externa realizada ni
soporte de formatos de firmware no confirmados. La evidencia de pruebas se
detalla en este informe.

Referencias: #3696, #3785, #3786, #3787.
