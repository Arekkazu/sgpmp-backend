# CU05 (M05) — Gaps entre el documento y la base de datos (RF-78 + RF-79)

## Fecha de análisis / aplicación
2026-07-31

## Contexto

CU-05 "Acumular inversión y proveer costos a M06" cubre **RF-78** (acumulación
continua y atómica de costos directos por ciclo productivo — ALIMENTO/
MEDICAMENTO heredados de RF-75/76 vía CU-01/CU-04, más SERVICIO_VETERINARIO e
INSEMINACION de registro directo) y **RF-79** (provisión estructurada de esos
costos hacia M06 para valoración NIC 41, modalidades INCREMENTAL/CONSOLIDADO).

Al iniciar este CU, RF-78/RF-79 estaban en **0% de implementación** en
`src/supplies` (confirmado por grep exhaustivo — sin rastro de "acumulado",
"provision", "nic41" ni "hash_integridad" salvo columnas ya presentes en
`RegistroSuministroModel` heredadas de CU-04).

Decisión de alcance acordada con el usuario antes de este análisis: **M05 es
autocontenido frente a M06** — no escribe en `modulo6.registros_costos` (schema
real y maduro, con sus propias reglas RF-90 de PUC/`accounting_account` que M05
no tiene contexto para inventar). M05 persiste sus propios artefactos NIC41 y
expone endpoints de consulta/pull; la ingesta real hacia `modulo6` queda
pendiente explícito (mismo estilo que CU-04 documentó PDF/Excel como pendiente).

---

## Hallazgo crítico — `id_ciclo_productivo` es un catálogo reutilizable, no una instancia por activo

Verificado con datos reales de `modulo2.gestiones_fases`:

```
id_ciclo_productiva=1 → activos [1, 2, 5, 5, 57]
```

Los activos 2 y 5 tienen cada uno una fase `es_activa=true` **simultánea**
sobre el mismo `id_ciclo_productivo=1`; el activo 5 además tiene dos filas
sobre ese mismo catálogo (una cerrada `id_gestion_fases=30`, una reabierta
`id_gestion_fases=32`). El scaffolding preexistente de `acumulado_ciclo` tenía
`UNIQUE INDEX idx_acumulado_ciclo_uniq (id_ciclo_productivo)` — una sola fila
por **catálogo**, no por activo — lo que habría mezclado los suministros de
activos distintos en el mismo acumulado.

**Decisión**: la clave real de "ciclo productivo ACTIVO de un activo" que pide
RF-78 es la fila de **`modulo2.gestiones_fases` (`id_gestion_fases`)**, no el
catálogo `ciclos_productivos`. Todo el diseño usa `id_gestion_fases` como clave
de acumulación; `id_ciclo_productivo`/`id_activo_biologico` se conservan
denormalizados solo para filtros/joins de display.

---

## Gap 1 (crítico) — `id_gestion_fases` como clave real de acumulación

```sql
ALTER TABLE modulo5.registro_suministro
  ADD COLUMN id_gestion_fases integer REFERENCES modulo2.gestiones_fases(id_gestion_fases);
CREATE INDEX idx_registro_suministro_gestion_fases ON modulo5.registro_suministro (id_gestion_fases);

UPDATE modulo5.registro_suministro rs
SET id_gestion_fases = (
  SELECT gf.id_gestion_fases
  FROM modulo2.gestiones_fases gf
  WHERE gf.id_activo_biologico = rs.id_activo_biologico
    AND gf.id_ciclo_productiva = rs.id_ciclo_productivo
  ORDER BY
    (rs.fecha_aplicacion BETWEEN gf.fecha_inicio::date
       AND COALESCE(gf.fecha_finalizacion::date, 'infinity'::date)) DESC,
    gf.es_activa DESC,
    gf.fecha_inicio DESC
  LIMIT 1
)
WHERE rs.id_gestion_fases IS NULL;
-- Resultado: 18/18 filas backfilladas (7 por contención temporal sin ambigüedad;
-- 11 filas de activo=1 por desempate es_activa/fecha_inicio, porque sus dos fases
-- tienen fecha_finalizacion < fecha_inicio — dato de semilla de M02 defectuoso,
-- preexistente y ajeno a este CU. No bloqueante.

ALTER TABLE modulo5.acumulado_ciclo
  ADD COLUMN id_activo_biologico integer,
  ADD COLUMN id_gestion_fases integer;
ALTER TABLE modulo5.acumulado_ciclo
  ADD CONSTRAINT fk_acumulado_ciclo_activo FOREIGN KEY (id_activo_biologico)
      REFERENCES modulo2.activos_biologicos(id_activo_biologico),
  ADD CONSTRAINT fk_acumulado_ciclo_gestion_fases FOREIGN KEY (id_gestion_fases)
      REFERENCES modulo2.gestiones_fases(id_gestion_fases),
  ADD CONSTRAINT chk_acumulado_no_negativo CHECK (acumulado_total_ciclo >= 0);
ALTER TABLE modulo5.acumulado_ciclo
  ALTER COLUMN id_activo_biologico SET NOT NULL,
  ALTER COLUMN id_gestion_fases SET NOT NULL;

DROP INDEX modulo5.idx_acumulado_ciclo_uniq;
CREATE UNIQUE INDEX idx_acumulado_ciclo_uniq ON modulo5.acumulado_ciclo (id_gestion_fases);
CREATE INDEX idx_acumulado_ciclo_activo ON modulo5.acumulado_ciclo (id_activo_biologico);

ALTER TABLE modulo5.provision_nic41
  ADD COLUMN id_gestion_fases integer REFERENCES modulo2.gestiones_fases(id_gestion_fases);
CREATE INDEX idx_provision_gestion_fases ON modulo5.provision_nic41 (id_gestion_fases);

ALTER TABLE modulo5.auditorias_suministros
  ADD COLUMN id_gestion_fases integer REFERENCES modulo2.gestiones_fases(id_gestion_fases);
CREATE INDEX idx_auditorias_suministros_gestion_fases ON modulo5.auditorias_suministros (id_gestion_fases);
```

`id_ciclo_productivo` se mantuvo `NOT NULL` en `acumulado_ciclo` (denormalizado,
para filtros/joins de display), pero el índice único que garantiza "un
acumulado por instancia real" ahora es sobre `id_gestion_fases`.

Se corrigieron (`CREATE OR REPLACE VIEW`) los joins rotos contra
`acumulado_ciclo` en `vw_m05_costos_produccion` y `vw_m05_provision_incrementales`
(antes `ac.id_ciclo_productivo = rs/aus.id_ciclo_productivo`, ahora
`ac.id_gestion_fases = rs/aus.id_gestion_fases`). `vw_m05_provision_nic41` y
`vw_m05_trazabilidad_costos` no requirieron cambio.

---

## Gap 2 — `tipo_suministro` en `registro_suministro` + deduplicación por contenido

```sql
ALTER TABLE modulo5.registro_suministro
  ADD COLUMN tipo_suministro varchar(30)
    CHECK (tipo_suministro IN ('ALIMENTO','MEDICAMENTO','SERVICIO_VETERINARIO','INSEMINACION'));

UPDATE modulo5.registro_suministro SET tipo_suministro = 'ALIMENTO'    WHERE id_registro_rf75 IS NOT NULL;
UPDATE modulo5.registro_suministro SET tipo_suministro = 'MEDICAMENTO' WHERE id_registro_rf76 IS NOT NULL;
ALTER TABLE modulo5.registro_suministro ALTER COLUMN tipo_suministro SET NOT NULL;

CREATE UNIQUE INDEX uq_registro_suministro_dedup_contenido
ON modulo5.registro_suministro (id_activo_biologico, id_ciclo_productivo, tipo_suministro,
                                 fecha_aplicacion, cantidad, precio_unitario_resuelto)
WHERE tipo_operacion = 'REGISTRO';
```

Sin `id_tipo_suministro` previo, ALIMENTO/MEDICAMENTO solo se distinguían por
`id_registro_rf75/rf76 IS NOT NULL` — insuficiente para SERVICIO_VETERINARIO/
INSEMINACION (registro directo, sin RF-75/76 de origen), que quedarían
indistinguibles entre sí. Dedup por contenido solo aplica a `tipo_operacion=
'REGISTRO'` (una corrección puede coincidir en contenido con otra fila sin ser
duplicado real). "Tolerancia de redondeo" (Restricción 8 de RF-78): la app
cuantiza (`Decimal.quantize`) cantidad/precio a la escala real de columna (4 y
2 decimales) antes de comparar/persistir, así el índice compara siempre
valores normalizados — sin mecanismo de tolerancia aparte en SQL.

**Deduplicación previa de datos de prueba**: al aplicar el índice se encontraron
4 filas ALIMENTO preexistentes (activo=1, ciclo=1, 2026-05-09, cantidad=5,
`precio_unitario_resuelto=0.00`) exactamente duplicadas por contenido — residuo
de verificaciones repetidas de CU-01 (costo=$0, sin impacto financiero real; sin
trigger de inmutabilidad sobre esta tabla derivada). Se conservó la más antigua
(`fecha_registro` 03:26:26) y se eliminaron las otras 3 antes de crear el
índice, mismo criterio que CU-01 aplicó al deduplicar datos de prueba antes de
sus índices únicos parciales (`uq_consumo_validado_dup`).

---

## Gap 3 — Modelo ORM faltante

No existía `AuditoriaSuministroModel` en `src/supplies/infrastructure/models/`
(confirmado por grep) pese a que la tabla `modulo5.auditorias_suministros` es
usada por triggers de CU-01/02/04. Se crea nuevo (ver código).

---

## Gap 4 — Enum de eventos de negocio en `auditorias_suministros`

`enum_auditoria_suministro_tipo_operacion` solo tenía `INSERT/UPDATE/DELETE/
SELECT` (triggers DML genéricos ya en producción). Se agregaron 8 valores de
negocio, sin afectar las filas existentes:

```sql
ALTER TYPE modulo5.enum_auditoria_suministro_tipo_operacion ADD VALUE IF NOT EXISTS 'SUMINISTRO_REGISTRADO';
ALTER TYPE modulo5.enum_auditoria_suministro_tipo_operacion ADD VALUE IF NOT EXISTS 'SUMINISTRO_CORREGIDO';
ALTER TYPE modulo5.enum_auditoria_suministro_tipo_operacion ADD VALUE IF NOT EXISTS 'REGISTRO_FALLIDO';
ALTER TYPE modulo5.enum_auditoria_suministro_tipo_operacion ADD VALUE IF NOT EXISTS 'CONFLICTO_CONCURRENCIA';
ALTER TYPE modulo5.enum_auditoria_suministro_tipo_operacion ADD VALUE IF NOT EXISTS 'CICLO_CONSOLIDADO';
ALTER TYPE modulo5.enum_auditoria_suministro_tipo_operacion ADD VALUE IF NOT EXISTS 'PROVISION_INCREMENTAL_ENTREGADA';
ALTER TYPE modulo5.enum_auditoria_suministro_tipo_operacion ADD VALUE IF NOT EXISTS 'PROVISION_INCREMENTAL_FALLIDA';
ALTER TYPE modulo5.enum_auditoria_suministro_tipo_operacion ADD VALUE IF NOT EXISTS 'REPORTE_COSTOS_GENERADO';
```

---

## Gap 5 — `calcular_hash_integridad()` (no modificado, documentado)

El trigger genérico ya usado por `auditorias_suministros`/`provision_nic41`
excluye literalmente las columnas `'hash_integridad'`, `'creado_en'`,
`'id_registro_suministro'` al calcular el SHA-256. Ninguna de las dos tablas
tiene columnas con esos nombres exactos (su PK/timestamp se llaman distinto),
así que el hash real **incluye su propia PK y su timestamp de generación** —
comportamiento correcto y estable (la PK ya está resuelta antes del `BEFORE
INSERT`). No se modificó por ser genérico y estar en uso; se documenta para
quien verifique el hash.

---

## Gap 6 — Acumulación atómica vía trigger único (decisión de arquitectura)

Un solo trigger `AFTER INSERT` en `registro_suministro` mantiene
`acumulado_ciclo` para las 4 categorías por igual (ALIMENTO/MEDICAMENTO ya
insertados por los triggers de CU-04, y SERVICIO_VETERINARIO/INSEMINACION/
CORRECCION insertados directamente por la app de este CU). Respeta el
principio ya establecido en el proyecto ("costos, inmutabilidad y auditoría de
`modulo5` los hacen triggers de BD; la app no los duplica", ver
`m05_triggers_logica`) y evita dos mecanismos de acumulación que podrían
divergir. `INSERT ... ON CONFLICT DO UPDATE` es atómico nativamente (Postgres
serializa por el lock de fila del índice único), así que la ruta feliz no
necesita `SELECT FOR UPDATE` ni reintentos manuales de la app — solo el flujo
de corrección (que sí lee antes de decidir si el resultado sería negativo) usa
`SELECT FOR UPDATE` desde la app.

```sql
CREATE OR REPLACE FUNCTION modulo5.fn_acumular_costo_ciclo() RETURNS trigger AS $$
DECLARE
  v_delta numeric;
  v_costo_original numeric;
BEGIN
  IF NEW.id_gestion_fases IS NULL THEN
    RAISE WARNING 'registro_suministro %: sin id_gestion_fases; no se acumula.', NEW.id_registro_suministro;
    RETURN NEW;
  END IF;

  IF NEW.tipo_operacion = 'CORRECCION' THEN
    SELECT costo_registro INTO v_costo_original
    FROM modulo5.registro_suministro WHERE id_registro_suministro = NEW.id_registro_original;
    v_delta := NEW.costo_registro - COALESCE(v_costo_original, 0);
  ELSE
    v_delta := NEW.costo_registro;
  END IF;

  INSERT INTO modulo5.acumulado_ciclo
    (id_activo_biologico, id_ciclo_productivo, id_gestion_fases, acumulado_total_ciclo,
     acumulado_por_categoria, version_acumulado)
  VALUES
    (NEW.id_activo_biologico, NEW.id_ciclo_productivo, NEW.id_gestion_fases, v_delta,
     jsonb_build_object(NEW.tipo_suministro, v_delta), 0)
  ON CONFLICT (id_gestion_fases) DO UPDATE SET
    acumulado_total_ciclo = modulo5.acumulado_ciclo.acumulado_total_ciclo + v_delta,
    acumulado_por_categoria = jsonb_set(
      COALESCE(modulo5.acumulado_ciclo.acumulado_por_categoria, '{}'::jsonb),
      ARRAY[NEW.tipo_suministro],
      to_jsonb(COALESCE((modulo5.acumulado_ciclo.acumulado_por_categoria ->> NEW.tipo_suministro)::numeric, 0) + v_delta)
    ),
    version_acumulado = modulo5.acumulado_ciclo.version_acumulado + 1,
    fecha_ultima_actualizacion = now();
  RETURN NEW;
END; $$ LANGUAGE plpgsql;

CREATE TRIGGER trg_acumular_costo_ciclo
AFTER INSERT ON modulo5.registro_suministro
FOR EACH ROW EXECUTE FUNCTION modulo5.fn_acumular_costo_ciclo();
```

### Bug encontrado y corregido durante la verificación E2E: `INSERT ... ON CONFLICT DO UPDATE` con delta negativo

El diseño original de arriba falla en el escenario 7/8 (corrección que reduce
un costo, `v_delta < 0`, sobre un `id_gestion_fases` que ya tiene fila en
`acumulado_ciclo`): PostgreSQL valida el `CHECK` de la tabla contra los
**valores literales del `VALUES` del INSERT candidato**, antes de resolver si
hay conflicto — es decir, `chk_acumulado_no_negativo` se evalúa contra
`v_delta` solo (p. ej. `-30000`), no contra el resultado final que tendría la
rama `DO UPDATE` (`230000 + (-30000) = 200000`, positivo). El INSERT candidato
viola el CHECK y el statement completo falla, **aunque la fila ya exista y el
UPDATE real habría sido seguro**. No se manifestó en las pruebas iniciales
porque todo REGISTRO tiene `costo_registro > 0` (nunca negativo); solo
CORRECCION puede producir un delta negativo, y el primer caso de prueba con
delta negativo fue justamente el escenario 7.

**Fix** — reemplazar `INSERT ... ON CONFLICT DO UPDATE` por `UPDATE` primero
(el CHECK se evalúa entonces contra el valor acumulado final, correcto) y
`INSERT ... ON CONFLICT DO UPDATE` solo como fallback si `NOT FOUND` (caso
alcanzable únicamente desde un REGISTRO, ya que una CORRECCION siempre
referencia un `id_registro_original` cuyo REGISTRO ya creó la fila — por lo
que `v_delta` es positivo en ese fallback, y el `ON CONFLICT` ahí solo cubre
la carrera de dos primeras-inserciones concurrentes sobre un
`id_gestion_fases` nuevo):

```sql
CREATE OR REPLACE FUNCTION modulo5.fn_acumular_costo_ciclo() RETURNS trigger AS $$
DECLARE
  v_delta numeric;
  v_costo_original numeric;
BEGIN
  IF NEW.id_gestion_fases IS NULL THEN
    RAISE WARNING 'registro_suministro %: sin id_gestion_fases; no se acumula.', NEW.id_registro_suministro;
    RETURN NEW;
  END IF;

  IF NEW.tipo_operacion = 'CORRECCION' THEN
    SELECT costo_registro INTO v_costo_original
    FROM modulo5.registro_suministro WHERE id_registro_suministro = NEW.id_registro_original;
    v_delta := NEW.costo_registro - COALESCE(v_costo_original, 0);
  ELSE
    v_delta := NEW.costo_registro;
  END IF;

  UPDATE modulo5.acumulado_ciclo SET
    acumulado_total_ciclo = acumulado_total_ciclo + v_delta,
    acumulado_por_categoria = jsonb_set(
      COALESCE(acumulado_por_categoria, '{}'::jsonb),
      ARRAY[NEW.tipo_suministro],
      to_jsonb(COALESCE((acumulado_por_categoria ->> NEW.tipo_suministro)::numeric, 0) + v_delta)
    ),
    version_acumulado = version_acumulado + 1,
    fecha_ultima_actualizacion = now()
  WHERE id_gestion_fases = NEW.id_gestion_fases;

  IF NOT FOUND THEN
    INSERT INTO modulo5.acumulado_ciclo
      (id_activo_biologico, id_ciclo_productivo, id_gestion_fases, acumulado_total_ciclo,
       acumulado_por_categoria, version_acumulado)
    VALUES
      (NEW.id_activo_biologico, NEW.id_ciclo_productivo, NEW.id_gestion_fases, v_delta,
       jsonb_build_object(NEW.tipo_suministro, v_delta), 0)
    ON CONFLICT (id_gestion_fases) DO UPDATE SET
      acumulado_total_ciclo = modulo5.acumulado_ciclo.acumulado_total_ciclo + v_delta,
      acumulado_por_categoria = jsonb_set(
        COALESCE(modulo5.acumulado_ciclo.acumulado_por_categoria, '{}'::jsonb),
        ARRAY[NEW.tipo_suministro],
        to_jsonb(COALESCE((modulo5.acumulado_ciclo.acumulado_por_categoria ->> NEW.tipo_suministro)::numeric, 0) + v_delta)
      ),
      version_acumulado = modulo5.acumulado_ciclo.version_acumulado + 1,
      fecha_ultima_actualizacion = now();
  END IF;

  RETURN NEW;
END; $$ LANGUAGE plpgsql;
```

Verificado tras el fix: escenario 7 (corrección −30000 sobre acumulado 230000)
→ 200000 correcto; escenario 15 (2 requests concurrentes sobre el mismo
`id_gestion_fases` nuevo) → ambas exitosas, total exacto (suma sin pérdida),
confirmando que la rama `NOT FOUND` + `ON CONFLICT` sigue serializando
correctamente la carrera de primera-inserción.

Se extendieron (additivamente) `fn_trg_poblar_registro_suministro_alimento` y
`fn_trg_poblar_registro_suministro_medicamento` (CU-04) para poblar
`id_gestion_fases` y el literal `tipo_suministro` en cada INSERT que generan —
mismo cuerpo/lógica de negocio original, sin tocar Python de CU-01/CU-04. Con
esto, el INSERT en `registros_consumo_alimentos`/`registros_medicamentos`
dispara toda la cascada (ledger → acumulado) en una sola transacción de BD.

---

## Gap 7 — Política de `naturaleza_costo` por categoría (pendiente M09)

`modulo9.especies` no tiene ninguna columna de política de capitalización
(confirmado: `id_especie, nombre, descripcion, fecha_actualizacion,
fecha_creacion, es_activo`). Gap real, mismo patrón que "M40 fuera de alcance"
en CU-01. Se resuelve en `domain/services/politica_naturaleza_costo.py` con
defaults documentados, aislados y fáciles de reemplazar cuando M09 tenga
configuración real:

| tipo_suministro | naturaleza_costo | razón |
|---|---|---|
| ALIMENTO | MANTENIMIENTO | ya establecido por trigger de CU-04 |
| MEDICAMENTO | MANTENIMIENTO | ídem |
| SERVICIO_VETERINARIO | MANTENIMIENTO | costo operativo recurrente |
| INSEMINACION | INVERSION | única con valor reproductivo/genético capitalizable evidente |

---

## Gap 8 — RBAC: recursos 55/56 (`MAX(id_recurso)` confirmado en 54)

```sql
INSERT INTO modulo1.recursos (id_recurso, nombre_recurso, descripcion, es_proceso_especial) VALUES
  (55, 'costeo_directo_suministros', 'Registro/corrección directa de costos SERVICIO_VETERINARIO e INSEMINACION y consulta del acumulado por ciclo — RF-78', true),
  (56, 'provision_nic41', 'Consolidación y consulta de la provisión de costos NIC-41 hacia M06 — RF-79', true);
```

### Matriz RBAC

| Recurso | Acción | Roles | Justificación |
|---|---|---|---|
| 55 `costeo_directo_suministros` | C (1) | Admin, Productor, Veterinario | Productor/Admin = rol operativo real de M05; Veterinario por precedente de RF-76 (registra medicamentos → registra SERVICIO_VETERINARIO). |
| 55 | R (2) | Admin, Productor, Veterinario, Contador, Revisor Fiscal | Consumo operativo + financiero, mismo criterio que recurso 51/52 de CU-04. |
| 55 | U (3, corrección) | Admin, Contador | Una corrección afecta el acumulado de inversión (dato financiero); se restringe a autoridad financiera. |
| 56 `provision_nic41` | E (5, consolidar) | Admin, Contador | RF-79 es responsabilidad del Contador (representante de M06) + Admin como respaldo. |
| 56 | R (2) | Admin, Productor, Contador, Revisor Fiscal | Visibilidad amplia de solo lectura, mismo criterio que recurso 51. |

```sql
INSERT INTO modulo1.permisos (id_rol, id_recurso, id_accion, nombre, es_activo) VALUES
  (1,55,1,'admin_crear_costeo_directo_suministros',true),
  (2,55,1,'prod_crear_costeo_directo_suministros',true),
  (3,55,1,'vet_crear_costeo_directo_suministros',true),
  (1,55,2,'admin_leer_costeo_directo_suministros',true),
  (2,55,2,'prod_leer_costeo_directo_suministros',true),
  (3,55,2,'vet_leer_costeo_directo_suministros',true),
  (5,55,2,'cont_leer_costeo_directo_suministros',true),
  (8,55,2,'revfiscal_leer_costeo_directo_suministros',true),
  (1,55,3,'admin_actualizar_costeo_directo_suministros',true),
  (5,55,3,'cont_actualizar_costeo_directo_suministros',true),
  (1,56,5,'admin_ejecutar_provision_nic41',true),
  (5,56,5,'cont_ejecutar_provision_nic41',true),
  (1,56,2,'admin_leer_provision_nic41',true),
  (2,56,2,'prod_leer_provision_nic41',true),
  (5,56,2,'cont_leer_provision_nic41',true),
  (8,56,2,'revfiscal_leer_provision_nic41',true);
```

---

## Gap 9 — No existe hook de cierre de ciclo (RF-41)

Confirmado por grep: `cerrar_ciclo`/`cierre_ciclo`/RF-41 no están implementados
en ningún módulo; no hay trigger en `gestiones_fases` que notifique a M05.
**Decisión**: CU-05 expone su propio endpoint `POST
/suministros/nic41/ciclo/{id_gestion_fases}/consolidar` (recurso 56, acción E)
que verifica `gestiones_fases.es_activa=false AND fecha_finalizacion IS NOT
NULL` para ese `id_gestion_fases` antes de permitir la consolidación
definitiva — mismo estilo que la regla interina de alcance del Gestor de
Granja documentada en CU-04.

---

## Gap 10 — Anulación de RF-75/76 no revierte RF-78 (pendiente, mitigado)

`anular_medicamento_use_case.py`/`anular_consumo_alimento_use_case.py` anulan
la fila origen (`UPDATE estado_registro`) pero no existe ningún trigger `AFTER
UPDATE` que reaccione a la transición `VALIDADO→ANULADO` insertando una
`CORRECCION` reversora en `registro_suministro`. No se construye reversión
automática en este CU (requeriría decidir la semántica de una reversión total
bajo el `CHECK cantidad > 0` de `registro_suministro`). **Mitigación**: el
endpoint de corrección de este CU acepta `id_registro_original` de cualquier
tipo de suministro (incluidos ALIMENTO/MEDICAMENTO), así que Contador/
Administrador pueden emitir manualmente una corrección que refleje una
anulación aguas arriba mientras no exista el mecanismo automático.

---

## Gap 11 — `provision_nic41.modalidad='INCREMENTAL'` sin usar (documentado)

El esquema de `provision_nic41` (`version_reporte`, `id_reporte_anterior`,
`lista_registros`, `hash_integridad`) encaja con un artefacto CONSOLIDADO
(pocas filas por ciclo), no con un evento de alta frecuencia por cada
suministro. Se usa exclusivamente con `modalidad='CONSOLIDADO'` en este CU. El
"evento" RF-79 INCREMENTAL se modela como una fila en `auditorias_suministros`
(`tipo_operacion='PROVISION_INCREMENTAL_ENTREGADA'`) emitida en la misma
transacción que la acumulación, reutilizando
`id_evento_provision := registro_suministro.id_idempotencia` (sin columna UUID
redundante) — justificado porque el modelo es *pull* (M06/Contador consultan),
no hay paso de entrega HTTP separado que deduplicar aparte del propio registro.

---

## Scaffolding de BD preexistente descartado (huérfano e inconsistente con el RF)

Mismo patrón que ICA antes de CU-02 y RF-77/81 antes de CU-04:

| Objeto BD | Problema | Decisión |
|---|---|---|
| `modulo5.costos_productivos` | Sus propios triggers de inmutabilidad citan literalmente "RF-78 Restricción 6" en los mensajes de error, pero sus columnas (`costo_medicamento`, `costo_mano_obra`, `costo_infraestructura`) no coinciden con las 4 categorías reales de RF-78 — de hecho incluye mano_obra e infraestructura, que la Restricción 4 de RF-78 excluye explícitamente del alcance. Su enum propio `enum_costo_productivo_tipo_operacion` (REGISTRO\|AJUSTE\|REVERSO) tampoco coincide con el vocabulario del RF (REGISTRO\|CORRECCION). | No se usa. Se deja intacta. |
| `modulo5.mediciones_inventarios` | Enum `enum_medicion_inventario_tipo_costo` separa SERVICIO y VETERINARIO en vez de la categoría unificada SERVICIO_VETERINARIO del RF. 0 filas. | No se usa. Se deja intacta. |

---

## Pendientes explícitamente diferidos (no implementados en este CU)

- **Política de capitalización por especie en M09** (Gap 7) — usa defaults
  documentados en `politica_naturaleza_costo.py`, reemplazable sin tocar el
  use case cuando M09 tenga la configuración real.
- **Reversión automática de RF-78 al anular un registro RF-75/76** (Gap 10) —
  mitigado con corrección manual por Contador/Administrador.
- **Ingesta real hacia `modulo6.registros_costos`** — decisión confirmada con
  el usuario: M05 solo expone lectura/pull (`acumulado_ciclo`,
  `provision_nic41`); la ingesta real hacia M06/RF-90 queda para cuando M06 se
  implemente.
- **Integración M40** (`origen_precio=M40_AUTOMATICO`) — sigue fuera de
  alcance, mismo estado que CU-01/CU-04 (M40 no existe en el sistema).
- **Catálogo `tipos_suministro` en M09 con unidades por tipo** — no existe;
  `unidad_medida` sigue sin catálogo, validado solo por presencia/formato en
  el DTO.
- **`provision_nic41.modalidad='INCREMENTAL'`** sin usar (Gap 11), documentado
  igual que otros objetos huérfanos de CU-02/CU-04.
- **Backfill ambiguo de `id_gestion_fases`** para 11 filas de `activo_biologico=1`
  (Gap 1) — por desempate determinístico, no por certeza temporal, debido a
  datos de semilla de M02 con `fecha_finalizacion < fecha_inicio`.
