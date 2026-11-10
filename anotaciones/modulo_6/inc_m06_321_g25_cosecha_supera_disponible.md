# INC-M06-321-G25 — Se reconocía una cosecha mayor que lo que tenía el activo de consumo (RF-85)

**RF:** RF-85 v1.2 (restricción 2, paso 6). **Issue:** #1008.
**Estado:** corregido con pruebas unitarias. Sin cambios de BD ni de frontend.

## Causa

`ProcesarEventosM02UseCase._cosecha_consumo` calculaba `proporcion = min(1, cantidad / magnitud)`. Con 1.000,1 kg
sobre un activo de 1.000 kg (100,01 %), la proporción se recortaba a 1 sin aviso y el producto se reconocía con:
- `cantidad_cosechada` 1000.1;
- `valor_reduccion_activo` 18.800.000,00;
- `costo_venta_producto` 1.199,88, porque el costo total se repartía entre más kilos de los que había.

RF-85 R2 dice: «la reducción del valor del activo biológico debe ser proporcional a la cantidad cosechada; no se
admiten reducciones totales salvo que la cosecha equivalga a la totalidad del activo». Una cosecha mayor que el
activo no tiene una reducción válida.

## Corrección

Si `cantidad_cosechada > magnitud` del último cálculo del activo (después de remedirlo), el producto **no se
reconoce**:
- el evento queda `MEDICION_PENDIENTE`;
- se audita `RECONOCIMIENTO_PRODUCTO_PENDIENTE` (WARNING) con el mensaje «La cantidad cosechada (1000.1 kg) supera
  la cantidad disponible del activo TRU-007 (1000 kg). El producto no se reconoció: corrija la cantidad del evento
  productivo o el último pesaje del activo en Activos biológicos.»;
- no se escribe el producto ni la línea de asiento, y el activo no se reduce.

Hasta la cantidad disponible todo sigue igual. Exactamente lo disponible es la cosecha total de FA-4. El `min(1, …)`
se quita porque la proporción ya no puede pasar de 1.

## Decisiones

1. **El rechazo es en M06.** RF-43 (M02) solo exige cantidad mayor que 0 y no conoce la clasificación CONSUMO ni la
   magnitud valorada del activo. El evento productivo de M02 sigue siendo válido como registro de producción. Lo que
   no se hace es el reconocimiento contable.
2. **Sin tolerancia.** Se compara la cantidad del evento con la magnitud del activo a 4 decimales (`DECIMAL(18,4)`),
   en kg, la única unidad que admite la cosecha de consumo hoy.

## Verificación

`tests/financial_valuation/test_inc_m06_321_g25_cosecha_supera_disponible.py` (3 pruebas):
- 1.000,1 kg de 1.000 kg: pendiente con el mensaje, sin producto ni línea de asiento, aviso WARNING;
- 1.000 kg de 1.000 kg (100 %): se reconoce con proporción 1 y una reducción de 18.800.000;
- 999,9 kg: proporción 0,9999 y una reducción de 18.798.120.

Sin el cambio, la primera falla: el producto se reconocía.
