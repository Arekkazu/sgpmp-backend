# INC-M06-310-G12 — MEDICION_CON_ESTIMACION no dejaba el motivo de la estimación (RF-83)

**RF:** RF-83 (FA-1, restricción 3) y RF-94. **Issue:** #997.
**Estado:** corregido con pruebas unitarias. Sin cambios de BD.

## Causa

El payload de `MEDICION_CON_ESTIMACION` traía `origen`, `valor_anterior`, `valor_actual`, `transformacion`
y `precio` (el efecto precio). No decía que no había precio vigente ni qué precio histórico se usó: eso
solo quedaba en `supuestos_aplicados` de `mediciones_posteriores`. La ficha pide el motivo en el registro
de auditoría.

**Hallazgo relacionado.** En el cierre con `incluir_activos_sin_precio = true`, el precio congelado puede ser
el último conocido, ya vencido. `Valorador.valorar` marcaba `tiene_valor_estimado` con un precio congelado
solo si su fuente era `ESTIMADA`. Ese caso se medía como `MEDICION_POSTERIOR` sin estimación, aunque RF-87
FA-2 dice «inclúyalos con el último precio conocido como estimación».

## Corrección

- `domain/services/precios.py`: `motivo_estimacion(precio, dia)` devuelve:
  - `SIN_PRECIO_VIGENTE` si el precio no está vigente ese día (se usó el último conocido);
  - `FUENTE_ESTIMADA` si el precio vigente es una estimación del Contador;
  - `None` en otro caso.
- `application/services/valorador.py`: con precio congelado, la medición es estimada si
  `motivo_estimacion` no es `None`. Sin precio congelado no cambia (`precio_para` ya lo resolvía así).
- `application/services/medidor.py`: el evento `MEDICION_CON_ESTIMACION` agrega:
  - `motivo_estimacion`;
  - `descripcion_motivo`, legible, ej.: «No había precio de mercado vigente para la especie Bovino el
    2026-11-08: se usó el último precio conocido, vigente desde el 2026-09-01.»;
  - `precio_usado`: id, precio unitario, unidad, fuente, vigencia y vencimiento.

  Se conservan los campos que ya traía. `MEDICION_POSTERIOR` no cambia.

## Efecto del hallazgo relacionado

Un cierre que incluye activos sin precio vigente ahora registra esas mediciones como estimadas:

- evento `MEDICION_CON_ESTIMACION` (WARNING) con su motivo;
- `tiene_valor_estimado` en el cálculo y la medición;
- `es_estimacion` en sus líneas de asiento.

## Verificación

- `tests/financial_valuation/test_inc_m06_310_g12_motivo_estimacion.py`:
  - `motivo_estimacion` en sus cuatro casos;
  - el evento con precio histórico trae motivo, descripción y precio usado, y conserva los campos previos;
  - con precio vigente de fuente `ESTIMADA` el motivo es `FUENTE_ESTIMADA`;
  - una medición no estimada no agrega motivo;
  - el valorador marca como estimado el precio congelado vencido.
- No se hizo prueba de integración contra Postgres.

## Relación con otros PR

Toca el mismo bloque de `medidor.py` que #994 (`componentes_sin_asiento` en `MEDICION_POSTERIOR`) y #995
(`MEDICION_PENDIENTE` tras la medición estimada). Al mergear se conservan las tres claves del payload y las
filas de la tabla de seguimiento.
