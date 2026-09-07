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
