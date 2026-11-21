# INC-M03-110-G42 — Orden temporal de eventos Edge · RF-55/RF-56

| Fecha | Nombre | Que se hizo |
|---|---|---|
| 2026-10-26 | Leandro | INC-M03-110-G42 RF-55/RF-56: corregir el orden temporal recibido por el backend y exponer ambos instantes originales. |

## Resultado y alcance

La [issue #646](https://github.com/Arekkazu/sgpmp-backend/issues/646) contiene dos situaciones diferentes: el bloqueo para observar fechas generadas por un clasificador Edge real y una brecha comprobable en el backend. Se corrigió esta última sin depender del firmware.

El backend rechaza ahora `timestamp_procesamiento_edge < timestamp_captura` antes de persistir el evento o generar paquetes. Devuelve ambos instantes originales en la respuesta de recepción. Esto no demuestra cómo genera los tiempos el nodo ni permite declarar aprobado TC-M03-103.

## Base y definición confirmada

Se leyeron AGENTS.md, CLAUDE.md, CONTRIBUTING.md y las referencias de arquitectura existentes. Se ejecutó `git fetch origin dev`, se actualizó `dev` mediante avance rápido y se creó `fix/inc-m03-110-g42-orden-temporal-edge-rf55` desde `18b4ce67e8d23ed57fdfd108d44e0c2601e66604`, igual a `origin/dev` al comenzar. Se preservaron los archivos locales ajenos y los informes anteriores de G37.

RF-55 CA-13 exige coherencia entre captura y procesamiento, pero no establece una diferencia estrictamente positiva. RF-56, restricción 2, exige orden cronológico y coherencia. El reporte planteaba `procesamiento > captura`; el código y las pruebas existentes admitían igualdad.

El usuario confirmó expresamente **rechazar únicamente el procesamiento anterior a la captura y permitir igualdad por precisión del reloj**. Por tanto, la regla aplicada es:

```text
timestamp_procesamiento_edge >= timestamp_captura
```

No se agrega un mínimo artificial de latencia, no se reconstruyen timestamps y no se impone un nuevo rechazo por duración del procesamiento.

## Causa raíz

`RecibirEventoEdgeUseCase._validar_temporal` comprobaba el futuro de la captura y la antigüedad del buffer, pero no recibía el instante de procesamiento para compararlo. Ambos valores se copiaban a `EventoEdgeComputing` y al ORM sin comprobar su orden.

La entidad persistida ya tenía `fecha_captura` y `fecha_procesamiento`. El modelo de resultado del caso de uso y `EventoEdgeResponse` omitían la captura, impidiendo observar ambos instantes juntos en la respuesta.

Antes de la corrección, las diez pruebas nuevas de caso de uso ejecutadas sobre la base original fallaron: cuatro porque la inversión no era rechazada y seis porque faltaba la captura en el resultado. Esa corrida de reproducción queda separada del resultado final.

## Revisión de BD y seguridad

Se inspeccionó `modulo3.eventos_edge_computing` en la BD oficial `sgpmp_dev` mediante una transacción con `transaction_read_only=on`. Se consultaron metadatos, sin insertar eventos ni alterar datos o configuración.

- Ambas columnas existen como `timestamp with time zone NOT NULL`.
- No se encontró un CHECK que compare captura y procesamiento.
- Se conserva `trg_rf55_01_crear_paquete_inferencia`.
- La tabla inspeccionada no tiene RLS ni FORCE RLS activados; no se modificó ese estado ni se atribuye una protección inexistente a esta tabla.
- La lectura de `public.alembic_version` fue denegada (`42501`); no se afirma qué revisión está desplegada en la BD oficial.

No hace falta migración para el cambio de validación y respuesta. La regla se aplica en el caso de uso HTTP; no se presenta como una nueva garantía contra escrituras directas ajenas a ese flujo.

Para integración se creó **`sgpmp_g646_test`**, exclusiva y local, desde cero mediante Alembic hasta el único head `30168ab97bd4`. No se incorporaron correcciones de #625, #626 o #632. Se provisionaron privilegios de infraestructura solo en esa base, conservando triggers, políticas y permisos RBAC existentes. Los diez casos nuevos de integración ejecutan las peticiones con `sgpmp_app`, verificando `rolsuper=false` y `rolbypassrls=false`, y utilizan la identidad de servicio ya definida por `declarar_identidad_sistema`.

## Cambios implementados

| Archivo | Cambio |
|---|---|
| `src/telemetry/application/use_cases/inferencia/recibir_evento_edge_use_case.py` | Normaliza ambos valores antes de validar, detecta la inversión dentro del flujo existente de rechazo auditado y devuelve la captura persistida. |
| `src/telemetry/domain/entities/telemetria.py` | Añade `fecha_captura` a `ResultadoEventoEdge`; conserva la entidad y sus timestamps existentes. |
| `src/telemetry/infrastructure/schema/evento_edge_schema.py` | Expone `fecha_captura` junto a `fecha_procesamiento` en la respuesta. |
| `tests/telemetry/test_inc_m03_110_g42_orden_temporal_edge.py` | Casos unitarios y contrato HTTP con fakes para inversión, igualdad, precisión de microsegundos, orígenes y offsets. |
| `tests/integration/test_inc_m03_110_g42_orden_temporal_edge.py` | HTTP y PostgreSQL reales bajo rol API; verifica rechazo auditado sin evento/paquete, conservación de ambos instantes y rechazos temporales previos. |
| `anotaciones/modulo_3/api_reference_m03_telemetria_iot.md` | Actualiza regla, respuesta y error públicos. |

Los cinco archivos de código llevan la fila de seguimiento de esta tarea, con fecha real y nombre obtenido de `git config user.name`. Se conservaron las filas existentes.

## Contrato resultante

| Entrada | Resultado |
|---|---|
| Procesamiento anterior, incluso por un microsegundo | `400 ORDEN_TEMPORAL_INVALIDO`, campo `timestamp_procesamiento_edge`; sin INSERT del evento ni paquete. |
| Procesamiento igual | Se admite; conserva el comportamiento monoinstante previo. |
| Procesamiento posterior | Se admite dentro de las demás validaciones existentes. |
| Diferentes offsets horarios | Se comparan los instantes normalizados a UTC. |
| Captura futura más allá de la tolerancia existente | Se conserva `400 TIMESTAMP_FUTURO`. |
| Buffer con captura de más de 72 horas | Se conserva `400 TIMESTAMP_EXPIRADO`. |

La inversión sigue la auditoría existente `EVENTO_EDGE_RECHAZADO`, con el contenido recibido y el nuevo código. La bitácora mantiene su comportamiento best-effort: no se introduce otra política transaccional o de disponibilidad. Los eventos aceptados mantienen autenticación del broker, consolidación y reglas de envío existentes.

La respuesta `201` agrega `fecha_captura`; conserva los campos previos. Ambos instantes proceden del evento devuelto por persistencia y representan los valores recibidos normalizados, no la hora de recepción del servidor. Ejemplo parcial:

```json
{
  "fecha_captura": "2026-10-26T15:00:00Z",
  "fecha_procesamiento": "2026-10-26T15:00:00.000001Z"
}
```

Se habilita la observación de ambos valores durante el POST existente. No se agrega un GET histórico, un nuevo permiso ni una ruta de consulta de eventos; esa interfaz requeriría definir su contrato y alcance de acceso.

## Pruebas finales

| Grupo | Aprobadas | Fallidas | Omitidas |
|---|---:|---:|---:|
| `tests/telemetry` y `tests/configuration/test_dev14_parametros_dinamicos.py` | 663 | 0 | 0 |
| Integración nueva G42 en PostgreSQL 18 real | 10 | 0 | 0 |
| **Total distinto** | **673** | **0** | **0** |

Los 14 casos nuevos unitarios/HTTP están incluidos en los 663; no se suman otra vez. El primer grupo se revalidó con fakes/mocks y una URL local sin servicio PostgreSQL; no demuestra persistencia. El segundo usa router, adaptadores, repositorios, auditoría y PostgreSQL reales; no ejecuta un clasificador Edge ni un motor IA real.

La integración verifica NORMAL y DESVIACION_SIMPLE con igualdad, un microsegundo y 500 ms de diferencia; compara respuesta, fila almacenada y metadatos del paquete cuando corresponde. Para la inversión comprueba cero eventos y cero paquetes, además del rechazo auditado con ambos tiempos. Conserva los casos de captura futura y buffer expirado.

Se utilizó el shim de `fcntl` solo en el lanzador temporal de Windows. Hubo una aserción de prueba ajustada para comparar instantes equivalentes (`Z` y `+00:00`) y una primera corrida con HTTP interrumpida; no se contabilizan como resultados finales. La conexión local requirió ejecución fuera del sandbox por una denegación de loopback. No se alteró producción para resolver esas condiciones del entorno. Se observa el aviso preexistente de deprecación de `httpx`/Starlette.

La primera regresión utilizó la URL local de integración y algunos manejadores de auditoría de pruebas antiguas escribieron 15 registros mediante sesiones independientes. No fueron eventos Edge ni paquetes y no afectaron la BD oficial. Se repitieron los 663 casos con el lanzador unitario separado, sin una BD disponible, y se conservaron los diez resultados de integración bajo rol API. Al finalizar se descartó exclusivamente `sgpmp_g646_test`, incluidos esos registros desechables, y se detuvo el clúster local; se conservaron scripts y evidencias.

Evidencias temporales, fuera del commit:

```text
.pytest_cache/g646_unit_antes.xml
.pytest_cache/g646_unit_final.xml
.pytest_cache/g646_regresion.xml
.pytest_cache/g646_pg.xml
.pytest_cache/g646_run_tests.py
.pytest_cache/g646_run_unit.py
.pytest_cache/g646_resultados_consolidados.json
.pytest_cache/g646_preparar_bd.py
.pytest_cache/g646_inspeccionar_bd.py
```

## Dependencias y pendientes

La parte corregida corresponde a **Desarrollo/backend** y puede probarse en aislamiento. La validación de la generación de timestamps del nodo corresponde al **grupo IoT**, mediante AIOT-07 del **AIOT-DEV-03 — Acuerdo Consolidado de Desarrollo AIoT**, que asigna al Edge evaluar lecturas y emitir eventos RF-55. QA debe completar la aserción de TC-M03-103 y ejecutarla con eventos realmente generados por ese componente.

TC-M03-103 sigue pendiente de ejecución end-to-end. El backend ahora controla la entrada y expone ambos instantes, pero eso no acredita el reloj, el clasificador ni el despliegue del nodo. Esta entrega no se desplegó ni hizo escrituras de prueba en DEV compartido.
