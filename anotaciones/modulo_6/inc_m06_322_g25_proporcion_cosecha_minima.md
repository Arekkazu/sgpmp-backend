# INC-M06-322-G25 — Una cantidad cosechada válida en M02 no se podía reconocer en M06 (RF-85)

**RF:** RF-85 v1.2 (paso 6), con RF-43 de M02. **Issue:** #1009.
**Estado:** parte (a) corregida con pruebas y verificada contra Postgres. Parte (b) fuera de este PR: es de M02 y
de su especificación. Sin migración.

## Parte (a): 0,001 kg terminaba en ERROR

M02 acepta 0,001 kg, el mínimo de RF-43 (`decimal(12,3)`). Sobre un activo de consumo de 1.000 kg la proporción es
0,000001. `_cosecha_consumo` la guardaba con `q4` (4 decimales), así que quedaba en 0,0000. La columna
`proporcion_cosechada` es `NUMERIC(8,6)`, pero `chk_prod_agricola_proporcion_rango` exige > 0, de modo que el
INSERT fallaba: `ValidationError`, el evento en ERROR y ningún producto.

**Corrección:** `nic41.proporcion_registrada` guarda la proporción a 6 decimales, la precisión de su columna:
- una cosecha positiva nunca se guarda en 0: por debajo de lo representable se registra 0,000001;
- una parcial nunca se redondea a 1, porque 1 marca la cosecha total (FA-4);
- el valor de la reducción se sigue calculando con la proporción exacta.

En el caso del ticket, la proporción queda en 0,000001 y la reducción en 18,80. Cumple
`chk_prod_agricola_valor_coherente`.

## Parte (b): precisión 3 frente a 4 decimales

RF-85 declara `cantidad_cosechada DECIMAL(18,4)` y la ficha de QA pide aceptar 0,0001. Pero M02 rechaza 0,0001 con
400 `VALOR_NO_PERMITIDO`, y 33,3333 kg se guarda como 33,333, porque RF-43 define `cantidad_producida decimal(12,3)`.
M06 recibe la cantidad de M02 y su columna ya admite 4 decimales, así que el límite está en la captura de M02.

Cambiarlo requiere una migración de la columna de M02, el ajuste de su DTO y validación, y una modificación de RF-43.
Corresponde a un RFC o a un issue de M02. Pendiente de decisión del equipo.

## Lo que no se reproduce desde el código

`provisiones_m05: ERROR 1` en la misma llamada no sale de este cambio. Cada provisión de M05 se procesa en su propia
transacción, después del procesamiento de eventos, que ya hizo rollback. Lo más probable es una provisión pendiente
en ese ambiente que falla por otra causa (queda en el log `M06: no se pudo procesar la provisión ...`) y, como no se
marca, se reintenta en cada corrida.

## Verificación

`tests/financial_valuation/test_inc_m06_322_g25_proporcion_cosecha_minima.py` (7 pruebas):
- `proporcion_registrada`: 0,000001; menor que lo representable da el mínimo; 6 decimales; 0,9999996 queda en
  0,999999; 1; 0;
- procesador: 0,001 kg sobre 1.000 kg queda `PROCESADO`, con proporción 0,000001, reducción y línea de 18,80 y el
  valor coherente.

Contra una BD efímera con `alembic upgrade head` (FK desactivadas solo para sembrar; los CHECK activos):
`agregar_producto` con la proporción vieja (0,0000) falla con `ValidationError` y con la nueva se guarda 0,000001.
