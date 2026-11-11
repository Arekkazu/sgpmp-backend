# INC-M06-325-G30 — El historial de productos agrícolas no cumplía RNF-85-05 (RF-85)

**RF:** RF-85 v1.2 (salida 1, RNF-85-03, RNF-85-05). **Issue:** #1012.
**Estado:** corregido con pruebas del contrato HTTP; SQL verificado contra el esquema real. Sin migración ni frontend.

## Causa

- `GET /finanzas/periodos/{id_periodo_contable}/productos`, la única consulta de productos, no declaraba ningún
  parámetro de consulta. No se podía filtrar por tipo de producto ni por rango de valores: solo por período (el
  listado) o por activo (el historial del activo).
- El listado no traía `id_evento_productivo` (salida 1 y RNF-85-03) ni el usuario.

RNF-85-05: «El historial completo de reconocimientos de productos agrícolas debe estar disponible para consulta (…)
con filtros por activo, período, tipo de producto y rango de valores».

## Corrección

- `SqlAlchemyValoracionRepository.productos_agricolas(filtros)` reemplaza a `productos_del_periodo`. Los filtros son
  `id_periodo_contable`, `id_activo_biologico`, `tipo`, `id_especie`, `producto_agricola`, `valor_min` y `valor_max`
  (sobre `valor_producto`). Se combinan con AND, uno omitido no filtra, y el resultado tiene un máximo de 500 filas,
  como en Costos.
- Cada registro agrega `id_evento_productivo`, `id_periodo_contable`, `id_usuario` y `nombre_usuario` (de
  `modulo1.usuarios`).
- `ConsultarProductosAgricolasUseCase` valida el rango: mínimo mayor que máximo responde 400
  `RANGO_VALOR_INVALIDO` (`field: valor_min`).
- Endpoints:
  - `GET /finanzas/periodos/{id}/productos`: el mismo listado del período, ahora con los filtros. La pantalla de
    Productos sigue funcionando igual.
  - `GET /finanzas/productos` (nuevo): el historial completo, con el período como filtro opcional.

  En los dos, los parámetros se validan en la consulta: `tipo` en `Literal[PRODUCTO_DE_CONSUMO, PRODUCTO_PERIODICO]`,
  ids `> 0`, valores `≥ 0` y numéricos. Un valor fuera del catálogo responde 400 `VAL_ENTRADA`.
- `id_especie` y `producto_agricola` se agregan porque la pantalla de Productos filtra por esos campos (regla de
  filtros completos del 2026-11-05).

## Fuera de alcance

`GET /finanzas/auditoria` (RF-94) no filtra por tipo de producto ni por valor. RNF-85-05 pide el historial de los
reconocimientos, que es la consulta corregida aquí. La auditoría es el registro de eventos de RF-94, y sus filtros
están definidos en ese requerimiento.

## Verificación

`tests/financial_valuation/test_inc_m06_325_g30_historial_productos.py` (8 pruebas):
- el listado del período pasa todos los filtros;
- historial sin período;
- 400 `VAL_ENTRADA` con un tipo fuera del catálogo, un valor negativo, un valor no numérico o un id 0;
- 400 `RANGO_VALOR_INVALIDO` con el rango invertido; un rango igual es válido.

Contra una BD efímera con `alembic upgrade head` y tres productos sembrados, cada filtro solo y combinado
devolvió las filas esperadas. El registro trae `id_evento_productivo`, `id_usuario` y `nombre_usuario`.
