# TC-M09-G51 (TC-M09-102) — Permisos por rol sobre áreas productivas

**RF-20 v1.1 / CU-04 — Gestionar Infraestructura Productiva**

## Estado vigente — reevaluación 2026-10-06 (RF-20 v1.1, RFC-009)

**Resultado: PASA**: 48 requests, 83 assertions, 0 failed.

| Operación | Administrador | Productor | Ingeniero | Contador |
|---|---|---|---|---|
| Registrar | ✅ 201 | ⛔ 403 | ⛔ 403 | ⛔ 403 |
| Modificar | ✅ 200 | ⛔ 403 | ⛔ 403 | ⛔ 403 |
| Desactivar | ✅ 200 | ⛔ 403 | ⛔ 403 | ⛔ 403 |
| **Reactivar** (nueva en v1.1) | ✅ 200 | ⛔ 403 | ⛔ 403 | ⛔ 403 |
| Consultar listado | ✅ 200 | ✅ 200 | ✅ 200 | ⛔ 403 |
| Consultar detalle | ✅ 200 | ✅ 200 | ✅ 200 | ⛔ 403 |

Todos los 403 responden `ACCESO_DENEGADO`. Después de los intentos rechazados de cada rol, el
admin relee la finca y confirma que no tuvieron efecto: siguen existiendo solo las 2 áreas
creadas, el área activa sigue activa y sin editar, y la inactiva sigue inactiva.

Lo que exige la ficha, que el Productor reciba 403 en toda operación de escritura incluida la
reactivación, se cumple. Ingeniero y Contador se agregaron para cubrir "usuarios con diferentes
permisos"; sus resultados son los vigentes en `modulo1.permisos` de TEST.

Cambios en la colección (reescrita):
- La versión anterior editaba y desactivaba el área compartida `id_infraestructura=1`, usaba
  `tipo_area: "galpon"` (anterior al catálogo) y no incluía la reactivación. Además, para el
  admin solo comprobaba "no 403".
- Ahora cada rol no administrador recibe una finca propia, registrada por el admin con
  `id_usuario` = ese usuario (sale del `sub` del JWT), con un área activa y otra inactiva. Sin
  esa asignación, el detalle respondía 404 por alcance de finca (RF-25) y no se podía distinguir
  del RBAC. No se usa `PUT /usuarios/{id}/fincas` porque reemplaza la lista completa y le
  revocaría al usuario compartido sus otras fincas.
- El admin ejecuta la operación completa (201/200) en vez de solo "no 403".

Nota técnica: `PATCH /{id}/reactivar` usa el mismo permiso que desactivar (recurso 10, acción
D = 4). La exclusividad del Administrador depende de que ningún otro rol tenga la acción D sobre
`infraestructuras` en `modulo1.permisos`. Hoy se cumple, pero si se le diera "desactivar" a otro
rol también podría reactivar.

Evidencia: `Resultados/reporte-TC-M09-G51.html` (Newman htmlextra, 2026-10-06).
