# INC-M02-59-G36 / RF-45 — enum del trigger de baja

## Gap confirmado en `sgpmp_dev`

`modulo2.trg_fn_baja_actualizar_cantidad_lote()` declaraba `v_tipo_activo`
como `modulo2.enum_activo_biologico_tipo`, cuyos valores son `POBLACIONAL` e
`INDIVIDUAL`, pero lo comparaba con `'poblacional'`. PostgreSQL abortaba
cualquier inserción en `modulo2.eventos_bajas` con
`InvalidTextRepresentation`, incluso para activos individuales.

El baseline contenía el mismo defecto en `trg_fn_baja_cantidad_valida()`. En
`sgpmp_dev` esta función previa ya usa `POBLACIONAL`, por lo que existe una
deriva parcial entre esa base y el baseline versionado.

## Corrección

La migración `c4e8f1a2b603` reemplaza ambas funciones conservando su
comportamiento y usa el literal válido `POBLACIONAL`. No se aplicó DDL
directamente sobre la base de desarrollo; el cambio queda versionado para
ejecutarse mediante Alembic con el usuario propietario de las funciones.

## Validación

`tests/integration/test_rf45_trigger_baja.py` cubre ambos caminos del trigger:

- una baja individual inserta su detalle sin intentar convertir un literal inválido;
- una baja poblacional descuenta la cantidad afectada del lote.

La validación manual sobre `sgpmp_dev` usa DDL y datos dentro de una única
transacción sin capacidad de `commit`; al terminar se revierte y una segunda
conexión verifica que no quedaron activos de prueba.
