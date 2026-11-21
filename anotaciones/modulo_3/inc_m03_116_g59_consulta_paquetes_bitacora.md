# INC-M03-116-G59 — Consulta de paquetes y bitácora del ciclo de vida (RF-56) + aislamiento del doble en memoria (TC-M03-117)

**RF:** RF-56 (Postcondiciones 3 y 5, Fase 7, Salida 3, CA-8) y RF-63 (bitácora).
**Grupo:** TC-M03-G59. **Casos:** TC-M03-117 y TC-M03-118. **Issue:** #659.

## Qué estaba definido

RF-56 no fija rutas. Sí fija qué debe quedar disponible:

| RF-56 | Exige |
|---|---|
| Fase 7 y Salida 3 | Bitácora con `id_paquete`, `timestamp_envio`, estado del envío, número de reintentos y latencia |
| Postcondición 3 | Relación end-to-end `sensor_id → evento_edge → id_paquete → inferencia`, "permitiendo auditoría completa del flujo de datos" |
| Postcondición 5 | El paquete queda disponible para "seguimiento del pipeline de inferencia" y "diagnóstico técnico" |
| CA-8 | Registrar el ciclo completo de cada paquete en la bitácora técnica |

En el backend ya existían:

- **`GET /iot/auditoria`** (RF-63, recurso 39), que filtraba por `entidad_afectada_id`, pero **no
  por tipo de entidad**. El id 11 de un paquete se mezclaba con la lectura 11, la alerta 11, etc.
- **El alcance por finca de la bitácora** (M3-14) dejaba fuera los eventos `PAQUETE_IA` para
  quien no es auditor. El propio código lo anticipaba: "si un rol con finca los necesita, agregar
  su tipo aquí con su propio camino a la finca".
- **Una decisión previa del equipo** (`pendientes_frontend_m03.md`, #F8): no exponer la vista cruda
  `vw_m03_pipeline_inferencia`, porque las lecturas humanas van por monitoreo, historial, calidad y
  auditoría. Se respeta: no se expone la vista, sino una consulta por paquete apoyada en la
  bitácora RF-63.
- **Ningún endpoint para consultar un paquete por su id.**
- **Las rutas del ticket** (`/inferencia/paquetes/{id}` y `/inferencia/bitacora`) son las que
  asumía el script de QA. No están en ningún documento. Se sigue la convención `/iot/...` de M03.

## Cambios

| Pieza | Cambio |
|---|---|
| `GET /iot/paquetes-inferencia/{id_paquete}` (nuevo, `paquete_inferencia_router.py`) | Paquete con trazabilidad (`id_sensor` → `id_evento_edge_computing` → `id_paquete_inferencia` → `id_version_modelo`), estado, intentos, `fecha_envio`, contexto y metadatos (timestamps de captura y procesamiento Edge), más su `ciclo_vida`: los eventos RF-63 del paquete en orden cronológico |
| `ConsultarPaqueteInferenciaUseCase` (nuevo) | Devuelve 404 `PAQUETE_INFERENCIA_NO_ENCONTRADO` si el paquete no existe o está fuera de las fincas del usuario; si no, lee sus eventos `PAQUETE_IA` (tope de 200) y los ordena |
| `PaqueteInferenciaRepository.obtener` | Por id, con el mismo camino a la finca que la bitácora (equipo → infraestructura → finca, `_SQL_EQUIPOS_DE_FINCAS`) |
| `GET /iot/auditoria` | Filtro nuevo `entidad_afectada_tipo`, validado contra `EntidadAfectadaTipo` (400 `VAL_ENTRADA` si no existe). `?entidad_afectada_tipo=PAQUETE_IA&entidad_afectada_id={id}` da el ciclo de vida de un paquete, y sin el id, la bitácora de todos los paquetes |
| Alcance por finca de la bitácora (`_de_las_fincas`) | Camino de `PAQUETE_IA` a la finca por `paquetes_inferencia.id_dispositivo_iot` |
| `main.py` | Registra el router |

**RBAC:** recurso **39** (`bitacora_auditoria_iot`), acción **R**.

- **Por qué este recurso:** la consulta es de trazabilidad técnica sobre la misma bitácora RF-63
  (CA-8), con su mismo alcance por finca.
- **Sin DML de permisos:** `modulo1.recursos` no tiene un recurso para paquetes de RF-56, y
  reutilizar el 39 evita crear uno nuevo con sus filas de permisos.
- **Si Análisis prefiere un recurso propio:** se cambia el `require_permission` del router y se
  insertan sus permisos.

**Base de datos:** sin cambios.

- **Plan de la consulta del ciclo de vida:** `EXPLAIN` en `sgpmp_dev` muestra que usa el índice
  existente `idx_bitacora_iot_tipo_evento_entidad_afectada_id` por `entidad_afectada_id`, sobre
  unas 480 000 filas; no recorre la tabla completa.
- **Eventos de paquetes en DEV:** hoy no hay ninguno en la bitácora. Los paquetes existentes son
  anteriores a la auditoría de DEV-47.

## Eventos del ciclo de vida que quedan registrados

| Evento | Quién lo registra | Cuándo |
|---|---|---|
| `PAQUETE_INFERENCIA_GENERADO` | `SqlAlchemyPaqueteInferenciaRepository.guardar` y `ConsolidarEnviarPaqueteUseCase` | Al generarse el paquete |
| `CONTEXTO_INCOMPLETO` | Repositorio, al guardar | Si falta contexto multivariable (E2) |
| `PAQUETE_ENVIADO_IA` / `FALLO_ENVIO_PAQUETE` | Repositorio, en `actualizar_estado` | Al confirmarse o fallar el envío |
| `REINTENTO_ENVIO_PAQUETE_PROGRAMADO` | Repositorio (#656, todavía sin mergear) | Intento no confirmado con otro programado |
| `MOTOR_INFERENCIA_NO_INTEGRADO`, `MOTOR_INFERENCIA_NO_DISPONIBLE`, etc. | `ConsolidarEnviarPaqueteUseCase._registrar_fallo_motor` | Causa del fallo de envío |

Cada evento lleva en `accion_detallada` el estado del paquete, los intentos, `id_evento_edge` e
`id_dispositivo_iot`. `fecha_hora` hace de `timestamp_envio`.

**Lo que RF-56 pide y la bitácora todavía no tiene:**
- **Latencia del proceso** (Fase 7 y Postcondición 4): no se registra; requiere definir desde qué
  instante se mide.
- **Validación previa** (Fase 5): no es un paso separado; depende del contrato con M04, que está
  bloqueado (#658).

Se dejan como observación; no estaban en la acción correctiva.

## Doble en memoria de QA: TC-M03-117 `test_tc_m03_117_repos_aislados_entre_instancias`

`EventoEdgeRepoMemoria` vive en el script de QA (`tests/Test_Testing/...`), no en este repositorio;
el backend no tiene ese doble. La respuesta sobre el contrato que debe representar:

- **En PostgreSQL, el id lo genera la secuencia de cada tabla:** es único **dentro de una base de
  datos**. Dos instancias independientes del doble equivalen a **dos bases distintas**, así que es
  correcto que ambas generen el id 1. `assert 1 != 1` falla porque la prueba exige algo que el
  sistema real no promete.
- **Si el objetivo es el aislamiento**, que es lo que dice el nombre de la prueba, debe verificar que
  lo guardado en una instancia no aparece en la otra (`listar()` y `obtener(id)`), no que los ids
  sean distintos.
- **Si se quiere simular una sola base con dos repositorios** (dos sesiones), el doble debe compartir
  el contador entre instancias (atributo de clase o un generador inyectado). En ese caso los ids sí
  deben ser distintos, pero eso ya es otra prueba: unicidad dentro de una base, no aislamiento.

**Propuesta:** corregir la prueba al primer contrato (aislamiento de registros) y, si se quiere
cubrir la unicidad, agregar una prueba aparte con contador compartido. En el backend no hay nada
que cambiar.

## Pruebas

`tests/telemetry/test_inc_m03_116_g59_consulta_paquetes.py`, 11 pruebas, con dobles de repositorio
y SQL compilada:

- **Use case:**
  - Un paquete inexistente o fuera de las fincas da 404 y no consulta la bitácora.
  - El ciclo de vida sale en orden cronológico, filtrado por `PAQUETE_IA` y el id.
- **HTTP `GET /iot/paquetes-inferencia/{id}`:**
  - 200 con la trazabilidad y el ciclo de vida, sin exponer `componente_origen` y usando las
    fincas del usuario.
  - 404 si no existe, 403 sin permiso y 400 `VAL_ENTRADA` con un id 0.
- **SQL:**
  - `obtener` filtra por el id y por los equipos de las fincas.
  - `listar` filtra por `entidad_afectada_tipo`.
  - El alcance por finca incluye `PAQUETE_IA` por su equipo.
- **HTTP `GET /iot/auditoria`:** acepta `entidad_afectada_tipo=PAQUETE_IA` y rechaza un tipo
  inexistente con 400.
- **`main.py`:** registra `/iot/paquetes-inferencia/{id_paquete}`.

**Integración con PostgreSQL:** no se escribió una prueba de integración nueva, porque no se puede
ejecutar localmente sin `TEST_DATABASE_URL`. La consulta del ciclo de vida se validó con `EXPLAIN`
en `sgpmp_dev`.

CURL:
- `curls_m03_cu02_procesar_enviar_inferencia.md`, sección "Consultar un paquete y su ciclo de vida".
- `curls_m03_cu06_calidad_auditoria.md`, sección "Ciclo de vida de un paquete de inferencia".
