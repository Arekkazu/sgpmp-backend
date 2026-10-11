# INC-M02-66-G90 — Trigger de unicidad bloqueaba el reemplazo de sensor DIRECTA (RF-49)

**RF:** RF-49 (CU11) — Asociación de sensores IoT a activos biológicos.
**Endpoint:** `POST /activos-biologicos/{id_activo}/sensores`.
**Caso QA:** `TC-M02-G89`, dos defectos (`INC-M02-G89-01`, `INC-M02-G89-02`).

## INC-M02-G89-01 — Endpoints de ciclo de vida inexistentes (ya resuelto en `dev`)

**Qué reportó QA** (`TC-M02-216`, `TC-M02-218`, `TC-M02-219`): `PATCH /activos-biologicos/{id}/sensores/{id_asociacion}` no existía — desactivación manual, reactivación y rechazo de transición inválida respondían `404` por ausencia de ruta.

**Investigación:** ya resuelto en `dev` — ver `INC-M02-65-G89` (`anotaciones/modulo_2/inc_m02_65_g89_patch_ciclo_vida_asociacion_sensor.md`), que implementó `CambiarEstadoAsociacionSensorUseCase` con la tabla de transiciones `ACTIVA↔INACTIVA` y `SUPERADA` inalcanzable como destino. Mismo patrón que otros INC de este ciclo de tickets: QA corrió contra `sgpmp_test`, una revisión anterior. **No se requiere cambio de código para este defecto.**

## INC-M02-G89-02 — Trigger bloqueaba `ACTIVA → SUPERADA` (fix real de este ticket)

**Qué reportó QA** (`TC-M02-217`): registrar una segunda asociación DIRECTA para el mismo sensor y el mismo activo (reemplazo legítimo) respondía `500 Internal Server Error` en vez de `201`. Causa raíz según QA: el trigger `modulo2.trg_fn_asociacion_sensor_activo_unica` evaluaba `fecha_fin > now()`, sin excluir `id_activo_biologico = NEW.id_activo_biologico` ni los registros ya `SUPERADA`.

### Investigación (Paso 0) — hallazgo distinto a los INC anteriores de esta cadena

Se consultó `sgpmp_dev` en vivo vía MCP (`pg_get_functiondef`) antes de escribir nada:

```sql
SELECT p.proname, pg_get_functiondef(p.oid)
FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
WHERE n.nspname = 'modulo2' AND p.proname = 'trg_fn_asociacion_sensor_activo_unica';
```

El trigger **ya tiene la lógica corregida** en `sgpmp_dev`:

```sql
WHERE id_sensor = NEW.id_sensor
  AND tipo = 'directa'
  AND estado_asociacion = 'ACTIVA'
  AND fecha_fin IS NULL
  AND id_activo_biologico IS DISTINCT FROM NEW.id_activo_biologico
```

Las 3 correcciones que pide QA ya están aplicadas. **Pero a diferencia de los INC anteriores de esta cadena (`INC-M02-39-G27`, `INC-M02-40-G28`), esta corrección no existe en ningún commit ni migración de Alembic**: ni `alembic/versions/` ni `alembic/baseline/esquema_baseline.sql` la reflejan — el baseline sigue con la versión buggy (`fecha_fin > now()`, sin exclusión de activo, sin filtro de estado). Alguien aplicó el fix directamente contra la base de datos compartida, fuera de Alembic, sin registrar una revisión.

Esto es un problema real independiente de si `sgpmp_dev` "ya funciona": una base de datos nueva construida desde `baseline + alembic upgrade head` **no** tendría el fix, porque no hay ninguna migración que lo aplique.

### Fix

Migración `d014e2cc785d` (`v5.2.0_inc_m02_66_g90_trigger_asociacion_sensor_unica`), `CREATE OR REPLACE FUNCTION` con el texto exacto verificado contra `pg_get_functiondef` de la función en vivo (no una reconstrucción a mano — se copió el resultado de la consulta de solo lectura). `downgrade()` restaura el texto exacto del `esquema_baseline.sql` (la versión con el bug).

### 🔴 Requiere autorización de DBA

Sí — es una migración de Alembic sobre un trigger de `modulo2`.

### Por qué no se verificó con `alembic upgrade`/`downgrade` contra `sgpmp_dev`

A diferencia del resto de migraciones de esta sesión, aquí **no se ejecutó la migración** (ni `upgrade` ni `downgrade`) contra `sgpmp_dev` para verificarla. Motivo: `sgpmp_dev` ya tiene el trigger corregido aplicado fuera de banda; correr el `downgrade()` de esta migración —el paso normal para dejar `dev` como estaba antes de la aprobación formal del DBA— revertiría intencionalmente el trigger a la versión con el bug (`fecha_fin > now()`), afectando en vivo a cualquier otro usuario o prueba que dependa de que el reemplazo de sensores DIRECTA funcione hoy. Regresar la base compartida a un estado con bug, aunque sea unos segundos, no es un riesgo razonable solo para verificar una migración.

En su lugar, la verificación fue por **comparación exacta de texto**: el `upgrade()` de la migración es el resultado literal de `pg_get_functiondef` contra la función ya viva en `sgpmp_dev` (ver SQL arriba) — no hay diferencia entre lo que la migración escribiría y lo que ya está corriendo, así que aplicar `alembic upgrade head` en cualquier entorno (incluido uno nuevo desde `baseline`) reproduce exactamente el comportamiento ya verificado en producción/dev, sin necesidad de ejecutarlo contra la base compartida para confirmarlo.

### Pruebas

`tests/integration/test_inc_m02_66_g90_trigger_asociacion_sensor_unica.py` (nuevo, marcado `pytest.mark.integration`, requiere `TEST_DATABASE_URL` con la migración aplicada — mismo patrón que `test_inc_m02_75_g53_evento_fecha_race.py` para el trigger análogo de `eventos_activos`):

- `test_reemplazo_directa_sobre_el_mismo_activo_es_aceptado`: reproduce `TC-M02-217` — marca la asociación previa `SUPERADA` con `clock_timestamp()` y luego inserta la nueva, dentro de la misma transacción; no debe lanzar excepción.
- `test_directa_en_otro_activo_sigue_siendo_rechazada`: regresión — un sensor DIRECTA ya `ACTIVA` en **otro** activo debe seguir bloqueando la nueva asociación (`SENSOR_CONFLICT`, `P0229`). El fix no debe desactivar la unicidad real entre activos distintos.

**No se pudo ejecutar esta suite en este entorno**: `TEST_DATABASE_URL` no está configurada localmente (confirmado: ambos casos quedan en `skipped`, igual que el resto de `tests/integration/` en este entorno). Se espera que corra en CI, donde sí existe esa variable. No se fabrica un resultado de ejecución que no ocurrió.

Suite completa (`-m "not integration"`, sin tocar código de aplicación — este fix es enteramente de base de datos): 658 passed, mismos 2 fallos preexistentes en `test_registrar_transferencia_use_case.py` (no relacionados), 179 deselected (177 + los 2 nuevos casos de integración).

## Fuera de alcance

- Cualquier cambio de código Python: `AsociarSensorActivoUseCase` ya marca la asociación previa como `SUPERADA` correctamente antes de insertar la nueva — el bug era enteramente del trigger.
- Auditar si existen otros triggers/funciones con el mismo patrón de drift (corregidos en vivo sin migración) — este INC solo cubre `trg_fn_asociacion_sensor_activo_unica`.
