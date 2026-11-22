# INC-M06-320-G24 — La cosecha del 100 % no dejaba el activo en cero ni iniciaba su baja (RF-85)

**RF:** RF-85 v1.2 (paso 6, FA-4, postcondiciones 2 y 6). **Issue:** #1007.
**Estado:** corregido con pruebas unitarias; SQL y adaptador verificados contra el esquema real. Sin migración.

## Causa

En `ProcesarEventosM02UseCase._cosecha_consumo`, con 1.000 kg cosechados de 1.000 kg, la proporción era 1 y el
producto quedaba con `valor_reduccion_activo` = 18.800.000,00. Pero:
- no se creaba ningún cálculo nuevo, así que el último cálculo (18.800.000,0000) seguía siendo el valor vigente del
  activo;
- solo se auditaba `MEDICION_PENDIENTE` «quedó cosechado completamente: registre su baja»;
- el activo seguía ACTIVO en M02;
- si después se registraba la baja, `_baja` volvía a asentar los 18.800.000 como `BAJA_ACTIVO`.

## Restricciones encontradas

- No se puede guardar un cálculo en cero: `calculos_valor_razonable` exige `valor_razonable_bruto > 0`.
- El catálogo de estados de M02 no tiene `COSECHADO_COMPLETAMENTE`, y la especificación de M02 (RF-45) tampoco.
  Agregarlo exige migración y un cambio en M02.

Decisión del equipo (2026-11-09): baja automática, sin migración.

## Corrección

1. **Valor en cero.** El producto ya enlaza el cálculo consumido (`id_calculo_valor_razonable`,
   `tipo = PRODUCTO_DE_CONSUMO`, `proporcion_cosechada = 1`). El fragmento `CONSUMIDO_POR_COSECHA`
   (`infrastructure/repositories/sql.py`) lo detecta:
   - `ultimo_calculo` devuelve `None` si el último cálculo fue consumido. El activo no tiene base: una medición o
     una baja posterior no vuelven a usar su valor. La baja que llega de M02 queda `SIN_EFECTO`, sin doble asiento.
   - `activos_valorados` muestra `valor_razonable_neto = 0` y `cosechado_completamente = true`.
   - Revelaciones (`datos_revelaciones`): `valor_inicio` y `valor_cierre` valen 0 desde la cosecha total.
2. **Auditoría.** `MEDICION_POSTERIOR` (INFO) con `estado_activo = COSECHADO_COMPLETAMENTE`, el valor anterior, el
   valor actual 0, la reducción y el cálculo consumido. Reemplaza la alerta «registre su baja».
3. **Baja en M02 (RF-45).** Después del commit de M06, `BajaActivoPort` (adaptador `BajaActivoM02Adapter`) ejecuta
   el mismo `RegistrarEventoBajaUseCase` del endpoint de M02, en una sesión aparte como usuario de servicio:
   - tipo `sacrificio`, el de la cosecha que consume el activo en el catálogo de RF-45;
   - fecha de la cosecha;
   - motivo «Cosechado completamente: la cosecha del AAAA-MM-DD consumió todo el activo.»;
   - el activo pasa a BAJA con las validaciones, la bitácora y los triggers de M02.

   Si M02 la rechaza (por ejemplo, porque ya estaba en baja), el reconocimiento queda y se audita
   `MEDICION_PENDIENTE` (WARNING) con el motivo, para que la registren a mano.

## Fuera de alcance

- El estado `COSECHADO_COMPLETAMENTE` en M02: el activo termina en BAJA, y la cosecha total queda en la auditoría
  de M06 y en el motivo de la baja.

## Verificación

`tests/financial_valuation/test_inc_m06_320_g24_cosecha_total.py` (4 pruebas):
- cosecha del 100 %: el producto enlaza el cálculo consumido, no queda base, se audita el activo en cero y la baja
  se pide después del commit;
- cosecha parcial (40 %): queda el 60 % como base y no se pide baja;
- M02 rechaza la baja: alerta al Contador en un segundo commit;
- baja posterior sin base: `SIN_EFECTO`, sin `BAJA_ACTIVO_REGISTRADA`.

Contra una BD efímera con `alembic upgrade head`:
- `ultimo_calculo` devuelve `None` para el activo cosechado al 100 % y la base para el parcial;
- `activos_valorados` y `datos_revelaciones` corren con el fragmento nuevo;
- el adaptador ejecutó el caso de uso real de M02 y devolvió su rechazo para un activo inexistente.

No se probó una baja exitosa de punta a punta: requiere un activo completo de M02 con su finca e infraestructura.
