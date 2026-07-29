# Implementación Dev-M03 — Endpoint de mantenimiento (RF-60) y fix de reevaluar (RF-62)

> Fecha: 2026-07-27 · Equipo: **Dev (backend)** · Módulo: M03 (Telemetría e IoT)
> Alcance: cerrar las **dos** brechas atribuibles a Dev-M03 identificadas en el
> triage `anotaciones/modulo_3/pendientes_frontend_m03.md` (puntos **#2** y **#5**).
> Todo lo demás del triage es AIOT, dependencia de otros módulos (M02/M04/M08/M09)
> o fuera del RF, y **no** se tocó.

---

## Resumen

| # | Brecha | Tipo | Qué se hizo |
|---|--------|------|-------------|
| #2 | RF-60: falta transición manual `EN_MANTENIMIENTO ↔ ACTIVO` | Brecha de backend | Nuevo endpoint `PATCH /iot/dispositivos/{id}/mantenimiento` + caso de uso |
| #5 | RF-62: `POST /iot/calidad/reevaluar` → 500 (`usuario_actual.email` inexistente) | Bug de backend | Se resuelve el nombre real del usuario desde el módulo de identidad |

Ambas verificadas end-to-end contra la BD dev. **No se hizo commit** (por indicación).

---

## Paso 0 — Análisis de BD y RBAC (vía MCP postgres). Resultado: sin DDL/DML

- El enum `modulo3.enum_estado_dispositivo` ya incluye `EN_MANTENIMIENTO`.
- RBAC ya presente y activo:
  - Recurso **35** (`infraestructura_iot`), acción **3 (U)** → Administrador (`id_permiso 212`)
    e Ingeniero de Campo (`id_permiso 216`). `require_permission(35, 3)` autoriza exactamente a
    Admin+Ing, como pide RF-60. **Antes ningún endpoint la usaba.**
  - Recurso **38** (`calidad_telemetria`), acción **5 (E)** → Admin e Ing (el fix de reevaluar
    no toca RBAC).
- **Hallazgo clave:** `causa_primaria` (en `estados_dispositivos_iot` y en
  `historico_transiciones_dispositivos`) es del enum `enum_causa_inactividad`, cuyos únicos
  valores son `FALLO_CONECTIVIDAD, BATERIA_CRITICA, BATERIA_BAJA, SEÑAL_DEGRADADA,
  SOBRECALENTAMIENTO, SENSOR_FISICO_FALLIDO, FALLO_INFRAESTRUCTURA_COMPARTIDA`. **No hay un valor
  de "mantenimiento".** La columna es nullable → la transición manual usa `causa_primaria = NULL`.
  Inventar un valor habría reventado el INSERT.
- **Hallazgo clave 2 (trigger de BD):** existe el trigger `trg_rf60_02_log_transicion_estado`
  (`AFTER UPDATE` sobre `estados_dispositivos_iot`, función `fn_log_transicion_dispositivo`) que
  **inserta automáticamente la fila en `historico_transiciones_dispositivos`** en cada cambio de
  `estado_actual` (copiando `id_usuario` → `id_usuairo_responsable`, `causa_primaria`, etc., con
  `notas = 'Transición automática de estado operativo'`). Además el histórico es **append-only**
  (triggers `trg_rf60_03_..._no_update` y `trg_rf60_04_..._no_delete`).

**Conclusión:** no se aplicó ningún cambio de esquema ni de permisos. Todo fue código + documentación.

---

## A. Endpoint de mantenimiento — RF-60 CA-7/CA-8

**Contrato** (`PATCH /iot/dispositivos/{id_dispositivo_iot}/mantenimiento`, RBAC `(35, U)`, solo Admin/Ing):

- Body `AplicarMantenimientoDTO`: `nuevo_estado ∈ {EN_MANTENIMIENTO, ACTIVO}` (se normaliza a
  mayúsculas) + `motivo?` (máx. 500).
- Respuesta 200: `EstadoDispositivoIoTSchema` (estado ya actualizado).
- Errores: 404 `ESTADO_DISPOSITIVO_NO_ENCONTRADO`, 422 `ESTADO_SIN_CAMBIO`, 401/403 RBAC.

**Archivos:**

- *Nuevo* `src/telemetry/infrastructure/dto/aplicar_mantenimiento_dto.py` — DTO validando los dos estados.
- *Nuevo* `src/telemetry/application/use_cases/infraestructura/aplicar_mantenimiento_dispositivo_use_case.py`
  — caso de uso `AplicarMantenimientoDispositivoUseCase`.
- *Modificado* `src/telemetry/infrastructure/routers/infraestructura_iot_router.py` — nuevo handler
  `aplicar_mantenimiento_dispositivo` + imports.

**Flujo del caso de uso:** `obtener_por_dispositivo` (→ 404 si no existe) → guard `ESTADO_SIN_CAMBIO`
→ `estado.aplicar_transicion(nuevo_estado, causa=None, ahora, id_usuario=actor)` →
`estado_repo.actualizar(estado)` → `db.commit()` (con `try/except rollback`) → auditoría RF-63
best-effort **después** del commit.

**Registro del histórico:** lo hace el **trigger de BD**, no el caso de uso. Por eso el use case
**no** inserta manualmente en `historico_transiciones_dispositivos` (hacerlo generaría una fila
duplicada). Se reutiliza sin cambios la entidad `EstadoDispositivoIoT` (`aplicar_transicion`, que ya
acepta ambos estados) y el repo `SqlAlchemyEstadoDispositivoIoTRepository`.

**Auditoría RF-63:** evento `TRANSICION_MANTENIMIENTO_MANUAL`, `componente_origen=RF60`
(clasificación TÉCNICO, retención 1 año), `entidad_afectada_tipo=DISPOSITIVO`, con `nombre_usuario`
real y el `motivo` en `accion_detallada`. Emitida vía `RegistrarEventoAuditoriaIotUseCase`
(best-effort: no bloquea el flujo si falla).

**El job periódico no interfiere:** `EvaluarEstadoDispositivosUseCase` ya excluye `EN_MANTENIMIENTO`
(`listar_activos` lo filtra y `evaluar_transicion` retorna `None`), así que no pisa el estado manual.

---

## B. Fix del bug de reevaluar — RF-62

**Causa raíz:** `calidad_router.py` pasaba `usuario_actual.email`, pero `UsuarioActual`
(`src/identity_access/infrastructure/dependencies.py`) solo expone `id_usuario`, `id_token`,
`id_rol` (el JWT no lleva nombre ni correo) → `AttributeError` → **500 en cada llamada autorizada**.

**Corrección** (solo en `src/telemetry/infrastructure/routers/calidad_router.py`): resolver el
nombre real del usuario desde el módulo de identidad, reutilizando el patrón canónico del repo
(`usuarios_routers.py`):

```python
detalle = SqlAlchemyUsuarioRepository(db).obtener_detalle(usuario_actual.id_usuario)
nombre_usuario = f"{detalle.nombre} {detalle.apellidos}" if detalle else str(usuario_actual.id_usuario)
resultado = use_case.execute(dto=dto, id_usuario=usuario_actual.id_usuario, nombre_usuario=nombre_usuario)
```

El use case `SolicitarReevaluacionUseCase.execute(..., nombre_usuario: str)` ya era correcto y **no
se tocó**; el fix es exclusivamente del router. Así la auditoría RF-63 de la reevaluación queda con
el nombre humano real en `usuario_responsable`.

---

## Decisiones de diseño

- **Endpoint bidireccional único** (`/mantenimiento` con `nuevo_estado`) en lugar de dos rutas
  entrar/salir — menos superficie, mismo estilo que `PATCH /iot/alertas-tecnicas/{id}/estado`.
- **`causa_primaria = NULL`** para la transición manual (el enum no tiene valor de mantenimiento).
- **Se delega el histórico al trigger de BD** (fuente única) en vez de insertarlo en el use case,
  para no duplicar filas. El `motivo` humano vive en la bitácora RF-63.
- **Guard `ESTADO_SIN_CAMBIO` (422)** para rechazar no-ops.
- **Auditoría best-effort** tras el commit (patrón del módulo).
- **Nombre real del usuario** (nombre+apellidos) en vez del correo, tanto en el fix B como en la
  auditoría del endpoint de mantenimiento.

---

## Observación (fuera de alcance — no se corrigió)

El job `EvaluarEstadoDispositivosUseCase` **también** inserta explícitamente en el histórico *además*
de disparar el trigger `trg_rf60_02_log_transicion_estado`, por lo que cada transición automática
queda **duplicada** en `historico_transiciones_dispositivos`. Es un doble-registro preexistente,
ajeno a estas dos brechas; se deja anotado para que los líderes decidan (lo correcto sería que el
job deje de registrar explícitamente y confíe en el trigger, igual que hace el nuevo endpoint de
mantenimiento).

---

## Qué NO se hizo (alcance)

Del triage de `pendientes_frontend_m03.md`, todo lo demás queda igual: paneles de buffer/edge
(AIOT, RF-54/RF-55), exportación (M08), umbrales versionados y parámetros de calidad (M09),
vinculación de activos (M02), inferencia (M04), y las mejoras "fuera-RF" (tablero de flota, filtro
multi-estado, WebSocket/SSE).

---

## Cómo se verificó (end-to-end contra la BD dev)

1. **Fix B:** `SqlAlchemyUsuarioRepository(db).obtener_detalle(1)` → `"Carlos Rodríguez Pérez"`
   (confirma que ya no revienta con `AttributeError`).
2. **Mantenimiento → EN_MANTENIMIENTO** (dispositivo 1, actor id 1):
   - `estados_dispositivos_iot`: `estado_actual=EN_MANTENIMIENTO`, `causa_primaria=NULL`.
   - `historico_transiciones_dispositivos`: **exactamente 1** fila nueva (la del trigger) con
     `estado_nuevo=EN_MANTENIMIENTO`, `id_usuairo_responsable=1` — sin duplicado.
   - `bitacora_auditoria_iot`: evento `TRANSICION_MANTENIMIENTO_MANUAL` con `nombre_usuario` real,
     `entidad_afectada_tipo=DISPOSITIVO` y `accion_detallada.motivo` = el motivo enviado.
3. **Guards:** reenviar el estado actual → **422** `ESTADO_SIN_CAMBIO`; dispositivo inexistente →
   **404** `ESTADO_DISPOSITIVO_NO_ENCONTRADO`.
4. **Cleanup:** el estado del dispositivo 1 se restauró a su valor original (`INACTIVO` /
   `FALLO_CONECTIVIDAD`). Las filas de transición y de auditoría generadas por la prueba **quedan**
   en la BD (el histórico y la bitácora son append-only por diseño RF-60/RF-63).

> Para probar por HTTP: `POST /sesiones/` como Admin/Ing → reutilizar el `Authorization: Bearer` →
> `PATCH /iot/dispositivos/{id}/mantenimiento` con `{"nuevo_estado":"EN_MANTENIMIENTO","motivo":"..."}`.
