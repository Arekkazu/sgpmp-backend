# RF-11 — Retiro de `GET /usuarios/` legacy

## Gap encontrado

El router exponía `GET /usuarios/` sin autenticación ni RBAC. La ruta consultaba
directamente el modelo ORM y respondía con `UsuarioResponse`, incluyendo número
de identificación, teléfono, dirección y género. Tampoco aplicaba paginación.

## Decisión

Se eliminó la ruta legacy en lugar de protegerla porque ya existe
`GET /usuarios/admin`, que implementa el contrato de RF-11:

- exige `require_permission(1, 2)`;
- pagina con un máximo de 50 elementos;
- admite filtros combinables;
- delega la consulta al caso de uso `ListarUsuariosUseCase`;
- devuelve únicamente nombre, correo, rol y estado de cuenta.

El registro público `POST /usuarios/` conserva la misma URL y no fue modificado.
El frontend ya consumía `/usuarios/admin`, por lo que no requiere cambios.

## Resultado esperado

- `GET /usuarios/` responde `405 Method Not Allowed` porque solo permanece el
  método `POST` sobre esa ruta.
- `GET /usuarios/admin` sin JWT responde `401`.
- Un usuario autenticado sin el permiso de lectura sobre Usuarios recibe `403`.
- Un usuario autorizado recibe el listado paginado y reducido definido por
  RF-11.
