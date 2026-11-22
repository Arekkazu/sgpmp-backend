# RF-56 DEV-17 — Stub de inferencia y paquetes pendientes

Fecha: 2026-10-15. Historia #3513, épica #3503, subtareas #3568 y #3569.

## 1. Diagnóstico

### Hechos confirmados antes del cambio

- `MotorInferenciaStubAdapter.enviar_paquete` devolvía `True` sin realizar I/O.
- `ConsolidarEnviarPaqueteUseCase` guardaba el paquete en PENDIENTE, confirmaba
  esa transacción, llamaba al motor y guardaba ENVIADO si recibía un valor positivo.
- Un retorno `False` o una excepción genérica producían FALLIDO y un intento.
  Por ello, sustituir únicamente `True` por `False` no satisfacía DEV-17.
- El enum de dominio y el enum PostgreSQL contienen exactamente ENVIADO,
  PENDIENTE y FALLIDO. No era necesaria una migración ni un estado nuevo.
- La recepción confirma el evento en una transacción anterior a la del paquete.
  Si falla el paquete, el request propaga el error y el evento ya confirmado
  permanece almacenado. No se debe responder 201 si esa persistencia falla.
- El puerto de paquetes solo tenía guardar/actualizar_estado. No permitía
  recuperar por evento ni reutilizar un paquete al reconsolidarlo.
- No existe una restricción UNIQUE por evento en paquetes_inferencia ni una
  clave externa de idempotencia en el DTO de recepción.
- Solo se encontró el adaptador stub del puerto de inferencia. No existe una
  entrega real a IA que pueda certificarse con este checkout.
- El router existente es `POST /iot/eventos-edge`, autenticado mediante
  device_id/sensor_id/access_key. No se encontró un endpoint interno RF-56
  autenticado con token de servicio de broker.

La causa raíz era una confirmación ficticia en infraestructura interpretada
como entrega por aplicación. Violaba P7 y producía un estado de trazabilidad
que no representaba una comunicación real.

### Fuentes y decisiones pendientes

Se revisaron el código RF-56, sus puertos/adaptadores/repositorios, los modelos,
el baseline y migraciones, la documentación M03 y la ficha funcional RF-56
proporcionada. También se contrastó el esquema mediante consultas a PostgreSQL
aislado con todas las migraciones existentes aplicadas.

No se encontraron `AIOT-DEV-03_Acuerdo_Consolidado_Desarrollo_AIoT.md` ni
`AIOT-DEV-01` en el repositorio o entre los archivos AIoT disponibles en Downloads.
No se afirma que IA-1 y la pregunta 6 sean la misma decisión. Los principios
P1–P7 se aplican conforme a las instrucciones explícitas de esta tarea.

La posibilidad de pérdida silenciosa en una futura producción AIoT es el
riesgo descrito por la tarea, no una entrega real observada durante estas pruebas.

### Flujo anterior

```text
Evento persistido → paquete PENDIENTE persistido → stub devuelve True
                 → actualización ENVIADO, intento_envios=1 → HTTP 201
```

### Flujo corregido

```text
Evento persistido
  → bloquear el evento y buscar paquete existente
  → si existe: recuperarlo, sin crear ni reenviar
  → si no existe: guardar PENDIENTE/intento_envios=0 y confirmar
  → stub señala falta de integración
  → conservar el paquete confirmado, registrar warning y devolver PENDIENTE
```

El 201 confirma recepción/procesamiento y persistencia del paquete, no entrega
a IA. El estado pendiente es visible en `paquete_inferencia_estado`.

## 2. Cambios implementados

| Ruta | Responsabilidad | Cambio y justificación |
|---|---|---|
| `src/telemetry/domain/repositories/motor_inferencia_port.py` | Contrato de aplicación con el motor | Incorpora `MotorInferenciaNoIntegradoError` y documenta la distinción entre confirmación, intento fallido y ausencia de integración. Conserva la firma booleana. |
| `src/telemetry/infrastructure/adapters/motor_inferencia_stub_adapter.py` | Placeholder de integración | Lanza el error explícito; no devuelve True ni realiza comunicaciones ficticias. |
| `src/telemetry/application/use_cases/inferencia/consolidar_paquete_inferencia_use_case.py` | Persistencia y transición de estado | Reutiliza el paquete del mismo evento; captura la falta de integración después del commit y conserva PENDIENTE/0. Mantiene las ramas True/False y de excepción genérica. |
| `src/telemetry/domain/repositories/paquete_inferencia_repository.py` | Puerto de paquetes | Agrega recuperación por evento, con opción de bloquear el padre durante la consolidación. |
| `src/telemetry/infrastructure/repositories/paquete_inferencia_repository.py` | Acceso SQLAlchemy | Implementa consulta por evento y SELECT FOR UPDATE sobre la fila padre; devuelve entidades de dominio, sin commit/rollback propios. |
| `tests/telemetry/test_rf56_dev17_paquetes_pendientes.py` | Pruebas unitarias RF-56 | 16 pruebas sobre stub, orden de persistencia, estados, errores, reconsolidación y entradas no procesables. |
| `tests/integration/test_rf56_dev17_paquetes_pendientes.py` | Integración PostgreSQL | 16 pruebas del router real, persistencia, recuperación, fallos, validaciones y concurrencia con dos conexiones. |
| `anotaciones/modulo_3/api_reference_m03_telemetria_iot.md` | Contrato observable | Documenta 201/PENDIENTE con stub y cero intentos; actualiza la nota del adaptador. |
| `anotaciones/modulo_3/curls_m03_cu02_procesar_enviar_inferencia.md` | Ejemplos de consumo | Cambia los ejemplos del stub a PENDIENTE y distingue ausencia de integración de intento fallido. |
| `anotaciones/modulo_3/cu02_gaps_bd_rf56.md` | Decisiones de persistencia | Agrega una nota DEV-17: enum existente, recuperación, bloqueo y ausencia de migraciones. |
| `anotaciones/modulo_3/rf56_dev17_stub_paquetes_pendientes.md` | Informe técnico | Este documento de decisiones, reproducción, resultados y límites. |

### Semántica del puerto

`MotorInferenciaNoIntegradoError` deriva de `ServiceUnavailableError` y tiene
código `MOTOR_INFERENCIA_NO_INTEGRADO`. Su significado es que no se realizó
ningún intento porque no existe integración. No define protocolo, formato de
payload, ACK ni política de entrega del futuro IA-1.

RF-56 captura específicamente este error después de confirmar el paquete:
no lo convierte en un 503 del request de recepción ni en FALLIDO.
Fuera de ese flujo sigue siendo un error explícito de servicio no disponible.

El warning solo incluye el ID de paquete y la falta de integración; no incluye
access_key, tokens ni el contenido del paquete.

### Recuperación y duplicados

`obtener_por_evento(id_evento)` recupera el paquete, incluyendo estado, intentos,
contexto y metadatos. No se introduce un endpoint público nuevo de consulta.

La consolidación usa `bloquear_evento=True`: bloquea la fila del evento incluso
si aún no existe paquete, consulta y confirma la creación dentro de la misma
transacción. Una segunda consolidación del mismo ID espera y reutiliza la fila
existente. Esta carrera se verificó con dos conexiones PostgreSQL reales.

Reconsolidar no significa reenviar: se conserva el ID, estado y contador tanto
para PENDIENTE como para FALLIDO/ENVIADO. Un futuro procesador de reintentos
deberá operar sobre el paquete existente con el contrato acordado con IA.

La garantía cubre este flujo por ID de evento. No se agrega unicidad global
para escritores SQL externos ni se reparan duplicados históricos. Si hubiera
varias filas históricas por evento, la lectura elige la de menor ID de forma
determinista. Un nuevo POST sin identificador externo sigue creando un nuevo
evento; DEV-17 no inventa una clave de idempotencia de transporte.

## 3. Estado de los paquetes

| Situación | Antes | Después |
|---|---|---|
| Stub sin integración | ENVIADO, 1 intento, sin entrega real | PENDIENTE, 0 intentos, persistido y recuperable |
| Cambiar únicamente el stub a False | Habría producido FALLIDO/1 | Se distingue explícitamente ausencia de integración |
| Puerto devuelve True | ENVIADO/1 | ENVIADO/1; compatibilidad probada con doble del puerto |
| Puerto devuelve False | FALLIDO/1 | FALLIDO/1, conservado |
| Puerto lanza excepción genérica | FALLIDO/1 | FALLIDO/1, conservado |
| Error al guardar/confirmar el paquete | Error propagado | Error propagado, rollback del paquete y motor no invocado |
| Error al guardar el estado después del envío | Error propagado; paquete inicial confirmado | Mismo comportamiento; el paquete queda recuperable y reconsolidar no reenvía |
| Reconsolidación del mismo evento | Podía crear otra fila y volver a invocar al motor | Devuelve el paquete existente, sin crear ni reenviar |
| NORMAL o ERROR_CONFIGURACION | Evento sin paquete | Se conserva; `paquete_inferencia_estado=null` |

`fecha_envio` es una columna existente NOT NULL que el flujo ya rellena al
construir el paquete. Se conserva para compatibilidad: su presencia no es una
confirmación de entrega. El estado y el contador distinguen la falta de envío.

## 4. Subtareas completadas

- **#3568:** eliminada la confirmación ficticia; PENDIENTE/0 confirmado antes
  de invocar al stub; recuperación y reconsolidación del paquete existente.
- **#3569:** implementadas y ejecutadas 32 pruebas nuevas, incluidas las
  transacciones reales, validaciones del router y concurrencia por evento.

### Relación con P1–P7

| Principio | Aplicación en DEV-17 |
|---|---|
| P1 | No se modifica RF-17 ni se usa POST /v1/commands para entregar paquetes a IA. |
| P2 | Se conserva la separación entre recepción Edge y entrega. No se crean canales ni tablas de transporte. El camino broker → endpoint interno permanece pendiente donde no existe en este checkout. |
| P3 | Se conserva la recepción actual por access_key. Se verifican credencial inválida, sensor inexistente, estructura y temporalidad; no se simula autenticación de broker ni identidad MQTT. |
| P4 | El adaptador informa su resultado; el caso de uso gobierna los estados y el repositorio persiste. La consolidación reutiliza el mismo paquete. |
| P5 | Se confirma el paquete antes del motor; un fallo de persistencia no produce 201. No se cambia RF-54 ni se crea un buffer paralelo. |
| P6 | No se modifican tópicos MQTT ni jerarquías por serial. |
| P7 | El stub no confirma éxito y el paquete queda PENDIENTE/0 de forma observable y persistida. |

## 5. Pruebas ejecutadas

Entorno: Windows, Python 3.13.13, PostgreSQL **18.4** instalado localmente.
Se creó una instancia efímera que escucha solo en 127.0.0.1 y la base
`sgpmp_test_rf56_dev17`. Se aplicaron las migraciones existentes hasta
`3a9d5e7c1b24`. No se conectó el flujo de pruebas a bases compartidas.

### Evidencia por escenario

| Caso | Prueba/escenario | Esperado y obtenido |
|---|---|---|
| TC-01 | `test_stub_senala_falta_de_integracion` | Error explícito; ninguna confirmación ficticia. Aprobado. |
| TC-02/03 | `test_evento_edge_a_paquete_pendiente_persistido_y_recuperable`, SIMPLE y COMPUESTA | HTTP 201/PENDIENTE, 0 intentos, una fila real con contexto y trazabilidad. 2 aprobadas. |
| TC-04 | Misma integración, lectura en otra sesión después de rollback posterior | Mismo ID y estado recuperables. Aprobado dentro de esos 2 casos. |
| TC-05 | `test_doble_de_motor_conserva_confirmacion_y_fallo` | True → ENVIADO/1; False y excepción genérica → FALLIDO/1. 3 integraciones aprobadas; solo dobles, sin IA real. |
| TC-06 | `test_fallo_persistencia_no_confirma_ni_invoca_motor`, guardar y commit | HTTP 500 seguro, sin paquete nuevo y sin invocar al motor; evento previo conservado. 2 aprobadas. |
| TC-06 | `test_fallo_estado_conserva_paquete_y_reconsolidacion_no_reenvia` | Fallo posterior al commit inicial conserva paquete PENDIENTE/0, sin segunda entrega al reconsolidar. Aprobado. |
| TC-07 | `test_reconsolidar_mismo_evento_reutiliza_un_solo_paquete` | Reconsolidar dos veces conserva un paquete y no llama al motor. Aprobado. |
| TC-07 | `test_consolidaciones_concurrentes_del_mismo_evento_no_duplican` | Dos conexiones obtienen el mismo ID PENDIENTE/0; una fila. Aprobado. |
| TC-08 | Router real `POST /iot/eventos-edge` con adaptadores/repositorios reales | Recepción → evento → paquete confirmado; `enviado_backend=false`, sin activar otro productor. Verificado en las integraciones. |
| TC-09 | `test_recepcion_conserva_validaciones_existentes` | 401 para clave/sensor inválidos y 400 para estructura/timestamp futuro; sin eventos ni paquetes. 4 aprobadas. No certifica endpoint interno ausente. |
| TC-10 | Regresión de telemetría e ingesta/vinculación | 30 pruebas unitarias existentes y 6 integraciones existentes aprobadas. |
| Adicional | `test_eventos_sin_envio_conservan_flujo_actual` | NORMAL y ERROR_CONFIGURACION conservan 201 sin paquete. 2 aprobadas. |

### Resultados consolidados sin duplicaciones

| Grupo ejecutado | Resultado |
|---|---|
| Unitarias RF-56 nuevas | 16 aprobadas; incluidas en las 46 de telemetría |
| Telemetría compatible con Windows | 46 aprobadas = 16 nuevas + 30 existentes |
| Integración RF-56 nueva | 16 aprobadas |
| Integración existente de ingesta/vinculación | 6 aprobadas |
| Total de pruebas distintas | **68 aprobadas**, incluidas **32 nuevas** |
| Fallos funcionales pendientes de los casos ejecutados | 0 |
| Suite completa de telemetría | 1 error de recolección por fcntl; archivo afectado no ejecutado |
| AST de los 7 archivos Python modificados/agregados | Aprobado |
| git diff --check | Aprobado |
| Bandit, cinco archivos de producción, gate -lll -iii | Exit 0; alta/media/baja: 0/0/0 |
| Semgrep | No ejecutado localmente; herramienta no disponible |

No se suman dos veces ejecuciones enfocadas, reintentos o escenarios contenidos
en otra prueba. La recolección de la suite completa falla al importar `main`
desde `test_inc_m09_77_g137_observaciones_vision.py`, que termina importando
`fcntl` de M02. Ese archivo se excluyó para ejecutar las otras 46 pruebas.
No se simuló fcntl ni se modificaron módulos ajenos para forzar la recolección.

La primera ejecución de concurrencia alcanzó las aserciones funcionales pero
falló durante la limpieza al intentar borrar el dispositivo: M09 prohíbe todo
borrado físico. Se corrigió la finalización mediante inactivación del hardware
de prueba y la prueba completa pasó. No se debilitó ningún trigger.

Se observó la deprecación preexistente de Starlette/httpx. No hay certificación
de la suite completa del repositorio ni de una entrega real a IA.

### Comandos ejecutados

Se usó el Python del entorno virtual y DATABASE_URL/TEST_DATABASE_URL dirigidas
solo al PostgreSQL efímero. Las integraciones usaron basetemp exclusivos.

```powershell
python -m pytest --confcutdir=tests/telemetry tests/telemetry/test_rf56_dev17_paquetes_pendientes.py -q --tb=short --show-capture=no
python -m pytest --confcutdir=tests/telemetry tests/telemetry --ignore=tests/telemetry/test_inc_m09_77_g137_observaciones_vision.py -q --tb=short --show-capture=no
python -m pytest --confcutdir=tests/integration tests/integration/test_rf56_dev17_paquetes_pendientes.py tests/integration/test_inc_m09_64_g31_vinculacion_ingesta.py -q --tb=short --show-capture=no
python -m pytest --confcutdir=tests/telemetry tests/telemetry --collect-only -q --tb=short --show-capture=no
```

La última orden documenta la limitación de recolección; no es una suite aprobada.

### Aislamiento y limpieza

Las integraciones habituales usan el conftest existente: transacción exterior
y savepoints, con rollback final. La prueba concurrente necesita dos conexiones
que vean el evento y confirma su fixture únicamente en la base aislada; borra
sus paquetes/eventos de prueba e inactiva su hardware M09, sin eliminarlo
físicamente. Esas filas y su auditoría permanecen solo hasta destruir la base
efímera. No se afirma que las secuencias hayan sido restauradas.

La verificación final confirmó 0 eventos y 0 paquetes; quedaron únicamente
3 dispositivos de fixtures concurrentes, todos inactivos. Los triggers de
creación de paquete, inmutabilidad RF-53 y prohibición de borrado IoT siguieron
habilitados. Después se detuvo PostgreSQL y se eliminó la base/instancia
efímera completa, incluidos esos fixtures y su auditoría.

## 6. Limitaciones y dependencias

- Pendiente confirmar mediante documentos vigentes la relación IA-1/pregunta 6.
- Pendiente definir transporte, payload, confirmación y reintentos con IA.
- No existe motor real verificado; las ramas de éxito/fallo usan dobles del puerto.
- No se crea un worker, cron o cola para despachar automáticamente pendientes.
- No se certifica la ruta broker → endpoint interno con token de servicio,
  ACL/MQTT o buffer SQLite Edge. Se conserva y prueba el router disponible.
- No se introduce idempotencia de nuevos POST sin identificador externo ni
  unicidad global para productores que no usen este caso de uso.
- No se reparan paquetes históricos ENVIADO ni duplicados anteriores: no puede
  inferirse retrospectivamente qué entregas fueron reales sin evidencia.
- Si un futuro adaptador confirma entrega y luego falla la actualización en
  BD, el paquete queda pendiente; se conserva el comportamiento y se evita
  reenviarlo al reconsolidar. Resolver entrega ambigua exige el contrato IA-1.
- El puerto de paquetes incorpora un método abstracto: cualquier adaptador
  externo futuro deberá implementarlo. En el repositorio solo hay un adaptador
  de persistencia, que se actualizó y probó.
- Queda pendiente ejecutar el archivo de visión afectado por fcntl en un entorno
  compatible; no se incluyen cambios de portabilidad M02 en DEV-17.

## 7. Estado final

- #3568 y #3569 completadas en el alcance descrito.
- Estado utilizado: **PENDIENTE**, existente en dominio y PostgreSQL.
- 11 archivos modificados/agregados: cinco de producción, dos de pruebas y
  cuatro documentos. Ninguna migración ni cambio a enums/triggers.
- Rama `fix/rf56-dev17-paquetes-pendientes`, base `origin/dev` en `cd06a257`.
- El commit local y el estado Git se informan al entregar. No se realizó push,
  force-push ni despliegue.
- DEV-02 y DEV-04 permanecen en sus ramas independientes; no se mezclan aquí.
- No se modificaron bases compartidas, credenciales, tópicos MQTT, RF-17 ni RF-54.
- Las pruebas con persistencia se realizaron únicamente en la instancia
  efímera local; la instancia y su base fueron detenidas y eliminadas.

## 8. Documentación

Este informe es `anotaciones/modulo_3/rf56_dev17_stub_paquetes_pendientes.md`.
La referencia de API, los CURLs CU02 y la nota de gaps RF-56 se actualizaron
para que PENDIENTE/0 sea el resultado documentado del stub sin integración.
