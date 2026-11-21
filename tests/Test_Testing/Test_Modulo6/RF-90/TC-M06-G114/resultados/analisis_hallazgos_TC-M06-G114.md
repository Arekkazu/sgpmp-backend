# TC-M06-G114

No se consultó `GET /activos-biologicos/auditoria`. No se usó SQL local.

RF-90 es `POST /finanzas/costos`. RF-94 es `GET /finanzas/auditoria`, tabla `modulo6.auditorias_financieras`.
El evento de un registro exitoso es `COSTO_REGISTRADO`. `id_referencia` guarda el id del costo.

Costos leídos: 2. Eventos COSTO_REGISTRADO: 2. COSTO_CLASIFICADO: 0.
La comparación de la tabla es una lectura de datos ya existentes. No aprueba TC-M06-43.
Después del rechazo de monto 0, costos 2 y eventos 2.
Duplicados por referencia: ninguno. Costos sin evento: ninguno.
Costos cuya fecha no cae en el período guardado: 9, 8. La fecha es 2026-11-07 y el período 8 va del 2026-12-01 al 2026-12-31.
El evento repite ese período. El alta manual rechaza esa situación; el proceso de provisiones no lo comprueba.

