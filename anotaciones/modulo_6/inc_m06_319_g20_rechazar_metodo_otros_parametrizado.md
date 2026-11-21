# INC-M06-319-G20 — Marcar «otros costos» como PARAMETRIZADO se ignoraba en vez de rechazarse (RF-84)

**RF:** RF-84 v1.1 (entradas `metodo_costo_otros` = `ENUM (MANUAL)` y `otros_costos_disposicion`). **Issue:** #1006.
**Estado:** corregido con pruebas del contrato HTTP. Sin cambios de BD ni de frontend.

## Causa

`ConfirmarReconocimientoDTO` y `CostosManualesDTO` heredaban de `BaseDTO`, que ignora los campos desconocidos.
Enviar `metodo_costo_otros: "PARAMETRIZADO"` o `costos_manuales.metodo_otros: "PARAMETRIZADO"` respondía 201 y
reconocía el activo con neto 9.500.000, como si el campo no existiera.

La API no tiene un campo de método por componente: el método se deriva de los datos (`costos_venta` en
`domain/services/nic41.py`):
- un componente que viene en `costos_manuales` es MANUAL;
- uno que no viene usa el parámetro de M09;
- «otros» nunca se parametriza: sin valor manual vale 0.

Lo que el ticket confirma que ya funcionaba: «otros» sin justificación se rechaza (validador del DTO) y con
justificación se acepta como MANUAL.

## Corrección

`CostosManualesDTO` y `ConfirmarReconocimientoDTO` declaran `extra="forbid"`, igual que `CostoDTO` en el mismo
archivo (RF-90 CA-8). Un campo de método, o cualquier otro desconocido, responde **400 `VAL_ENTRADA`** con el campo
en `fields` (`metodo_costo_otros` o `costos_manuales.metodo_otros`) y el mensaje «Este campo no está permitido en esta
solicitud.». El activo no se reconoce.

## Decisiones

1. **Rechazar cualquier campo de método, también con MANUAL.** El método no es una entrada de la API, así que
   aceptarlo solo para validar que coincida agregaría un contrato nuevo sin necesidad.
2. **Rechazo en el DTO, no en el caso de uso.** Es un error de formato del cuerpo; el código existente ya traduce
   `extra_forbidden` a un mensaje legible.

## Impacto en el frontend

Ninguno. `finanzasApi.confirmar` envía solo `clasificacion`, `costos_manuales` (`transporte`, `comisiones`, `impuestos`,
`otros`) y `justificacion`. El PR de INC-M06-316-G16 agrega `referencia_documental` como campo declarado del DTO, así que
no lo afecta el `forbid`; al mergear hay que conservar ambos cambios.

## Verificación

`tests/financial_valuation/test_inc_m06_319_g20_metodo_otros.py` (6 pruebas):
- 400 con `metodo_costo_otros` arriba, con `costos_manuales.metodo_otros` y solo con el método;
- «otros» sin justificación, 400;
- «otros» con justificación, 201, y el componente queda MANUAL;
- sin costos manuales, «otros» no se deduce.

Sin el cambio fallan los 3 casos del ticket (respondían 201).
