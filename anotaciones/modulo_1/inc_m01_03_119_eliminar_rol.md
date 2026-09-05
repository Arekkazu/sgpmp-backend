# INC-M01-03-119 — Eliminación de roles sin usuarios (RF-03)

## Incidente

`DELETE /roles/{id_rol}` devolvía `500` para cualquier rol no protegido creado
por el flujo normal. El rol y sus permisos permanecían en la base de datos.

## Causa raíz

Había dos defectos acumulados:

1. RF-03 obliga a crear cada rol con al menos un permiso, pero la FK
   `modulo1.permisos.id_rol -> modulo1.roles.id_rol` estaba configurada como
   `NO ACTION`. SQLAlchemy intentaba desvincular esos permisos y PostgreSQL
   rechazaba sus `id_rol=NULL`, produciendo el `500` observado.
2. El trigger `trg_fn_proteger_rol_admin()` retornaba `NEW` también para
   `DELETE`. En PostgreSQL `NEW` es `NULL` durante un borrado y retornar `NULL`
   desde un trigger `BEFORE DELETE` cancela silenciosamente la operación.

## Corrección

- Alembic `c4a19e7d2b63`: cambia exclusivamente esa FK a `ON DELETE CASCADE`.
- La misma migración corrige el trigger de protección para retornar `OLD` al
  borrar un rol no protegido, sin alterar sus bloqueos `P0004` de Administrador.
- El trigger de permiso mínimo sigue bloqueando retirar manualmente el último
  permiso (`P0006`), pero permite la eliminación causada por la desaparición
  del rol padre.
- El ORM usa `passive_deletes="all"` para delegar la cascada en PostgreSQL.
- Los triggers `P0004` (rol protegido) y `P0005` (rol con usuarios) no se
  modifican; `usuarios.id_rol` continúa con `NO ACTION`.
- Se traduce correctamente `P0004` a HTTP 403 y `P0005` a HTTP 422 incluso si
  aparecen por una carrera concurrente.

## Cobertura

- Rol no protegido, con permisos y sin usuarios: `200`; desaparecen padre e
  hijos y se registra el evento de auditoría tipo 13.
- Rol con usuarios: `422 ROL_EN_USO`; no se elimina nada.
- Rol protegido: `403 ROL_PROTEGIDO`; no se elimina nada.
- Eliminación directa del último permiso: continúa rechazada con `P0006`.

La base `sgpmp_dev` solo se consultó para confirmar FK, triggers y datos. No se
aplicó DDL ni DML en desarrollo durante el diagnóstico.
