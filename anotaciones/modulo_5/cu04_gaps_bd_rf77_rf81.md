# CU04 (M05) — Gaps entre el documento y la base de datos (RF-77 + RF-81)

## Fecha de análisis / aplicación
2026-07-30

## Contexto
CU-04 "Reportar Gastos e Historial de Suministros" cubre **RF-77** (reporte de gastos
acumulados por activo, con desglose por categoría/período, tendencia vs período anterior y
gasto promedio por individuo) y **RF-81** (consulta paginada de trazabilidad/historial de
suministros con filtros combinados, RBAC por unidad productiva, exportación y SLA por nivel
de volumen).

Al momento de iniciar este CU, RF-77 y RF-81 estaban en **0% de implementación** en
`src/supplies` (confirmado por grep exhaustivo y por
`implementacion_dev_m05_rf75_rf76.md`, que lista "reporte de gastos/RF-77" explícitamente
como fuera de alcance de CU-01).

Este documento registra los gaps encontrados vía **MCP postgres** y las decisiones aplicadas
**antes** de codificar. Todo el DDL/DML se aplicó directo en la BD dev (no gestionado por
migraciones, igual que el resto del proyecto).

Decisiones de alcance tomadas con el usuario antes de este análisis (vinculantes):
1. Construir infraestructura async real (cola de trabajos en BD + workers `asyncio`, mismo
   patrón que el motor batch ICA de CU-02) en vez de un límite duro tipo RF-59.
2. Solo exportación **CSV** en esta iteración — no hay librería de PDF/Excel en el proyecto.
3. Crear los roles `Gestor de Granja` y `Revisor Fiscal` en `modulo1.roles` (RF-81 los
   menciona como actores y no existían).
4. Poblar y usar `modulo5.registro_suministro` (ledger unificado) como fuente del detalle de
   RF-81, alimentado desde `registros_consumo_alimentos`/`registros_medicamentos` (RF-75/76).

---

## Hallazgo transversal — scaffolding de BD preexistente, huérfano e inconsistente con el RF

Igual que ocurrió con ICA antes de CU-02, `modulo5` ya traía tablas/vistas/una función para
RF-77/RF-81 sin ningún consumidor en la app. Divergencias detectadas (decisión: no usar tal
cual, corregir donde hay bugs reales, aprovechar como lectura donde sirve):

| Objeto BD | Problema | Decisión |
|---|---|---|
| `modulo5.fn_consultar_historial_suministros(p_activo_id, p_filtro jsonb, p_pagina, p_limite)` | Etiquetada "(RF-81)" en sus mensajes de error, pero pagina por página/OFFSET (no por cursor), solo filtra `fecha_inicio`/`fecha_fin`/`origen`, y lee de `historial_suministros_activos` (tabla resumen, 0 filas) en vez del detalle granular | No se invoca. La app construye la consulta con SQL propio (`text()`) sobre `vw_m05_historial_suministros_detalle`. |
| `modulo5.historial_suministros_activos` | Tabla de resumen por consulta (0 filas, sin trigger que la alimente) | Se deja intacta, sin uso. No es la fuente de RF-81 (el detalle línea a línea vive en `registro_suministro`). |
| `modulo5.reporte_gastos_acumulados` | Snapshot por reporte generado; sin columnas de desglose SEMANAL/MENSUAL ni tendencia | Se usa como tabla de persistencia del "historial de reportes" (RNF de RF-77), pero el desglose/tendencia se calculan en la app y se guardan aparte (`resultado_json` en `ejecuciones_generacion_reportes_gastos`, ver Gap 4). |
| `modulo5.vw_m05_historial_suministros_detalle` | **Bug real**: `WHERE naturaleza_costo = 'INVERSION'` en ambas ramas del `UNION ALL`. Con el default de población `MANTENIMIENTO` (ver Gap 1), la vista devolvería 0 filas siempre | Corregida con `CREATE OR REPLACE VIEW` (Gap 0). |
| `modulo5.vw_m05_reporte_gastos_detalle` | Verificada contra datos reales antes de usarla: `SELECT count(*)` da 26 = 14 (consumo) + 12 (medicamento), sin duplicación cartesiana pese al `LEFT JOIN tipos_alimentos ON id_tipo_elemento::text = id_idempotencia::text` | Válida para uso directo, filtrando `estado = 'VALIDADO'` en la app (la vista no filtra por estado). |

---

## Gap 0 — Corrección del bug en `vw_m05_historial_suministros_detalle`

```sql
CREATE OR REPLACE VIEW modulo5.vw_m05_historial_suministros_detalle AS
SELECT rs.id_registro_suministro, ab.id_activo_biologico, ab.identificador AS identificador_activo,
       e.nombre AS especie, f.nombre AS finca, cp.id_ciclo_productivo, cp.nombre AS ciclo_productivo,
       'ALIMENTO'::text AS tipo_suministro, ta.nombre AS detalle, rs.fecha_aplicacion, rs.cantidad,
       rs.unidad_medida, rs.precio_unitario_resuelto AS precio_unitario, rs.costo_registro AS costo_total,
       rs.origen_precio, rs.tipo_operacion, rs.observacion, rs.fecha_registro, rs.id_registro_rf75 AS id_rf_origen
FROM modulo5.registro_suministro rs
JOIN modulo2.activos_biologicos ab ON ab.id_activo_biologico = rs.id_activo_biologico
JOIN modulo9.especies e ON e.id_especie = ab.id_especie
JOIN modulo9.infraestructuras i ON i.id_infraestructura = ab.id_infraestructura
JOIN modulo9.fincas f ON f.id_finca = i.id_finca
JOIN modulo9.ciclos_productivos cp ON cp.id_ciclo_productivo = rs.id_ciclo_productivo
LEFT JOIN modulo5.tipos_alimentos ta ON ta.id_tipo_elemento::text = rs.id_idempotencia::text
WHERE rs.id_registro_rf75 IS NOT NULL
UNION ALL
SELECT rs.id_registro_suministro, ab.id_activo_biologico, ab.identificador, e.nombre, f.nombre,
       cp.id_ciclo_productivo, cp.nombre, 'MEDICAMENTO'::text, rm.nombre_medicamento, rs.fecha_aplicacion,
       rs.cantidad, rs.unidad_medida, rs.precio_unitario_resuelto, rs.costo_registro, rs.origen_precio,
       rs.tipo_operacion, rs.observacion, rs.fecha_registro, rs.id_registro_rf76
FROM modulo5.registro_suministro rs
JOIN modulo2.activos_biologicos ab ON ab.id_activo_biologico = rs.id_activo_biologico
JOIN modulo9.especies e ON e.id_especie = ab.id_especie
JOIN modulo9.infraestructuras i ON i.id_infraestructura = ab.id_infraestructura
JOIN modulo9.fincas f ON f.id_finca = i.id_finca
JOIN modulo9.ciclos_productivos cp ON cp.id_ciclo_productivo = rs.id_ciclo_productivo
LEFT JOIN modulo5.registros_medicamentos rm ON rm.id_registro_rf76 = rs.id_registro_rf76
WHERE rs.id_registro_rf76 IS NOT NULL;
```

El filtro roto por `naturaleza_costo` se reemplazó por `id_registro_rfXX IS NOT NULL`, que es
la forma correcta y explícita de distinguir "es fila de alimento" vs "es fila de medicamento"
dentro de cada rama del `UNION ALL` (ambas ramas leen la misma tabla `registro_suministro`).

---

## Gap 1 — Triggers de población de `registro_suministro` (AFTER INSERT)

`registro_suministro` es el ledger granular unificado (uuid, con `origen_precio` y
`naturaleza_costo`) que RF-81 necesita para el detalle línea a línea. Estaba vacío y sin
ningún trigger que lo alimentara. Los registros de RF-75/76 nacen en estado `VALIDADO`
directamente (no hay paso de validación posterior), así que un `AFTER INSERT` es suficiente.

```sql
CREATE OR REPLACE FUNCTION modulo5.fn_trg_poblar_registro_suministro_alimento() RETURNS trigger AS $$
DECLARE v_id_ciclo integer;
BEGIN
  IF NEW.estado_registro <> 'VALIDADO' THEN RETURN NEW; END IF;
  SELECT id_ciclo_productiva INTO v_id_ciclo FROM modulo2.gestiones_fases
   WHERE id_activo_biologico = NEW.id_activo_biologico
   ORDER BY es_activa DESC, fecha_inicio DESC LIMIT 1;
  IF v_id_ciclo IS NULL THEN
    RAISE WARNING 'registro_suministro: activo % sin ciclo productivo; se omite ledger para consumo %',
      NEW.id_activo_biologico, NEW.id_consumo_alimeto;
    RETURN NEW;
  END IF;
  INSERT INTO modulo5.registro_suministro
    (id_activo_biologico, id_ciclo_productivo, cantidad, unidad_medida, precio_unitario_resuelto,
     costo_registro, origen_precio, fecha_aplicacion, observacion, tipo_operacion, id_registro_rf75, naturaleza_costo)
  VALUES
    (NEW.id_activo_biologico, v_id_ciclo, NEW.cantidad_suministrada, NEW.tipo_unidad,
     COALESCE(NEW.costo_unitario, 0), COALESCE(NEW.costo_total, 0), 'MANUAL',
     COALESCE(NEW.fecha_consumo, NEW.fecha_registro::date), NEW.observacion, 'REGISTRO',
     NEW.id_registro_rf75, 'MANTENIMIENTO');
  RETURN NEW;
END; $$ LANGUAGE plpgsql;

CREATE TRIGGER trg_poblar_registro_suministro_alimento
AFTER INSERT ON modulo5.registros_consumo_alimentos
FOR EACH ROW EXECUTE FUNCTION modulo5.fn_trg_poblar_registro_suministro_alimento();

-- Análogo para medicamentos (cantidad, unidad_dosis, costo_unitario_medicamento,
-- costo_total_medicamento, fecha_aplicacion, motivo_aplicacion, id_registro_rf76)
CREATE OR REPLACE FUNCTION modulo5.fn_trg_poblar_registro_suministro_medicamento() RETURNS trigger AS $$
DECLARE v_id_ciclo integer;
BEGIN
  IF NEW.estado_registro <> 'VALIDADO' THEN RETURN NEW; END IF;
  SELECT id_ciclo_productiva INTO v_id_ciclo FROM modulo2.gestiones_fases
   WHERE id_activo_biologico = NEW.id_activo_biologico
   ORDER BY es_activa DESC, fecha_inicio DESC LIMIT 1;
  IF v_id_ciclo IS NULL THEN
    RAISE WARNING 'registro_suministro: activo % sin ciclo productivo; se omite ledger para medicamento %',
      NEW.id_activo_biologico, NEW.id_registro_medicamento;
    RETURN NEW;
  END IF;
  INSERT INTO modulo5.registro_suministro
    (id_activo_biologico, id_ciclo_productivo, cantidad, unidad_medida, precio_unitario_resuelto,
     costo_registro, origen_precio, fecha_aplicacion, observacion, tipo_operacion, id_registro_rf76, naturaleza_costo)
  VALUES
    (NEW.id_activo_biologico, v_id_ciclo, NEW.cantidad, NEW.unidad_dosis,
     COALESCE(NEW.costo_unitario_medicamento, 0), COALESCE(NEW.costo_total_medicamento, 0), 'MANUAL',
     NEW.fecha_aplicacion, NEW.motivo_aplicacion, 'REGISTRO', NEW.id_registro_rf76, 'MANTENIMIENTO');
  RETURN NEW;
END; $$ LANGUAGE plpgsql;

CREATE TRIGGER trg_poblar_registro_suministro_medicamento
AFTER INSERT ON modulo5.registros_medicamentos
FOR EACH ROW EXECUTE FUNCTION modulo5.fn_trg_poblar_registro_suministro_medicamento();
```

**Decisiones de gap (documentadas y vinculantes)**:
- `origen_precio = 'MANUAL'` para todo registro RF-75/76 — no existe integración M40
  (pricing automático) en el sistema todavía. Cuando exista, el trigger (o la lógica que lo
  reemplace) deberá resolver el origen real.
- `naturaleza_costo = 'MANTENIMIENTO'` para todo registro de alimentación/medicación — RF-78
  (Acumulación de Inversión, que define la política de capitalización MANTENIMIENTO vs
  INVERSION según la especie configurada en M09) está fuera de alcance de este CU. Cuando
  RF-78 se implemente, podrá reclasificar estas filas.
- Si el activo no tiene ninguna fase en `gestiones_fases` (caso borde — no debería ocurrir
  dado que RF-33/37 exigen ciclo abierto para registrar consumo/medicamento), el trigger
  **no bloquea** el INSERT del padre; solo emite `RAISE WARNING` y omite el ledger. Deuda de
  integridad a monitorear, no bloqueante para RF-75/76.

---

## Gap 2 — Backfill de los registros VALIDADO ya existentes

```sql
INSERT INTO modulo5.registro_suministro (...)
SELECT ... FROM modulo5.registros_consumo_alimentos rca
LEFT JOIN LATERAL (SELECT id_ciclo_productiva FROM modulo2.gestiones_fases
  WHERE id_activo_biologico = rca.id_activo_biologico ORDER BY es_activa DESC, fecha_inicio DESC LIMIT 1) gf ON true
WHERE rca.estado_registro = 'VALIDADO' AND gf.id_ciclo_productiva IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM modulo5.registro_suministro rs WHERE rs.id_registro_rf75 = rca.id_registro_rf75);
-- Análogo para registros_medicamentos → id_registro_rf76
```

Resultado verificado: `registros_consumo_alimentos` tenía 14 filas totales (10 `VALIDADO`);
`registros_medicamentos` tenía 12 filas totales (7 `VALIDADO`). Backfill insertó **17** filas
en `registro_suministro` (10+7, exacto), y `vw_m05_historial_suministros_detalle` corregida
(Gap 0) devuelve también 17. Las filas `ANULADO` quedan correctamente excluidas del ledger,
consistente con la Restricción 1 de RF-77 ("solo VALIDADO").

---

## Gap 3 — Enum de formato de exportación: faltaba CSV

`modulo5.enum_historial_suministros_activos_formatos_exportacion` solo tenía
`XLS`/`PDF`/`PANTALLA`. Esta iteración solo exporta CSV (decisión de alcance #2):

```sql
ALTER TYPE modulo5.enum_historial_suministros_activos_formatos_exportacion ADD VALUE IF NOT EXISTS 'CSV';
```

---

## Gap 4 — Tablas del motor async RF-77 (generación de reportes de gastos)

No existía ninguna infraestructura de cola para reportes. Se replica el patrón de
`cola_calculo_ica`/`ejecuciones_batch_ica`/`fallos_calculo_ica` (CU-02), con una diferencia
deliberada: aquí cada fila de cola es **un trabajo único** (un reporte con sus propios
filtros), no un lote de N activos, así que `parametros`/`resultado_json` usan `jsonb` en vez
de columnas fijas — evita decenas de columnas nullable para filtros heterogéneos.

```sql
CREATE TABLE modulo5.cola_generacion_reportes_gastos (
  id_cola serial PRIMARY KEY,
  parametros jsonb NOT NULL,
  estado varchar(20) NOT NULL DEFAULT 'PENDIENTE',   -- PENDIENTE|EN_PROCESO|COMPLETADO|FALLIDO
  id_usuario_solicitante int NOT NULL REFERENCES modulo1.usuarios(id_usuario),
  fecha_solicitud timestamptz NOT NULL DEFAULT now(),
  fecha_procesado timestamptz
);
CREATE INDEX idx_cola_reportes_gastos_estado ON modulo5.cola_generacion_reportes_gastos (estado, fecha_solicitud);

CREATE TABLE modulo5.ejecuciones_generacion_reportes_gastos (
  id_ejecucion serial PRIMARY KEY,
  id_cola int NOT NULL REFERENCES modulo5.cola_generacion_reportes_gastos(id_cola),
  estado varchar(20) NOT NULL DEFAULT 'EN_PROCESO',
  intento int NOT NULL DEFAULT 1,
  hora_inicio timestamptz NOT NULL DEFAULT now(),
  hora_fin timestamptz,
  id_reporte_resultado int REFERENCES modulo5.reporte_gastos_acumulados(id_reporte_gasto_acumulado),
  resultado_json jsonb,     -- desglose semanal/mensual + tendencia
  creado_en timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_ejec_reportes_gastos_cola ON modulo5.ejecuciones_generacion_reportes_gastos (id_cola);

CREATE TABLE modulo5.fallos_generacion_reportes_gastos (
  id_fallo serial PRIMARY KEY,
  id_cola int NOT NULL REFERENCES modulo5.cola_generacion_reportes_gastos(id_cola),
  causa_fallo text, intentos int NOT NULL DEFAULT 0, timestamp_ultimo_intento timestamptz,
  resuelto boolean NOT NULL DEFAULT false, creado_en timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX uq_fallo_reporte_gastos_abierto ON modulo5.fallos_generacion_reportes_gastos (id_cola) WHERE NOT resuelto;

CREATE TABLE modulo5.configuracion_batch_reportes_gastos (
  id_configuracion int GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  num_workers_max int NOT NULL DEFAULT 2,
  max_reintentos int NOT NULL DEFAULT 3,
  backoff_minutos int[] NOT NULL DEFAULT ARRAY[1,3,5],
  limite_concurrencia int NOT NULL DEFAULT 5,        -- 429 si PENDIENTE+EN_PROCESO lo supera
  intervalo_poll_segundos int NOT NULL DEFAULT 15,
  es_activo boolean NOT NULL DEFAULT true,
  actualizado_en timestamptz NOT NULL DEFAULT now()
);
INSERT INTO modulo5.configuracion_batch_reportes_gastos DEFAULT VALUES;
```

---

## Gap 5 — Tablas del motor async RF-81 (consultas nivel 3/4 + exportaciones >10.000)

Mismo patrón y misma justificación de `jsonb` que el Gap 4. `tipo_trabajo` distingue
`CONSULTA_PESADA` (nivel 3/4 de volumen) de `EXPORTACION` (>10.000 registros).

```sql
CREATE TABLE modulo5.cola_trabajos_historial_suministros (
  id_cola serial PRIMARY KEY,
  tipo_trabajo varchar(20) NOT NULL,     -- CONSULTA_PESADA|EXPORTACION
  parametros jsonb NOT NULL,
  estado varchar(20) NOT NULL DEFAULT 'PENDIENTE',
  id_usuario_solicitante int NOT NULL REFERENCES modulo1.usuarios(id_usuario),
  fecha_solicitud timestamptz NOT NULL DEFAULT now(),
  fecha_procesado timestamptz
);
CREATE INDEX idx_cola_hist_sum_estado ON modulo5.cola_trabajos_historial_suministros (estado, fecha_solicitud);

CREATE TABLE modulo5.ejecuciones_trabajos_historial_suministros (
  id_ejecucion serial PRIMARY KEY,
  id_cola int NOT NULL REFERENCES modulo5.cola_trabajos_historial_suministros(id_cola),
  estado varchar(20) NOT NULL DEFAULT 'EN_PROCESO',
  intento int NOT NULL DEFAULT 1,
  hora_inicio timestamptz NOT NULL DEFAULT now(),
  hora_fin timestamptz,
  total_registros int,
  resultado_json jsonb,        -- metadatos + primera página (CONSULTA_PESADA)
  contenido_csv text,          -- payload completo (EXPORTACION)
  nombre_archivo varchar(120),
  creado_en timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_ejec_hist_sum_cola ON modulo5.ejecuciones_trabajos_historial_suministros (id_cola);

CREATE TABLE modulo5.fallos_trabajos_historial_suministros (
  id_fallo serial PRIMARY KEY,
  id_cola int NOT NULL REFERENCES modulo5.cola_trabajos_historial_suministros(id_cola),
  causa_fallo text, intentos int NOT NULL DEFAULT 0, timestamp_ultimo_intento timestamptz,
  resuelto boolean NOT NULL DEFAULT false, creado_en timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX uq_fallo_hist_sum_abierto ON modulo5.fallos_trabajos_historial_suministros (id_cola) WHERE NOT resuelto;

CREATE TABLE modulo5.configuracion_batch_historial_suministros (
  id_configuracion int GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  num_workers_max int NOT NULL DEFAULT 2,
  max_reintentos int NOT NULL DEFAULT 3,
  backoff_minutos int[] NOT NULL DEFAULT ARRAY[1,3,5],
  limite_concurrencia_exportaciones int NOT NULL DEFAULT 3,  -- 429 si se excede
  limite_concurrencia_consultas int NOT NULL DEFAULT 5,
  umbral_nivel3 int NOT NULL DEFAULT 10000,
  umbral_nivel4 int NOT NULL DEFAULT 50000,
  tope_maximo_registros int NOT NULL DEFAULT 200000,   -- rechazo duro (BusinessRuleError)
  umbral_exportacion_async int NOT NULL DEFAULT 10000,
  intervalo_poll_segundos int NOT NULL DEFAULT 15,
  es_activo boolean NOT NULL DEFAULT true,
  actualizado_en timestamptz NOT NULL DEFAULT now()
);
INSERT INTO modulo5.configuracion_batch_historial_suministros DEFAULT VALUES;
```

Los umbrales (10.000/50.000/200.000, 12/6 meses para RF-77) son constantes de configuración
propias — el RF no da números exactos de SLA medibles en este entorno, así que se fijan
valores razonables y configurables en vez de intentar replicar tiempos de respuesta
contractuales (ver sección de pendientes).

---

## Gap 6 — Roles nuevos (`Gestor de Granja`, `Revisor Fiscal`)

RF-81 menciona estos dos actores; no existían en `modulo1.roles` (los roles reales eran:
Administrador, Productor, Veterinario, Ingeniero de Campo, Contador, Supervisor).

```sql
INSERT INTO modulo1.roles (nombre_rol, descripcion, es_protegido) VALUES
  ('Gestor de Granja', 'Gestión operativa de unidades productivas asignadas; consulta trazabilidad de suministros de sus activos (RF-81).', false),
  ('Revisor Fiscal', 'Auditoría financiera con acceso de solo lectura total a trazabilidad e historial de suministros (RF-81).', false);
```

`id_rol` resultante confirmado: **7 = Gestor de Granja, 8 = Revisor Fiscal**.

---

## Gap 7 — Recursos y permisos RBAC nuevos

`MAX(id_recurso)` confirmado en 50 al momento de aplicar. Nuevos recursos:

```sql
INSERT INTO modulo1.recursos (id_recurso, nombre_recurso, descripcion, es_proceso_especial) VALUES
  (51, 'reporte_gastos_suministros', 'Generación y consulta de reportes de gastos acumulados de suministros — RF-77', true),
  (52, 'historial_suministros', 'Consulta y exportación de trazabilidad/historial de suministros — RF-81', true),
  (53, 'administracion_batch_reportes_gastos', 'Administración del motor async de reportes de gastos — RF-77', true),
  (54, 'administracion_batch_historial_suministros', 'Administración del motor async de historial de suministros — RF-81', true);
```

### Matriz RBAC final (E=5 ejecutar/generar, R=2 leer)

| Recurso | Acción | Roles | Justificación |
|---|---|---|---|
| 51 `reporte_gastos_suministros` | E | Administrador, Productor | RF-77 restringe explícitamente la generación a Productor/Administrador |
| 51 `reporte_gastos_suministros` | R | Administrador, Productor, Contador | Contador lee como insumo del módulo financiero (justificación explícita del RF) |
| 52 `historial_suministros` | R, E | Administrador, Productor, Veterinario, Contador, Gestor de Granja, Revisor Fiscal | RF-81 precondición: Gestor de Granja/Contador/Revisor Fiscal; se agregan Productor/Veterinario como actores secundarios del encabezado del CU-04 |
| 53 `administracion_batch_reportes_gastos` | E, R | Administrador, Productor | Espejo del recurso 50 (`administracion_batch_ica`) |
| 54 `administracion_batch_historial_suministros` | E, R | Administrador | El panel muestra cola/fallos de trabajos de *otros* usuarios (incl. Gestor de Granja) — se restringe a Admin para no filtrar visibilidad cruzada entre unidades productivas |

**Importante**: Gestor de Granja tiene el mismo permiso RBAC (52) que los demás roles — su
restricción real ("solo sus activos") se aplica **por dato, no por permiso**, dentro del use
case vía `AlcanceActivoPort` (ver siguiente sección). RBAC decide *si puede entrar al
endpoint*; el alcance decide *qué filas ve*.

DML de permisos (roles 1/2/3/5/7/8 confirmados arriba):

```sql
INSERT INTO modulo1.permisos (id_rol, id_recurso, id_accion, nombre, es_activo) VALUES
  (1,51,5,'admin_ejecutar_reporte_gastos_suministros',true),
  (2,51,5,'prod_ejecutar_reporte_gastos_suministros',true),
  (1,51,2,'admin_leer_reporte_gastos_suministros',true),
  (2,51,2,'prod_leer_reporte_gastos_suministros',true),
  (5,51,2,'cont_leer_reporte_gastos_suministros',true),
  (1,52,2,'admin_leer_historial_suministros',true),
  (1,52,5,'admin_ejecutar_historial_suministros',true),
  (2,52,2,'prod_leer_historial_suministros',true),
  (2,52,5,'prod_ejecutar_historial_suministros',true),
  (3,52,2,'vet_leer_historial_suministros',true),
  (3,52,5,'vet_ejecutar_historial_suministros',true),
  (5,52,2,'cont_leer_historial_suministros',true),
  (5,52,5,'cont_ejecutar_historial_suministros',true),
  (7,52,2,'gestor_leer_historial_suministros',true),
  (7,52,5,'gestor_ejecutar_historial_suministros',true),
  (8,52,2,'revfiscal_leer_historial_suministros',true),
  (8,52,5,'revfiscal_ejecutar_historial_suministros',true),
  (1,53,5,'admin_ejecutar_batch_reportes_gastos',true),
  (2,53,5,'prod_ejecutar_batch_reportes_gastos',true),
  (1,53,2,'admin_leer_batch_reportes_gastos',true),
  (2,53,2,'prod_leer_batch_reportes_gastos',true),
  (1,54,5,'admin_ejecutar_batch_historial_suministros',true),
  (1,54,2,'admin_leer_batch_historial_suministros',true);
```

---

## Gap 8 — `TooManyRequestsError` (429) en `src/shared/errors.py`

No existía ninguna clase 429 en la jerarquía de errores (`ValidationError` 400,
`AuthenticationError` 401, `AuthorizationError` 403, `NotFoundError` 404, `ConflictError` 409,
`GoneError` 410, `PreconditionFailedError` 412, `BusinessRuleError`/`FlowError` 422,
`LockedError` 423, `InfrastructureError` 500, `ServiceUnavailableError` 503). RF-77
(concurrencia de generación de reportes) y RF-81 (límite de exportaciones concurrentes) piden
HTTP 429 explícitamente. Se agregó `TooManyRequestsError(AppError)` con `status_code = 429`
en `src/shared/errors.py` — el handler global (`src/shared/error_handlers.py`) es genérico
por `exc.status_code`, no requirió cambios. Tabla de errores en `CLAUDE.md` actualizada.

---

## Gap 9 — `reporte_gastos_acumulados.id_activo_biologico` era `NOT NULL` (bug encontrado en verificación E2E)

Detectado al probar el flujo async con un reporte agregado por `id_infraestructura` (sin
`activo_biologico_id`, caso explícitamente soportado por RF-77: "todos los activos de una
especie en una infraestructura"): el trabajo se encoló correctamente (202) pero el worker lo
marcó `FALLIDO` con causa "Error de integridad en base de datos" — la columna
`id_activo_biologico` de `reporte_gastos_acumulados` era `NOT NULL`, incompatible con el
propio modelo de dominio (`ReporteGasto.id_activo_biologico: Optional[int]`) y con el caso de
uso agregado que el RF exige soportar.

```sql
ALTER TABLE modulo5.reporte_gastos_acumulados ALTER COLUMN id_activo_biologico DROP NOT NULL;
```

Corregido también el modelo ORM (`reporte_gasto_acumulado_model.py`):
`id_activo_biologico: Mapped[Optional[int]]` sin `nullable=False`. Reintentado el flujo tras
el fix — el reporte agregado se generó y persistió correctamente (ver
`curls_m05_cu04_reporte_gastos_historial.md`, escenario RF-77 async agregado).

---

## Pendientes explícitamente diferidos (no implementados en este CU)

- **PDF y Excel** de exportación (RF-77 pide PDF/CSV, RF-81 pide PDF/Excel) — solo CSV esta
  iteración. No se instaló `reportlab` ni `openpyxl`.
- **SLA con métricas/observabilidad real** (dashboards, alertado sobre tiempos de respuesta
  por nivel de volumen) — se implementan umbrales de enrutamiento sync/async configurables,
  no un sistema de monitoreo.
- **Caché de 30 min** de resultados de consulta repetidos — no implementado; cada consulta
  recalcula.
- **Modelo real de "unidad productiva asignada a un usuario"** — no existe ninguna tabla de
  este tipo en todo el esquema (verificado: no hay `usuario_finca`/`usuario_infraestructura`/
  `asignacion` en ningún schema). `UsuarioActual` solo tiene `id_usuario`, `id_token`,
  `id_rol`. Regla interina aplicada: Gestor de Granja solo ve activos donde
  `modulo2.activos_biologicos.id_usuario = usuario_actual.id_usuario` (el activo que él mismo
  registró), implementada exclusivamente en `AlcanceActivoM02Adapter` (infraestructura) para
  poder reemplazarse sin tocar el use case cuando M01 tenga un modelo real de asignación.
- **`SERVICIO_VETERINARIO` e `INSEMINACION`** como valores de `tipo_suministro_filtro` — se
  aceptan en el contrato de API/enum de dominio (no se excluyen, para no romper el contrato
  documentado del RF) pero no tienen tabla origen en `modulo5`; siempre devuelven 0
  resultados hasta que existan.
- **Reclasificación de `naturaleza_costo`** vía política de especie (RF-78/M09) — fuera de
  alcance de este CU.
- **Integración M40** para `origen_precio = M40_AUTOMATICO` — fuera de alcance.
