# Implementación DEV — M05 CU04: Reporte de Gastos e Historial de Suministros (RF-77, RF-81)

**Fecha:** 2026-07-31 · **Rama:** `feature/supplies`

Resumen de lo implementado para CU-04: reporte de gastos acumulados por activo/infraestructura/
especie con desglose por categoría y período, tendencia vs. período anterior (RF-77); y consulta
paginada de trazabilidad/historial de suministros con filtros combinados, RBAC por alcance de
activo y SLA por nivel de volumen (RF-81). Sigue la arquitectura hexagonal/DDD del proyecto (ver
`CLAUDE.md`). RF-77 y RF-81 estaban en 0% de implementación al iniciar este CU.

## Decisiones clave (acordadas antes de codificar)
- **Infraestructura async real** (no un límite duro tipo RF-59): dos motores independientes
  (reportes de gastos / trabajos de historial) replican el patrón de cola en BD + workers
  `asyncio` del motor batch ICA (RF-74/CU-02), pero como **poller continuo** (no cron diario),
  porque los trabajos se encolan en momentos arbitrarios.
- **Solo exportación CSV** en esta iteración — no hay librería de PDF/Excel en el proyecto. PDF y
  Excel quedan documentados como pendientes.
- **Roles nuevos** `Gestor de Granja` (id_rol=7) y `Revisor Fiscal` (id_rol=8) creados en
  `modulo1.roles` — RF-81 los menciona como actores y no existían.
- **`modulo5.registro_suministro`** (ledger unificado, existía vacío y huérfano) se pobló vía
  trigger `AFTER INSERT` desde `registros_consumo_alimentos`/`registros_medicamentos` (RF-75/76),
  y se usa como fuente del detalle de RF-81 — en vez de construir un nuevo mecanismo de escritura.
- **Restricción de alcance del Gestor de Granja** (RF-81 FA-04) implementada con una regla
  interina (`activos_biologicos.id_usuario = usuario_actual.id_usuario`) porque no existe ningún
  modelo de "unidad productiva asignada a usuario" en el sistema — aislada completamente en
  `AlcanceActivoM02Adapter` para poder reemplazarse sin tocar el use case.
- Scaffolding de BD preexistente (`fn_consultar_historial_suministros`, `historial_suministros_activos`,
  vistas `vw_m05_*`) resultó incompleto/con bugs reales frente al RF — mismo patrón que ICA antes
  de CU-02. Se corrigieron los bugs aprovechables (Gap 0) y se construyó el resto en la app.

Detalle completo de gaps de BD/RBAC (con todo el DDL aplicado) en
[`cu04_gaps_bd_rf77_rf81.md`](cu04_gaps_bd_rf77_rf81.md).

## Paso 0 (BD/RBAC) — aplicado vía MCP postgres, resumen
- Gap 0: fix de `vw_m05_historial_suministros_detalle` (filtro roto por `naturaleza_costo`).
- Gap 1-2: triggers de población de `registro_suministro` + backfill (17 filas, VALIDADO únicamente).
- Gap 3: `ALTER TYPE ... ADD VALUE 'CSV'` en el enum de formato de exportación.
- Gap 4-5: 8 tablas nuevas (cola/ejecución/fallos/configuración × 2 motores async).
- Gap 6: roles `Gestor de Granja` (7), `Revisor Fiscal` (8).
- Gap 7: recursos **51-54** + 23 permisos RBAC.
- Gap 8: `TooManyRequestsError` (429) nueva en `src/shared/errors.py`.
- Gap 9 (encontrado en verificación E2E, no en el análisis inicial): `reporte_gastos_acumulados.id_activo_biologico`
  era `NOT NULL`, rompía los reportes agregados por infraestructura/especie que el propio RF-77 exige soportar.

## Estructura de código (`src/supplies/`)

### Dominio
- `domain/value_objects/` — `estado_trabajo_async.py` (compartido), `reporte_gasto_enums.py`
  (`GranularidadDesglose`, `EstadoTendencia`, `CategoriaGasto`), `historial_suministro_enums.py`
  (`TipoTrabajoHistorial`, `OrigenPrecio`, `NaturalezaCosto`, `TipoSuministroFiltro`, `NivelVolumen`).
- `domain/entities/` — `reporte_gasto.py` (`ReporteGasto`, `FiltrosReporteGasto`, `LineaGasto`,
  desgloses, `TendenciaGasto`), `trabajo_reporte_gasto.py`, `historial_suministro.py`
  (`FiltrosHistorialSuministro`, `LineaHistorialSuministro`, `ResultadoHistorialSuministro`,
  `ResumenConsultaHistorial`), `trabajo_historial_suministro.py`.
- `domain/services/calculadora_reporte_gasto.py` — **cálculo puro** (patrón `calculadora_ica.py`):
  desglose por categoría, desglose temporal (SEMANAL/MENSUAL, agrupado por `isocalendar()`/año-mes),
  tendencia (SIN_BASE_COMPARATIVA/SIN_MOVIMIENTO/CALCULADA con recorte al inicio de ciclo).
  Reutilizado tal cual por el flujo síncrono y por el worker async.
- `domain/repositories/` — puertos: `reporte_gasto_repository`, `detalle_gasto_read_port`,
  `trabajo_reporte_gasto_repository`, `fallo_reporte_gasto_repository`,
  `configuracion_batch_reporte_gasto_repository`, `historial_suministro_read_port`,
  `alcance_activo_port`, `trabajo_historial_suministro_repository`,
  `fallo_historial_suministro_repository`, `configuracion_batch_historial_repository`.
  Reutiliza `activo_consulta_port` (`ActivoConsultaPort`) ya existente de CU-01/CU-02.

### Infraestructura
- `infrastructure/models/` — 10 modelos ORM (sqlacodegen + adaptación manual: Base compartida,
  enum PG→`String`, sin `relationship`). **No** se generó modelo para `historial_suministros_activos`
  (tabla intencionalmente sin uso, ver gap doc).
- `infrastructure/repositories/`:
  - `detalle_gasto_read_repository.py` y `historial_suministro_read_repository.py` — SQL propio con
    `text()` (patrón `historial_telemetria_repository.py`), no las vistas `vw_m05_*` (les faltan
    columnas de filtrado como `id_infraestructura`/`id_especie`, o tienen joins espurios).
  - 8 repositorios más para los motores async y snapshots, todos `flush()`-only + `raise_from_db_error`.
- `infrastructure/adapters/alcance_activo_m02_adapter.py` — única pieza con lógica condicional por
  `id_rol` (Gestor de Granja=7) en todo RF-81.
- `infrastructure/dto/` — `generar_reporte_gastos_dto.py`, `solicitar_trabajo_historial_dto.py`.
  Los `GET` de solo consulta **no** llevan DTO (filtros vía `Query(...)`, patrón `monitoreo_router.py`).
- `infrastructure/schema/` — `reporte_gasto_schema.py` (incluye
  `ReporteGastoResponse.desde_snapshot_y_resultado_json` para reconstruir la respuesta rica de un
  trabajo async desde `resultado_json`), `historial_suministro_schema.py`.
- `infrastructure/factories/` — `reporte_gastos_factory.py`, `historial_suministros_factory.py`.
- `infrastructure/routers/` — 4 routers: `reporte_gastos_router.py` (recurso 51),
  `batch_reportes_gastos_router.py` (recurso 53), `historial_suministros_router.py` (recurso 52),
  `batch_historial_suministros_router.py` (recurso 54, solo Admin).

### Aplicación
- `application/use_cases/reporte_gastos/` — `generar_reporte_gastos_use_case.py` (decide sync/async
  por umbral de meses; `generar_forzado()` para el worker), `consultar_reporte_gastos_use_case.py`,
  `listar_historial_reportes_use_case.py`, `consultar_estado_trabajo_reporte_use_case.py`,
  `procesar_cola_reportes_gastos_use_case.py` (worker: semáforo `asyncio` + `to_thread` + reintentos
  con backoff, patrón `EjecutarBatchICAUseCase`).
- `application/use_cases/historial_suministros/` — `consultar_historial_suministros_use_case.py`
  (aplica `AlcanceActivoPort` + gate de nivel de volumen; `consultar_forzado()` para el worker),
  `exportar_historial_sincrono_use_case.py` (+ `lineas_a_csv()` reutilizado por el worker;
  `exportar_forzado()` sin límite de tamaño), `solicitar_trabajo_historial_use_case.py` (valida 429
  por tipo de trabajo), `consultar_estado_trabajo_historial_use_case.py`,
  `descargar_resultado_trabajo_historial_use_case.py`, `procesar_cola_historial_suministros_use_case.py`
  (worker, despacha CONSULTA_PESADA/EXPORTACION).

### `main.py`
- 4 routers nuevos registrados.
- 2 tareas nuevas en `lifespan` (poller continuo, no cron): `_procesar_cola_reportes_gastos_periodicamente()`,
  `_procesar_cola_historial_suministros_periodicamente()`.

## Verificación end-to-end

Ejecutada contra servidor local real con 6 usuarios de prueba (Admin/Productor/Veterinario/
Contador/Gestor de Granja/Revisor Fiscal + Ingeniero de Campo para el caso RBAC negativo). Todos
los escenarios del plan verificados exitosamente — CURLs completos y respuestas reales en
[`curls_m05_cu04_reporte_gastos_historial.md`](curls_m05_cu04_reporte_gastos_historial.md).

**Dos bugs reales encontrados y corregidos durante la verificación** (no en el análisis estático):
1. `reporte_gastos_acumulados.id_activo_biologico` era `NOT NULL` en BD → rompía reportes
   agregados. Ver Gap 9.
2. El endpoint de estado de un trabajo async de RF-77 devolvía el reporte sin desglose/tendencia
   (solo el snapshot de columnas fijas, no `resultado_json`). Corregido con
   `ReporteGastoResponse.desde_snapshot_y_resultado_json`.

Confirmado además: ningún trabajo quedó huérfano en `EN_PROCESO`; el límite de concurrencia (429)
respeta exactamente el valor configurado (3 exportaciones simultáneas); el gate de nivel de volumen
rechaza correctamente consultas síncronas por encima del umbral y las redirige a modo async; la
restricción de alcance del Gestor de Granja deniega y permite correctamente según pertenencia real
del activo.

## Qué NO se hizo (pendientes explícitos, ver gap doc)
- PDF y Excel de exportación.
- SLA con métricas/observabilidad real (dashboards, alertado).
- Caché de resultados de 30 min.
- Modelo real de "unidad productiva asignada a usuario" (M01).
- `SERVICIO_VETERINARIO`/`INSEMINACION` como origen de datos real (aceptados en el contrato de
  filtro, siempre 0 resultados).
- Reclasificación de `naturaleza_costo` vía RF-78/M09; integración M40 para `origen_precio` automático.
- Limpieza automática de exportaciones vencidas a las 72h (Restricción 3 de RF-81) — el campo de
  retención no se modela todavía; los archivos completados quedan disponibles indefinidamente en
  `contenido_csv` hasta que se implemente ese mecanismo.
