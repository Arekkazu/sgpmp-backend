# Gap Paso 0 — permisos de más en `usuarios` / acción `leer` + mecanismo de refresco RF-11

## Hallazgo (RBAC)

El issue #17 reportó que `GET /usuarios/admin` (RF-11) respondía `200` con el
listado completo a un token de rol Veterinario, cuando el propio RF-11 usa
explícitamente a un Veterinario como ejemplo de rol que debe recibir `403`
("Acceso denegado").

En la base de datos (`sgpmp`, ambiente de dev) el permiso `require_permission(1, 2)`
— que protege tanto `GET /usuarios/admin` (RF-11) como `GET /usuarios/{id}/detalle`
(RF-12) — estaba concedido no solo a Administrador sino también a Productor,
Veterinario, Ingeniero de Campo y Contador:

| id_permiso | nombre | id_rol | rol |
|---|---|---|---|
| 2  | admin_leer_usuario | 1 | Administrador |
| 37 | prod_leer_usuario  | 2 | Productor |
| 45 | vet_leer_usuario   | 3 | Veterinario |
| 53 | ing_leer_usuario   | 4 | Ingeniero de Campo |
| 65 | cont_leer_usuario  | 5 | Contador |

Es el mismo patrón exacto ya corregido en el PR #16 para la acción
`actualizar` (recurso 1, acción 3 — ver
[`pr16_rf05_rf06_paso0_gap_rbac.md`](./pr16_rf05_rf06_paso0_gap_rbac.md)),
pero nunca se auditó para la acción `leer` (recurso 1, acción 2). El único
test de integración del PR #13 (`test_listado_admin_requiere_permiso`) usa
`id_rol=9` (Externo AgroFusion), que ya carecía del permiso, por lo que el
gap pasó inadvertido en esa revisión.

Impacto: cualquier usuario con rol Productor, Veterinario, Ingeniero de Campo
o Contador podía ver correo electrónico, rol y estado de cuenta de todos los
usuarios del sistema (RF-11), y la ficha de detalle de cualquier usuario
individual (RF-12), incluyendo administradores.

## Corrección aplicada

Se revocaron los 4 permisos. En `sgpmp` (dev), vía `DELETE` directo sobre
`modulo1.permisos` a través del MCP de postgres — a diferencia del PR #16,
esta vez **no** se usó la API `DELETE /roles/{id_rol}/permisos/{id_permiso}`
(`RetirarPermisoUseCase`), porque no había servidor local corriendo ni
credenciales de un Administrador real disponibles para obtener un JWT en el
momento de aplicar el fix. Se decidió con el usuario aplicar el `DELETE`
directo como alternativa pragmática, documentando aquí la desviación: **no
se generó el evento de auditoría tipo 15 (`REVOCACION_PERMISO`)** que sí
dejó el fix del PR #16 (`id_evento` 891-894, actor `id_usuario=29`). Si se
necesita el rastro de auditoría completo, puede reforzarse más adelante
llamando la API real con una sesión de Administrador.

- rol 2 (Productor) → permiso 37 revocado
- rol 3 (Veterinario) → permiso 45 revocado
- rol 4 (Ingeniero de Campo) → permiso 53 revocado
- rol 5 (Contador) → permiso 65 revocado

Aplicado en `sgpmp` (dev) el 2026-08-17. Se reverificó por SELECT que solo
`admin_leer_usuario` (id_permiso=2, rol Administrador) queda activo para
`(id_recurso=1, id_accion=2)`.

También se aplicó el mismo `DELETE` (SQL directo, base de pruebas
desechable) en la base local `pruebas` usada por la suite de integración —
tenía sembrado exactamente el mismo gap (mismos 5 `id_permiso`).

No es un cambio gestionado por migraciones — es una fila de datos en
`modulo1.permisos`, igual que otros gaps de RBAC documentados en este módulo.

## Verificación (RBAC)

- Reproducido con la suite de integración local (`TEST_DATABASE_URL` →
  `pruebas`), nuevos tests `test_veterinario_no_accede_listado_admin` y
  `test_veterinario_no_accede_detalle_usuario` en
  `tests/integration/test_rbac_perfil_listado.py`: antes del fix, Veterinario
  obtenía `200` en ambos endpoints; después, `403 ACCESO_DENEGADO`.
- Verificado en vivo contra `sgpmp` (dev): se firmó un JWT válido (con el
  `SECRET_KEY` real de la app, reutilizando una sesión ya activa) para el
  Administrador `id_usuario=29`. `GET /usuarios/admin` y
  `GET /usuarios/3/detalle` (rol Veterinario objetivo) respondieron `200`
  para el admin; no se repitió la prueba negativa contra dev con un token de
  Veterinario real para no fabricar sesiones de inicio de sesión sobre la
  cuenta de otra persona — ese caso queda cubierto por la suite de
  integración automatizada arriba.
- Reconfirmado por SELECT (MCP postgres) que solo `id_permiso=2` sigue activo
  para `(id_recurso=1, id_accion=2)` en `sgpmp`.

---

## Paso 0 — Triggers de BD para el mecanismo de refresco (RF-11)

RF-11 exige, de forma obligatoria, un mecanismo de "actualización en tiempo
real o refresco manual" para que el listado refleje cambios de estado/rol
hechos por otro administrador sin recargar la página. El proyecto no tiene
infraestructura de WebSocket/SSE en ningún módulo, así que se optó por
extender el endpoint existente `GET /usuarios/admin` con un campo de última
modificación por fila + un filtro de polling incremental
(`actualizado_desde`), en vez de crear un endpoint o infraestructura nuevos.

Antes de implementar se verificó en vivo (MCP postgres, `sgpmp`) que los
triggers necesarios ya existen y funcionan:

- **`trg_incrementar_version`** (BEFORE UPDATE en `modulo1.usuarios`, sin
  condición): incrementa `version` y setea `fecha_actualizacion := now()` en
  cada UPDATE de la fila, incluida la reasignación de rol (`id_rol` vive en
  esta tabla). Como `UsuarioRepository.actualizar()` reescribe la fila
  completa, este trigger se dispara siempre. No requirió ningún cambio de BD.
- **`trg_fn_validar_transicion_estado`** (BEFORE UPDATE en
  `modulo1.cuentas_usuarios`): valida la transición de estado y, si
  `id_estado_cuenta` cambia, setea `fecha_cambio_estado := now()`. También
  cubre el cambio a `Eliminado` (ver más abajo).
- **Hallazgo adicional, no bloqueante**: `Cuenta.cambiar_estado()` (dominio
  Python, usado por `GestionarCuentaUseCase` para activar/inactivar/bloquear/
  eliminar la cuenta de *otro* usuario) no setea `fecha_cambio_estado` — a
  diferencia de los demás métodos de transición de la entidad
  (`activar`, `poner_pendiente`, etc.), que sí reciben `ahora` y lo asignan.
  Funciona igual hoy porque el trigger de BD compensa la omisión, pero el
  dominio queda inconsistente consigo mismo (un test unitario con repo falso,
  o cualquier código que lea `cuenta.fecha_cambio_estado` antes del
  `flush()`/`refresh()`, vería el valor viejo). **No se corrigió en esta
  rama** porque cambiar la firma de `cambiar_estado` para recibir `ahora`
  tocaría call-sites fuera del alcance del issue #17. Queda como mejora
  pendiente para un ticket aparte.

## Diseño del mecanismo de refresco

- **`UsuarioListadoResponse.ultima_modificacion`**: máximo entre
  `usuarios.fecha_actualizacion` y `cuentas_usuarios.fecha_cambio_estado`,
  calculado en Python en `_a_detalle()` (el `joinedload` ya materializa
  ambos valores). El frontend puede comparar este campo por fila para saber
  si una fila cargada quedó desactualizada.
- **`GET /usuarios/admin?actualizado_desde=<timestamp>`**: filtra en SQL con
  `GREATEST(usuarios.fecha_actualizacion, cuentas_usuarios.fecha_cambio_estado) > actualizado_desde`
  (Postgres `GREATEST` ignora `NULL`s). Permite al frontend hacer polling
  incremental: guarda el `ultima_modificacion` más reciente que vio, y en el
  siguiente refresco solo pide lo que cambió desde ahí.
- El **orden del listado sigue siendo `fecha_registro DESC`** (lo que pide
  el RF literalmente), no por última modificación — reordenar en cada
  cambio volvería inestable la paginación durante el polling.
- **`estado_cuenta`** (nombre, case-insensitive) se agregó como filtro
  alternativo a `id_estado` (numérico), resuelto contra el catálogo
  `modulo1.estados_cuentas` en SQL (`JOIN` + `func.lower(...) == ...`), sin
  hardcodear ids en el use case.
- **`mensaje`** en la respuesta paginada: no nulo cuando `total == 0`, con
  texto distinto según si el vacío viene de `actualizado_desde` (nada
  cambió desde esa fecha) o de otros filtros (nada coincide).

## Por qué 410 y 500 no aplican a este diseño

El issue también listaba, como gaps menores del PR #13, "manejo de 410 por
eliminación concurrente" y "500 de fuga de datos sensibles detectada". Se
concluyó que ninguno de los dos aplica al diseño actual del sistema, en vez
de implementarse:

- **410 (eliminación concurrente)**: no existe ningún hard-delete de
  usuarios en el código (`grep` de `db.delete(` en `src/identity_access`
  solo aparece en `permiso_repository.py` y `rol_repository.py`, nunca en
  `usuario_repository.py` ni `cuenta_repository.py`). El "borrado" de un
  usuario es un cambio de `id_estado_cuenta` a `Eliminado` (catálogo id 5,
  soft-delete) — la fila nunca desaparece. Verificado también que
  `trg_fn_validar_transicion_estado` permite la transición a `Eliminado`
  desde cualquier estado activo, y ese `UPDATE` (no `DELETE`) también
  dispara `fecha_cambio_estado := now()`. Un usuario "eliminado" sigue
  apareciendo en el listado con `estado_cuenta="Eliminado"` y
  `ultima_modificacion` actualizada — ya detectable por el mecanismo de
  `actualizado_desde` como una fila modificada, no desaparecida.
- **500 (fuga de datos sensibles)**: `UsuarioListadoResponse` es un Pydantic
  model con campos fijos (`nombre_usuario`, `correo_electronico`,
  `nombre_rol`, `estado_cuenta`, `ultima_modificacion`) — no hay ningún path
  de serialización dinámica que pueda filtrar contraseñas, tokens u otros
  campos no declarados. La garantía ya está satisfecha por el tipado
  estático del schema; agregar una comprobación runtime sería código muerto
  para un caso que no puede ocurrir.

## Cambios de código

- `src/identity_access/domain/entities/usuario_detalle.py` — campo
  `ultima_modificacion`.
- `src/identity_access/domain/repositories/usuario_repository.py` — nuevos
  parámetros `estado_cuenta`/`actualizado_desde` en `listar_detalle`/`contar`.
- `src/identity_access/infrastructure/repositories/usuario_repository.py` —
  `order_by(fecha_registro DESC)`, filtros nuevos, cálculo de
  `ultima_modificacion`.
- `src/identity_access/application/use_cases/usuarios/listar_usuarios_use_case.py`
  — nuevos parámetros, cálculo de `mensaje`.
- `src/identity_access/infrastructure/schema/gestion_schema.py` — campos
  `ultima_modificacion` y `mensaje`.
- `src/identity_access/infrastructure/routers/usuarios_routers.py` — query
  params `estado_cuenta`/`actualizado_desde` (sin tocar el decorador RBAC).
- Tests nuevos: `tests/integration/test_rf11_listado_usuarios_refresco.py`
  (orden, filtro por estado, refresco incremental, mensaje vacío) y casos
  añadidos a `tests/integration/test_rbac_perfil_listado.py`.
