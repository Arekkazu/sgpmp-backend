# Ids creados en DEV, finca El rosal (id 1), por las pruebas del bovino del 2026-11-02

Esta lista sustituye a los resultados y reportes de esas corridas, que se borraron de la carpeta. Sirve para pedir al DBA o a Desarrollo que eliminen estos registros: la API de DEV no tiene borrado (solo baja o desactivacion) y el area 12 no se puede desactivar mientras tenga dispositivos. DEV no tiene sandbox. Todo lo listado es nuevo; no se modifico ningun dato que ya existiera en la finca (Potrero 1 y 2, Corral 1, Estanque Checho, BOV-001-DEV y sus sensores solo se leyeron).

| Tipo | Ids | Estado actual |
|---|---|---|
| Areas (infraestructuras) | 9, 11, 12 | 9 y 11 desactivadas; **12 activa** (`QA-FLUJO-BOVINO-LECT-210356`) |
| Activos biologicos (animales) | 8, 9, 10, 11, 12, 13 | todos con evento de baja (tipo `perdida`) |
| Dispositivos IoT | 11, 12, 13 | desactivados (seriales `QA-BOV-LECT-210356`, `QA-BOV-LECT-210530` y `QA-BOV-ALR-…`) |
| Sensores | 21, 22, 23, 24, 25, 26 | `QA-TEMP-CORP-…` y `QA-FC-…`; los 21 y 22 sin especie compatible |
| Asociaciones sensor-area | 21 a 26 | sin desactivar (no hay endpoint) |
| Asociaciones sensor-animal | 11, 12, 13, 14 (inferidas) | inactivas |
| Calibraciones | 20 a 25 (las 24 y 25 son inferidas) | ganancia 1, offset 0 |
| Lecturas de telemetria | 24 en total: 22 en los sensores 23 y 24, y 2 en los sensores 25 y 26 | las 22 de los sensores 21 y 22 se rechazaron (401) y no se guardaron |
| Alertas | 105, 106 (VENCIDA), 109 (RESUELTA), 110 (DESCARTADA) | generadas por el sistema a partir de las lecturas |

Efectos asociados: eventos de auditoria de cada creacion y baja; notificaciones enviadas por las alertas criticas (campo `fecha_notificacion`); estadisticas del historial que cuentan esas lecturas.

Criterio de identificacion: los nombres y seriales empiezan por `QA-`; las areas, por `QA-FLUJO-BOVINO-`; los animales, por `QA-BOV-`.

Las pruebas se repitieron despues en la finca 3 (QA Pruebas Flujo), ver `REPORTE_repeticion_finca3.md`.
