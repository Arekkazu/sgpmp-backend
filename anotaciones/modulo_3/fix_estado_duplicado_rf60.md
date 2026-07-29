# Fix — Estado duplicado por dispositivo (RF-60): 500 en `GET /iot/dispositivos/{id}/estado`

> Fecha: 2026-07-28 · Equipo: **Dev (backend)** · Módulo: M03 (Telemetría e IoT) · CU05
> Rama: `tweak/iot`. **No se hizo commit** (pendiente de indicación).

---

## Síntoma

`GET /api/iot/dispositivos/2/estado?limite_historial=50` → **500 Internal Server Error**:

```
sqlalchemy.exc.MultipleResultsFound: Multiple rows were found when one or none was required
```

## Causa raíz

El repo `SqlAlchemyEstadoDispositivoIoTRepository.obtener_por_dispositivo` usaba
`scalar_one_or_none()`, que exige ≤1 fila. El modelo RF-60 asume **un estado actual por dispositivo**
(el heartbeat hace get-or-insert-or-update por dispositivo; Fase 2 actualiza in-place), pero la DB
**no lo obligaba**: `modulo3.estados_dispositivos_iot` solo tenía PK sobre
`id_estado_dispositivo_iot`, sin `UNIQUE` sobre `id_dispositivo_iot`. El dispositivo 2 quedó con 2
filas (ids 1 y 3, ambas `INACTIVO/FALLO_CONECTIVIDAD`).

**Alineación con RF-60:** la inmutabilidad (Restricción 6 / RNF-06) aplica al historial de
transiciones y a los periodos de inactividad, **no** al registro de estado actual → deduplicar es
correcto. Por Restricción 11 (`timestamp_ultimo_contacto` = contacto más reciente) se conserva la
fila con el `fecha_ultimo_contacto` más nuevo. Verificado por MCP: solo el dispositivo 2 estaba
duplicado; nada referencia por FK a `id_estado_dispositivo_iot` (borrado seguro).

Efecto colateral corregido: `listar_activos` (evaluación periódica cada 60 s) ya no procesará el
dispositivo 2 dos veces.

## Cambios aplicados

### DB dev (vía MCP postgres) — **no gestionado por migraciones**

```sql
-- Fila conservada: id=1 (contacto 2026-05-12, el más reciente). Borrada: id=3 (contacto 2024-06-01).
DELETE FROM modulo3.estados_dispositivos_iot WHERE id_estado_dispositivo_iot = 3;

ALTER TABLE modulo3.estados_dispositivos_iot
  ADD CONSTRAINT uq_estados_dispositivos_iot_dispositivo UNIQUE (id_dispositivo_iot);
```

### Código

- `src/telemetry/infrastructure/repositories/estado_dispositivo_iot_repository.py` —
  `obtener_por_dispositivo`: `scalar_one_or_none()` → selección determinista de **una** fila
  (`order_by(fecha_ultima_actualizacion desc, fecha_ultimo_contacto desc nullslast, id desc)
  .limit(1).scalars().first()`). No cambia la firma del puerto (`Optional[EstadoDispositivoIoT]`);
  solo lectura, sin `commit()`.

> Comportamiento aceptado (fuera de alcance): con el `UNIQUE`, una carrera de doble-INSERT en
> `guardar()` daría `IntegrityError` → `raise_from_db_error` → `ConflictError` (409). Raro y
> aceptable; no se añadió `ON CONFLICT`.

## Verificación (contra BD dev)

1. Tras el `DELETE`: `count(*) WHERE id_dispositivo_iot=2` → **1**.
2. Constraint presente (`pg_constraint` contype `u` sobre `id_dispositivo_iot`); un INSERT duplicado
   de prueba (dentro de un bloque `DO`, con rollback) fue rechazado con `unique_violation`.
3. Import del repo → sin errores.
4. `ObtenerEstadoDispositivoUseCase(...).execute(dev, limite_historial=50)` para dev ∈ {1, 2, 3}:
   - dev=2 → OK, `id_estado=1`, historial=5 (antes: `MultipleResultsFound`).
   - dev=1 → OK (id_estado=2, historial=15); dev=3 → OK (id_estado=4, historial=3).

Equivale a `GET /iot/dispositivos/2/estado?limite_historial=50` → **200**.

## Replicar a staging/prod

La feature no funcionará en otros entornos hasta ejecutar la limpieza de duplicados (conservando el
de contacto más reciente por `id_dispositivo_iot`) **antes** del `ALTER TABLE … ADD CONSTRAINT
UNIQUE`. Ver también `cu05_gaps_bd_rf60_rf61.md`.
