# CU02 (M05) — Gaps entre el documento y la base de datos (RF-74)

## Fecha de análisis / aplicación
2026-07-30

## Contexto
CU-02 "Calcular y Consultar Eficiencia Alimenticia (ICA)" cubre **RF-74**: cálculo del
Índice de Conversión Alimenticia (`CA = Alimento Total Consumido (kg) / Ganancia de Peso
Total (kg)`) por activo y período (SEMANAL / MENSUAL / POR_CICLO), su consulta (vigente e
historial) y el **motor batch nocturno** con fiabilidad (reintentos con backoff, cola
persistente, workers, límite/priorización, estados de ejecución).

Este documento registra los gaps encontrados vía **MCP postgres** y las decisiones
aplicadas **antes** de codificar. Todo el DDL/DML se aplicó directo en la BD dev (no
gestionado por migraciones, igual que el resto del proyecto).

Tabla objetivo: `modulo5.resultado_ica` (+ vista `modulo5.vw_m05_historial_ica`).

---

## Hallazgo transversal — Maquinaria ICA preexistente en BD, inconsistente y huérfana

La BD ya traía piezas de un ICA a medio construir. **Decisión del equipo: implementar la
lógica ICA en la aplicación (`src/supplies`) escribiendo a `resultado_ica`, y dejar los SPs
de BD intactos pero sin usar.** Divergencias detectadas (se ignoran a propósito):

| Objeto BD | Problema | Decisión |
|---|---|---|
| `sp_calcular_ica`, `fn_calcular_ica_periodo`, `sp_ejecutar_batch_ica_automatizado` | Leen/escriben `mediciones_incrementales` (**0 filas**); el batch **no persiste** en `resultado_ica` | No se invocan. La app calcula y persiste. |
| `fn_clasificar_eficiencia_ica` | Umbrales ≤1.5 / ≤2.5 / ≤3.5 — **no** son los del RF (<2.0 / 3.6–5.0 / >5.0) | Se ignora. La clasificación la hace el servicio de dominio con umbrales del RF. |
| Fuente de peso `mediciones_incrementales` | Vacía; el peso real (RF-40) vive en `modulo2.eventos_crecimeinto` ↔ `modulo2.eventos_activos` | El adapter de pesaje consulta `modulo2`, no `mediciones_incrementales`. |
| `fn_trg_disparar_recalculo_ica_post_consumo` (trigger en `registros_consumo_alimentos`) | Dispara recálculo hacia la maquinaria vieja (mediciones_incrementales) | Inofensivo para CU-01; la app no depende de él. El recálculo real es responsabilidad del batch/endpoint manual de CU-02. |

`resultado_ica` **no tenía triggers** (verificado): los valores que inserta la app no se
sobrescriben, y no había auditoría automática para esta tabla (ver Gap 5).

---

## Gap 1 — `resultado_ica`: faltan columnas para vigente/historial/reintentos

La tabla no distinguía el resultado "vigente" del histórico ni registraba el número de
intento. Aplicado:

```sql
ALTER TABLE modulo5.resultado_ica
  ADD COLUMN estado_resultado varchar(20) NOT NULL DEFAULT 'CALCULADO',  -- CALCULADO | CA_NO_CALCULABLE
  ADD COLUMN es_vigente       boolean     NOT NULL DEFAULT true,
  ADD COLUMN intento          integer     NOT NULL DEFAULT 1;

-- Un único resultado vigente por (activo, período); el reemplazo pone es_vigente=false
-- en el anterior (queda como histórico) e inserta el nuevo vigente.
CREATE UNIQUE INDEX uq_resultado_ica_vigente
  ON modulo5.resultado_ica (id_activo_biologico, periodo_evaluacion)
  WHERE es_vigente;
```

Columnas ya presentes y reutilizadas: `ca_calculado`, `clasificacion_ca`
(`enum_clasificacion_ca`: EXCELENTE/ACEPTABLE/BAJA/CRITICA), `data_quality_score`,
`causa_no_calculo` (varchar), `tipo_calculo` (varchar), `alimento_consumido_total_kg`,
`ganancia_peso_kg`, `fecha_inicio_periodo`, `fecha_fin_periodo`, `id_usuario`,
`fecha_calculo`, `periodo_evaluacion` (`enum_periodo_evaluacion`: SEMANAL/MENSUAL/POR_CICLO).

---

## Gap 2 — Tablas del motor batch (no existían)

```sql
-- Estados de cada corrida del batch (FA-05/06/12, panel admin)
CREATE TABLE modulo5.ejecuciones_batch_ica (
  id_ejecucion serial PRIMARY KEY,
  estado varchar(20) NOT NULL DEFAULT 'EN_EJECUCION',   -- EN_EJECUCION|COMPLETADO|INTERRUMPIDO
  tipo_disparo varchar(20) NOT NULL DEFAULT 'AUTOMATICO', -- AUTOMATICO|MANUAL
  hora_inicio timestamptz NOT NULL DEFAULT now(),
  hora_fin timestamptz, hora_corte timestamptz,
  cantidad_activos_total int NOT NULL DEFAULT 0,
  cantidad_activos_procesados int NOT NULL DEFAULT 0,
  cantidad_activos_pendientes int NOT NULL DEFAULT 0,
  cantidad_fallidos int NOT NULL DEFAULT 0,
  causa_interrupcion varchar(50),                        -- VENTANA_EXCEDIDA|MANUAL
  num_workers int NOT NULL DEFAULT 1,
  limite_configurado int,
  id_usuario_disparo int REFERENCES modulo1.usuarios(id_usuario),
  id_usuario_interrupcion int REFERENCES modulo1.usuarios(id_usuario),
  creado_en timestamptz NOT NULL DEFAULT now()
);

-- Cola persistente (FA-07 límite superado, FA-06 ventana excedida, reactivación)
CREATE TABLE modulo5.cola_calculo_ica (
  id_cola serial PRIMARY KEY,
  id_activo_biologico int NOT NULL REFERENCES modulo2.activos_biologicos(id_activo_biologico),
  id_ejecucion_batch int REFERENCES modulo5.ejecuciones_batch_ica(id_ejecucion),
  prioridad int NOT NULL DEFAULT 100,
  estado varchar(20) NOT NULL DEFAULT 'EN_COLA',         -- EN_COLA|PROCESANDO|COMPLETADO|OMITIDO
  motivo varchar(50),                                    -- LIMITE_SUPERADO|VENTANA_EXCEDIDA|REINTENTO
  fecha_encolado timestamptz NOT NULL DEFAULT now(),
  fecha_procesado timestamptz
);
CREATE UNIQUE INDEX uq_cola_ica_activo_pendiente
  ON modulo5.cola_calculo_ica (id_activo_biologico) WHERE estado IN ('EN_COLA','PROCESANDO');

-- Fallos persistentes (E5 → CA_FALLO_PERSISTENTE tras N reintentos)
CREATE TABLE modulo5.fallos_calculo_ica (
  id_fallo int GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  id_activo_biologico int NOT NULL REFERENCES modulo2.activos_biologicos(id_activo_biologico),
  periodo_evaluacion modulo5.enum_periodo_evaluacion,
  causa_fallo text, intentos int NOT NULL DEFAULT 0,
  timestamp_ultimo_intento timestamptz,
  id_ejecucion_batch int REFERENCES modulo5.ejecuciones_batch_ica(id_ejecucion),
  resuelto boolean NOT NULL DEFAULT false,
  fecha_resolucion timestamptz, tipo_resolucion varchar(20), -- MANUAL|AUTOMATICO
  creado_en timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX uq_fallo_ica_abierto
  ON modulo5.fallos_calculo_ica (id_activo_biologico, periodo_evaluacion) WHERE NOT resuelto;

-- Parámetros del motor (fila única, sembrada por defecto)
CREATE TABLE modulo5.configuracion_batch_ica (
  id_configuracion int GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  limite_activos int NOT NULL DEFAULT 5000,
  num_workers_max int NOT NULL DEFAULT 4,
  umbral_paralelizacion int NOT NULL DEFAULT 500,
  ventana_horas int NOT NULL DEFAULT 4,
  hora_ejecucion time NOT NULL DEFAULT '02:00',
  max_reintentos int NOT NULL DEFAULT 3,
  backoff_minutos int[] NOT NULL DEFAULT ARRAY[2,4,6],
  es_activo boolean NOT NULL DEFAULT true,
  actualizado_en timestamptz NOT NULL DEFAULT now(),
  id_usuario_actualiza int REFERENCES modulo1.usuarios(id_usuario)
);
INSERT INTO modulo5.configuracion_batch_ica (limite_activos, num_workers_max, umbral_paralelizacion, ventana_horas, hora_ejecucion)
SELECT 5000, 4, 500, 4, '02:00'
WHERE NOT EXISTS (SELECT 1 FROM modulo5.configuracion_batch_ica);
```

---

## Gap 3 — Tipo de alerta ICA (faltaba en el enum)

RF-74 paso 8 / CA-3: al clasificar `CRITICA` se genera una alerta. Reutilizamos
`modulo3.alertas`. El enum no tenía el tipo; aplicado:

```sql
ALTER TYPE modulo3.enum_tipo_alerta ADD VALUE IF NOT EXISTS 'CONVERSION_ALIMENTICIA';
```

La alerta se persiste con `severidad='CRITICO'` (`enum_buffer_nivel_severidad`),
`origen_evento='BACKEND'` (cálculo manual) o `'EVALUACION_PERIODICA'` (batch),
`tipo_variable='conversion_alimenticia'`, `valor=ca`, `fecha_evento=now()`.

---

## Gap 4 — RBAC (recursos y permisos no existían)

```sql
INSERT INTO modulo1.recursos (id_recurso, nombre_recurso, descripcion, es_proceso_especial) VALUES
  (49, 'eficiencia_alimenticia', 'Cálculo y consulta de ICA — RF-74', true),
  (50, 'administracion_batch_ica', 'Administración del motor batch ICA — RF-74', true);
SELECT setval('modulo1.recursos_id_recurso_seq', (SELECT max(id_recurso) FROM modulo1.recursos));

-- Recurso 49: E(5) cálculo manual, R(2) consulta — Admin(1), Productor(2), Veterinario(3)
-- Recurso 50: E(5) interrumpir/reactivar/reintentar, R(2) panel — Admin(1), Productor(2)
INSERT INTO modulo1.permisos (id_rol, id_recurso, id_accion, nombre, es_activo) VALUES
  (1,49,5,'admin_ejecutar_eficiencia_alimenticia',true),
  (2,49,5,'prod_ejecutar_eficiencia_alimenticia',true),
  (3,49,5,'vet_ejecutar_eficiencia_alimenticia',true),
  (1,49,2,'admin_leer_eficiencia_alimenticia',true),
  (2,49,2,'prod_leer_eficiencia_alimenticia',true),
  (3,49,2,'vet_leer_eficiencia_alimenticia',true),
  (1,50,5,'admin_ejecutar_batch_ica',true),
  (2,50,5,'prod_ejecutar_batch_ica',true),
  (1,50,2,'admin_leer_batch_ica',true),
  (2,50,2,'prod_leer_batch_ica',true);
```

Sin estas filas, `require_permission` devuelve `403` silencioso en todos los endpoints.

---

## Gap 5 — Auditoría de `resultado_ica` (no existía trigger)

M05 audita por trigger a `modulo5.auditorias_suministros` (memoria del proyecto:
"auditoría de modulo5 la hacen triggers de BD; la app no los duplica"). `resultado_ica`
carecía de trigger. Se creó uno espejando `fn_trg_auditoria_consumo_alimento`, con
**fallback a usuario sistema (id 1)** porque las corridas automáticas/batch tienen
`id_usuario NULL` y `auditorias_suministros.id_usuario` es `NOT NULL`:

```sql
CREATE OR REPLACE FUNCTION modulo5.fn_trg_auditoria_resultado_ica() RETURNS trigger ...
  INSERT INTO modulo5.auditorias_suministros (entidad_afectada, tipo_operacion,
    datos_anteriores, datos_nuevos, id_usuario, ip_origen, fecha_evento, resultado, id_activo_biologico)
  VALUES ('resultado_ica', v_tipo_op, v_datos_ant, v_datos_nue,
    COALESCE(NEW.id_usuario, OLD.id_usuario, 1), NULL, NOW(), 'EXITOSO',
    COALESCE(NEW.id_activo_biologico, OLD.id_activo_biologico));
-- Trigger AFTER INSERT OR UPDATE ON modulo5.resultado_ica
```

**Consecuencia de diseño:** la app **no** implementa capa de auditoría para ICA (no hay
`AuditoriaICAPort`/adapter). La auditoría la genera el trigger. La trazabilidad de las
corridas batch adicionalmente vive en `ejecuciones_batch_ica`.

---

## Enums de dominio (sin nuevos tipos PG; varchar en BD, str-Enum en la app)

- `estado_resultado`: `CALCULADO` | `CA_NO_CALCULABLE`
- `tipo_calculo`: `MANUAL` | `AUTOMATICO` | `REINTENTO_AUTOMATICO` | `REINTENTO_MANUAL`
- `causa_no_calculo` (jerarquía): `SIN_PESO_INICIAL` > `SIN_PESO_FINAL` >
  `SIN_REGISTROS_CONSUMO` > `DATO_INVALIDO` / `PESO_SIN_VARIACION_POSITIVA` / `POBLACION_INVALIDA`
- Estados de batch/cola/fallo: ver Gap 2.

Umbrales de clasificación del RF (por defecto): `< 2.0` EXCELENTE · `2.0–3.5` ACEPTABLE ·
`3.6–5.0` BAJA · `> 5.0` CRITICA. `CA` truncado a 4 decimales. `data_quality_score =
factores_presentes / 4 × 100` (peso inicial, peso final, consumo, variación positiva).

---

## Verificación aplicada (MCP postgres)
`cols_resultado_ica=3`, `tablas_batch=4`, `config_seed=1`, `enum_alerta=1`,
`trigger_audit=1`, `recursos=2`, `permisos=10`, `idx_vigente=1`. ✅

## Datos de prueba disponibles en dev
- Activo **1**: 7 consumos VALIDADO + pesajes (`peso_vivo` 2024, `PESO` 2026) → calculable / según ventana.
- Activo **5**: 1 consumo VALIDADO + pesajes `PESO` crecientes (1.50→2.50, 2026-06-28) → calculable con ganancia positiva.
- Activo **8**: 1 consumo VALIDADO, sin pesaje → `CA_NO_CALCULABLE` (SIN_PESO_*).
