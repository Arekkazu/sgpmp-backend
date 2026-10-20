# DEV-12 — Heartbeat extendido y diagnóstico técnico RF-60

Historia #3524; subtareas #3603–#3606. Verificación: 2026-10-19.
Rama `fix/dev12-heartbeat-extendido`, basada en DEV-05 `07db21e0`.

## 1. Resumen y estado real

Se implementaron los dos campos opcionales del heartbeat, su persistencia con
el esquema DB-03 existente y la alerta `SENSOR_FISICO_FALLIDO`. HTTP y las
escrituras SQL del broker usan las mismas etapas post-commit de DEV-05.

Se incorporó la evaluación de sobrecalentamiento y la generación de alerta de
firmware a partir de un puerto de política explícito. **Estas dos alertas no
están habilitadas con configuración real en producción:** faltan la fuente M09
de sus parámetros y la convención/comparador aprobado por FW-06. El worker
registra estas dependencias como etapas fallidas pendientes de reintento, sin
confirmar evaluaciones ficticias y sin impedir la alerta de sensor fallido.

No se declara completada toda #3524. No hay una nueva migración ni se ha
modificado `sgpmp_dev`.

## 2. Diagnóstico previo y dependencias

| Componente | Estado al iniciar | Desvío / acción |
|---|---|---|
| DTO HTTP | Sin los dos campos opcionales | Extender validación y transporte |
| Entidad, ORM y repositorio | Sin los campos | Mapear las columnas reales DB-03 |
| DB-03 | Migración existente en otra rama, fuera de `dev` | Reutilizar `65541db23c71`, sin duplicar DDL |
| Esquema efectivo `sgpmp_dev` | Sin `json_sensores_operativos` ni `temperatura_dispositivo` | Pendiente integrar y aplicar la migración existente |
| Catálogo técnico | Contiene las tres causas | Reutilizar `alertas`, tipo `TECNICA`, origen `HEARTBEAT` |
| SENSOR_FISICO_FALLIDO | Sin evaluación backend | Implementado con detalle y deduplicación |
| SOBRECALENTAMIENTO | Sin umbral autorizado ni fuente persistente M09 | Evaluador y etapa preparados; política real pendiente |
| FIRMWARE_DESACTUALIZADO | Versión instalada persistida, sin mínimo ni convención aprobados | Puerto de comparación explícito; integración real pendiente |
| DEV-05 | Disponible en rama, no integrado en `origin/dev` | Base de esta rama, se reutiliza su worker y evidencia durable |
| DEV-14 | Parte MLOps disponible en otra rama; configuración de dispositivos pendiente | No almacenar umbrales de dispositivos en MLOps como atajo |
| BRK-07 | Contrato documentado, implementación no disponible en este workspace | Se prueba el INSERT equivalente, no MQTT real |
| FW-06 | Contrato concreto no encontrado | No asumir SemVer ni ordenar versiones como texto |
| DEV-06 | Disponible en otra rama, fuera de esta base | Autenticación actual conservada; coordinar integración del token |

Se leyeron los RF actualizados y los documentos entregados con sufijo `(1)`:
acuerdo consolidado AIoT, D11/P2/P4, y reparto de tareas DB-03/DEV-12.
Los documentos son referencia funcional, no autorización para desplegar cambios
o contactar a otros responsables.

### Confirmación de la migración que ya existía

Rama remota: `origin/feature/aiot-db03-columnas-heartbeat-vision`.
Commit: `80238afc`. Archivo:

```text
alembic/versions/65541db23c71_db03_columnas_heartbeat_y_vision.py
revision = 65541db23c71
down_revision = 3a9d5e7c1b24
```

La migración agrega `heartbeats.json_sensores_operativos JSONB` y
`heartbeats.temperatura_dispositivo NUMERIC(5,2)`, ambas nullable. También agrega
campos de visión; no se reimplementan aquí. El nombre del sobre permanece
`sensores_operativos`, traducido por el mapeo ORM a `json_sensores_operativos`.

La consulta real de `sgpmp_dev` se hizo con `transaction_read_only=on` y confirmó
la ausencia de ambas columnas. `member_dev` no tiene SELECT sobre
`public.alembic_version`, por lo que no se afirma una revisión desplegada:
la comprobación se basa en el esquema efectivo de `information_schema`.

**No hay que pedir otra migración a Samuel para esos dos campos.** Hay que
integrar y aplicar la existente en los entornos autorizados. Esta migración no
agrega los parámetros operativos M09 solicitados por DEV-14: son dependencias
distintas. Tampoco existe configuración remota equivalente para temperatura
interna o versión mínima de firmware en el esquema inspeccionado.

## 3. Contrato HTTP y persistencia #3603

`POST /iot/heartbeat` conserva headers, campos anteriores y HTTP 200 de aceptación.
Los campos nuevos son opcionales y admiten null de acuerdo con las columnas:

```json
{
  "sensores_operativos": [
    {"sensor": "sensor_temperatura", "operativo": true},
    {"sensor": "sensor_humedad", "operativo": false}
  ],
  "temperatura_dispositivo": 45.5
}
```

Este fragmento no sustituye el body completo: se conservan `tipo_mensaje`,
`fecha_registro` y los demás campos del contrato previo.

- `sensor`: string no vacío después de la normalización de espacios existente;
  no se impone una longitud/regex nueva ni se convierte en un ID SQL inventado.
- `operativo`: booleano estricto; no acepta `0`, `1` ni strings `"false"`.
- Cada elemento requiere sus dos propiedades y rechaza propiedades ajenas.
- Temperatura: número JSON finito en °C. Se valida la representación de
  `NUMERIC(5,2)` para evitar overflow o redondeo implícito al persistir;
  no es un rango físico o clínico inventado.
- Omitido/null significa sin reporte. `[]` significa reporte sin elementos.
  Ninguno de esos casos genera fallo de sensor ni sobrecalentamiento.

La respuesta incorpora ambos campos de forma aditiva. El repositorio guarda
SQL NULL cuando falta el JSON, conserva `[]` y recupera el contenido almacenado.
Un error de commit no devuelve una aceptación falsa.

## 4. Evaluación común después del commit #3604

El endpoint solo valida identidad y confirma el heartbeat. El broker conserva
su INSERT. El worker de DEV-05 recupera la fila persistida en ambos casos.

Se agregaron tres etapas independientes, dependientes de `HEARTBEAT_ESTADO`:

```text
HEARTBEAT_SENSORES
HEARTBEAT_TEMPERATURA
HEARTBEAT_FIRMWARE
```

Se seleccionan únicamente filas que reportan el dato correspondiente. Los
heartbeats antiguos sin estos datos conservan sus etapas anteriores. Una
etapa pendiente no impide completar las otras.

Se reutilizan los locks por fila/dispositivo, las transacciones con savepoints,
la espera de reintento y la evidencia RF-63 existentes. Alerta y evidencia de
finalización se confirman juntas. Si falla la persistencia, ambas se revierten;
el heartbeat original permanece y el intento fallido se registra aparte.

### Sensor físico fallido

Cualquier `operativo: false` genera una alerta técnica MODERADO con causa
`SENSOR_FISICO_FALLIDO`. La alerta conserva `id_heartbeat` y el conjunto ordenado
de identificadores fallidos en `metadato_evento`. No se cambia el estado operativo
del dispositivo por el fallo; el trigger conserva contacto y reconexión.

Se mantiene la política de alerta activa por dispositivo/causa y se distingue
el conjunto de sensores afectados. Un conjunto equivalente, incluso en otro
orden o con identificadores repetidos, no crea otra alerta activa. Un conjunto
distinto no queda suprimido por la alerta anterior. Se consolida el reporte
fallido; no se crean alertas separadas por cada sensor. El historial inicial lo
crea el trigger existente, sin duplicar una inserción manual.

El JSON que llega por INSERT directo también se valida al procesarlo. Si es
incompatible, su etapa queda fallida con evidencia; no se transforma un string
`"false"` en una confirmación o diagnóstico válido.

La correspondencia entre identificador D11 y variable/sensor de RF-58/RF-59
no está formalizada por el contrato disponible. No se actualizan sensores
SQL por coincidencias supuestas de nombres ni se declara implementada esa
propagación como parte de este cambio.

### Sobrecalentamiento y firmware #3605

`DiagnosticoHeartbeatPort` declara las dependencias que debe satisfacer la
configuración real por dispositivo/familia:

- `obtener_umbrales_temperatura(id_dispositivo)`: límite máximo operativo y,
  cuando lo defina la política autorizada, límite crítico.
- `comparar_firmware(id_dispositivo, version_instalada)`: mínimo aplicable y
  resultado de comparación según la convención aprobada por FW-06.

Son contratos internos preparados para integración, no un adaptador persistente
ya conectado a M09. No se agrega un stub exitoso ni una configuración por defecto.

El evaluador térmico usa `temperatura > máximo` y puede generar MODERADO o
CRITICO con los límites inyectados. La evaluación de firmware genera
`FIRMWARE_DESACTUALIZADO` LEVE únicamente si el puerto confirma que la versión
es anterior, conservando instalada y mínima en metadata. No compara strings.

La composición de producción todavía no tiene esa política. Si se necesita,
produce errores visibles para la etapa post-commit:

```text
UMBRAL_SOBRECALENTAMIENTO_NO_DISPONIBLE
POLITICA_FIRMWARE_NO_DISPONIBLE
```

El heartbeat se conserva y la etapa queda pendiente; HTTP 200 solo confirma
recepción persistida, no una evaluación que no ocurrió. Los parámetros y la
convención deben acordarse antes de habilitar ambas alertas con datos reales.

En DEV se observaron versiones como `0.1.0`, `v1.9.5`, `pi-test` y `demo-1.0`.
Eso no prueba un contrato SemVer único. No se verificó una comparación real
`1.10.0` frente a `1.9.0`; permanece pendiente de FW-06.

## 5. Archivos modificados

Rutas relativas a la raíz del repositorio:

| Archivo | Responsabilidad del cambio |
|---|---|
| `src/telemetry/infrastructure/dto/heartbeat_dto.py` | DTO de sensor y validación de los campos opcionales |
| `src/telemetry/domain/entities/heartbeat.py` | Transportar datos extendidos sin dependencia ORM |
| `src/telemetry/infrastructure/models/heartbeat_model.py` | Mapeo físico DB-03 existente |
| `src/telemetry/infrastructure/repositories/heartbeat_repository.py` | Persistir y reconstruir los campos |
| `src/telemetry/infrastructure/schema/heartbeat_schema.py` | Respuesta compatible y aditiva |
| `src/telemetry/application/use_cases/infraestructura/recibir_heartbeat_use_case.py` | Transportar los nuevos datos antes del commit |
| `src/telemetry/application/use_cases/infraestructura/evaluar_diagnostico_heartbeat_use_case.py` | Evaluador compartido sin commits propios |
| `src/telemetry/domain/repositories/diagnostico_heartbeat_port.py` | Contrato explícito pendiente de configuración/comparación |
| `src/telemetry/domain/repositories/alerta_repository.py` | Ampliación compatible del filtro de alerta técnica |
| `src/telemetry/infrastructure/repositories/alerta_repository.py` | Deduplicar por conjunto de sensores fallidos |
| `src/telemetry/domain/repositories/postcommit_port.py` | Nuevas etapas y requisito de estado |
| `src/telemetry/infrastructure/repositories/postcommit_repository.py` | Seleccionar solo campos reportados |
| `src/telemetry/infrastructure/workers/postcommit_worker.py` | Composición única para HTTP y SQL/MQTT |
| `tests/telemetry/test_dev12_heartbeat_extendido.py` | Contrato, diagnóstico y errores de persistencia |
| `tests/integration/test_dev12_heartbeat_extendido.py` | PostgreSQL, HTTP, worker, reintentos y rollback |
| `anotaciones/modulo_3/api_reference_m03_telemetria_iot.md` | Actualización del contrato documentado |

## 6. Verificación #3606

La integración se ejecutó en PostgreSQL 18.4 local aislado, sobre el baseline
`3a9d5e7c1b24` y aplicando el `upgrade()` exacto de la migración DB-03 obtenida
de su rama. No se copió permanentemente al PR ni se creó DDL alternativo.
La tabla de Alembic conserva el baseline; la aplicación aislada de DB-03 se
documenta por separado, sin atribuir una revisión desplegada a DEV.

La equivalencia MQTT se comprueba mediante el INSERT que consume el backend;
no se declara una ejecución real del broker o del firmware. Las pruebas térmicas
y de firmware inyectan dobles del puerto; no prueban una configuración real M09.

Los resultados y casos individuales se conservan en
[`rf60_dev12_validacion.json`](rf60_dev12_validacion.json). Las ejecuciones
enfocadas preliminares no se suman otra vez a las regresiones.

| Grupo | Aprobadas | Fallidas | Omitidas | Xfail previos |
|---|---:|---:|---:|---:|
| Telemetría (incluye 44 nuevas unitarias) | 90 | 0 | 0 | 0 |
| Integración DEV-12/DEV-05 (incluye 18 nuevas) | 46 | 0 | 1 | 2 |
| Configuración M09 | 555 | 1 | 0 | 0 |
| Predicción M04 | 23 | 0 | 0 | 0 |
| Shared seleccionado | 73 | 0 | 0 | 0 |
| **Total distinto** | **787** | **1** | **1** | **2** |

Se ejecutaron 791 casos distintos; las 62 pruebas nuevas de DEV-12 aprobaron.
El fallo M09 es `test_la_aplicacion_sirve_el_directorio_de_logotipos`, por
`ModuleNotFoundError: fcntl`. La omisión corresponde al escenario que requiere
DEV-02; los dos xfail documentan contratos DB-02 aún pendientes en el baseline.

Se verificaron persistencia/recuperación de ambos campos, identidad HTTP,
ausencia/null/arreglo vacío, equivalencia HTTP/INSERT, detalle del sensor,
historial inicial único, deduplicación con orden distinto, fallos de sensores
distintos, errores de configuración independientes, rollback después de insertar
la alerta y recuperación posterior, JSON inválido del broker y ausencia de
visibilidad de un heartbeat sin commit desde otra conexión.

No se ejecutaron por dependencia la lectura real de parámetros térmicos/firmware
desde M09, el comparador real de versiones ni el flujo MQTT con broker y firmware.
No se contabilizan como aprobadas las pruebas de esas integraciones pendientes.

### Comandos

```powershell
.venv/Scripts/python.exe -m pytest --confcutdir=tests/telemetry tests/telemetry -q --ignore=tests/telemetry/test_inc_m09_77_g137_observaciones_vision.py --junitxml=.dev12-telemetry.xml --tb=short
# TEST_DATABASE_URL y DATABASE_URL apuntaron exclusivamente a la base temporal:
.venv/Scripts/python.exe -m pytest --confcutdir=tests/integration tests/integration/test_dev12_heartbeat_extendido.py tests/integration/test_dev05_ingesta_bplus_postcommit.py -q --tb=short --junitxml=.dev12-integration.xml --basetemp=<temporal-propio>/pytest-integracion-final
.venv/Scripts/python.exe -m pytest --confcutdir=tests/configuration tests/configuration -q --ignore=tests/configuration/test_inc_m09_75_g142_disparo_automatico_vision.py --basetemp=<temporal-propio>/pytest-configuracion --junitxml=.dev12-configuracion.xml --tb=short
.venv/Scripts/python.exe -m pytest --confcutdir=tests/prediction tests/prediction -q --junitxml=.dev12-prediccion.xml --tb=short
.venv/Scripts/python.exe -m pytest --confcutdir=tests/shared tests/shared/test_db_error_translator.py tests/shared/test_error_handlers_globales.py tests/shared/test_contexto_rls.py tests/shared/test_database_reintentos.py tests/shared/test_orm_foreign_keys_resolvibles.py -q --junitxml=.dev12-shared.xml --tb=short
.venv/Scripts/python.exe -m compileall -q src/telemetry tests/telemetry/test_dev12_heartbeat_extendido.py tests/integration/test_dev12_heartbeat_extendido.py
uv tool run --offline bandit -f json -q <archivos Python de producción modificados>
git diff --check
```

La ejecución total y las omisiones se resumen en la evidencia JSON. No se
declara una suite completa del backend aprobada: el entorno Windows no puede
importar `fcntl` desde M02. El fallo de aplicación completa y los dos archivos
no recolectables por ese motivo son previos a DEV-12. Los xfail DB-02 y la
omisión DEV-02 pertenecen a la regresión heredada de DEV-05, sin debilitarla.

## 7. Estado de entrega y pendientes

- #3603: contrato, entidad, mapeo y persistencia implementados y probados con DB-03.
- #3604: sensor fallido operativo; sobrecalentamiento probado con política inyectada, fuente persistente pendiente.
- #3605: generación y trazabilidad preparadas; mínimo, formato y comparador FW-06 reales pendientes.
- #3606: pruebas del alcance disponible ejecutadas; límites de cobertura registrados.
- Integrar y desplegar DB-03 existente antes de desplegar este ORM. El código requiere sus columnas incluso para filas antiguas.
- Integrar DEV-05 antes de DEV-12. La base de revisión inmediata es `fix/dev05-ingesta-bplus-postcommit`; comparar contra `dev` antes de integrar DEV-05 mostraría también esa dependencia.
- Recibir la definición de temperatura máxima/criticidad y mínimo de firmware por alcance, su almacenamiento M09 y la convención FW-06. No se solicita otra vez la migración ya existente de heartbeat.
- Coordinar BRK-07/FW-06/DEV-06 para verificar el flujo MQTT real, payload y autenticación del broker.
- Integrar DEV-14 por separado; sus parámetros MLOps no sustituyen configuración operativa de dispositivos.
- No se realizaron push, cambios de producción, migraciones compartidas ni mensajes a otros responsables.
- La instancia PostgreSQL temporal fue detenida y eliminada tras conservar la evidencia sanitizada; no quedan auxiliares de pruebas en el repositorio.

El commit local de DEV-12 contiene su ampliación sobre DEV-05; no incorpora
la solución DEV-14 ni la migración de Samuel. El hash se comunica en la entrega.
