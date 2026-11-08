# TC-M06-G90

No se usó SQL local. No se consultó la auditoría de M07 porque una consulta sin permiso escribe un evento.

POST /finanzas/cotizaciones no llama a asientos ni a AAEF. Sí guarda la cotización y COTIZACION_REGISTRADA.
Activo leído: {'id_activo_biologico': 943, 'estado': 'ACTIVO', 'especie': 'Bovino', 'valor_razonable_neto': '3015990.0000', 'fecha_calculo': '2026-11-07T20:16:42.872378Z', 'valorado_por_costo': False}. Cotizaciones existentes: 2. Eventos COTIZACION_REGISTRADA: 0. Líneas del período 8: 8.
TC-M06-50: BLOQUEADO. No hubo comparación posterior porque no hubo registro.
