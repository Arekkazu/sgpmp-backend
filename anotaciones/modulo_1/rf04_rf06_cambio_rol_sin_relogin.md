# RF-04/06 — Cambio de rol sin relogin

## Hallazgo confirmado

El access token conserva el claim `rol` con el valor existente durante el
login. `get_current_user` utilizaba ese valor como autoridad y la edición
administrativa invalidaba todas las sesiones al reasignar el rol. Por ello, el
usuario tenía que volver a iniciar sesión para obtener los permisos nuevos.

El sistema de refresh token ya está implementado, pero esperar a que el access
token expire tampoco cumple la aplicación inmediata exigida por RF-04/06.

## Solución aplicada

- El JWT continúa transportando `sub`, `jti` y `rol` para mantener compatibilidad.
- `sub` y `jti` siguen identificando al usuario y al token persistido.
- El claim `rol` deja de ser autoridad para RBAC.
- `get_current_user` consulta `modulo1.usuarios.id_rol` en cada request y entrega
  ese valor vigente a `require_permission` y a los casos de uso.
- Una reasignación de rol ya no revoca la sesión del usuario.
- El cambio de correo conserva la revocación de sesiones existente.
- Cuando el access token se renueva, `RefreshTokenUseCase` ya consulta el usuario
  en base de datos y emite el JWT nuevo con el rol actual.

No se requieren cambios de base de datos ni migraciones Alembic.

## Resultado

En el primer request posterior al commit del cambio de rol, RBAC consulta los
permisos del rol nuevo. Esto también retira inmediatamente los permisos del rol
anterior, sin esperar expiración, refresh, logout ni nuevo login.

