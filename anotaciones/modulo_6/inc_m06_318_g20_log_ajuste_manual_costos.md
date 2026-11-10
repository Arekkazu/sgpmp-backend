# INC-M06-318-G20 — La sobrescritura manual de costos no dejaba log de auditoría (RF-84)

**RF:** RF-84 (restricción 5, salida 3, postcondición 3, CA-3). **Issue:** #1005.
**Estado:** corregido con pruebas unitarias y el insert verificado contra el esquema real. Sin migración.

## Causa

`AJUSTE_MANUAL_COSTOS_VENTA` está en `enum_auditoria_financiera_tipo_evento` y en el catálogo de la consulta
(`DESCRIPCIONES`), pero ningún código lo emitía. Al confirmar con comisiones manuales de 250.000 sobre 200.000
parametrizados (2 % de 10.000.000), el cálculo sí quedaba `MIXTO` con la justificación. Sin embargo, la auditoría
del activo solo traía `RECONOCIMIENTO_INICIAL`, sin ítem, valor original ni valor manual. Además, el valor
parametrizado que se reemplazaba no se conservaba en ningún lado: `costos_venta` lo descartaba.

## Corrección

- `domain/services/nic41.costos_venta`: `CostosVenta.originales` guarda, para cada componente MANUAL, el valor
  parametrizado que reemplazó (`None` si M09 no lo parametriza; `otros` nunca se parametriza).
- `Valorador.valorar` devuelve `ajustes_manuales` (`item`, `valor_original`, `valor_manual`), y la propuesta los
  conserva.
- `ConfirmarReconocimientoUseCase` registra, en la misma transacción del cálculo, un evento
  **`AJUSTE_MANUAL_COSTOS_VENTA`** (INFO) por componente sobrescrito:
  - `datos_nuevos`: `item`, `valor_original`, `metodo_original` (`PARAMETRIZADO` o `SIN_PARAMETRO`),
    `valor_manual`, `justificacion`, `id_calculo_valor_razonable`, `id_parametro_costo_venta`;
  - `datos_anteriores`: `{item, valor}` original;
  - `monto_afectado`: el valor manual; `id_referencia`: el cálculo;
  - Contador (`id_usuario`) y fecha: columnas del evento.

## Decisiones

1. **Un evento por ítem.** La salida 3 habla de «ítem modificado»; con varios ítems sobrescritos, cada uno queda
   consultable por separado.
2. **Las columnas `metodo_valoracion_*` quedan vacías.** Son del método de valoración (valor razonable / costo),
   no del método de costo; el método va en el payload.
3. **Solo en la confirmación del reconocimiento.** Es el único flujo que acepta costos manuales hoy.

## Verificación

`tests/financial_valuation/test_inc_m06_318_g20_log_ajuste_manual.py` (6 pruebas):
- originales en el dominio: con parámetro, sin parámetro y sin manuales;
- confirmación real con propuesta y valorador del caso del ticket: un evento con 200.000 → 250.000, la
  justificación, el Contador, el período y el cálculo;
- un evento por ítem (comisiones y otros);
- sin manuales, ningún evento de ajuste.

El insert del evento con `SqlAlchemyAuditoriaFinancieraRepository` se ejecutó contra una BD efímera con
`alembic upgrade head`: el enum se acepta, `datos_anteriores` se guarda y el trigger calcula el hash. La BD se
borró al terminar.
