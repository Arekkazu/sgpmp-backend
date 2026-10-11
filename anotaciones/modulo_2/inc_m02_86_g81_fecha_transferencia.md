# INC-M02-86-G81 — Fecha futura en transferencia interna

## Hallazgo

`RegistrarTransferenciaDTO` validaba E-10 mediante un `ValueError` de Pydantic.
El manejador global convertía ese `RequestValidationError` en
`400 / VAL_ENTRADA`, aunque RF-48 y el contrato del endpoint declaran 422.

## Corrección

La validación de fecha futura se trasladó a
`RegistrarTransferenciaUseCase`, donde se representa como
`BusinessRuleError` asociado a `fecha_transferencia`. De esta forma, el
endpoint responde `422 / FECHA_TRANSFERENCIA_FUTURA` con el mensaje funcional
de E-10 sin modificar el manejo de validaciones de los demás módulos.

## Validación

- `POST /activos-biologicos/{id_activo}/transferencias` responde 422 para una
  fecha cinco días posterior a la fecha actual.
- La respuesta conserva el campo `fecha_transferencia` y el mensaje de E-10.
- El rechazo ocurre antes de consultar repositorios o iniciar escrituras.
- Una fecha igual a la actual continúa por el flujo normal.
- Las 61 pruebas de `tests/biological_assets` pasan.
- Las 11 pruebas de los manejadores globales pasan.

## Base de datos

La validación contra `sgpmp_dev` se ejecutó con una transacción de solo lectura.
Los contadores de movimientos, historial de infraestructura, bitácora RF-48 y
activos biológicos permanecieron iguales antes y después. No se modificaron
datos ni se requiere migración de base de datos.
