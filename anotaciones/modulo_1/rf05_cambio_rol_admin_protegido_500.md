# RF-05 — Cambiar el rol de un Administrador devolvía 500

## Síntoma
Un administrador edita a otro usuario con rol **Administrador** y le cambia el rol
(`PUT /usuarios/{id}`). La API respondía:

```
500 ERROR_INTERNO — "Error inesperado en base de datos"
```

El frontend mostraba un error genérico de base de datos que no explica qué pasó.

## Causa
`modulo1.trg_fn_proteger_reasignacion_rol_admin` impide cambiar el rol de un usuario
cuyo rol actual es protegido (`es_protegido = true`, es decir, Administrador). Lanza:

```
RAISE EXCEPTION 'PROTECTED_ADMIN: No se puede cambiar el rol del usuario porque su rol actual "%" es protegido.'
    USING ERRCODE = 'P0004';
```

psycopg2 trae `P0004` como `AssertFailure`, que SQLAlchemy envuelve en un `InternalError`
y no en un `IntegrityError`. `raise_from_db_error` no tenía mapeado ese SQLSTATE y lo
dejaba caer al 500 genérico.

## Arreglo
`src/shared/db_error_translator.py` traduce `P0004` por la etiqueta del mensaje, igual
que ya se hacía con `P0211`:

| Etiqueta | Error | HTTP | `error_code` |
|---|---|---|---|
| `PROTECTED_ADMIN` | `BusinessRuleError` | 422 | `ROL_ADMIN_PROTEGIDO` |
| `PROTECTED_ROLE` | `AuthorizationError` | 403 | `ROL_PROTEGIDO` (el mismo que ya usa `rol_repository`) |
| Cualquier otra | se mantiene 500 | | |

El `message` es el texto del trigger sin la etiqueta, por ejemplo:
*No se puede cambiar el rol del usuario porque su rol actual "Administrador" es protegido.*
El frontend no necesita cambios: si un `error_code` no está en su catálogo i18n, muestra
el `message` del backend.

El arreglo está en el traductor compartido, así que también cubre otros caminos que
disparan el mismo `PROTECTED_ADMIN`, como cambiar el estado de la cuenta de un
Administrador.

## Verificación
- `tests/shared/test_db_error_translator.py`: casos `PROTECTED_ADMIN` (rol y estado),
  `PROTECTED_ROLE` y etiqueta desconocida (sigue siendo 500).
- Trigger real: con un Postgres 17 desechable migrado a head, se hizo `UPDATE` del rol de
  un Administrador → `InternalError/AssertFailure P0004` → traducido a
  `BusinessRuleError 422 ROL_ADMIN_PROTEGIDO`.
- `tests/shared` + `tests/identity_access`: 323 pasan.

## Pendiente para Análisis (no se cambia en este arreglo)
El RF-05 permite que un administrador cambie el rol de otro usuario y solo prohíbe dos
casos: degradarse a sí mismo (restricción de autogestión) y dejar el sistema sin
administrador activo. El use case aplica esas dos reglas
(`RESTRICCION_AUTOEDICION_ADMIN`, `ULTIMO_ADMIN_PROTEGIDO`). El trigger es más estricto:
bloquea cambiar el rol de **cualquier** Administrador, aunque haya otros activos.

Hay que definir qué regla vale:
- **Si vale la del trigger:** el use case puede validarla antes de llegar a la BD.
- **Si vale la del RF:** el DBA debe relajar el trigger con una migración.

Mientras tanto, la regla que manda en la práctica es la de la base de datos, y ahora
el usuario ve su mensaje real.
