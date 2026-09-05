# Gap Paso 0 — permisos de más en `usuarios` / acción `actualizar`

## Hallazgo

Durante la verificación del PR #16 (`feature/rf05-rf06-unified-rbac-account-profile`,
"RF-05/06: unificar autorización de perfil y gestión de cuenta") se encontró
que `PATCH /usuarios/{id_usuario}` — el endpoint administrativo que permite
editar a **cualquier** usuario, incluida la reasignación de rol — quedó
protegido con `require_permission(1, 3)` (recurso `usuarios`, acción
`actualizar`).

En la base de datos (`sgpmp`, ambiente de dev) ese permiso estaba concedido no
solo a Administrador sino también a Productor, Veterinario, Ingeniero de Campo
y Contador:

| id_permiso | nombre | id_rol | rol |
|---|---|---|---|
| 3  | admin_actualizar_usuario | 1 | Administrador |
| 38 | prod_actualizar_usuario  | 2 | Productor |
| 46 | vet_actualizar_usuario   | 3 | Veterinario |
| 54 | ing_actualizar_usuario   | 4 | Ingeniero de Campo |
| 66 | cont_actualizar_usuario  | 5 | Contador |

Antes del PR esto era inofensivo: el use case de edición validaba
`usuario_actual.id_rol == ROL_ADMINISTRADOR` a mano, sin depender del permiso
RBAC. El PR elimina justo esa validación (ese es su objetivo — mover la
autorización al router), por lo que al fusionarlo tal cual, cualquier usuario
con rol Productor/Veterinario/Ingeniero de Campo/Contador podía editar a
cualquier otro usuario y **reasignarle el rol**, incluido promoverlo a
Administrador. Verificado en vivo contra la base `pruebas` (transacción de
prueba, revertida): un usuario Productor promovió a otro usuario a
Administrador vía `PATCH /usuarios/{id}` con respuesta `200`.

Los 4 permisos de más probablemente eran un residuo de un diseño anterior en
el que el mismo endpoint servía tanto la edición propia como la
administrativa, y el permiso recurso=1/acción=3 se usaba para autorizar la
autoedición. Ahora que la autoedición vive en `PATCH /usuarios/me` (sin
dependencia RBAC — solo requiere autenticación), ese permiso amplio quedó
obsoleto para los roles no administrativos.

## Corrección aplicada

Se retiraron los 4 permisos usando el use case real de la API
(`RetirarPermisoUseCase`, vía `DELETE /roles/{id_rol}/permisos/{id_permiso}`),
no `DELETE` manual, para conservar el registro de auditoría en
`modulo1.eventos` (tipo de evento 15, `REVOCACION_PERMISO`):

- rol 2 (Productor) → permiso 38
- rol 3 (Veterinario) → permiso 46
- rol 4 (Ingeniero de Campo) → permiso 54
- rol 5 (Contador) → permiso 66

Aplicado en `sgpmp` (dev) el 2026-08-15, actor `id_usuario=29`. Los eventos de
auditoría quedaron registrados como `id_evento` 891–894. También se aplicó el
mismo `DELETE` (vía SQL directo, al ser una base de pruebas desechable) en la
base local `pruebas` usada por la suite de integración.

Tras el retiro, solo Administrador conserva `admin_actualizar_usuario`
(recurso 1, acción 3). Se reverificó en vivo que Productor/Veterinario/
Ingeniero de Campo/Contador reciben `403 ACCESO_DENEGADO` al intentar
`PATCH /usuarios/{id}` de otro usuario.

No es un cambio gestionado por migraciones — es una fila de datos en
`modulo1.permisos`, igual que otros gaps de RBAC documentados en este módulo.

## Verificación

Reproducido con la suite de integración local (`TEST_DATABASE_URL` →
`pruebas`) usando los fixtures `client`/`crear_usuario_db`/`crear_auth_headers`
de `tests/integration/conftest.py`: antes del fix, un Productor obtenía `200`
y reasignaba el rol de otro usuario; después del fix, Productor/Veterinario/
Ingeniero de Campo/Contador obtienen `403 ACCESO_DENEGADO` en el mismo intento.
