# INC-M06-326-G30 — La reducción del valor del activo de consumo no era acumulativa (RF-85)

**RF:** RF-85 v1.2 (CA-2, CA-6, postcondición 2), con RF-83. **Issue:** #1013.
**Estado:** corregido con pruebas y verificado contra el esquema real. Sin migración ni frontend.
**Rama apilada** sobre `fix/m06-inc321-g25-cosecha-supera-disponible` (#1008): el rechazo de la tercera cosecha es
la validación de ese PR.

## Causa

Caso: tres cosechas del mismo día de 400, 400 y 300 kg sobre un activo de 1.000 kg con valor neto de 18.800.000.
Las tres se reconocían, las reducciones sumaban 20.680.000 (más que el activo) y el activo quedaba en 13.160.000.

`_cosecha_consumo` vuelve a medir el activo antes de cada cosecha (RF-83). La magnitud sale del último pesaje de M02
(`DatosActivo.magnitud`), y M02 no baja el peso con las cosechas. Con eso:
- la proporción se calculaba siempre sobre 1.000 kg, así que las reducciones anteriores se perdían;
- la nueva medición comparaba 1.000 kg contra la base remanente (600 kg) y registraba una **ganancia falsa por
  transformación biológica**. Por eso el activo terminaba con 13.160.000.

## Corrección

La magnitud en kg del activo descuenta lo cosechado:
- `DatosActivo.kg_cosechados`: los kg reconocidos como `PRODUCTO_DE_CONSUMO` cuyo evento productivo es posterior al
  último pesaje (o todos, si no hay pesaje);
- `magnitud(PESO_KG) = max(0, peso × cabezas − kg_cosechados)`;
- `ActivoFinancieroM02Adapter` los suma con un `LATERAL` sobre `reconocimientos_productos_agricolas` y los eventos de
  M02. Un pesaje nuevo reinicia el descuento, porque ya mide lo que queda.

En el caso del ticket:

| Cosecha | Magnitud medida | Proporción | Reducción | Queda |
|---|---|---|---|---|
| 400 kg | 1.000 kg | 0,4 | 7.520.000 | 600 kg · 11.280.000 |
| 400 kg | 600 kg | 0,6667 | 7.520.000 | 200 kg · 3.760.000 |
| 300 kg | 200 kg | — | rechazada: «supera la cantidad disponible del activo (200 kg)» (#1008) | 200 kg · 3.760.000 |

Las reducciones suman 15.040.000, nunca más que el valor del activo, y no se registra ninguna variación por
transformación.

## Decisiones

1. **M06 no escribe el peso en M02.** El ticket menciona que M06 no actualiza el activo en M02, pero el peso de M02
   es el de RF-40 (pesajes): cambiarlo desde M06 inventaría un pesaje. M06 descuenta lo cosechado en su propia
   magnitud y el próximo pesaje de M02 trae el peso real.
2. **El descuento usa la cantidad cosechada en kg,** la única unidad que hoy admite la cosecha de consumo. Cuando se
   admitan otras unidades con conversión (RF-85 v1.2 C24.4), habrá que sumar la cantidad convertida.

## Verificación

`tests/financial_valuation/test_inc_m06_326_g30_reduccion_acumulativa.py`:
- `magnitud` descuenta lo cosechado y nunca es negativa;
- las tres cosechas del ticket, con `Medidor` y `Valorador` reales sobre un repositorio en memoria: 7.520.000 y
  7.520.000; la tercera queda pendiente con «300 kg … (200 kg)»; quedan 200 kg y 3.760.000, sin variaciones.

Sin el cambio, la prueba de las tres cosechas falla porque la tercera se reconocía.

El adaptador se probó contra una BD efímera con `alembic upgrade head`, con un pesaje de 1.000 kg y estas cosechas:
- una de consumo de 50 kg antes del pesaje (no cuenta);
- dos de consumo de 400 kg después (cuentan);
- una periódica (no cuenta).

Resultado: `kg_cosechados = 800` y magnitud de 200 kg. Con un pesaje nuevo de 210 kg, `kg_cosechados = 0` y la
magnitud vuelve a ser 210 kg.
