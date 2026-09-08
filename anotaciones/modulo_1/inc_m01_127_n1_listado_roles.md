# INC-M01-127 — N+1 en el listado de roles

Fecha: 2026-09-08 · Rama: `fixes-report`

## Qué pasaba

`GET /roles/` encadenaba una consulta de roles y, por cada rol, **una consulta
adicional** de permisos:

```python
roles = self.roles_repo.listar()                     # 1 query
return [
    {"rol": rol, "permisos": self.permisos_repo.listar_por_rol(rol.id_rol)}  # N queries
    for rol in roles
]
```

El endpoint hacía ~N+1 round-trips a la base de datos (con ~8 roles, ~9
consultas). Combinado con la latencia de red del entorno desplegado, `GET /roles/`
superaba el umbral de 200 ms que exige TC-M01-127.

## Qué se hizo

Se agregó al puerto `PermisoRepository` un método que agrupa los permisos de
varios roles en **una sola consulta**:

- `domain/repositories/permiso_repository.py` — `listar_por_roles(id_roles) -> dict[int, list[Permiso]]`.
- `infrastructure/repositories/permiso_repository.py` — implementación con
  `WHERE id_rol IN (...)` y `order_by(id_rol, id_recurso, id_accion)`.
- `application/use_cases/roles/listar_roles_use_case.py` — usa el método nuevo
  (2 consultas en total, independiente del número de roles).

## Pruebas

- `tests/identity_access/test_rf04_listar_roles_sin_n1.py` — verifica que el use
  case llama una sola vez a `listar_por_roles` (y nunca a `listar_por_rol`),
  pasando los ids en orden, y que agrupa los permisos por rol incluyendo el caso
  de rol sin permisos.

## Alcance

No se garantiza por sí solo quedar por debajo de 200 ms: parte de la latencia
medida en el entorno QA es tiempo de red del proxy (`sslip.io`). Esta mejora
elimina el factor que crece con el número de roles (el N+1), que era el único
margen de optimización de código.
