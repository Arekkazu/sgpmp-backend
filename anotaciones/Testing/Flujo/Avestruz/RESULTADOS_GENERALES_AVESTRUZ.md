# Resultados generales - pruebas del flujo de avestruz en DEV

Fecha: 2026-11-02/03 (hora local; el servidor ya estaba en el 3 de noviembre UTC). Ambiente: DEV (`https://api.inmero.co/api-sgpmp-dev`), sin sandbox. Finca de QA: **QA Pruebas Flujo (id 3)**; no se escribió en El rosal ni en La florida. Especie: **Avestruz Qa (id 7)**, creada para estas pruebas porque el avestruz no existía en DEV: grupo `ESPECIES_GRANDES` (propuesto, pendiente de confirmar por Desarrollo), `MODELO_ESPECIES_GRANDES`, paradigma INDIVIDUAL, densidad 0.02 (valor de prueba `[QA]`, no un dato real de la especie). Plan de origen: `planes_multiespecie/plan_E7_avestruz.md` y `datos_E7_avestruz.md`.

## 1. Resumen

| Bloque | Resultado |
|---|---|
| Capacidad, incluida la **multiespecie** con Bovino | 17 de 17 pasan |
| Lecturas en fronteras (temperatura corporal y frecuencia cardiaca, umbrales propios de QA) | 14 pasan y 8 informativas, 0 fallan |
| Ciclo de vida de alertas | 10 de 10 pasan |
| Calibración de visión (F9) y predicción (F10) | No ejecutadas |

## 2. Capacidad (área de 155 m², capacidad `floor(0.02 × 155 = 3.1)` = 3)

| Prueba | Resultado |
|---|---|
| Crear el área | 201, capacidad 3 |
| Animales 1, 2 y 3 (límite exacto) | 201 |
| Animal 4 | 422 `CAPACIDAD_EXCEDIDA` |
| Identificador repetido | 409 `IDENTIFICADOR_DUPLICADO` |
| Reducir a 150 m² (capacidad 3) / a 149.99 m² (capacidad 2) con 3 animales | 200 / 422 `CAPACIDAD_EXCEDIDA`; la superficie no cambia |
| Área con Avestruz + Ternero | 422 `GRUPOS_MANEJO_INCOMPATIBLES` |
| **Área de 150 m² con Avestruz (0.02) + Bovino (0.1)** | 201, capacidad **3** = `floor(MIN(0.02, 0.1) × 150)`; el bovino solo daría 15 |
| Mismas especies en orden inverso | 201, capacidad 3 |
| 3 animales en el área multiespecie / el cuarto | 201 / 422 `CAPACIDAD_EXCEDIDA` |

## 3. Lecturas en fronteras
La especie es nuestra, así que se le crearon dos umbrales de QA (no afectan a ninguna finca de la entrega): temperatura corporal 37-43 °C (normal 37-39.8, precaución 39.8-40.5, crítico 40.5-43) y frecuencia cardiaca 30-180 bpm (normal 30-100, precaución 100-140, crítico 140-180). Fixture propio: un animal, un dispositivo y dos sensores.

| Valor | Semáforo | Calidad | Alerta |
|---|---|---|---|
| Mínimo (37.0 °C, 30 bpm) y dentro de normal | VERDE | `LECTURA_VALIDA` | no |
| Frontera normal/precaución (39.8 °C, 100 bpm) | **VERDE** | `LECTURA_VALIDA` | no |
| Justo encima (39.81 °C, 100.01 bpm) | AMARILLO | `LECTURA_VALIDA` | no |
| Frontera precaución/crítico (40.5 °C, 140 bpm) | **AMARILLO** | `LECTURA_VALIDA` | no |
| Justo encima (40.51 °C, 140.01 bpm) | ROJO | `LECTURA_VALIDA` | sí, una CRITICO por sensor (283 y 284) |
| Máximo (43.0 °C, 180 bpm) | ROJO | `LECTURA_VALIDA` | no (misma alerta) |
| 36.99 y 43.01 °C; 29.99 y 180.01 bpm | AMARILLO | `FUERA_DE_RANGO` | no |

La regla de inclusividad es la misma que en el resto de especies: el límite superior pertenece a la banda de abajo. La alerta de frecuencia cardiaca quedó asociada a la lectura de 179.99 bpm y no a la primera crítica (la asociación lectura-alerta es asíncrona).

## 4. Ciclo de vida de alertas
Alertas 285 y 286, ambas CRITICO y ACTIVA al generarse. Mismas transiciones que en las demás especies; CERRADA, los retrocesos y un estado inventado dan 422 `TRANSICION_INVALIDA`, y un motivo de 501 caracteres da 400.

## 5. Datos que quedan en DEV
| Tipo | Ids | Estado |
|---|---|---|
| **Especie (catálogo global)** | 7 (Avestruz Qa) | **desactivada**, pero sigue apareciendo en el listado de especies marcada como `INACTIVA` |
| Umbrales de la especie 7 | 10 (temperatura corporal), 11 (frecuencia cardiaca) | desactivados |
| Áreas (finca 3) | 26, 27, 28, 29 | 26 a 28 desactivadas; **29 activa** (tiene dispositivos) |
| Animales | 43 a 50 | todos con baja |
| Dispositivos | 22, 23 | desactivados |
| Sensores | 46 a 49 | con calibración y asociación al área |
| Lecturas | 24 guardadas | 22 de fronteras y 2 del ciclo de alertas |
| Alertas | 283 y 284 (se vencerán solas), 285 (resuelta), 286 (descartada) | |

## 6. Pendiente
- Confirmar con Desarrollo el grupo de manejo del avestruz.
- Temperatura ambiental, humedad y frecuencia respiratoria (la especie de prueba no tiene umbrales para ellas).
- F9 (no hay cámara para esta especie) y F10 (`MODELO_ESPECIES_GRANDES` sin configuración del motor en DEV).

## 7. Archivos de esta carpeta
- `capacidad_avestruz_dev.py`, `fronteras_avestruz_dev.py` y `alertas_ciclo_avestruz_dev.py`, con sus `resultados_*_avestruz_finca3.json`.
- Para repetir: `QA_FINCA_ID=3 python3 <script> ...`. Los scripts se niegan a correr en las fincas 1 y 2. Los tokens no se guardan en los archivos.
