# INC-M09-G82 — control de acceso a fincas por contexto (RF-25)

Issue: #176
Endpoint afectado: `GET /configuracion/fincas` y `GET /configuracion/fincas/{id_finca}`

## Hallazgo reproducido

El router solo aplicaba `fincas.id_usuario` cuando `id_rol == 2`. Cualquier otro rol con
permiso `R`, incluido Ingeniero de Campo, enviaba `id_usuario_filtro=None` al caso de uso y
obtenía alcance global. La regresión reproduce el caso con la finca 19: antes del ajuste el
detalle respondía `200` y el listado incluía la finca ajena.

El Cypress entregado por pruebas confirma que `ingeniero@pecuaria.co` no tiene unidad
productiva asignada en la interfaz. Ese archivo no consulta directamente el endpoint de
fincas, por lo que se agregó cobertura HTTP específica para la autorización server-side.

## Corrección

- La lectura conserva el RBAC dinámico de RF-19: Veterinario e Ingeniero siguen teniendo
  acceso al endpoint cuando su rol posee el permiso `R`.
- Un rol de solo lectura queda limitado por `modulo9.fincas.id_usuario`, la misma relación
  usuario-finca usada por el contexto de RF-25.
- Un rol con permiso activo `U` sobre el recurso `fincas` conserva el alcance global de
  administración. La decisión se consulta en `modulo1.permisos`; no se usan IDs fijos de rol.
- El detalle de una finca existente fuera del contexto responde `403
  FINCA_NO_AUTORIZADA` y el cuerpo no contiene datos de la finca.
- Una finca inexistente conserva `404 FINCA_NO_ENCONTRADA` y un rol sin `R` conserva `403
  ACCESO_DENEGADO`.

No se requieren cambios de esquema ni migraciones.

## Validación

- Regresión previa: 3 fallos esperados (`200` en detalle ajeno, listado global para usuario
  sin finca y listado con finca ajena para usuario asignado).
- Pruebas de configuración: `226 passed`.
- Casos enfocados de RF-25/RBAC: `31 passed`.
- PostgreSQL real sobre una copia temporal actualizada a `a50010e91978`: `3 passed` para
  Ingeniero sin finca, Ingeniero con finca propia y Administrador con alcance global.

La copia temporal se eliminó después de ejecutar las pruebas. No se insertaron ni
modificaron datos en la base de desarrollo.

## Addendum — TC-M09-157-G82 (#305)

QA reabrió el mismo escenario desde pruebas funcionales (issue #305): no puede ejecutar
TC-M09-157 en el ambiente DEV compartido porque ningún usuario de prueba tiene finca
asignada (las fincas 1-6 pertenecen a usuarios sin credenciales de QA).

Re-verificado sobre `fix/m09` (rc.47, 2026-09-19): la corrección de este documento sigue
vigente en el código actual sin cambios adicionales.

- `src/configuration/infrastructure/routers/finca_router.py:44-57` resuelve el alcance de
  lectura (`_id_usuario_alcance_lectura`) vía `AlcanceFincaAdapter`, nunca con `id_rol`
  quemado.
- `src/shared/alcance_finca_adapter.py` decide alcance global vs. restringido consultando
  `modulo1.permisos` (`tiene_permiso` sobre `fincas`/actualizar/desactivar), no por catálogo
  fijo de roles.
- `src/configuration/application/use_cases/fincas/consultar_fincas_use_case.py:19-27`
  (`ConsultarFincasUseCase.obtener`) lanza `AuthorizationError(code="FINCA_NO_AUTORIZADA")`
  cuando `finca.id_usuario != id_usuario_filtro`.
- Regresión ya existente y en verde: `tests/integration/test_inc_m09_g82_acceso_finca_integration.py`
  (3 tests, PostgreSQL real) y `tests/configuration/test_inc_m09_g82_acceso_finca.py` (6 tests) —
  `9 passed` re-ejecutados en `fix/m09` el 2026-09-19.

No se modificó el ambiente DEV compartido ni se asignó una finca a ningún usuario existente
para esta verificación. Lo que bloquea TC-M09-157 en DEV es la falta de un usuario de prueba
con finca asignada, no el código: corresponde a QA/ops provisionar ese fixture (o una finca
de prueba dedicada) fuera de los datos de un usuario real.
