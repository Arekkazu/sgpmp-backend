# F8 - Ciclo de vida de alertas (RF-57) - Bovino en DEV

Ejecutada 2026-11-02T16:12:56 contra https://api.inmero.co/api-sgpmp-dev. Escribe en DEV (sin sandbox). Fixture propio en el area fija de QA 12; alertas generadas por lecturas criticas (41.0 C y 150 bpm) de sensores de QA.

| Id | Prueba | Esperado | HTTP | Error | Estado resultante | Resultado |
|---|---|---|---|---|---|---|
| E0 | Alertas generadas (A=109 FIEBRE/CRITICO, B=110 FIEBRE/CRITICO) | ACTIVA, CRITICO | - | - | ACTIVA / ACTIVA | PASA |
| L1 | ACTIVA -> CERRADA (estado que no existe) | 422 TRANSICION_INVALIDA, sigue ACTIVA | 422 | TRANSICION_INVALIDA | ACTIVA | PASA |
| L2 | ACTIVA -> EN_ATENCION | 200, fecha_atencion informada | 200 | - | EN_ATENCION | PASA |
| L3 | EN_ATENCION -> RESUELTA | 200, fecha_resolucion informada | 200 | - | RESUELTA | PASA |
| L4 | RESUELTA -> ACTIVA (retroceso) | rechazo 4xx, sigue RESUELTA | 422 | TRANSICION_INVALIDA | RESUELTA | PASA |
| L5 | RESUELTA -> EN_ATENCION | rechazo 4xx, sigue RESUELTA | 422 | TRANSICION_INVALIDA | RESUELTA | PASA |
| L6 | Motivo de 501 caracteres | 400/422 (maximo 500), sin cambio | 400 | VAL_ENTRADA | ACTIVA | PASA |
| L7 | ACTIVA -> DESCARTADA con motivo | 200, motivo_descarte informado | 200 | - | DESCARTADA | PASA |
| L8 | DESCARTADA -> ACTIVA (retroceso) | rechazo 4xx, sigue DESCARTADA | 422 | TRANSICION_INVALIDA | DESCARTADA | PASA |
| L9 | Estado inexistente | 400/422 | 422 | TRANSICION_INVALIDA | DESCARTADA | PASA |

## Hallazgos

1. Todas las transiciones validas funcionan (ACTIVA a EN_ATENCION a RESUELTA, y ACTIVA a DESCARTADA con motivo) y fijan fecha_atencion, fecha_resolucion y motivo_descarte. Los retrocesos, CERRADA y un estado inexistente se rechazan con 422 TRANSICION_INVALIDA; un motivo de 501 caracteres da 400.
2. **Una alerta sin atender vence sola a los 5 minutos** (fecha_vencimiento = generacion + 5 min) y pasa a VENCIDA, que es un estado terminal: toda transicion desde ahi da 422 TRANSICION_INVALIDA. Una primera corrida (resultados_alertas_ciclo_corrida1_INVALIDA.json) fallo por eso: las alertas 105 y 106 ya estaban VENCIDAS. Hay que recorrer el ciclo dentro de esos 5 minutos.
3. La alerta del bovino se genera como FIEBRE / CRITICO para temperatura corporal, y la frecuencia_evento sube cuando llegan nuevas lecturas criticas del mismo sensor (la alerta 105 llego a 3).
4. Limpieza: animal con baja, asociaciones inactivas y dispositivo desactivado. El area 12 sigue como area fija de QA.

Para repetir: python3 alertas_ciclo_bovino_dev.py <token_sesion> <env_broker> <salida.json> 12
