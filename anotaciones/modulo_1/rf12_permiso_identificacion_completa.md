# RF-12 — Permiso para ver la identificación completa

## Verificación del gap

El 27 de agosto de 2026 se comprobó en `origin/dev`, en el historial remoto y
mediante una consulta de solo lectura a `sgpmp_dev` que no existía la combinación
RBAC necesaria. No se aplicaron cambios manuales a desarrollo.

El caso de uso ya consulta esta capacidad:

| Elemento | Valor |
|---|---:|
| Administrador | `id_rol = 1` |
| Usuarios | `id_recurso = 1` |
| Ejecutar | `id_accion = 5` (`E`) |

Los tres IDs se verifican contra sus catálogos antes de sembrar el permiso.

## Solución

La migración Alembic
`f2c84d91a6e7_rf12_permiso_identificacion_completa.py` inserta exclusivamente:

```text
admin_ejecutar_identificacion_completa
rol=1, recurso=1, acción=5, activo=true
```

La operación es idempotente: si la combinación ya está activa no la duplica; si
existe inactiva y no es un registro administrativo protegido, la reactiva. No
concede esta capacidad a Productor, Veterinario ni otros roles.

El `downgrade` conserva el registro. Esto es intencional porque los triggers
`trg_proteger_permisos_admin_delete` y
`trg_proteger_permisos_admin_update` definen los permisos `admin_*` como
permanentes e inmutables. Intentar eliminarlo o desactivarlo rompería una regla
de integridad vigente en la base.

## Aplicación

```bash
alembic upgrade head
```

## Verificación

```sql
SELECT
    p.id_permiso,
    p.nombre,
    r.nombre_rol,
    re.nombre_recurso,
    a.codigo,
    p.es_activo
FROM modulo1.permisos AS p
JOIN modulo1.roles AS r ON r.id_rol = p.id_rol
JOIN modulo1.recursos AS re ON re.id_recurso = p.id_recurso
JOIN modulo1.acciones AS a ON a.id_accion = p.id_accion
WHERE p.id_rol = 1
  AND p.id_recurso = 1
  AND p.id_accion = 5;
```

Debe retornar una sola fila activa. El Administrador verá la identificación
completa y los actores sin esa combinación seguirán recibiéndola enmascarada.

