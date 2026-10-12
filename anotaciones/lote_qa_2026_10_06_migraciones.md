# Lote QA 2026-10-06 — parte con migraciones (#489, #494)

Complementa `anotaciones/lote_qa_2026_10_06.md` (PR sin migraciones). Gaps de BD
encontrados, la decisión tomada y el SQL que aplican las dos migraciones Alembic.
**Requieren la autorización del DBA antes del merge.**

| Migración | Issue | Objeto | Tipo de cambio |
|-----------|-------|--------|----------------|
| `785d330f7541` | #489 INC-M02-64-G101 (RF-52) | `modulo2.bitacora_auditoria_m02` | Función + 3 triggers nuevos |
| `0618e6f7b308` | #494 INC-M09-64-G31 (RF-61 → RF-17) | `modulo3.vinculaciones_lecturas` | CHECK reemplazado |

Cadena: `78f6f579b5ba` (head actual de `dev`, DEV y TEST) → `785d330f7541` → `0618e6f7b308`.
Un solo head.

## #489 — Bitácora RF-52 sin protección en BD

**Gap.** RF-52, restricción 1: "La bitácora es append-only. Esta restricción debe estar
implementada a nivel de base de datos, no solo a nivel de lógica de negocio." Verificado en
DEV (2026-10-06): `modulo2.bitacora_auditoria_m02` no tiene triggers y `sgpmp_app`,
`rol_app`, `rol_dev`, `rol_impl`, `rol_aiot` y `rol_migracion` tienen UPDATE y DELETE sobre
la tabla.

**Decisión.** Trigger para todos los roles, mismo patrón y mismo SQLSTATE (`P0252`
IMMUTABLE_AUDIT) que `trg_auditoria_activos_inmutable_*` de M02. No se tocan los grants:
los gestiona la fase de control de acceso por BD (F4, PR #485) y el trigger ya cubre a
todos los roles, incluido el dueño de la tabla. La aplicación solo inserta
(`SqlAlchemyBitacoraAuditoriaRepository.registrar`) y ninguna función de la base modifica
esta tabla, así que el flujo actual no cambia. La tabla no tiene FKs, así que no hay
cascadas que choquen con el bloqueo.

CA-3 también pide "registrar el intento en la propia bitácora": eso no es posible desde un
trigger que aborta, porque el rollback borra también ese registro. Por API ya se cumple
(no hay rutas de escritura y los rechazos se auditan).

```sql
CREATE FUNCTION modulo2.fn_bitacora_auditoria_m02_inmutable() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    RAISE EXCEPTION
        'IMMUTABLE_AUDIT: La bitácora de auditoría RF-52 (modulo2.bitacora_auditoria_m02) es append-only. Operación % bloqueada.',
        TG_OP
    USING ERRCODE = 'P0252';
END;
$$;

CREATE TRIGGER trg_antes_actualizar_bitacora_auditoria_m02
    BEFORE UPDATE ON modulo2.bitacora_auditoria_m02
    FOR EACH ROW EXECUTE FUNCTION modulo2.fn_bitacora_auditoria_m02_inmutable();
CREATE TRIGGER trg_antes_eliminar_bitacora_auditoria_m02
    BEFORE DELETE ON modulo2.bitacora_auditoria_m02
    FOR EACH ROW EXECUTE FUNCTION modulo2.fn_bitacora_auditoria_m02_inmutable();
CREATE TRIGGER trg_antes_truncar_bitacora_auditoria_m02
    BEFORE TRUNCATE ON modulo2.bitacora_auditoria_m02
    FOR EACH STATEMENT EXECUTE FUNCTION modulo2.fn_bitacora_auditoria_m02_inmutable();
```

Nombres según `anotaciones/convencion_nomenclatura_bd.md` (`fn_`, `trg_` + momento + acción + tabla).
Downgrade: elimina los tres triggers y la función.

## #494 — La ingesta no crea vinculación

Había **tres causas**; las dos primeras las reportó QA y la tercera apareció al probar con
SQL real:

1. **CHECK.** `chk_vinculacion_modelo` exigía activo en toda fila INDIVIDUAL y lo prohibía
   en toda POBLACIONAL. Una lectura sin coincidencia (`SIN_VINCULAR`, o `AMBIGUA` con
   varios candidatos) no se podía guardar, aunque RF-61 (restricción 9) dice que
   SIN_VINCULAR "es válido" y se resuelve después. Un lote POBLACIONAL (que en M02 es el
   activo POBLACIONAL) tampoco podía quedar como el activo de su lectura, así que nunca se
   reclasificaba contra RF-17. En DEV solo existen 6 vinculaciones, todas de siembra (2024);
   ninguna `SIN_VINCULAR`.
2. **Stub de M02.** `ActivoBiologicoStubAdapter` siempre devolvía `[]`.
3. **FKs rotas en el ORM.** `VinculacionLecturaModel` declaraba FKs a `modulo3.telemetria` y
   `modulo9.infraestructura` (en singular). SQLAlchemy no lo detecta al importar: el flush
   falla con `NoReferencedTableError` antes de llegar a la base. **`AlertaModel` y
   `ReglaAlertaModel` tenían el mismo error**: con el código de `dev`, el INSERT de una
   alerta RF-57 por el ORM también falla así (verificado con un flush de `AlertaModel`).

Las tres fallaban en silencio: la ingesta descarta el error de vinculación como warning y
responde 201.

**Decisión sobre el CHECK.** La regla que sostiene RF-61 (postcondición 2: una lectura
CONFIRMADA tiene trazabilidad directa hacia su activo) es "una vinculación INDIVIDUAL
vigente apunta a su animal". El CHECK nuevo es más permisivo que el anterior: toda fila que
cumplía el viejo cumple el nuevo, así que el `upgrade` no puede fallar con los datos
existentes.

```sql
ALTER TABLE modulo3.vinculaciones_lecturas
    DROP CONSTRAINT chk_vinculacion_modelo,
    ADD CONSTRAINT ck_vinculacion_lectura_modelo_manejo CHECK (
        modelo_manejo <> 'INDIVIDUAL'::modulo3.enum_modelo_manejo
        OR estado_vinculacion <> 'VINCULADA'::modulo3.enum_estado_vinculacion
        OR id_activo_biologico IS NOT NULL
    );
```

El constraint modificado toma el prefijo `ck_` de la convención. **Downgrade:** restaura
`chk_vinculacion_modelo` y falla si ya existen filas que solo admite la regla nueva
(lecturas sin activo o POBLACIONAL con lote); habría que resolverlas antes de volver atrás.

**Código.**
- `ActivoBiologicoM02Adapter` reemplaza al stub (que se elimina). Busca los activos del área
  en estado operativo (ACTIVO, EN_TRATAMIENTO, AISLADO, los mismos que admiten eventos en
  RF-39): uno → `VINCULADA` al animal o a su lote; varios → `AMBIGUA`; ninguno →
  `SIN_VINCULAR`. Usa el estado actual del área (Subcomponente A, alcance MVP de RF-61);
  el historial para datos de buffer (Subcomponente B) es Fase 2.
- `VinculacionLectura.resolver()` acepta `SIN_VINCULAR` además de `AMBIGUA` (RF-61 Fase C1),
  como ya ofrece el frontend en `VinculacionDetalleModal`. Al resolver o corregir se
  reclasifica el semáforo contra RF-17 (sin cambios).
- FKs de los tres modelos corregidas, y un test exige que toda FK del ORM resuelva.

**Qué puede ejecutar QA tras el despliegue (TC-M09-66/67/68).** Una telemetría nueva deja
su fila en `GET /iot/vinculaciones?id_telemetria=<id>`. Si el área tiene un único activo
operativo queda `VINCULADA` y el semáforo se calcula con RF-17 en la misma ingesta; si
queda `SIN_VINCULAR` o `AMBIGUA`, `PATCH /iot/vinculaciones/{id}/resolver` la asocia y
reclasifica.

## Verificación

Postgres 17 desechable, `alembic upgrade head` desde cero:

- `upgrade` → `downgrade 78f6f579b5ba` → `upgrade` limpios.
- `tests/integration/test_inc_m02_64_g101_bitacora_append_only.py`: UPDATE, DELETE y
  TRUNCATE rechazados con `P0252` (3/3); sin la migración, 3/3 fallan.
- `tests/integration/test_inc_m09_64_g31_vinculacion_ingesta.py` (telemetría, dispositivo,
  sensor y activos reales): sin activos → SIN_VINCULAR; uno → VINCULADA; lote POBLACIONAL
  → VINCULADA al lote; varios → AMBIGUA; resolver SIN_VINCULAR dispara RF-17; el CHECK
  sigue exigiendo activo a una INDIVIDUAL VINCULADA. Con el CHECK viejo, 5/6 fallan por
  `chk_vinculacion_modelo`.
- `tests/shared/test_orm_foreign_keys_resolvibles.py`: falla con los modelos de `dev`.
- Suite completa: 1363 aprobadas, sin fallos nuevos respecto a `dev` en la misma base.

## Aplicación en DEV/TEST

Por el workflow de migraciones (o `alembic upgrade head` a mano, si el CI no tiene runner),
una vez autorizado. Comprobación posterior:

```sql
SELECT version_num FROM alembic_version;                       -- 0618e6f7b308
SELECT tgname FROM pg_trigger
 WHERE tgrelid = 'modulo2.bitacora_auditoria_m02'::regclass AND NOT tgisinternal;  -- 3 trg_antes_*
SELECT conname FROM pg_constraint
 WHERE conrelid = 'modulo3.vinculaciones_lecturas'::regclass AND contype = 'c';     -- ck_vinculacion_lectura_modelo_manejo
```
