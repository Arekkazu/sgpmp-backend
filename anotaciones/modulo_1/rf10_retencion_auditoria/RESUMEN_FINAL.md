# RF-10 — Resumen final de lo aplicado

Rama: `feature/rf10-retencion-auditoria-12-meses` · Cierre: 2026-08-27

Este documento cierra la tarea "política de retención de 12 meses y archivado
automático", que `estado_M01.md` listaba como el único gap real de RF-10.

Contenido de la carpeta:

- [`TAREAS.md`](./TAREAS.md) — checklist de ejecución.
- [`diseno.md`](./diseno.md) — decisiones de diseño y su justificación.
- [`curls_rf10_archivado.md`](./curls_rf10_archivado.md) — endpoints y errores.

---

## 1. Lo que ya traía la rama (verificado, sin cambios)

El commit `e44d41d` implementó la retención y el archivado. Se verificó contra el
esquema real y quedó tal cual:

| Pieza | Ubicación |
|---|---|
| Tabla histórica inmutable | `modulo1.eventos_archivados` (migración `8fc28a787fc8`) |
| Trigger de inmutabilidad | `trg_proteger_eventos_archivados` |
| Caso de uso del archivado | `src/identity_access/application/use_cases/auditoria/archivar_auditoria_use_case.py` |
| Modelo ORM | `src/identity_access/infrastructure/models/eventos_archivados_model.py` |
| Copia idempotente por lotes + advisory lock | `SqlAlchemyEventoRepository.archivar_eventos_anteriores` / `.adquirir_bloqueo_archivado` |
| Tarea diaria 04:00 UTC | `main.py` → `_archivar_auditoria_diariamente()` |

Puntos confirmados en la revisión:

- `down_revision='d4e2f8a15c9b'` encadena con el head real de `sgpmp`.
- Las 12 columnas replican 1:1 `modulo1.eventos`, más `fecha_archivado`.
- El trigger nuevo es réplica exacta de `modulo1.trg_fn_proteger_auditoria`
  (mismo `ERRCODE P0002`, mismo prefijo `IMMUTABLE_RECORD`).
- `commit()`/`rollback()` viven sólo en el use case.
- Idempotencia doble: `NOT EXISTS` + `ON CONFLICT (id_evento) DO NOTHING`.

## 2. Lo que faltaba y se agregó

### 2.1 El archivo histórico no lo leía nadie

`modulo1.eventos_archivados` era data muerta: sin endpoint, sin schema y sin método
de lectura en el repositorio.

**Se agregó `GET /auditoria/archivado/`**, reusando por completo
`ConsultarAuditoriaUseCase` mediante un parámetro `archivados: bool`. Así el
histórico hereda, sin duplicar código, el permiso RBAC, el 403 que audita el intento
denegado, el 400 del rango de fechas inconsistente, la paginación tope 50 y la
verificación del hash SHA-256 por fila.

Archivos tocados:

- `src/identity_access/infrastructure/repositories/evento_repository.py` —
  `_query_con_filtros` parametrizado por modelo; `listar_eventos` y `contar_eventos`
  aceptan `archivados`. `_a_entidad` y `_verificar_hash` se reusan sin duplicar,
  porque `EventosArchivados` replica los nombres de columna de `Eventos`.
- `src/identity_access/domain/repositories/evento_repository.py` — parámetro
  `archivados` en el puerto.
- `src/identity_access/application/use_cases/auditoria/consultar_auditoria_use_case.py` —
  propaga `archivados` y lo deja en el detalle del evento de auditoría tipo 16.
- `src/identity_access/infrastructure/routers/auditoria_routers.py` — segunda ruta
  y extracción del cuerpo común a `_consultar`.

### 2.2 El FA de fallo del archivado sólo dejaba un log

El RF pide *"dispara una alerta crítica al administrador — Notificación Interna"*.
La rama sólo hacía `logger.exception`.

**Se agregó una alerta real**: un evento de auditoría tipo 25
(`FALLO_ARCHIVADO_AUDITORIA`, resultado `fallido`) más una notificación por
destinatario en la bandeja interna de RF-14 (canal 2), con el mensaje del RF y el
texto de la excepción real.

Archivos tocados:

- `alembic/versions/a3b7c1d95e40_rf10_tipo_evento_fallo_archivado.py` — **nueva**.
- `src/identity_access/application/use_cases/auditoria/notificar_fallo_archivado_use_case.py` — **nuevo**.
- `src/identity_access/domain/value_objects/evento_categoria.py` — `25 → MODIFICACION`.
- `src/identity_access/domain/repositories/usuario_repository.py` y su implementación —
  `listar_ids_con_permiso(id_recurso, id_accion)`.
- `main.py` — dispara la alerta en el `except` del scheduler, con sesión limpia y
  `try/except` propio para que un fallo de la alerta no tumbe el bucle diario.

Los destinatarios se resuelven por permiso `(6, 2)` contra `modulo1.permisos`, no
por un `id_rol` quemado, y se limitan a cuentas en estado `Activo`.

---

## 3. SQL aplicado, por base

Ambas bases quedaron al día. Todo es aditivo: no se tocó ni una fila de
`modulo1.eventos`.

### `sgpmp` (desarrollo)

```bash
.venv/bin/alembic upgrade head
# d4e2f8a15c9b -> 8fc28a787fc8   (tabla histórica + 2 índices + trigger)
# 8fc28a787fc8 -> a3b7c1d95e40   (tipo de evento 25 + setval de la secuencia)
```

Estado resultante: `alembic_version = a3b7c1d95e40`,
`modulo1.eventos_archivados` con 3 índices (PK incluida) y 1 trigger,
`modulo1.tipos_eventos` con la fila 25 y la secuencia en 25.

### `pruebas` (integración)

Esta base sólo tiene el esquema `modulo1`, así que la cadena completa de Alembic no
corre ahí: incluye migraciones de `modulo3` y `modulo9` sobre tablas inexistentes.
Se aplicaron **sólo** las dos revisiones de RF-10, ejecutando su `upgrade()` dentro
de un `Operations.context`. Su `alembic_version` sigue en el baseline
`f7fe43537842`, que es la situación previa de esa base y no una regresión de RF-10.

### RBAC

Sin cambios. La lectura del histórico reusa el permiso ya existente
`(recurso 6 = auditoría, acción 2 = leer)`.

---

## 4. Verificación ejecutada

| Qué | Resultado |
|---|---|
| Suite completa `pytest tests` | **124 passed, 7 skipped** |
| Unitarias sin DB `-m "not integration"` | **78 passed** |
| Integración contra `pruebas` | **41 + 5 nuevas, todas en verde** |
| Rutas registradas en la app | `GET /auditoria/` y `GET /auditoria/archivado/` |
| Archivado ejecutado contra `sgpmp` | `bloqueo_adquirido=True`, `eventos_archivados=0`, corte `2025-08-28` |

El archivado en dev procesa 0 filas y eso es lo correcto: hay 936 eventos y el más
antiguo es de `2026-01-27`, así que todavía no hay nada con más de 12 meses. El
comportamiento con datos vencidos se cubre en `pruebas`, donde los tests siembran
eventos de 2025 y verifican el corte estricto.

Tests agregados en esta tarea:

- `tests/identity_access/test_rf10_alerta_fallo_archivado.py` (4 casos).
- `tests/integration/test_rf10_consulta_archivado_integration.py` (5 casos).
- `tests/identity_access/test_rf10_categorias_eventos.py` actualizado para el tipo 25.

---

## 5. Mapeo RF-10 → evidencia

| Criterio del RF | Dónde se cumple |
|---|---|
| Registra todos los eventos definidos | 25 tipos en `modulo1.tipos_eventos`; ya existía |
| Cada registro con todos los campos obligatorios | `modulo1.eventos`, 12 columnas |
| Registra intentos fallidos | `resultado = fallido` (login fallido, acceso denegado, fallo de archivado) |
| No permite modificación de registros | `trg_proteger_auditoria_*` y `trg_proteger_eventos_archivados` |
| Consulta con filtros funcionales | `GET /auditoria/` y `GET /auditoria/archivado/` |
| Paginación funciona | `pagina` / `tamano` con tope 50 en ambos endpoints |
| Retención mínima de 12 meses | tarea diaria 04:00 UTC + `modulo1.eventos_archivados` |
| Hash SHA-256 verificado en cada consulta | `_verificar_hash` → `integridad_ok`, también en el histórico |
| FA hash mismatch | `integridad_ok = false` en la respuesta; ya existía |
| FA acceso denegado 403 + registro del incidente | `ConsultarAuditoriaUseCase`, aplica a ambos endpoints |
| FA rango de fechas inválido 400 | `RANGO_FECHAS_INVALIDO`, aplica a ambos endpoints |
| FA inmutabilidad 405 | sin rutas `PUT`/`PATCH`/`DELETE`; trigger en DB como segunda barrera |
| FA fallo del archivado → alerta al administrador | evento tipo 25 + notificación interna canal 2 |

---

## 6. Pendientes y avisos

- **`modulo1.eventos` no decrece.** Es la consecuencia asumida de copiar en vez de
  trasladar; ver la justificación en `diseno.md`. Si el grupo de análisis decide que
  la tabla activa debe reducirse, hay que resolver antes la FK `NOT NULL` de
  `modulo1.notificaciones` y el trigger que bloquea `DELETE`.
- **Atribución del evento de fallo.** Se le asigna el destinatario de menor
  `id_usuario` porque `eventos.id_usuario` es `NOT NULL`. Un usuario de sistema
  dedicado sería más limpio si el catálogo de usuarios lo permite algún día.
- **No sembrar eventos sintéticos antiguos en `sgpmp`**: el trigger de inmutabilidad
  impide borrarlos después. Toda prueba con datos va en `pruebas`.
- El FA de "exceso de resultados 206" del RF no se implementa como 206: el sistema
  fuerza la paginación con `tamano ≤ 50` y devuelve 200. Es la conducta previa del
  endpoint activo y se mantuvo igual en el histórico por consistencia.
