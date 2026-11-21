# DEV-07 — Observaciones de visión con el sobre D4

Historia #3525, subtareas #3607/#3608. Verificación: 2026-10-19.
Rama `fix/dev07-vision-contrato-d4`; base DEV-06 `1d503b51`.

## 1. Resumen

Se implementó el sobre D4 v1 en `POST /iot/telemetria/vision`, manteniendo el
lote anterior bajo autenticación de servicio del broker. Se validan estructura,
componentes canónicos, fechas con zona, identidad y asociación cámara/área.
DB-03 conserva la ventana original y el objeto de versiones de la cascada.
El backend sigue calculando la aptitud y ningún campo del cliente la determina.

La persistencia y el consumo RF-24 se verificaron con PostgreSQL real aislado.
No se declara entrega a un motor IA real ni cumplimiento integral del RF-62
actualizado: la fórmula ponderada, nuevos estados y metadata requieren alinear
el esquema y la configuración existentes. Esta limitación es distinta de los
dos campos ya cubiertos por DB-03.

## 2. Matriz de diagnóstico

| Componente | Estado al iniciar | Desvío | Cambio / estado final |
|---|---|---|---|
| DTO | Solo device_id/serial/lote, vector libre | No recibe D4 singular | DTO D4 estricto más lote compatible |
| Autenticación | DEV-06 disponible en rama, no integrado en dev | Serial solo no debe autenticar | Rama basada en DEV-06; token real reutilizado |
| Componentes | Diccionario libre de floats finitos | Sin conjunto ni rangos canónicos | Tres componentes obligatorios, rangos RF-53/RF-56 |
| Calidad | Cobertura/tracks/fps y catálogo heredado | Estados distintos del RF actualizado | Preservado y explicitado; transición normativa pendiente |
| Inicio de ventana | No se transporta ni persiste | Se pierde la ventana | Mapeo DB-03 `fecha_inicio_ventana` |
| Versiones | Sin campos | Se pierde trazabilidad por componente | Objeto DB-03 `json_version_cascada` |
| Aptitud | Promedio heredado de cuatro dimensiones | No corresponde a fórmula ponderada nueva | Backend conserva compatibilidad; brecha documentada |
| RF-56 | Consolida eventos Edge; no consume visión directamente | Contrato de entrega de visión no implementado | Datos persistidos disponibles; no se fabrica integración IA |
| RF-24 | Adaptador real ya lee esta tabla y el flag backend | No necesitaba otro repositorio | Reutilizado y probado con D4 persistido |
| Deduplicación | Precheck y UNIQUE cámara/fecha | Carrera puede producir conflicto | INSERT ON CONFLICT DO NOTHING sobre la misma clave |
| Pruebas | Archivo de visión importa main/M02 | fcntl impide colección en Windows | Nuevas pruebas independientes de main, más regresiones |

## 3. DB-03 y destinos consultados

Se reutilizó la migración de Samuel `65541db23c71`, commit `80238afc`, rama
`feature/aiot-db03-columnas-heartbeat-vision`, padre `3a9d5e7c1b24`.
Sus nombres físicos son `fecha_inicio_ventana TIMESTAMPTZ` y
`json_version_cascada JSONB`, nullable; no `ventana_inicio/version_cascada`.

El usuario informa DB-03 aplicada. La consulta autorizada de solo lectura sobre
`sgpmp_dev` por 5447 no mostró esos campos en `information_schema` ni en
`pg_catalog`; tampoco la conexión local `.env` a `integrador` por 5432.
Se documenta esa fotografía de los destinos consultados, sin afirmar que no
esté aplicada en otro destino. No se modificó ninguna de esas bases.

Para verificar código y esquema se creó PostgreSQL 18.4 aislado, se aplicó el
baseline y el upgrade exacto de DB-03 mediante `Operations.context`. No se creó
otra migración ni se incluyó DDL de Samuel dentro de este PR. El registro
Alembic de la instancia aislada conserva el baseline; DB-03 se registra como
aplicación adicional en la evidencia, no como revisión desplegada de DEV.

## 4. D4 frente a RFC-011 vigente

Los RF entregados sí integran formalmente RFC-011 y AIOT-SPEC-01 el 2026-10-16.
Ese punto documental de AN-1 tiene evidencia; no se mantiene como "sin fórmula".
Persisten discrepancias de compatibilidad:

- D4 usa `serial/calidad`; los nombres equivalentes
  `dispositivo_serial/indicadores_calidad` se admiten como aliases. Si se
  envían ambos nombres, deben coincidir.
- D4 incluye `n_tracks` y versiones. El RF agrega `n_individuos_observados`,
  `tipo_dato` y `origen`; no se inventan ni se confunden individuos con tracks.
  No existe almacenamiento de esos campos en la tabla revisada; se rechazan
  en esta versión en vez de aceptarlos y descartarlos.
- El catálogo SQL vigente solo admite `CALIBRADA/DEGRADADA/SIN_DETECCION`;
  el RF exige `CALIBRADO/EN_CALIBRACION/SIN_LINEA_BASE`. No son aliases
  intercambiables por simple parecido de texto.
- El cálculo heredado usa pesos iguales, mientras la especificación nueva
  define suma ponderada, modificador por calibración, parámetros M09 y flags.
  Esa configuración y metadata no existen en el esquema inspeccionado.
- El RF aclara explícitamente que `ventana_fin` define la captura; se usa esa
  relación documentada y se conserva inicio sin reemplazarlo por recepción.

La parte compatible se implementó sin sustituir unilateralmente D4 por otra
interpretación ni cambiar el cálculo anterior. La ampliación normativa precisa
está en [la solicitud de compatibilidad](dev07_solicitud_compatibilidad_rfc011.md).
No fue enviada automáticamente.

## 5. Contrato implementado #3607

Ejemplo estructural; `CALIBRADA` es un literal real del catálogo vigente:

```json
{
  "serial": "CAMARA-001",
  "area_id": 15,
  "ventana_inicio": "2026-10-19T14:00:00Z",
  "ventana_fin": "2026-10-19T14:01:00Z",
  "componentes": {"densidad_actividad": 0.65, "dispersion_espacial": 2.4, "tasa_movimiento": 1.8},
  "calidad": {"cobertura_ventana": 0.95, "n_tracks": 20, "n_tracks_perdidos": 2, "fps_efectivo": 24.5, "estado_calibracion": "CALIBRADA"},
  "version_cascada": {"detector": "1.0.0", "seguimiento": "1.0.0", "metricas": "1.0.0", "anomalias": "1.0.0"}
}
```

Requiere `Authorization: Bearer <token de servicio>`, configurado por
`BROKER_SERVICE_TOKEN` mediante DEV-06. Falta/incorrecto: 401;
integración sin token configurado: 503. No se agregaron credenciales al código.

Se resuelve el serial en M09 y se comprueban existencia, dispositivo activo,
categoría CAMARA y área asociada. Un token válido no omite estas comprobaciones.
La consulta anterior por device_id/serial se conserva para el lote compatible.

El nuevo DTO rechaza campos desconocidos y bloques incompletos, valores no
finitos, densidad fuera de [0,1], dispersión/movimiento negativos, tracks no
enteros/no representables por INTEGER, fps negativo/no representable por su
tipo normativo y versiones vacías. No se presume SemVer para los strings de
versión de los componentes. Las fechas requieren zona e inicio < fin; se
convierten a UTC y se conserva la validación temporal del caso de uso existente.

`apto_para_ia`, `es_apto_para_ia`, índice o clase enviados por el cliente se
rechazan; no se aceptan como decisiones de calidad. Los contratos D4 y lote
no se mezclan mediante extra fields ignorados.

## 6. Persistencia #3608

La entidad incorpora inicio y versiones opcionales. El repositorio guarda:

| D4 | Tabla observaciones_vision |
|---|---|
| `ventana_inicio` | `fecha_inicio_ventana` |
| `ventana_fin` | `fecha_observacion` |
| `version_cascada` | `json_version_cascada`, objeto estructurado |
| `componentes` | `json_vector`, solo los tres componentes |
| Calidad | Columnas de cobertura/tracks/fps/estado existentes |
| Resultado backend | Índice, clase y `es_apto_para_ia` existentes |

El lote anterior persiste NULL en los campos nuevos. Se mantiene su respuesta
y se agregan ventana/versiones de forma aditiva. NIC41 siempre false.

Se conserva exactamente la UNIQUE de cámara/fecha. El precheck evita consultas
innecesarias y el INSERT ON CONFLICT cubre carreras entre procesos. Un reenvío
incrementa duplicadas y no sobrescribe ventana, versiones ni vector original.
El repositorio no confirma transacciones; el caso de uso confirma el lote o lo
revierte completo, incluyendo errores posteriores al INSERT.

No se cambió la clave por la mención normativa a cuatro campos/origen: falta
precisar su aplicación al dato de visión y coordinar su soporte de esquema.

## 7. Integraciones y aptitud

El backend conserva la función heredada de calidad: cuatro dimensiones, pesos
iguales y tramos 80/40. Una observación degradada puede ser apta con reserva;
el solo hecho de llegar al endpoint no la hace apta. La nueva fórmula ponderada
no se presenta como implementada. Los comentarios anteriores que afirmaban
que todavía no existía fórmula normativa fueron corregidos.

`ObservacionVisionM03Adapter` ya entrega el flag backend y los componentes a
RF-24. Una prueba integra 40 observaciones D4 persistidas, el adaptador real y
el caso de uso real de calibración: obtiene resultado EXITOSA. Las salidas de
calibración/publicación/auditoría se aíslan con dobles; no se afirma persistencia
real de una nueva línea base en esa prueba.

No existe en esta base un consumidor RF-56 de visión conectado a IA. No se
inventó un envío ni se modificó el stub de inferencia de otra tarea. Los datos
quedan en la fuente real que RF-24 ya consume, sin pérdida de sus metadatos.
BRK-03 y el hardware de cámara no están presentes en este workspace; las
pruebas HTTP no equivalen a una ejecución MQTT/hardware real.

## 8. Archivos

Rutas relativas a la raíz del repositorio:

| Archivo | Responsabilidad |
|---|---|
| `src/telemetry/infrastructure/dto/observacion_vision_d4_dto.py` | Sobre estricto, componentes, calidad, versiones, aliases y ventana |
| `src/telemetry/infrastructure/dto/ingerir_observaciones_vision_dto.py` | Mantiene lote compatible y rechaza extras ambiguos |
| `src/telemetry/domain/entities/observacion_vision.py` | Transporta ventana/versiones y documenta la fórmula heredada |
| `src/telemetry/domain/repositories/dispositivo_port.py` | Resolución de cámara por serial |
| `src/telemetry/infrastructure/adapters/dispositivo_m09_adapter.py` | Consulta real M09 reutilizada por identidad vieja/nueva |
| `src/telemetry/domain/repositories/observacion_vision_repository.py` | None ante duplicado concurrente |
| `src/telemetry/infrastructure/models/observacion_vision_model.py` | Mapeo DB-03 existente |
| `src/telemetry/infrastructure/repositories/observacion_vision_repository.py` | Persistencia y deduplicación atómica |
| `src/telemetry/application/use_cases/ingesta/ingerir_observaciones_vision_use_case.py` | Normalización, validación y transacción común |
| `src/telemetry/infrastructure/routers/telemetria_router.py` | Publica ambos contratos con autenticación existente |
| `src/telemetry/infrastructure/schema/telemetria_schema.py` | Respuesta con ventana/versiones |
| `tests/telemetry/test_dev07_vision_d4.py` | Contrato y casos de uso sin main |
| `tests/integration/test_dev07_vision_d4.py` | PostgreSQL, seguridad, concurrencia, rollback y RF-24 |
| `anotaciones/modulo_3/api_reference_m03_telemetria_iot.md` | Contrato actualizado |

## 9. Verificación

Las 46 nuevas unitarias y las 15 integraciones nuevas aprobaron. No se suman
las ejecuciones enfocadas otra vez al total de regresión. La evidencia
sanitizada se conserva en `rf53_dev07_validacion.json`.

| Grupo | Aprobadas | Fallidas | Omitidas |
|---|---:|---:|---:|
| Telemetría, incluidas 46 nuevas unitarias | 76 | 0 | 0 |
| PostgreSQL DEV-07, todas nuevas | 15 | 0 | 0 |
| Configuración M09 | 555 | 1 | 0 |
| Predicción M04 | 23 | 0 | 0 |
| Shared seleccionado | 73 | 0 | 0 |
| **Total distinto** | **742** | **1** | **0** |

Las 61 pruebas nuevas aprobaron. El fallo restante es el previo
`test_la_aplicacion_sirve_el_directorio_de_logotipos`, que importa main/M02 y
requiere fcntl. Tres archivos no recolectables por esa dependencia se listan
aparte en la evidencia; no se inventa el número de casos que contienen.
Compilación, diff-check y Bandit aprobaron; no se ejecutó Semgrep.

Comandos ejecutados:

```powershell
.venv/Scripts/python.exe -m pytest --confcutdir=tests/telemetry tests/telemetry/test_dev07_vision_d4.py -q --tb=short --junitxml=.dev07-unit.xml
.venv/Scripts/python.exe -m pytest --confcutdir=tests/telemetry tests/telemetry -q --ignore=tests/telemetry/test_inc_m09_77_g137_observaciones_vision.py --ignore=tests/telemetry/test_dev06_token_servicio_broker.py --junitxml=.dev07-telemetry.xml --tb=short
# TEST_DATABASE_URL y DATABASE_URL solo en la instancia aislada:
.venv/Scripts/python.exe -m pytest --confcutdir=tests/integration tests/integration/test_dev07_vision_d4.py -q --tb=short --junitxml=.dev07-integration.xml --basetemp=<temporal-propio>/pytest-integracion
.venv/Scripts/python.exe -m pytest --confcutdir=tests/configuration tests/configuration -q --ignore=tests/configuration/test_inc_m09_75_g142_disparo_automatico_vision.py --basetemp=<temporal-propio>/pytest-configuracion --junitxml=.dev07-configuracion.xml --tb=short
.venv/Scripts/python.exe -m pytest --confcutdir=tests/prediction tests/prediction -q --junitxml=.dev07-prediccion.xml --tb=short
.venv/Scripts/python.exe -m pytest --confcutdir=tests/shared tests/shared/test_db_error_translator.py tests/shared/test_error_handlers_globales.py tests/shared/test_contexto_rls.py tests/shared/test_database_reintentos.py tests/shared/test_orm_foreign_keys_resolvibles.py -q --junitxml=.dev07-shared.xml --tb=short
.venv/Scripts/python.exe -m compileall -q src/telemetry src/configuration/infrastructure/adapters/observacion_vision_m03_adapter.py
uv tool run --offline bandit -f json -q <archivos Python de producción modificados>
git diff --check
```

Los archivos excluidos importan main y M02/fcntl, no disponible en Windows.
No se modifican para forzar aprobación. La autenticación del nuevo endpoint
sí se verifica mediante el router real en las pruebas PostgreSQL.

## 10. Entrega y pendientes

- Parte D4 compatible implementada, persistida y probada; lote anterior conservado.
- DB-03 reutilizada, sin nueva migración ni cambios en bases compartidas.
- Confirmar el destino donde el usuario aplicó DB-03 para verificar ese despliegue.
- Integrar DEV-06 antes de este cambio; la comparación inmediata es contra su rama, no contra dev sin esa dependencia.
- Alinear el sobre ampliado, catálogos, metadata y configuración M09 descritos en la solicitud. No declarar cerrado todo el RF actualizado.
- Validar BRK-03/hardware y definir el consumo real RF-56 sin confirmaciones ficticias de entrega.
- Ejecutar los archivos dependientes de fcntl en un entorno compatible.
- La evaluación heredada se ejecuta en la ingesta; la especificación posterior exige calidad asíncrona. Su adopción debe coordinarse con el almacenamiento y la política ponderada, sin presentarla como implementada aquí.
- No se realizaron push ni mensajes a terceros. El hash del commit local se comunica en la entrega.
- PostgreSQL temporal detenido y eliminado; evidencia sanitizada conservada y auxiliares de prueba retirados.
