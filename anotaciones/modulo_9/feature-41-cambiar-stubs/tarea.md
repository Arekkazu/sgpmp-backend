# Feature #41 — Reemplazar stubs de finca e infraestructura por consultas reales

Rama: `feature/#41-cambiar-stubs`

## Contexto

`FincaStubAdapter` e `InfraestructuraStubAdapter` (`src/configuration/infrastructure/adapters/`)
implementan el puerto `tiene_dependencias_activas()` que usan `DesactivarFincaUseCase` /
`DesactivarInfraestructuraUseCase` para bloquear la desactivación de una finca o área
productiva si todavía tiene dispositivos IoT o activos biológicos activos asociados
(RF-19 FA-04 / RF-20 FA-04). Ambos stubs retornan `False` siempre — el comentario dice
"hasta que RF-21 (IoT) y RF-33 (Activos Biológicos) estén implementados", pero ambos
módulos ya existen. Es el hallazgo transversal #1 de `anotaciones/modulo_9/estado.md`:
hoy se puede desactivar cualquier finca o área aunque tenga dispositivos o animales/lotes
activos, sin que el sistema lo detecte.

Plan completo: `/home/arekkazu/.claude/plans/vamos-realizar-la-siguiente-glittery-galaxy.md`
(referencia local, fuera del repo).

## Hallazgo de BD

No se requirió ningún cambio de esquema. Verificado en vivo contra la BD dev vía MCP
postgres:

- `modulo9.dispositivos_iot` (`es_activo`, FK a `infraestructuras`) — existe.
- `modulo2.activos_biologicos` (`id_infraestructura` FK a `modulo9.infraestructuras`,
  `id_estado` FK a `modulo2.estados_activos_biologicos`) — existe. Sin `id_finca`
  directo; la finca se resuelve vía `infraestructuras.id_finca`.
- **Ya existían, sin documentar en el repo ni en `alembic/`**, dos vistas hechas a
  medida para este chequeo: `modulo9.vw_rf19_dependencias_fincas` y
  `modulo9.vw_rf20_dependencias_infraestructuras`. Cuentan `dispositivos_activos`
  (`es_activo IS TRUE`) resolviendo la asociación *vigente* de cada dispositivo a su
  área — vía `sensores_areas_asociadas` (soporta reasignación de RF-22) o vía el
  device-tag de un activo biológico (`activos_biologicos.id_dispositivo_iot`) — no
  solo la FK estática `dispositivos_iot.id_infraestructura`. Mismo patrón que
  `vw_rf16_dependencias_ciclos`, ya consumida por `dependencia_ciclo_repository.py`.
- Esas vistas **solo** cuentan dispositivos IoT, no activos biológicos "alojados" en
  el área. Se complementa con una consulta directa a `modulo2.activos_biologicos`
  (`id_estado NOT IN (5, 6)` — excluye CERRADO y BAJA — mismo criterio que
  `InfraestructuraM09Adapter.calcular_ocupacion`).
- RBAC ya estaba aplicado (`admin_desactivar_finca`, `admin_desactivar_infraestr`,
  ver `cu04_gaps_bd_rf18_rf19_rf20.md`). No se tocó.

## Decisión de diseño (confirmada con el usuario)

Reutilizar las vistas `vw_rf19_dependencias_fincas` / `vw_rf20_dependencias_infraestructuras`
existentes en vez de reimplementar el join a mano — evita duplicar la lógica de
asociación vigente de RF-22 y sigue el mismo patrón que `dependencia_ciclo_repository.py`.

## Checklist

- [x] Crear `src/configuration/infrastructure/adapters/finca_dependency_adapter.py`
- [x] Crear `src/configuration/infrastructure/adapters/infraestructura_dependency_adapter.py`
- [x] Actualizar DI en `finca_router.py` (`FincaDependencyAdapter(db)`)
- [x] Actualizar DI en `infraestructura_router.py` (`InfraestructuraDependencyAdapter(db)`)
- [x] Borrar `finca_stub_adapter.py` e `infraestructura_stub_adapter.py`
- [x] Verificación in-process contra la BD dev (ver detalle abajo — se prefirió sobre
      curl+JWT porque ejercita exactamente el código nuevo sin el ruido de emitir
      login/token, que es una capa ya validada y sin relación con este cambio)
- [x] Sanity check de solo lectura contra datos reales de dev (finca 1 / infra 1)
- [x] Cerrar este documento con el resumen final

## Resumen final

### Qué se aplicó

1. **`src/configuration/infrastructure/adapters/finca_dependency_adapter.py`** (nuevo) —
   `FincaDependencyAdapter(FincaDependencyPort)`. Recibe `db: Session`. Consulta
   `dispositivos_activos` de `modulo9.vw_rf19_dependencias_fincas` (cuenta IoT activo
   con resolución de asociación vigente, soporta reasignación RF-22) y, si es 0,
   hace `EXISTS` contra `modulo2.activos_biologicos` unido a `modulo9.infraestructuras`
   por `id_finca`, excluyendo `id_estado IN (5, 6)` (CERRADO, BAJA).
2. **`src/configuration/infrastructure/adapters/infraestructura_dependency_adapter.py`**
   (nuevo) — mismo patrón contra `vw_rf20_dependencias_infraestructuras` y
   `activos_biologicos.id_infraestructura` directo.
3. **`finca_router.py`** / **`infraestructura_router.py`** — DI actualizada:
   `dependency_port=FincaStubAdapter()` → `FincaDependencyAdapter(db)` (mismo cambio
   para infraestructura). No se tocó ningún use case.
4. **Borrados**: `finca_stub_adapter.py`, `infraestructura_stub_adapter.py` (sin
   consumidores tras el paso 3).

### BD

Ningún cambio de esquema. Se reutilizaron dos vistas que ya existían en la BD dev sin
estar documentadas en el repo ni en `alembic/`: `modulo9.vw_rf19_dependencias_fincas`
y `modulo9.vw_rf20_dependencias_infraestructuras` (confirmadas con `pg_get_viewdef`,
mismo patrón que `vw_rf16_dependencias_ciclos` ya consumida por
`dependencia_ciclo_repository.py`). RBAC sin cambios (ya aplicado en CU04).

### Verificación realizada

Se optó por ejecutar los use cases directamente en proceso contra la BD dev (en vez
de curl+JWT) porque ejercita el 100% del código nuevo (adapters + wiring en el use
case) sin la capa de autenticación, que es preexistente y no se tocó en este cambio.
Resultados:

- **Bloqueo con dependencias reales** (sin ninguna escritura, la excepción se lanza
  antes del `commit()`):
  - `DesactivarFincaUseCase.execute(1, ...)` → `BusinessRuleError` `FINCA_CON_DEPENDENCIAS` ✅
    (finca 1 tiene 3 dispositivos IoT activos + activos biológicos activos en sus áreas)
  - `DesactivarInfraestructuraUseCase.execute(1, ...)` → `BusinessRuleError`
    `INFRAESTRUCTURA_CON_DEPENDENCIAS` ✅ (área 1 tiene 9 activos biológicos activos)
- **Éxito sin dependencias** (datos desechables creados para la prueba: finca
  "Finca Prueba Stub Verificacion" id=8, área "Area Prueba Stub Verificacion" id=13,
  sin dispositivos ni activos biológicos):
  - `DesactivarInfraestructuraUseCase.execute(13, ...)` → éxito, `es_activo=False`,
    fila de auditoría `DEACTIVATE` en `auditorias_infraestructuras` ✅
  - `DesactivarFincaUseCase.execute(8, ...)` → éxito, `es_activo=False`, fila de
    auditoría `DEACTIVATE` en `auditorias_fincas` ✅
- Antes de este cambio, los 4 casos habrían "pasado" silenciosamente porque el stub
  siempre devolvía `False` — el bug descrito en el hallazgo transversal #1 queda
  confirmado y corregido.

### Limpieza de datos de prueba

Se borró la infraestructura de prueba (id=13) y su fila de auditoría, y la fila de
auditoría de la finca de prueba. La finca de prueba (id=8) **no se pudo eliminar
físicamente**: un trigger de BD (`trg_fn_finca_no_delete_con_dependencias`) lo
bloquea por diseño, consistente con la restricción del propio RF-19 ("no eliminar,
solo desactivar"). Queda en la BD dev como `es_activo=false`, nombre
`Finca Prueba Stub Verificacion`, id=8 — inofensiva y fácilmente identificable como
resto de esta verificación.

### Alcance no cubierto por este cambio

Este fix resuelve únicamente RF-19/RF-20 del hallazgo transversal #1. Los otros tres
stubs listados en `estado.md` (`proceso_critico_stub.py` para RF-15,
`dependencia_patologia_stub.py` y `dependencia_metrica_stub.py` para RF-16) siguen
pendientes — su motivo documentado ("esperan al módulo de Predicción/IA — M04") sigue
siendo válido, no se tocaron.
