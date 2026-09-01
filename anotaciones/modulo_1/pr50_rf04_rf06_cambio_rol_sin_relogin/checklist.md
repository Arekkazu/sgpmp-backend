# PR #50 — RF-04/06: aplicar cambios de rol sin requerir relogin

Issue #1599 · PR #50 · rama `feature/rf04-rf06-cambio-rol-sin-relogin` (commit único `ccff907`)
Rama de revisión local: `review/pr50-rf04-rf06` (creada desde `origin/dev`, sin commit ni push)

Documento de trabajo: se va cerrando a medida que avanza la revisión.
El resumen definitivo queda en `resumen.md` de esta misma carpeta.

---

## El problema que resuelve el PR

`id_rol` viajaba fijo dentro del JWT desde el login y nunca se revalidaba contra la base.
Si un administrador reasignaba el rol de un usuario puntual, ese usuario seguía operando con
los permisos del rol anterior hasta que el token expirara o cerrara sesión. Incumple el
criterio de aceptación de RF-04: *"aplica los cambios de permisos a usuarios con sesiones
activas sin requerir cierre de sesión"*.

Ojo con la distinción: cambiar **los permisos de un rol** ya se aplicaba en vivo
(`require_permission` consulta `modulo1.permisos` en cada request, sin caché). Lo que no se
aplicaba era **reasignar el rol de un usuario concreto**.

---

## Revisión del PR — qué estaba bien

- [x] El arreglo está en el único choke point que existe. `dependencies.py:62` era el único
      punto de `src/` que leía el claim `rol` del JWT; todo lo demás consume
      `usuario_actual.id_rol`: `shared/rbac.py:49`, `GET /sesiones/me/permisos`
      (`sesiones_routers.py:172`), `finca_router.py:85,110`, los tres use cases de
      `configuration/.../personalizacion/`, y `consultar_detalle_usuario_use_case.py:148`.
- [x] `src/shared/agrofusion_auth.py` es un camino M2M distinto (secreto de plataforma, sin
      `id_rol`) y no se ve afectado.
- [x] `usuarios.id_rol` es `NOT NULL` (ORM y `information_schema` en `sgpmp`), así que el
      `scalar()` devolviendo `None` solo puede significar "fila de usuario inexistente".
      No hay falso 401 por un `id_rol` nulo.
- [x] `RefreshTokenUseCase` ya leía el rol desde base (`refresh_token_use_case.py:137,142`),
      así que la afirmación de la documentación del PR sobre el refresh es cierta.
- [x] Retirar la invalidación de sesiones al cambiar de rol respeta RF-06: su lista de
      invalidación es solo INACTIVO / BLOQUEADO / ELIMINADO. El rol nunca estuvo ahí.
- [x] Las tres guardas de `editar_perfil_use_case.py` siguen intactas — el PR solo toca las
      líneas 276-278: autoedición de rol bloqueada (`:138`), el rol debe existir (`:149`),
      protección del último usuario activo de un rol protegido (`:251`).
- [x] `rol_modificado` se sigue usando en `:136`, `:194`, `:252`. No queda variable muerta.
- [x] Ninguna prueba unitaria usa `TestClient` ni `dependency_overrides`, así que la query
      nueva de `get_current_user` solo afecta a las de integración, que sí insertan filas
      reales de usuario vía `crear_usuario_db`.
- [x] **No hace falta ningún cambio de base de datos.** Sin DDL, sin DML, sin Alembic. El
      arreglo solo cambia de dónde se lee un dato que ya existía.

## Riesgos detectados en el PR — todos resueltos

Los tres se cerraron encima del merge, en la misma rama de revisión.

- [x] **Query extra por request autenticado.** El PR añadía un `SELECT usuarios.id_rol`
      además del `SELECT` de `cuentas_usuarios` que ya hacía `get_current_user`.
      **Resuelto**: ambas se fusionaron en una sola consulta con `outerjoin`. Medido con un
      listener de `before_cursor_execute`: el request pasó de **6 a 5 SELECT**, y dentro de
      `get_current_user` de **3 a 2**. El PR ya no añade ninguna consulta respecto a `dev`.
- [x] **Código de error nuevo `USUARIO_SESION_INVALIDO` (401)**, no contemplado en los flujos
      alternos del RF. **Resuelto**: se reutiliza `TOKEN_REVOCADO`, que ya existía y describe
      el mismo hecho desde el punto de vista del cliente (la sesión no vale). Cero contrato
      nuevo.
- [x] **Faltaba el chequeo de estado de cuenta.** RF-04 restringe: *"Los permisos asociados a
      un rol solo serán efectivos para usuarios que se encuentren en estado activo dentro del
      sistema."* No estaba implementado en ningún sitio.
      **Resuelto**: el gate va en `require_permission` (`src/shared/rbac.py`), **no** en
      `get_current_user`. Esa ubicación es la que dice el RF ("los *permisos* solo serán
      efectivos") y es la única que no rompe el alta por SSO: una cuenta `PENDIENTE_DATOS`
      tiene que poder autenticarse para completar su perfil por `PATCH /usuarios/me`, que no
      pasa por RBAC. El estado viaja en `UsuarioActual`, ya resuelto por `get_current_user`,
      así que el gate **no cuesta ninguna consulta adicional**.

### Gap adicional encontrado y cerrado

- [x] **Bloquear una cuenta por intentos fallidos no invalidaba sus tokens.**
      `login_use_case.py` hacía `cuenta.bloquear()` y confiaba en el trigger de BD, pero
      `trg_invalidar_sesiones_por_estado` **solo** marca `sesiones.es_activa = FALSE` y no
      toca `tokens.fecha_uso`, que es contra lo que valida `get_current_user`.
      Resultado medido sin el arreglo: la cuenta queda `"estado_cuenta":"Bloqueado"` y
      `GET /usuarios/me` sigue devolviendo **200** con todos los datos del usuario.
      **Resuelto**: `login_use_case` llama `invalidar_todas_sesiones()` antes de guardar la
      cuenta, mismo patrón y mismo orden que `gestionar_cuenta_use_case`. Ahora devuelve
      **401 TOKEN_REVOCADO**.
      Cubierto por `tests/integration/test_rf06_bloqueo_invalida_sesiones.py`, verificado que
      falla sin el arreglo.

Se revisaron todos los caminos que mutan el estado de una cuenta. El único roto era el del
login; `gestionar_cuenta_use_case` y `cambiar_estado_usuario_agrofusion_use_case` ya invalidaban.

---

## Conflicto de merge

La rama llegó 26 commits detrás de `dev`. Tres hunks, los tres se resuelven conservando
ambos lados.

- [x] `dependencies.py` (imports) — `dev` añadió `establecer_id_token`, el PR añadió
      `Usuarios`. Se conservan **los dos**.
- [x] `dependencies.py` (return) — `dev` añadió la llamada `establecer_id_token(id_token)`
      (auditoría RF-10), el PR reescribió el `return` con `id_rol_vigente`. Se conservan
      **la llamada y el return nuevo**.
- [x] `tests/integration/README.md` — por ir vieja, la rama reescribía la línea de RF-01 con
      la redacción anterior ("script SQL") pisando la de `dev` ("migración Alembic"), y
      reescribía la de RF-05/06 perdiendo el "autorizacion RBAC en router". Se conserva la
      redacción de `dev` y se añade solo la línea nueva de RF-04/06.
- [x] `anotaciones/modulo_1/estado_M01.md` auto-mergeado: verificado que solo cambian las
      secciones de RF-04; las ediciones de `dev` (RF-01, RF-12) quedan intactas.
- [x] `editar_perfil_use_case.py` auto-mergeado: conserva la validación de identificación de
      `dev` (`:315`) y aplica el cambio del PR (`:277`, solo `correo_modificado`).

---

## Verificación

- [x] Comprobar que la base `pruebas` tiene permisos distintos sembrados para los roles 2 y 3
      (el test de integración nuevo asierta `permisos_rol_nuevo != permisos_rol_anterior`).
      En `sgpmp` difieren: 45 vs 63 permisos activos.
- [x] Suite unitaria — **121 passed**, 0 fallos
- [x] Suite de integración contra `pruebas` — **77 passed, 7 skipped**, 0 fallos.
      Suite completa: **201 passed, 7 skipped**.
- [x] Comparar contra `origin/dev` limpio — 119 + 73, mismos 7 skips, 0 fallos. Los 7 skips
      son de módulo 9 (`pruebas` no tiene ese schema). Sin regresiones.
- [x] Prueba end-to-end con login real y `require_permission`: 403 → PATCH del rol → **200
      con el mismo JWT**. El mismo E2E contra `dev` falla con 401 TOKEN_REVOCADO.
- [x] Resolver los tres riesgos y volver a pasar las suites
- [x] Cerrar el gap del bloqueo por intentos fallidos, con test que falla sin el arreglo
- [x] Corregir el trigger de BD por migración Alembic y verificar el ida y vuelta
- [x] Medir la reducción de consultas con un listener de SQLAlchemy
- [x] Escribir `resumen.md`

---

## Estado del árbol

El merge queda **resuelto y stageado pero sin commit**, en la rama `review/pr50-rf04-rf06`.
Nada se ha pusheado. `dev` no se tocó.

---

## Trigger de BD corregido (migración Alembic)

- [x] `trg_fn_invalidar_sesiones_por_estado` solo marcaba `sesiones.es_activa`, que la
      autenticación no mira. **Resuelto** con la migración `e8bb4f321a44`: ahora también
      marca `tokens.fecha_uso` (acceso y refresco) cuando el estado pasa a 3/4/5.
- [x] Acotado a los estados 3/4/5 a propósito, con test que lo fija: revocar en *cualquier*
      cambio de estado echaría de su sesión al usuario que acaba de activar su cuenta
      `PENDIENTE_DATOS` tras completar el perfil por SSO.
- [x] `upgrade` → `downgrade` → `upgrade` verificado contra `sgpmp`.
- [x] Aplicada a `sgpmp` (head `e8bb4f321a44`). En `pruebas` se aplicó el mismo DDL, generado
      en modo offline desde la propia migración, **sin** tocar `alembic_version`: esa base es
      solo-modulo1 y no puede correr las 13 migraciones pendientes (5 tocan `modulo9`).

---

## Hallazgo que queda abierto (preexistente, no de este PR)

