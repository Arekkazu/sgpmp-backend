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

Ambas bases quedaron al día. Todo es aditivo: no se modificó ni se borró ninguna
fila de `modulo1.eventos`.

### `sgpmp` (desarrollo)

```bash
.venv/bin/alembic upgrade head
# d4e2f8a15c9b -> 8fc28a787fc8   (tabla histórica + 2 índices + trigger)
# 8fc28a787fc8 -> a3b7c1d95e40   (tipo de evento 25 + setval de la secuencia)
# a3b7c1d95e40 -> b5d81f27ac93   (3 campos del RF x 2 tablas, 3 índices, línea base)
# b5d81f27ac93 -> c8e4a5b13d72   (siembra de la línea base de integridad)
```

Estado resultante: `alembic_version = c8e4a5b13d72`; `modulo1.eventos` con 15
columnas y 4 índices; `modulo1.eventos_archivados` con las mismas 3 columnas
nuevas; `modulo1.tipos_eventos` con la fila 25 y la secuencia en 25;
`modulo1.integridad_baseline` con 92 filas (21 `SIN_HASH`, 71 `ESQUEMA_ANTERIOR`).

### `pruebas` (integración)

Esta base sólo tiene el esquema `modulo1`, así que la cadena completa de Alembic no
corre ahí: incluye migraciones de `modulo3` y `modulo9` sobre tablas inexistentes.
Se aplicaron **sólo** las cuatro revisiones de RF-10, ejecutando su `upgrade()`
dentro de un `Operations.context`. Su `alembic_version` sigue en el baseline
`f7fe43537842`, que es la situación previa de esa base y no una regresión de RF-10.

La siembra de la línea base depende del ambiente: inspecciona los eventos
existentes y sólo registra los que ya no son verificables. En `pruebas` insertó 0
filas porque no hay legado, que es lo correcto.

### RBAC

Sin cambios. La lectura del histórico reusa el permiso ya existente
`(recurso 6 = auditoría, acción 2 = leer)`.

---

## 4. Verificación ejecutada

| Qué | Resultado |
|---|---|
| Suite completa `pytest tests` | **138 passed, 7 skipped** |
| Rutas registradas en la app | `GET /auditoria/`, `GET /auditoria/archivado/`, más `PUT`/`PATCH`/`DELETE` que responden 405 |
| Archivado ejecutado contra `sgpmp` | `bloqueo_adquirido=True`, `eventos_archivados=0`, corte a 12 meses |
| Clasificación de integridad en `sgpmp` | **844 `INTEGRO`, 92 `LEGADO`, 0 `MANIPULADO`** |

El archivado en dev procesa 0 filas y eso es lo correcto: hay 936 eventos y el más
antiguo es de `2026-01-27`, así que todavía no hay nada con más de 12 meses. El
comportamiento con datos vencidos se cubre en `pruebas`, donde los tests siembran
eventos de 2025 y verifican el corte estricto.

Tests agregados en esta tarea:

- `tests/identity_access/test_rf10_alerta_fallo_archivado.py` (4 casos).
- `tests/integration/test_rf10_consulta_archivado_integration.py` (5 casos).
- `tests/integration/test_rf10_conformidad_integration.py` (14 casos): un caso por
  cada punto de la auditoría de conformidad — campos obligatorios, 500 por
  manipulación, línea base, 403 auditado, 405, 400 por filtros, 206, índices y
  espejo del catálogo de tipos.
- `tests/identity_access/test_rf10_categorias_eventos.py` actualizado para el tipo 25.

`tests/integration/conftest.py` cambió en dos puntos: `crear_evento_db` ahora
calcula un hash real por defecto (un evento sin hash ya no cuenta como íntegro) y
la app de integración registra `RequestContextMiddleware`, para que las pruebas
reflejen el comportamiento de `main.py`.

---

## 4-bis. Cierre de la auditoría de conformidad literal

Tras cerrar retención y archivado se hizo una revisión campo por campo y flujo
por flujo del RF ([`auditoria_cumplimiento_rf10.md`](./auditoria_cumplimiento_rf10.md)),
que encontró 8 incumplimientos. Todos quedaron cerrados.

### A. Campos obligatorios de la sección "Entradas"

Faltaban `nombre_usuario`, `direccion_ip` y `user_agent` como columnas, y
`id_sesion` sólo se llenaba en 4 de los 29 puntos de registro (16% de los
eventos). Se agregaron las tres columnas —nullable, porque los eventos previos
son inmutables— y se llenan **en el único punto por el que pasan todos los
eventos**, `SqlAlchemyEventoRepository.registrar`, en vez de tocar los 29
llamadores:

- IP y user-agent salen del contexto del request (`src/shared/audit_context.py`),
  que puebla `RequestContextMiddleware`. Ese middleware existía pero **nunca se
  registraba en `main.py`**, por eso la IP sólo llegaba donde el router la pasaba
  a mano; ahora está activo.
- `id_sesion` se deriva del `jti` del JWT que deposita `get_current_user`.
- `nombre_usuario` se congela desde `modulo1.usuarios` al momento del evento, de
  modo que el registro siga identificando al actor aunque después cambie de nombre.
- `descripcion` toma por defecto el nombre del tipo de evento.

El contexto guarda un objeto **mutable** a propósito: FastAPI corre las
dependencias síncronas en un threadpool con una copia del contexto, así que un
`ContextVar.set()` hecho en `get_current_user` se perdería al volver; mutar un
objeto ya enlazado sí se ve desde fuera.

Los tres campos se exponen en `AuditoriaItemResponse` y se copian al histórico.

### B. FA "Fallo de integridad del registro" → 500

Antes devolvía 200 con `integridad_ok: false`. Ahora `ConsultarAuditoriaUseCase`
lanza `INTEGRIDAD_AUDITORIA_VIOLADA` (500) con el mensaje del RF y el
`id_evento` afectado.

**Problema que esto destapó:** en `sgpmp` hay 92 eventos no verificables —21 sin
hash y 71 con hash de un esquema anterior, irreproducible—. Como son inmutables,
el 500 literal habría dejado la consulta rota de forma permanente sobre datos
legítimos.

Se resolvió con `modulo1.integridad_baseline`: registra, una sola vez por
ambiente, el hash **recalculado** de esos eventos al adoptar la política. La
clasificación queda en tres estados:

- `INTEGRO` — el hash almacenado coincide con el recalculado.
- `LEGADO` — no verificable desde antes de la política y sin cambios desde
  entonces. Se reporta como no íntegro pero no escala a 500.
- `MANIPULADO` — cualquier otro caso. Escala a 500.

Guardar el hash recalculado y no el almacenado es lo que da la garantía: si el
contenido de un registro de la línea base cambiara después, el recálculo dejaría
de coincidir y pasaría a `MANIPULADO`. La línea base es append-only e inmutable
por trigger, igual que la auditoría.

Estado real en `sgpmp`: **844 íntegros, 92 legado, 0 manipulados.**

Además, un evento sin `hash_integridad` ya **no** se reporta como íntegro: el RF
declara el hash obligatorio, así que su ausencia no puede leerse como registro
sano. Antes `_verificar_hash` devolvía `True` en ese caso, lo que permitía que
borrar el hash hiciera pasar un registro manipulado.

### C. FA "Acceso denegado" → mensaje del RF y el intento auditado

`require_permission` es dependencia de ruta y corta antes del caso de uso, así
que el bloque que registraba el intento denegado era **código muerto**: nunca se
alcanzaba, y el cliente recibía el mensaje genérico de RBAC.

Se reemplazó por `verificar_acceso_auditoria` en el router, que consulta la misma
tabla `modulo1.permisos` —la decisión sigue siendo RBAC, no un `id_rol` quemado—
pero además registra el evento tipo 16 con resultado `fallido` antes de lanzar el
403 con el mensaje del RF. De paso se eliminó el `ROL_ADMINISTRADOR = 1` del caso
de uso, que violaba la regla de `CLAUDE.md`.

Si la auditoría del incidente falla, se hace rollback y se devuelve el 403 igual:
no poder registrar el intento no debe convertir una denegación en un 500 que la
oculte.

### D. FA "Intento de modificación o eliminación" → 405 con el mensaje del RF

Antes respondía el `{"detail": "Method Not Allowed"}` por defecto de FastAPI. Se
agregó `MethodNotAllowedError` (405) a `src/shared/errors.py` y rutas explícitas
`PUT`/`PATCH`/`DELETE` sobre `/auditoria` que devuelven el mensaje del RF en el
formato de error del proyecto. La base ya lo bloqueaba por trigger; esto cubre la
capa de API que el RF exige por separado.

### E. FA "Exceso de resultados" → 206 Partial Content

Cuando el total supera `UMBRAL_SATURACION` (10.000), la respuesta viaja con
**HTTP 206** y el campo `mensaje` con el texto del RF. Por debajo del umbral sigue
siendo 200 con `mensaje: null`.

### F. FA "Filtro de búsqueda inválido" → también por `id_usuario` inexistente

Sólo se validaba el rango de fechas. Ahora el caso de uso recibe
`UsuarioRepository` y rechaza con 400 `FILTROS_INCONSISTENTES` tanto el rango
inconsistente como un `id_usuario` que no existe.

### G. FA "Blocker" → mensaje del RF

El rollback de la acción principal ya era correcto, pero la excepción se propagaba
cruda. Ahora `registrar()` traduce cualquier fallo de persistencia a
`AUDITORIA_OBLIGATORIA_FALLIDA` (500) con el mensaje del RF, nombrando la
operación cancelada.

El nombre de la operación sale de `_NOMBRE_POR_TIPO_EVENTO`, un espejo de
`modulo1.tipos_eventos` en el dominio: consultarlo en DB justo cuando la DB es lo
que falla no serviría. `test_nombres_de_tipo_evento_coinciden_con_el_catalogo`
vigila que el espejo no derive.

Sólo la escritura del evento dispara el Blocker. Resolver el nombre del usuario o
la sesión es enriquecimiento y falla en silencio: no tendría sentido cancelar un
cambio de contraseña porque no se pudo leer un nombre para mostrar.

### H. RNF de rendimiento y escalabilidad

`modulo1.eventos` sólo tenía la clave primaria como índice. Se agregaron
`ix_eventos_fecha`, `ix_eventos_usuario_fecha` e `ix_eventos_tipo_fecha`, que
cubren los filtros y el `ORDER BY fecha_evento DESC` del endpoint.

---

## 5. Mapeo RF-10 → evidencia

| Criterio del RF | Dónde se cumple |
|---|---|
| Registra todos los eventos definidos | 25 tipos en `modulo1.tipos_eventos` |
| Cada registro con todos los campos obligatorios | `modulo1.eventos`, 15 columnas (incluye `nombre_usuario`, `direccion_ip`, `user_agent`) |
| Almacena IP y sesión | contexto del request → `registrar()`, en los 29 puntos de registro |
| Registra intentos fallidos | `resultado = fallido` (login fallido, acceso denegado, fallo de archivado) |
| No permite modificación de registros | `trg_proteger_auditoria_*`, `trg_proteger_eventos_archivados`, `trg_proteger_integridad_baseline` |
| Consulta con filtros funcionales | `GET /auditoria/` y `GET /auditoria/archivado/` |
| Paginación funciona | `pagina` / `tamano` con tope 50 en ambos endpoints |
| Retención mínima de 12 meses | tarea diaria 04:00 UTC + `modulo1.eventos_archivados` |
| Hash SHA-256 verificado en cada consulta | `clasificar_integridad` → `integridad` / `integridad_ok`, también en el histórico |
| FA hash mismatch → 500 | `INTEGRIDAD_AUDITORIA_VIOLADA`, con línea base para el legado irreparable |
| FA blocker → 500 y rollback | `AUDITORIA_OBLIGATORIA_FALLIDA` desde `registrar()` |
| FA acceso denegado 403 + registro del incidente | `verificar_acceso_auditoria` en el router |
| FA filtros inválidos 400 | `FILTROS_INCONSISTENTES`: rango de fechas e `id_usuario` inexistente |
| FA inmutabilidad 405 | rutas `PUT`/`PATCH`/`DELETE` que devuelven el mensaje del RF; triggers en DB |
| FA exceso de resultados 206 | `UMBRAL_SATURACION = 10.000` → HTTP 206 + campo `mensaje` |
| FA fallo del archivado → alerta al administrador | evento tipo 25 + notificación interna canal 2 |
| RNF consulta < 3 s y alto volumen | 3 índices nuevos sobre `modulo1.eventos` |

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
- **Los 92 eventos de la línea base nunca serán `INTEGRO`.** Son inmutables y su
  hash es irreproducible; se reportan como `LEGADO` de forma permanente. Es la
  única lectura posible del RF: exige a la vez inmutabilidad absoluta y hash
  verificable, y esos registros nacieron antes de la segunda regla.
- **Los campos nuevos son nullable y quedan vacíos en los eventos previos.** No se
  pueden rellenar sin violar la inmutabilidad. Se llenan a partir de los eventos
  registrados desde esta versión.
- **La fórmula del hash no cambió.** IP y user-agent viajan dentro de `detalle`,
  que ya entraba en el cálculo, así que los eventos anteriores siguen validando
  igual. Incluir las columnas nuevas en la fórmula habría invalidado los 844
  registros que hoy son íntegros.
- **`_NOMBRE_POR_TIPO_EVENTO` duplica `modulo1.tipos_eventos`.** Es deliberado: el
  mensaje del FA Blocker se necesita justamente cuando la DB no responde.
  `test_nombres_de_tipo_evento_coinciden_con_el_catalogo` falla si derivan.
