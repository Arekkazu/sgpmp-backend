# CU01 (M05) — Gaps entre el documento y la base de datos (RF-75, RF-76)

## Fecha de análisis
2026-07-29 / 2026-07-30

## Contexto
CU-01 "Gestionar Registro de Suministros" cubre RF-75 (consumo de alimentos) y RF-76
(aplicación de medicamentos) sobre activos biológicos con ciclo productivo abierto. La
BD `modulo5` ya estaba modelada (tablas, enums, FKs y **una batería de triggers** que
implementan buena parte de la lógica). Este documento registra los gaps encontrados vía
MCP postgres y las decisiones aplicadas **antes** de codificar.

Tablas núcleo del CU-01: `modulo5.registros_consumo_alimentos`,
`modulo5.registros_medicamentos`, `modulo5.tipos_alimentos`,
`modulo5.auditorias_suministros`.

---

## Hallazgo transversal — Triggers de BD que implementan lógica del CU-01

La BD ya hace por trigger lo que normalmente iría en la aplicación. **Decisión: la
aplicación NO duplica estas responsabilidades**; valida en el use case para producir
errores HTTP limpios y deja que el trigger sea el refuerzo (backstop).

| Trigger (modulo5) | Efecto |
|---|---|
| `fn_trg_calcular_costo_total_consumo` (BEFORE INSERT) | Valida `cantidad>0`, exige tipo de alimento **ACTIVO** y calcula `costo_total = cantidad * costo_unitario` **del catálogo** |
| `fn_trg_calcular_costo_total_medicamento` (BEFORE INSERT) | Valida `cantidad>0` y `costo_unitario>0`, calcula `costo_total_medicamento = cantidad * costo_unitario_medicamento` |
| `fn_trg_tipo_alimento_debe_estar_activo` (BEFORE INSERT) | Rechaza `id_tipo_alimento` inexistente o no ACTIVO |
| `fn_trg_consumo_alimento_inmutable_validado` / `fn_trg_medicamento_inmutable_validado` (BEFORE UPDATE) | Bloquea editar un VALIDADO; en `VALIDADO→ANULADO` solo permite cambiar estado + campos de anulación; medicamento: bloquea re-anular un ANULADO |
| `fn_trg_*_no_delete` (BEFORE DELETE) | Registros append-only, no se pueden borrar |
| `fn_trg_auditoria_consumo_alimento` / `fn_trg_auditoria_medicamento` (AFTER INSERT/UPDATE) | **Escriben la auditoría automáticamente** en `modulo5.auditorias_suministros` |
| `trg_auditoria` → `auditoria.fn_auditoria_dml()` | Auditoría DML global en `auditoria.logs_dml` |
| `fn_trg_disparar_recalculo_ica_post_consumo` | Dispara recálculo ICA (RF-74, fuera de alcance) |

**Consecuencias de diseño:**
- No se implementa capa de auditoría en la aplicación (no hay `auditoria_*` port/repo/model
  en `src/supplies`): la auditoría la generan los triggers. Escribirla desde la app
  duplicaría filas.
- No se calcula `costo_total` en la app; se relee tras `flush`/`refresh`.
- El costo del **consumo** es autoritativo desde el **catálogo** (`tipos_alimentos`), no
  desde el input. Por eso el DTO de consumo **no recibe** `costo_unitario` (ajuste sobre
  la decisión inicial de diseño, que asumía input con fallback a catálogo).

---

## Gap 1 — Índices únicos parciales para duplicados (faltaban)
Solo existían índices btree no-únicos. Sin unicidad no se puede garantizar el rechazo de
duplicados (FA-05/E8/E13) ante concurrencia. Aplicado:

```sql
CREATE UNIQUE INDEX uq_consumo_validado_dup
  ON modulo5.registros_consumo_alimentos
     (id_activo_biologico, fecha_consumo, coalesce(hora_suministro,'00:00:00'::time), lower(tipo_alimento))
  WHERE estado_registro = 'VALIDADO';

CREATE UNIQUE INDEX uq_medicamento_validado_dup
  ON modulo5.registros_medicamentos
     (id_activo_biologico, lower(nombre_medicamento), fecha_aplicacion, coalesce(hora_aplicacion,'00:00:00'::time))
  WHERE estado_registro = 'VALIDADO';
```
`raise_from_db_error` traduce la violación a `ConflictError` 409. Además el use case hace
un pre-check para el mensaje descriptivo.

## Gap 2 — Enum `via_aplicacion` incompleto
`enum_registro_medicamenti_via_aplicacion` tenía solo `ORAL, IM, IV, SC`; RF-76 exige 6
vías. Aplicado:
```sql
ALTER TYPE modulo5.enum_registro_medicamenti_via_aplicacion ADD VALUE IF NOT EXISTS 'TOPICA';
ALTER TYPE modulo5.enum_registro_medicamenti_via_aplicacion ADD VALUE IF NOT EXISTS 'INTRAMAMARIA';
```
El API acepta el vocabulario RF (`ORAL, INTRAMUSCULAR, INTRAVENOSA, SUBCUTANEA, TOPICA,
INTRAMAMARIA`) y el value object `ViaAplicacion` mapea a los códigos de BD
(`INTRAMUSCULAR→IM`, `INTRAVENOSA→IV`, `SUBCUTANEA→SC`, resto igual).

## Gap 3 — Falta `nombre_veterinario` (RF-76 obligatorio, CA-5)
La tabla solo tenía `id_usuario_veterinario` (FK). Aplicado:
```sql
ALTER TABLE modulo5.registros_medicamentos ADD COLUMN IF NOT EXISTS nombre_veterinario varchar(150);
```
El DTO exige `nombre_veterinario`; además el use case setea
`id_usuario_veterinario = usuario_actual.id_usuario` cuando el actor es Veterinario (rol 3).

## Gap 4 — `descripcion_clinica` NOT NULL sin equivalente en el RF
`registros_medicamentos.descripcion_clinica` es NOT NULL pero el RF no lo define. Se
puebla con `motivo_aplicacion` (misma información clínica). `registros_medicamentos` **no
tiene** columna `observaciones` (el campo opcional del RF-76 no se persiste).

## Gap 5 — Paridad de CHECK de anulación en medicamentos
`registros_consumo_alimentos` tenía `chk_consumo_anulacion` (≥20) pero medicamentos no.
Aplicado con `NOT VALID` (hay filas ANULADO de prueba con justificación nula que no deben
bloquear el DDL; el CHECK se aplica a inserciones/actualizaciones nuevas):
```sql
ALTER TABLE modulo5.registros_medicamentos ADD CONSTRAINT chk_medicamento_anulacion
  CHECK (estado_registro = 'VALIDADO'
      OR (estado_registro = 'ANULADO' AND justificacion_anulacion IS NOT NULL
          AND char_length(justificacion_anulacion) >= 20)) NOT VALID;
```
**Longitud mínima de anulación: 20 caracteres** (decisión del equipo, coincide con el
CHECK real y RF-76; el encabezado del CU y la Restricción 5 de RF-75 mencionaban 50 pero
se descartó por contradecir la BD y la mayoría del documento).

## Gap 6 — `observacion` de consumo (varchar(60)) vs RF-75 (varchar(255))
No se amplió: existe una vista `modulo5.vw_m05_registro_alimentacion` que depende de la
columna y bloquea el `ALTER TYPE`. **Decisión:** conservar `varchar(60)` y limitar el DTO
a 60 caracteres. (Revisión del plan inicial, que proponía ampliarla.)

## Gap 7 — Campos RF-obligatorios que la BD deja nullable
`fecha_consumo`, `id_usuario` (consumo) y `via_aplicacion`, `hora_aplicacion`,
`motivo_aplicacion` (medicamento) son nullable en BD pero obligatorios en el RF. **No se
alteró la BD** (hay filas de prueba que podrían violar el NOT NULL); se exige a nivel DTO
(Pydantic required). Nota: el trigger de "fecha no futura" del consumo valida
`fecha_inicio_periodo` (no `fecha_consumo`); la validación real de `fecha_consumo` se hace
en el use case.

## Gap 8 — RBAC: no existía recurso para el Módulo 5 (recursos llegaban a 46)
Aplicado — dos recursos y sus permisos:
```sql
INSERT INTO modulo1.recursos (id_recurso, nombre_recurso, descripcion, es_proceso_especial)
VALUES (47, 'consumo_alimentos', 'Registro de consumo de alimentos por activo biológico (RF-75)', false),
       (48, 'medicamentos',      'Registro de aplicación de medicamentos por activo biológico (RF-76)', false);
-- (se insertó con id explícito porque la secuencia de recursos estaba desincronizada)
```
Permisos (`{rol}_{accion}_{recurso}`), acciones C=1, R=2, D=4:
- **consumo_alimentos (47)** — C: admin(1), prod(2), vet(3) · R: admin, prod, vet · D(anular): admin, vet
- **medicamentos (48)** — C: admin(1), vet(3) · R: admin, prod, vet · D(anular): admin, vet

**Registrar medicamento restringido a Administrador y Veterinario** (no Productor),
por decisión del equipo, alineado con RF-76 Precondición 2.

## Gap 9 — `pgcrypto` no instalado (bloqueaba TODAS las inserciones)
El trigger `modulo5.calcular_hash_integridad()` (sobre `auditorias_suministros`, disparado
por la auto-auditoría) usa `digest(text,'sha256')` de la extensión **pgcrypto**, que no
estaba instalada. Como cada INSERT en los registros dispara la auto-auditoría, **ningún
registro podía guardarse** (error 500 `UndefinedFunction: digest`). Aplicado:
```sql
CREATE EXTENSION IF NOT EXISTS pgcrypto;   -- instalada en schema public
```

---

## Observación — Desincronización de estados en datos semilla de modulo2 (RF-44)
Al registrar un medicamento con período de retiro, se invoca RF-44 para poner el activo
`EN_TRATAMIENTO`. El trigger `modulo2.trg_fn_estado_activo_unico_vigente` exige que el
`id_estado_anterior` coincida con el último histórico. Varios activos de prueba tienen
`activos_biologicos.id_estado` desincronizado respecto a su último histórico (p.ej. activo
5: tabla=ACTIVO pero último histórico=AISLADO; activo 8: tabla=CERRADO pero último=INACTIVO).
Esto afecta por igual al flujo real de RF-44 de biological_assets; **no es un defecto de
M05**. Para las pruebas E2E se reconciliaron los históricos vía INSERT (mecanismo correcto,
no UPDATE directo — este último está bloqueado por
`trg_fn_activo_biologico_bloquear_cambio_estado_directo`).

---

## Resumen de decisiones
| # | Gap | Acción |
|---|-----|--------|
| 1 | Duplicados sin unicidad | Índices únicos parciales sobre VALIDADO |
| 2 | Enum vía incompleto | `ADD VALUE` TOPICA, INTRAMAMARIA + mapeo en VO |
| 3 | Falta nombre_veterinario | `ADD COLUMN nombre_veterinario varchar(150)` |
| 4 | descripcion_clinica NOT NULL | Se puebla con motivo_aplicacion; sin `observaciones` en medicamento |
| 5 | CHECK anulación medicamento | `chk_medicamento_anulacion` NOT VALID; mínimo 20 |
| 6 | observacion 60 vs 255 | Se conserva 60 (vista dependiente); DTO limitado a 60 |
| 7 | Nullable vs obligatorio | Enforce en DTO, sin alterar BD |
| 8 | RBAC ausente | Recursos 47/48 + 15 permisos |
| 9 | pgcrypto faltante | `CREATE EXTENSION pgcrypto` |

> Nota: estos cambios de BD (índices, enum, columna, CHECK, extensión, RBAC) se aplicaron
> directamente al entorno dev vía MCP postgres; **no están gestionados por migraciones**.
