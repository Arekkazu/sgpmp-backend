# Repeticion de las pruebas del bovino en la finca de QA (finca 3 - QA Pruebas Flujo)

Ejecutada el 2026-11-02 en DEV con el usuario majito231027@hotmail.com. Finca creada para esto: **QA Pruebas Flujo (id 3)**. Los scripts exigen QA_FINCA_ID y se niegan a escribir en las fincas 1 (El rosal) y 2 (La florida). Se comprobo despues que esas dos fincas no cambiaron.

| Bloque | Resultado | Archivo |
|---|---|---|
| Capacidad (area 13) | 11 de 11 pasan; limpieza completa (bajas y area desactivada) | resultados_capacidad_finca3.json |
| Lecturas en fronteras (area 14) | 22 lecturas aceptadas (201); 14 PASA y 8 informativas (fronteras y fuera de rango); 0 FALLA | resultados_fronteras_finca3.json |
| Ciclo de vida de alertas (alertas 143 y 144) | 10 de 10 pasan | resultados_alertas_ciclo_finca3.json |

## Comparacion con El rosal

Mismos resultados en los tres bloques. Las reglas observadas se repiten: capacidad floor(0.1 x superficie), 422 CAPACIDAD_EXCEDIDA al pasar el limite, limite superior de cada banda en la banda de abajo (39.5 y 120 VERDE; 40.0 y 140 AMARILLO), FUERA_DE_RANGO sin alerta y con semaforo AMARILLO, una sola alerta CRITICO por sensor, y el mismo ciclo de vida de alertas. Diferencia menor: la alerta de frecuencia cardiaca quedo asociada a la lectura de 160 bpm en lugar de la de 140.01 (la asociacion lectura-alerta es asincrona); la alerta si se genero con la primera lectura critica.

## Datos que quedan en la finca 3

| Tipo | Ids |
|---|---|
| Finca | 3 (QA Pruebas Flujo) |
| Areas | 13 (desactivada), 14 (activa; tiene dispositivos) |
| Animales (con baja) | 14, 15, 16, 17, 18 |
| Dispositivos (desactivados) | 14, 15 |
| Sensores | 27 a 30 |
| Alertas | 141, 142, 143 (RESUELTA), 144 (DESCARTADA) |
| Lecturas | 24 |

Todo esta aislado de las fincas de la entrega. Una mejora respecto a El rosal: esta vez el script dio de baja los animales y desactivo el area 13 de forma automatica.

Para repetir: QA_FINCA_ID=3 python3 <script> <token_sesion> ... (ver el encabezado de cada script).
