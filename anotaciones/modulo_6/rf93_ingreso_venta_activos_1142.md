# Ingreso por venta de activos biológicos en el estado de resultados (#1142, INC-M06-364-G71)

**Fecha:** 2026-11-15 · **RF:** RF-45 (M02), RF-93 (M06) · **Origen:** issue #1142 (TC-M06-G71, QA)

## Qué se hizo

En el estado de resultados de SGPMP, una venta aparecía solo como gasto (su valor en libros) y sin el ingreso, así
que una venta rentable se veía como pérdida. La contabilidad externa sí cuadraba, porque ahí entra la factura.

- **M02 · baja por venta (RF-45):** la baja guarda `valor_venta` (lo recibido) y `referencia_venta` (factura o
  remisión). Los dos son opcionales y solo se aceptan si `tipo_baja = venta`.
- **M06 · estado de resultados (RF-93):** componente nuevo de INGRESOS `ingresos_venta_activos` = suma de los
  valores de venta del período. Se presenta en bruto: el ingreso Y queda en ingresos y el valor en libros X sigue en
  «Valor en libros de activos vendidos» (gastos). El neto Y − X es la utilidad de la venta, o su pérdida.
- **Sin asiento por la venta:** la factura de venta se registra en la contabilidad externa (RFC-018), igual que los
  costos de mantenimiento que viajan como factura y que el estado toma de RF-90 y no de las líneas.
- El estado devuelve `ventas_sin_valor`: cuántas ventas del período no tienen valor (las registradas antes del
  campo), para avisar que su ingreso no aparece.
- La auditoría de la baja en M06 (`BAJA_ACTIVO_REGISTRADA`) y la bitácora de M02 (RF-52) guardan el valor de venta.

## Paso 0 · Base de datos

| Gap | Decisión | SQL |
|---|---|---|
| `modulo2.eventos_bajas` no guarda el precio de venta | Dos columnas que aceptan nulos (las bajas anteriores y las que no son venta no tienen valor) | Migración `b8a323f06e9b` |
| Integridad | `ck_evento_baja_valor_venta`: nulo, o mayor que 0 y solo en ventas. `ck_evento_baja_referencia_venta`: nula, o no vacía y solo en ventas | Misma migración |
| Datos existentes | Ninguno que migrar: la tabla es inmutable (triggers de UPDATE y DELETE) | — |
| Permisos | Los GRANT de `eventos_bajas` son de tabla: cubren las columnas nuevas | — |
| `estados_resultados_periodo` | Sin cambio: los componentes van en `json_componentes` (jsonb) | — |

RBAC: sin cambios (mismos endpoints y permisos).

## Archivos

- M02: `domain/entities/activo_biologico.py`, `infrastructure/models/evento_baja_model.py`,
  `infrastructure/repositories/evento_activo_repository.py`, `infrastructure/dto/registrar_evento_baja_dto.py`,
  `application/use_cases/gestion/registrar_evento_baja_use_case.py`, `infrastructure/schema/activo_biologico_schema.py`,
  `infrastructure/routers/activo_biologico_router.py`.
- M06: `domain/services/consolidacion.py`, `application/services/reportes.py`,
  `infrastructure/repositories/reporte_repository.py`, `infrastructure/adapters/evento_m02_adapter.py`,
  `application/use_cases/valoracion/procesar_eventos_m02_use_case.py`,
  `application/use_cases/reportes/exportar_reporte_use_case.py`.

## Decisiones

- **Bruto y no neto:** con `max(Y − X, 0)` (la propuesta del ticket) una venta con pérdida desaparecía, y sumando
  además X en gastos el valor en libros se contaba dos veces.
- **Fuente:** el valor llega en la misma consulta de líneas del estado (la línea de la baja apunta a su evento), así
  hereda los filtros de finca, especie y activo y la exclusión de activos del cierre.
- **Opcional en el backend:** el frontend que aún no envía el campo sigue registrando ventas, y el estado avisa con
  `ventas_sin_valor`. El formulario nuevo lo pide en las ventas.
- **Sacrificio:** no tiene valor de venta (sigue solo como valor en libros).

## Qué NO se hizo

- No se asienta el ingreso ni cambia el comprobante NIC 41, la exportación contable, la matriz ni la conciliación ¶50.
- No se toma el precio de una cotización (RF-COT). Queda como mejora: sugerirlo en el formulario.

## Verificación

Pruebas unitarias (`tests/financial_valuation/test_inc_m06_364_g71_ingreso_venta.py`), de integración
(`tests/integration/test_inc_m06_364_g71_ingreso_venta_integration.py`) y downgrade y upgrade de la migración en
un Postgres desechable. Las integraciones de M02 y M06 tienen los mismos fallos ambientales que `dev`.

## Requerimientos por actualizar (Análisis)

RF-45 (campos de la venta), RF-93 v1.3 (componente nuevo y presentación en bruto), nota a RFC-018 (la venta se
reporta, no se asienta) y TC-M06-G71 (criterio: ingreso Y, gasto X, neto Y − X).
