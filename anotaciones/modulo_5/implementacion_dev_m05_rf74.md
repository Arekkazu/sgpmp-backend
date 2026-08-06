# Implementación DEV — M05 CU02: Eficiencia Alimenticia / ICA (RF-74)

**Fecha:** 2026-07-30 · **Rama:** `feature/supplies`

Resumen de lo implementado para CU-02 (RF-74): cálculo del Índice de Conversión Alimenticia
por activo y período, su consulta (vigente + historial) y el motor batch nocturno con
fiabilidad. Sigue la arquitectura hexagonal/DDD del proyecto (ver `CLAUDE.md`).

## Decisiones clave
- **Lógica app-owned → `modulo5.resultado_ica`.** Los SPs de BD preexistentes de ICA
  (`sp_calcular_ica`, `sp_ejecutar_batch_ica_automatizado`, …) se dejan **intactos y sin uso**
  (usaban `mediciones_incrementales` vacía, umbrales distintos y no persistían). Ver
  [`cu02_gaps_bd_rf74.md`](cu02_gaps_bd_rf74.md).
- **Peso real desde RF-40:** `modulo2.eventos_crecimeinto` ↔ `modulo2.eventos_activos`
  (INDIVIDUAL→`valor_medicion`, POBLACIONAL→`nuevo_peso_promedio`), no `mediciones_incrementales`.
- **ORM generados con `sqlacodegen`** y adaptados (Base compartida, enum PG→`String`, sin relaciones cross-module).
- **Auditoría por trigger de BD** (la app no la duplica): se añadió `fn_trg_auditoria_resultado_ica`.

## Paso 0 (BD/RBAC) — aplicado vía MCP postgres
Detalle y SQL en [`cu02_gaps_bd_rf74.md`](cu02_gaps_bd_rf74.md). Resumen:
- `resultado_ica` + `estado_resultado`, `es_vigente`, `intento` + índice único parcial `uq_resultado_ica_vigente`.
- Tablas nuevas: `ejecuciones_batch_ica`, `cola_calculo_ica`, `fallos_calculo_ica`,
  `configuracion_batch_ica` (sembrada).
- `ALTER TYPE modulo3.enum_tipo_alerta ADD VALUE 'CONVERSION_ALIMENTICIA'`.
- Trigger de auditoría `fn_trg_auditoria_resultado_ica` (fallback a usuario sistema 1 en batch).
- RBAC: recursos `49 eficiencia_alimenticia`, `50 administracion_batch_ica` + 10 permisos.

## Estructura de código (`src/supplies/`)
- **Dominio**
  - `domain/value_objects/eficiencia_enums.py` — `PeriodoEvaluacion`, `ClasificacionCA`,
    `EstadoResultadoCA`, `TipoCalculo`, `CausaNoCalculo`, estados de batch/cola, `MotivoEncolado`.
  - `domain/value_objects/periodo_calculo.py` — resuelve la ventana `(inicio,fin)` por período.
  - `domain/services/calculadora_ica.py` — **cálculo puro**: fórmula, jerarquía de causa,
    `data_quality_score`, clasificación por umbrales del RF, truncado a 4 decimales.
  - `domain/entities/` — `resultado_ica.py` (con `_snapshot()`), `ejecucion_batch_ica.py`
    (transiciones), `fallo_calculo_ica.py`, `item_cola_ica.py`.
  - `domain/repositories/` — puertos: `resultado_ica`, `ejecucion_batch_ica`, `cola_calculo_ica`,
    `fallo_calculo_ica`, `configuracion_batch_ica`, `consumo_ica_read_port`, `pesaje_consulta_port`,
    `alerta_ica_port`, `activos_batch_port`.
- **Infraestructura**
  - `infrastructure/models/` — 5 modelos ORM (sqlacodegen) para las tablas de arriba.
  - `infrastructure/repositories/` — 6 implementaciones SQLAlchemy (`flush()`-only, `raise_from_db_error`).
    `resultado_ica_repository.guardar` desmarca el vigente anterior antes de insertar.
  - `infrastructure/adapters/` — `pesaje_m02_adapter` (SQL directo a `modulo2`),
    `alerta_ica_m03_adapter` (INSERT directo a `modulo3.alertas`), `activos_batch_m02_adapter`.
    Reutiliza `ActivoM02Adapter` y `CicloM02Adapter` de CU-01.
  - `infrastructure/dto/calcular_ica_dto.py`, `infrastructure/schema/eficiencia_schema.py`.
  - `infrastructure/factories/eficiencia_factory.py` — wiring de use cases (routers/batch/scheduler).
- **Aplicación** (`application/use_cases/eficiencia/`)
  - `calcular_ica_use_case.py` — **núcleo** (manual, batch y reintento). Persiste, genera alerta si
    CRITICA, `commit`/`rollback`. `CA_NO_CALCULABLE` por datos → 200 (no reintento).
  - `consultar_ica_vigente_use_case.py`, `consultar_historial_ica_use_case.py`.
  - `ejecutar_batch_ica_use_case.py` — motor completo: selección/priorización, límite→cola,
    workers paralelos (`asyncio` + `to_thread`, sesión por activo), ventana, reintentos+backoff,
    `CA_FALLO_PERSISTENTE`, interrupción cooperativa.
  - `interrumpir_batch_ica_use_case.py`, `reintentar_ica_manual_use_case.py`.
- **Routers** (`infrastructure/routers/`)
  - `eficiencia_alimenticia_router.py` (recurso 49): `POST /calcular`, `GET .../vigente`, `GET .../historial`.
  - `batch_ica_router.py` (recurso 50): `POST /ejecutar`, `/{id}/interrumpir`,
    `/activos/{id}/reintentar`, `GET /estado`, `/cola`, `/fallos`.
  - Registrados en `main.py`.
- **Scheduler** (`main.py`): `_ejecutar_batch_ica_diario` en el `lifespan` (junto al de RF-60);
  corre el batch a `hora_ejecucion` (02:00 por defecto).

## Verificación realizada (end-to-end, contra BD dev)
1. **Cálculo manual (Flujo A):** activo 1 MENSUAL → `CALCULADO`, `CA=6.7226`, `CRITICA`,
   `ganancia=59.5`, `dq=100`; fila en `resultado_ica` (`es_vigente=true`) + alerta
   `CONVERSION_ALIMENTICIA/CRITICO` en `modulo3.alertas` + auditoría en `auditorias_suministros`.
2. **CA_NO_CALCULABLE:** activo 1 SEMANAL → causa `SIN_REGISTROS_CONSUMO`, `dq=75` (200, persistido).
3. **Reemplazo de vigente:** recalcular MENSUAL → el anterior queda `es_vigente=false` y aparece en historial.
4. **Batch (Flujo C):** `ejecuciones_batch_ica` `COMPLETADO`, 10 activos procesados, 0 fallidos;
   22 resultados vigentes; cola y fallos vacíos.
5. **Interrupción:** interrumpir una corrida `COMPLETADO` → `422 BATCH_NO_EN_EJECUCION` (guarda de estado).
6. **Reintento manual:** activo 1 → recalcula SEMANAL/MENSUAL y omite POR_CICLO (sin ciclo) sin abortar.
7. **HTTP:** `uvicorn` arranca; `/health` 200; endpoints protegidos sin token → `401`; 9 rutas ICA en OpenAPI.
8. **RBAC (a nivel de datos):** recurso 49 (R+E → roles 1/2/3), recurso 50 (R+E → roles 1/2).

## Datos de prueba añadidos en dev (permanentes por triggers de inmutabilidad)
- Pesaje para activo 1: `PESO 400.00 kg` el 2026-07-28 (`eventos_activos`/`eventos_crecimeinto`, id_evento 89).
- Consumo VALIDADO para activo 1: `400 kg` el 2026-07-15 (`registros_consumo_alimentos`, id 30).
Estos crean el caso calculable/CRITICA usado en la verificación. No se pudieron revertir (M02/M05
tienen triggers `no_delete`/inmutabilidad). Las filas de `resultado_ica`, alertas y batch generadas
son datos legítimos del módulo y se dejan como evidencia.

## Pendientes / notas
- El backoff de reintentos (`configuracion_batch_ica.backoff_minutos`, def. `[2,4,6]` min) es lento
  para probar el camino de fallo técnico; ajustable en dev vía esa fila.
- La "notificación a Admin/Productor" por límite superado se materializa como cola + panel de batch
  (no push/email). El envío real de notificaciones queda fuera de alcance (va después del `commit`).
- El batch manual (`POST /batch/ejecutar`) se **espera** a que termine (await); para volúmenes muy
  grandes en producción, el disparo nocturno del scheduler es el canal principal.
