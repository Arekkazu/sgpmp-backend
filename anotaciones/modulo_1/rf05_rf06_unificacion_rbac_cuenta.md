# RF-05/06 — Unificación de RBAC y gestión de cuenta

## Hallazgo

`PATCH /usuarios/{id_usuario}` no tenía una dependencia RBAC y los casos de
uso de edición de perfil y gestión de cuenta decidían si el actor era
administrador comparando `id_rol == 1`.

Además, el estado de cuenta podía cambiarse tanto desde la edición de perfil
como desde `POST /usuarios/{id_usuario}/gestionar`. Solo el segundo flujo exigía
motivo para acciones críticas, protegía al último administrador activo y
registraba la operación en `gestiones_cuenta`.

## Decisión aplicada

- `PATCH /usuarios/me` edita exclusivamente el perfil propio y usa el DTO sin
  campos administrativos.
- `PATCH /usuarios/{id_usuario}` requiere `require_permission(1, 3)` y permite
  editar otro perfil y asignar un rol existente.
- `POST /usuarios/{id_usuario}/gestionar` conserva
  `require_permission(4, 3)` y es la única vía para activar, inactivar, bloquear
  o eliminar una cuenta.
- Los DTO de perfil rechazan campos adicionales; `id_estado_cuenta` ya no forma
  parte del contrato de edición.
- Los casos de uso no determinan acceso comparando el rol del actor. Reciben una
  operación que el router ya autorizó y conservan solamente reglas de negocio,
  como impedir la autoasignación de rol o la autogestión de estado.
- La protección del último administrador consulta el rol real del usuario y la
  marca `roles.es_protegido`. El conteo usa ese `id_rol` obtenido de base de
  datos; no existe un ID de administrador fijo en los casos de uso ni en el
  repositorio de cuentas.
- Al cambiar un rol se invalidan todas las sesiones del usuario afectado, porque
  el rol forma parte del JWT y los permisos nuevos deben aplicarse desde el
  siguiente inicio de sesión.

## Configuración RBAC requerida

La base de datos debe conceder al rol administrativo los permisos activos:

- recurso `1` (Usuarios), acción `3` (Actualizar);
- recurso `4` (Gestión de cuentas), acción `3` (Actualizar).

La aplicación consulta estos permisos en `modulo1.permisos`; no los inserta ni
los deduce por nombre de rol.
