# Lecturas en las fronteras de los umbrales - Bovino en DEV

Ejecutada 2026-11-02T16:06:10 contra https://api.inmero.co/api-sgpmp-dev. Escribe en DEV (sin sandbox). Fixture propio: area fija de QA id 12, dispositivo y sensores nuevos, animal nuevo; no toca PC-BOV-001. Lecturas enviadas por POST /iot/telemetria con el token de servicio del broker (no se guarda).

Umbrales de DEV (especie Bovino): temperatura corporal 38-43 C (normal 38-39.5, precaucion 39.5-40, critico 40-43); frecuencia cardiaca 40-160 bpm (normal 40-120, precaucion 120-140, critico 140-160).

| Sensor | Valor | Esperado | Semaforo | Calidad | Alerta | Resultado |
|---|---|---|---|---|---|---|
| QA-TEMP-CORP | 37.99 | fuera de [min,max] | AMARILLO | FUERA_DE_RANGO | - | INFO |
| QA-TEMP-CORP | 38.0 | normal -> VERDE | VERDE | LECTURA_VALIDA | - | PASA |
| QA-TEMP-CORP | 39.49 | normal -> VERDE | VERDE | LECTURA_VALIDA | - | PASA |
| QA-TEMP-CORP | 39.5 | frontera normal/precaucion (inclusividad no definida) | VERDE | LECTURA_VALIDA | - | INFO |
| QA-TEMP-CORP | 39.51 | precaucion -> AMARILLO | AMARILLO | LECTURA_VALIDA | - | PASA |
| QA-TEMP-CORP | 39.99 | precaucion -> AMARILLO | AMARILLO | LECTURA_VALIDA | - | PASA |
| QA-TEMP-CORP | 40.0 | frontera precaucion/critico (inclusividad no definida) | AMARILLO | LECTURA_VALIDA | - | INFO |
| QA-TEMP-CORP | 40.01 | critico -> ROJO | ROJO | LECTURA_VALIDA | 105 | PASA |
| QA-TEMP-CORP | 42.99 | critico -> ROJO | ROJO | LECTURA_VALIDA | - | PASA |
| QA-TEMP-CORP | 43.0 | critico -> ROJO | ROJO | LECTURA_VALIDA | - | PASA |
| QA-TEMP-CORP | 43.01 | fuera de [min,max] | AMARILLO | FUERA_DE_RANGO | - | INFO |
| QA-FC | 39.99 | fuera de [min,max] | AMARILLO | FUERA_DE_RANGO | - | INFO |
| QA-FC | 40 | normal -> VERDE | VERDE | LECTURA_VALIDA | - | PASA |
| QA-FC | 119.99 | normal -> VERDE | VERDE | LECTURA_VALIDA | - | PASA |
| QA-FC | 120 | frontera normal/precaucion (inclusividad no definida) | VERDE | LECTURA_VALIDA | - | INFO |
| QA-FC | 120.01 | precaucion -> AMARILLO | AMARILLO | LECTURA_VALIDA | - | PASA |
| QA-FC | 139.99 | precaucion -> AMARILLO | AMARILLO | LECTURA_VALIDA | - | PASA |
| QA-FC | 140 | frontera precaucion/critico (inclusividad no definida) | AMARILLO | LECTURA_VALIDA | - | INFO |
| QA-FC | 140.01 | critico -> ROJO | ROJO | LECTURA_VALIDA | 106 | PASA |
| QA-FC | 159.99 | critico -> ROJO | ROJO | LECTURA_VALIDA | - | PASA |
| QA-FC | 160 | critico -> ROJO | ROJO | LECTURA_VALIDA | - | PASA |
| QA-FC | 160.01 | fuera de [min,max] | AMARILLO | FUERA_DE_RANGO | - | INFO |

## Hallazgos

1. **Inclusividad de las fronteras (observada):** el limite superior pertenece a la banda de abajo. 39.5 es VERDE, 40.0 es AMARILLO, 120 es VERDE, 140 es AMARILLO. Los minimos (38.0 y 40) son VERDE y los maximos (43.0 y 160) son ROJO. Las bandas son (inferior, superior], con el valor minimo incluido en la primera. El requisito no lo dice: conviene confirmarlo con Desarrollo y dejarlo escrito.
2. **Fuera de [min, max]:** 37.99 y 43.01 C, 39.99 y 160.01 bpm quedan FUERA_DE_RANGO (se guardan, con valor ajustado) y sin alerta, de acuerdo con TC-M03-016. Su semaforo es AMARILLO, tambien por encima del maximo del umbral; hay que confirmar si deberia ser ROJO.
3. **Alertas:** solo se genero una alerta CRITICO por sensor (40.01 C -> alerta 105; 140.01 bpm -> alerta 106). Las lecturas criticas siguientes (42.99, 43.0, 159.99, 160) no crearon otra, lo que concuerda con la ventana de deduplicacion de 30 min. Las lecturas en precaucion (AMARILLO) no generan alerta.
4. **Contrato de ingesta:** una captura con hora anterior a la asociacion del sensor devuelve 401 ERROR_AUTENTICACION aunque el token sea valido (mensaje enganoso). El token de servicio del broker de DEV funciona.
5. **Limpieza:** la API no deja desactivar un area con un dispositivo, aunque este desactivado, y no permite moverlo ni borrarlo. El area 12 queda activa como area fija de QA, sin dispositivos ni animales activos.

Para repetir: python3 fronteras_bovino_dev.py <token_sesion> <env_broker> <salida.json> 12
