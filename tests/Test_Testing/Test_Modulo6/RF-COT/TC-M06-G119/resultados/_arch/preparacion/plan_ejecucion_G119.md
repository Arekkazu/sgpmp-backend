# TC-M06-G119 — Plan de ejecución (pendiente de autorización)

## TC-M06-51 — Anulación (cotización 6)

1. Confirmar coordinación con G118 (activo 1571 / cotización 6).
2. Tras autorización expresa: `POST /finanzas/cotizaciones/6/anulacion` con body preparado.
3. Verificar estado `ANULADA`, motivo almacenado, evento `COTIZACION_ANULADA`.
4. Segundo intento (misma u otra version): esperar 422 `COTIZACION_NO_MODIFICABLE`.
5. Verificar activo 1571 sin cambio de estado/VR.

Estado preparación: apta=True

## TC-M06-52 — Vencimiento automático (cotización 7)

**CERRADO DOCUMENTALMENTE — APROBADO** (2026-11-13).

Evidencia: `resultados/ultima_evaluacion/evidencia_escenario_tc52_TC-M06-G119.json`.
No llamar `vencer()` ni reprocesar.

## Restricciones

- No alterar cotizaciones 4/5.
- No cerrar 220 / no reabrir 219.
- No SQL. No modificar backend.
