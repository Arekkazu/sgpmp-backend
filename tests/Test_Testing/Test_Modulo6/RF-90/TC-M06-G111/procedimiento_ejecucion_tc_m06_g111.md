# Procedimiento TC-M06-G111

Ejecutor: `ejecutar_tc_m06_g111.py`.

## TC-M06-37

Registro de costo con fecha en periodo cerrado. Esperado: HTTP 422 `PERIODO_CONTABLE_CERRADO` sin persistencia.

Evidencia: `resultados/primera_evaluacion/` (2026-11-08).

## TC-M06-41

Datos aislados usados el 2026-11-10: NIT 900000002, periodo 219, activo 1568.

1. POST costo OTRO sin naturaleza → 201, `PENDIENTE_CLASIFICACION` (id 1690).
2. GET prevalidacion → `puede_cerrar: false`, `COSTOS_PENDIENTE_CLASIFICACION`.
3. POST cierre → 422 `CIERRE_BLOQUEADO`; periodo sigue ABIERTO.
4. POST clasificacion → 200 `MANTENIMIENTO`.
5. GET prevalidacion → `puede_cerrar: true`.
6. No ejecutar cierre definitivo (corresponde a G71).

Evidencia: `resultados/ultima_evaluacion/` (`*_periodo_219.*`).

## Publicacion

La estructura final solo conserva `primera_evaluacion/` y `ultima_evaluacion/` mas `comparacion_evaluaciones.html`.
