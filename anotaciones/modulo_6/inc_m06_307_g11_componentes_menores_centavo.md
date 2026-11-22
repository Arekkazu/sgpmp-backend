# INC-M06-307-G11 — Componentes menores a 0,01 descartaban la medición o el reconocimiento (RF-83, RF-82, RF-86)

**RF:** RF-83 (medición posterior), RF-82 (reconocimiento inicial), RF-86 (variaciones y líneas de asiento). **Issue:** #994.
**Estado:** corregido con pruebas unitarias. Sin cambios de BD.

## Causa

El cálculo (`calculos_valor_razonable`) y la medición (`mediciones_posteriores`) guardan 4 decimales; la
variación (`variaciones_valor_razonable`) y la línea (`lineas_asiento_nic41`) guardan 2, y RF-86 trunca
el valor de la línea. El backend usaba el valor **truncado** para decidir si había algo que registrar:

- **(a) Medición.** `Medidor.medir` declaraba `MEDICION_SIN_VARIACION` cuando los dos componentes truncaban
  a 0,00. Con precio 0,01/kg, 400 kg → 400,01 kg da +0,0001: no se creaba el cálculo ni la medición y
  el valor vigente quedaba en 4,0000 (esperado 4,0001; con 399,99 kg, 3,9999). Además, como la
  variación nunca se registraba, los cambios pequeños no se acumulaban en mediciones posteriores.
- **(b) Reconocimiento.** Con bruto 1.000,0000 y costos 999,9999 el neto es 0,0001. El hecho
  `RECONOCIMIENTO_NACIMIENTO` (también donación, traslado y el modelo de costo) iba a la línea con el
  valor sin truncar; PostgreSQL lo guarda como 0,00 y `ck_linea_asiento_nic41_valor_positivo`
  (`valor > 0`) respondía 400 `VALOR_NO_PERMITIDO`, revirtiendo el reconocimiento completo.

## Corrección

- `application/services/medidor.py`: "sin variación" se decide con los componentes de 4 decimales
  (CA-14: monto 0 = sin registro). Si hay variación, se registran el cálculo y la medición; un componente
  que trunca a 0,00 no crea variación ni línea, y queda en el payload de `MEDICION_POSTERIOR` como
  `componentes_sin_asiento`.
- `application/services/propuesta_reconocimiento.py`: `_hecho` trunca el valor de la línea a 2 decimales
  (RF-86) y no crea el hecho si queda en 0,00. El reconocimiento se registra con su valor de 4 decimales.

Las bajas (`BAJA_ACTIVO`) y los productos agrícolas (RF-85) ya omitían la línea con `if valor > 0`; el
criterio es el mismo.

## Decisiones

1. **Se omite también la variación, no solo la línea.** La variación guarda 2 decimales: 0,0001 quedaría
   como un registro `GANANCIA_…` de 0,00, que CA-14 descarta, y una variación sin línea aparecería como
   cadena incompleta en RF-91. La medición (4 decimales) conserva el monto exacto.
2. **El reconocimiento sin hecho queda sin par de cuentas** (`cuenta_debito`/`cuenta_credito` nulos), igual
   que una compra cuyo neto coincide con el costo. `chk_reconoc_cuentas_no_vacias` lo admite.
3. Los montos omitidos (< 0,01 por componente) no llegan al estado de resultados (RF-93), que suma
   variaciones de 2 decimales; RF-93 ya tolera ±0,01 entre fuentes.

## Verificación

- `tests/financial_valuation/test_inc_m06_307_g11_variacion_menor_centavo.py`: +0,0001 y −0,0001 crean
  cálculo y medición sin variación ni línea y el valor vigente avanza; variación 0 sigue siendo
  `MEDICION_SIN_VARIACION`; +0,01 sigue creando variación y línea; `_hecho` y los cuatro orígenes con
  neto o diferencia menor a 0,01 quedan sin línea.
- Escalas y CHECK consultados en `sgpmp_dev` (`information_schema.columns`, `pg_constraint`, trigger
  `tgr_m06_04_consistencia_medicion`, que no exige variaciones para una medición).
- No se hizo prueba de integración contra Postgres: M06 no tiene fixtures de activo, precio y finca con titular.
