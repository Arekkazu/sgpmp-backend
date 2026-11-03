# Resultados generales - pruebas del flujo de bovino en DEV

Fecha: 2026-11-02. Ambiente: DEV (`https://api.inmero.co/api-sgpmp-dev`), sin sandbox. Especie: Bovino (id 2, `ESPECIES_GRANDES`, `MODELO_ESPECIES_GRANDES`, densidad 0.1). Plan de origen: `planes_multiespecie/plan_E1_vaca.md` y `datos_E1_vaca.md`.

## 1. Resumen

| Bloque | Qué se probó | Finca | Resultado |
|---|---|---|---|
| Solo lectura | 43 verificaciones sobre el bovino de Potrero 1: telemetría, semáforo, estadísticas, alertas y dashboard | El rosal (1) | 36 pasan, 0 fallan, 11 informativas |
| Capacidad | Área de 35 m² (capacidad 3), cargas de 1 a 4 animales, identificador repetido, reducción de superficie, grupos incompatibles | El rosal (1) y QA Pruebas Flujo (3) | 11 de 11 en ambas |
| Lecturas en fronteras | 22 lecturas sobre los límites de los umbrales de temperatura corporal y frecuencia cardiaca | El rosal (1) y QA Pruebas Flujo (3) | Sin contradicciones en ambas (14 pasan y 8 informativas; 0 fallan) |
| Ciclo de vida de alertas | Transiciones válidas e inválidas de las alertas | El rosal (1) y QA Pruebas Flujo (3) | 10 de 10 en ambas |
| Calibración de visión (F9) | No ejecutada | - | El Potrero no tiene cámara en DEV |
| Predicción (F10) | No ejecutada con escritura | - | `MODELO_ESPECIES_GRANDES` no tiene configuración del motor en DEV |

Las corridas con escritura se hicieron primero en El rosal. Como esa finca es la de la entrega, se repitieron en una finca nueva de QA (id 3) con otro usuario, y los resultados de El rosal se retiraron de la carpeta. Quedan como evidencia los de la finca 3.

## 2. Detalle por bloque

### 2.1 Solo lectura (Potrero 1, animal BOV-001-DEV)
- Dispositivo `PC-BOV-001` ACTIVO con último contacto de segundos. Es un simulador Edge, no una Raspberry física.
- Umbrales de DEV: temperatura corporal 38-43 °C (normal 38-39.5, precaución 39.5-40, crítico 40-43) y frecuencia cardiaca 40-160 bpm (normal 40-120, precaución 120-140, crítico 140-160), ambos `APLICADA`.
- 264 lecturas por sensor en el día, sin duplicados, en orden y sin huecos mayores de 10 min.
- El semáforo histórico coincide con la banda del umbral en todas las lecturas.
- Las alertas de nivel crítico tienen severidad CRITICO y el valor cae en la banda que dicen.

### 2.2 Capacidad (áreas de 35 m², capacidad `floor(0.1 × 35)` = 3)
| Prueba | Resultado |
|---|---|
| Crear el área | 201, capacidad 3 |
| Animales 1, 2 y 3 (límite exacto) | 201 |
| Animal 4 | 422 `CAPACIDAD_EXCEDIDA` |
| Identificador repetido | 409 `IDENTIFICADOR_DUPLICADO` |
| Reducir a 30 m² con 3 animales | 200 |
| Reducir a 29.99 m² con 3 animales | 422 `CAPACIDAD_EXCEDIDA`; la superficie no cambia |
| Área con Bovino y Ternero | 422 `GRUPOS_MANEJO_INCOMPATIBLES` |

### 2.3 Lecturas en fronteras (22 lecturas, todas aceptadas con 201)
| Valor | Semáforo | Calidad | Alerta |
|---|---|---|---|
| 37.99 °C y 43.01 °C; 39.99 y 160.01 bpm | AMARILLO | `FUERA_DE_RANGO` | no |
| 38.0 °C (mínimo) y 40 bpm | VERDE | `LECTURA_VALIDA` | no |
| 39.5 °C y 120 bpm (frontera normal/precaución) | VERDE | `LECTURA_VALIDA` | no |
| 40.0 °C y 140 bpm (frontera precaución/crítico) | AMARILLO | `LECTURA_VALIDA` | no |
| 39.51 °C y 120.01 bpm | AMARILLO | `LECTURA_VALIDA` | no |
| 40.01 °C y 140.01 bpm | ROJO | `LECTURA_VALIDA` | sí, una por sensor |
| 42.99 y 43.0 °C; 159.99 y 160 bpm | ROJO | `LECTURA_VALIDA` | no (misma alerta) |

### 2.4 Ciclo de vida de alertas
- ACTIVA a EN_ATENCION a RESUELTA: 200, con `fecha_atencion` y `fecha_resolucion`.
- ACTIVA a DESCARTADA con motivo: 200, con `motivo_descarte`.
- ACTIVA a CERRADA, los retrocesos (RESUELTA a ACTIVA o EN_ATENCION, DESCARTADA a ACTIVA) y un estado inventado: 422 `TRANSICION_INVALIDA`.
- Motivo de 501 caracteres: 400 `VAL_ENTRADA`.

## 3. Hallazgos para confirmar con Desarrollo
1. **Inclusividad de las fronteras:** el límite superior pertenece a la banda de abajo, es decir (inferior, superior], con el mínimo en la primera banda. El requisito no lo dice.
2. **Fuera de [min, max]:** se guarda como `FUERA_DE_RANGO` sin alerta (como pide TC-M03-016). Su semáforo es AMARILLO si queda dentro de la tolerancia de semáforo (por defecto el 10 % del rango del umbral, RF-58) y ROJO si se pasa de ella; en el bovino solo probamos valores a 0.01 del límite, por eso salieron AMARILLO. Se comprobó en la tortuga (oxígeno 15.01 AMARILLO y 20.0 ROJO). Falta confirmar con Desarrollo que ese es el comportamiento previsto.
3. **Alertas:** una alerta CRITICO por sensor; las lecturas críticas siguientes se suman a `frecuencia_evento` (ventana de 30 min). Las lecturas en precaución no generan alerta.
4. **Vencimiento:** una alerta sin atender pasa sola a VENCIDA a los 5 minutos y es terminal. El ciclo debe recorrerse dentro de ese tiempo.
5. **401 engañoso:** una captura con hora anterior a la asociación del sensor responde 401 `ERROR_AUTENTICACION` aunque el token sea válido.
6. **Requisitos de un sensor:** debe tener la especie en `especies-compatibles` (`PUT` con `ids_especies`), si no la asociación al animal da 400 `COMPATIBILIDAD_SENSOR_NO_CONFIGURADA`; y debe estar calibrado, si no las lecturas quedan `ERROR_CALIBRACION` con `valor_ajustado` vacío.
7. **`pct_fuera_rango`:** la API cuenta lo que queda fuera de la banda normal, no fuera de [min, max].
8. **Historial:** muestra la versión de umbral vigente, no la que regía al capturar. No está verificado.
9. **Asociación lectura-alerta:** es asíncrona; en una corrida la alerta de frecuencia cardiaca quedó ligada a la lectura de 160 bpm en lugar de la de 140.01.
10. **Umbrales que faltan para Bovino en DEV:** frecuencia respiratoria, actividad, temperatura ambiental y humedad. Por eso el semáforo de esos sensores y el estado general de Potrero 1 están en GRIS.
11. **Motor de IA:** `MODELO_ESPECIES_GRANDES` no tiene configuración (`CONFIGURACION_MOTOR_NO_ENCONTRADA`), aunque hay una inferencia de bovino en modo sombra.
12. **Lecturas `ERROR_CALIBRACION`:** cuatro al inicio del día en los sensores del simulador, y cuatro lecturas críticas anteriores a la última versión del umbral sin alerta. Parecen deberse a la calibración y a la versión del umbral de ese día.

## 4. Limitaciones de las pruebas
- DEV no tiene sandbox ni borrado por API: lo creado queda (con baja o desactivación).
- Capacidad multiespecie no probada: DEV no tiene otra especie `ESPECIES_GRANDES`.
- No se usó la Raspberry física (`RASPBERRY3B-TEST`, en el Estanque Checho de El rosal); el recorrido cubre broker y backend, no el firmware.
- La frecuencia respiratoria, la actividad, la temperatura ambiental y la humedad no se probaron con lecturas porque no tienen umbral para Bovino.

## 5. Datos que quedan en DEV
- **Finca 3 (QA Pruebas Flujo):** áreas 13 (desactivada) y 14 (activa), animales 14 a 18, dispositivos 14 y 15, sensores 27 a 30, alertas 141 a 144, 24 lecturas. Aislado de las fincas de la entrega.
- **El rosal (1):** lo creado en las primeras corridas sigue allí; ver `IDS_PRUEBAS_EL_ROSAL.md`. Requiere limpieza por parte del DBA o de Desarrollo. El área 12 sigue activa.

## 6. Archivos de esta carpeta
- Scripts: `capacidad_bovino_dev.py`, `fronteras_bovino_dev.py`, `alertas_ciclo_bovino_dev.py` y `verificar_vaca_dev.py` (solo lectura).
- Resultados: `resultados_capacidad_finca3.json`, `resultados_fronteras_finca3.json`, `resultados_alertas_ciclo_finca3.json` y `resultados_solo_lectura.json`.
- Reportes: `REPORTE_repeticion_finca3.md` y `REPORTE_vaca_dev_solo_lectura.md`.
- Lista de ids de El rosal: `IDS_PRUEBAS_EL_ROSAL.md`.

Para repetir las pruebas con escritura: `QA_FINCA_ID=<id de una finca de QA> python3 <script> ...`. Los scripts se niegan a correr en las fincas 1 y 2. Los tokens y contraseñas no se guardan en los archivos.
