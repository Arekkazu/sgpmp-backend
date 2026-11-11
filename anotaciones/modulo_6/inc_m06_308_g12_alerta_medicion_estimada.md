# INC-M06-308-G12 — La medición estimada no alertaba al Contador (RF-83)

**RF:** RF-83 (restricción 3, FA-1 y salida 4). **Issue:** #995.
**Estado:** corregido con pruebas unitarias. Sin cambios de BD.

## Causa

RF-83 dice que sin precio de mercado vigente la medición usa el último precio conocido, se marca
`valor_estimado = true` "y genera una alerta al Contador para revisión"; la salida 4 nombra esa alerta
`MEDICION_PENDIENTE` ("identifica el activo y la fecha pendiente de resolución").

`Medidor.medir` registraba la medición estimada y el evento `MEDICION_CON_ESTIMACION` (WARNING), pero no
escribía `MEDICION_PENDIENTE` ni avisaba al Contador. La medición que quedaba pendiente (sin precio) sí
escribía `MEDICION_PENDIENTE` en RF-94, aunque su docstring decía "se alerta al Contador" y tampoco
avisaba. M06 solo notificaba el cierre y los vencimientos de precios.

## Corrección

- `application/services/medidor.py`:
  - Medición estimada: además de `MEDICION_CON_ESTIMACION`, escribe `MEDICION_PENDIENTE` (WARNING,
    `motivo = PRECIO_ESTIMADO`, `id_medicion`, `id_referencia` = la medición) y deja una alerta en cola.
  - Medición pendiente: mismo evento que antes, más la alerta en cola.
  - El medidor no hace `commit()`, así que no envía nada. `tomar_alertas()` entrega y vacía la cola.
- `procesar_eventos_m02_use_case.py`: tras el `commit()` de cada evento envía sus alertas con
  `a_contadores("ALERTA_FINANCIERA_NIC41", …, id_finca)`; si el evento se revierte, las descarta.
- `ejecutar_cierre_periodo_use_case.py`: envía las alertas del cierre después de su `commit()` y del aviso
  de cierre; si los pasos fallan, las descarta.
- `m06_factory.py`: el procesador de eventos recibe el notificador.

Mensaje al Contador (bandeja interna de M01, tipo `ALERTA_FINANCIERA_NIC41`, a los Contadores de la finca):
«El activo BOV-007 se midió el 2026-11-08 con un precio estimado porque la especie Bovino no tiene precio
de mercado vigente. Revise la medición y registre el precio vigente.»

## Decisiones

1. **Se registra `MEDICION_PENDIENTE` aunque la medición sí se hizo.** Es el nombre de la alerta en la
   salida 4 de RF-83 y lo que QA busca entre los eventos del activo. `motivo = PRECIO_ESTIMADO` e
   `id_medicion` lo distinguen de una medición que no se hizo.
2. **Una alerta por activo.** Un cierre con `incluir_activos_sin_precio = true` puede enviar varias.
   RF-83 FA-2 pide "una lista de activos MEDICION_PENDIENTE", que ya trae la respuesta del cierre.
3. El ingreso sin costo (`_nueva_base`) sigue escribiendo su `MEDICION_PENDIENTE` sin notificar; queda
   fuera de este issue.

## Verificación

- `tests/financial_valuation/test_inc_m06_308_g12_alerta_medicion_estimada.py`:
  - La medición estimada escribe `MEDICION_CON_ESTIMACION` y `MEDICION_PENDIENTE` y deja una alerta con
    el activo, la especie y la fecha.
  - Con precio vigente no hay alerta.
  - La medición pendiente alerta.
  - El procesador avisa después del `commit()` y no avisa si revierte.
- El paso de envío del cierre no tiene prueba propia (el caso de uso necesita muchos colaboradores).
- No se hizo prueba de integración contra Postgres. `ALERTA_FINANCIERA_NIC41` existe en
  `modulo1.tipos_eventos` de `sgpmp_dev` (id 40).
