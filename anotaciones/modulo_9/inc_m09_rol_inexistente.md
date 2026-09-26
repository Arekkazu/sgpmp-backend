# INC-M09-29-G83 (#163) — Rol inexistente en el JWT

## Comportamiento real (confirmado en código)

El backend **no** usa el claim `rol` del JWT para autorizar. `get_current_user`
(`src/identity_access/infrastructure/dependencies.py`) resuelve el rol **vigente en la
base de datos** en cada request:

```python
fila = db.query(Usuarios.id_rol, CuentasUsuarios)...
id_rol_vigente, cuenta = fila
```

El claim `rol` se conserva en el JWT "por compatibilidad, pero no es autoridad para RBAC"
(comentario literal del código). Por eso mutar `rol` en el token no produce ningún efecto:
el sistema sigue leyendo `modulo1.usuarios.id_rol`.

Consecuencia para un rol que **no existe** (si llegara a presentarse):

- `require_permission` (`src/shared/rbac.py`) consulta `modulo1.permisos` con ese `id_rol`.
- Sin filas → `AuthorizationError` `ACCESO_DENEGADO` (HTTP 403).
- **Nunca** se conceden permisos por defecto ni permisos de otro rol: la compuerta es la
  tabla `permisos`, no la existencia del rol.

Esto es exactamente lo que pide el issue ("nunca conceder permisos por defecto o de un
rol diferente") y ya está garantizado por diseño.

## Restricción estructural que impide el escenario por la vía de BD

`modulo1.usuarios.id_rol` tiene la FK `fk_rol → modulo1.roles(id_rol)`. Un usuario cuyo
`id_rol` no exista en `roles` **no puede persistirse** (violación de FK), ni siquiera con
SQL directo sin desactivar temporalmente la constraint. Por eso el escenario "usuario con
rol inexistente" no es reproducible operando solo sobre datos reales.

## Mecanismo de prueba para TEST

Dos opciones, en orden de preferencia:

1. **Ignorar el claim `rol` del JWT (lo que QA ya puede hacer hoy).** Generar un token con
   un claim `rol` arbitrario/inexistente y comprobar que la autorización sigue siendo la
   del `id_rol` real de la BD: el token mutado no otorga ni revoca nada. Esto demuestra el
   punto sin tocar la base.

2. **Fixture de test que inyecta `UsuarioActual(id_rol=inexistente)`.** El test unitario
   `tests/identity_access/test_rf25_rol_inexistente_rbac.py` fija este contrato: con un
   `id_rol` sin filas en `permisos`, `require_permission` responde 403 `ACCESO_DENEGADO`.

## Cierre

Regresión agregada en `tests/identity_access/test_rf25_rol_inexistente_rbac.py` (2 casos).
No se requirió cambio de código: el comportamiento correcto ya estaba implementado.
