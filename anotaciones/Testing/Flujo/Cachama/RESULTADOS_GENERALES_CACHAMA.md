# Resultados generales - pruebas del flujo de cachama en DEV

Fecha: 2026-11-02 (hora local; el servidor ya estaba en el 3 de noviembre UTC). Ambiente: DEV (`https://api.inmero.co/api-sgpmp-dev`), sin sandbox. Finca de QA: **QA Pruebas Flujo (id 3)**; no se escribió en El rosal ni en La florida. Especie: Cachama Blanca (id 1, `ACUICULTURA`, `MODELO_ACUICULTURA`, paradigma POBLACIONAL, densidad 5). Plan de origen: `planes_multiespecie/plan_E4_cachama.md` y `datos_E4_cachama.md`. Es la única especie poblacional de DEV con umbrales, por eso permite probar fronteras en este paradigma.

## 1. Resumen

| Bloque | Resultado |
|---|---|
| Capacidad (lotes con conteo) | 10 de 10 pasan |
| Lecturas en fronteras: temperatura ambiental y humedad | 14 PASA y 8 informativas, 0 fallan |
| Lecturas en fronteras: **temperatura del agua** | **No se pudo ejecutar**: la API rechaza la variable (404) |
| Ciclo de vida de alertas | 10 de 10 pasan |
| Calibración de visión (F9) y predicción (F10) | No ejecutadas |

## 2. Capacidad (área de 2.05 m² tipo Estanque, capacidad `floor(5 × 2.05)` = 10)

| Prueba | Resultado |
|---|---|
| Crear el área | 201, capacidad 10 |
| Lote de 11 peces en el área vacía | 422 `CAPACIDAD_EXCEDIDA` |
| Lote de 9 peces | 201 |
| Segundo lote de 1 pez (total 10, límite exacto) | 201 |
| Tercer lote de 1 pez (total 11) | 422 `CAPACIDAD_EXCEDIDA` |
| Reducir a 2.0 m² con 10 peces | 200 |
| Reducir a 1.99 m² (capacidad 9) con 10 peces | 422 `CAPACIDAD_EXCEDIDA`; la superficie no cambia |
| Área con Cachama + Bovino | 422 `GRUPOS_MANEJO_INCOMPATIBLES` |

## 3. Lecturas en fronteras (umbrales vigentes en DEV)

Fixture propio: un dispositivo y tres sensores, cada uno asociado a su propio lote de 1 pez (un lote solo admite un sensor poblacional). Umbrales leídos en vivo, sin crear ni modificar nada:

| Variable | Rango | Normal | Precaución | Crítico |
|---|---|---|---|---|
| Temperatura del agua (id 1) | 24-34 °C | 24-30 | 30-32 | 32-34 |
| Temperatura ambiental (id 9) | 18-40 °C | 18-32 | 32-35 | 35-40 |
| Humedad relativa (id 10) | 40-100 % | 40-70 | 70-80 | 80-100 |

Resultados para temperatura ambiental y humedad (22 lecturas enviadas, 21 guardadas):

| Valor | Semáforo | Calidad | Alerta |
|---|---|---|---|
| Debajo del mínimo (17.99 °C, 39.99 %) y encima del máximo de temperatura (40.01 °C) | AMARILLO | `FUERA_DE_RANGO` | no |
| Mínimo del umbral (18.0 °C, 40.0 %) | VERDE | `LECTURA_VALIDA` | no |
| Frontera normal/precaución (32.0 °C, 70.0 %) | **VERDE** | `LECTURA_VALIDA` | no |
| Justo encima (32.01 °C, 70.01 %) | AMARILLO | `LECTURA_VALIDA` | no |
| Frontera precaución/crítico (35.0 °C, 80.0 %) | **AMARILLO** | `LECTURA_VALIDA` | no |
| Justo encima (35.01 °C, 80.01 %) | ROJO | `LECTURA_VALIDA` | sí (una alerta CRITICO por sensor: 270 y 271) |
| Dentro de crítico y máximo (39.99 y 40.0 °C; 99.99 y 100.0 %) | ROJO | `LECTURA_VALIDA` | no (misma alerta) |
| Humedad 100.01 % | - | - | rechazada 422 `ERROR_SENSOR` (fuera del rango físico) |

La regla de inclusividad es la misma del bovino: el límite superior pertenece a la banda de abajo.

## 4. Hallazgo principal: la temperatura del agua no se puede enviar
- La temperatura del agua (id 1) tiene un umbral para Cachama, pero su variable no tiene `codigo_telemetria` en el catálogo. Los 11 envíos dieron **404 `VARIABLE_NO_ENCONTRADA`**, probando `TEMPERATURA_AGUA`, `Temperatura del agua` y `id_variable` = 1.
- Lo mismo ocurre con otras variables del catálogo sin código: amoniaco total, nitrito, salinidad y turbidez. Con ello, el principal parámetro de un estanque (y su umbral) no se puede alimentar por `POST /iot/telemetria`.
- Hay que confirmar con Desarrollo cuál es el código que debe enviar un sensor de temperatura del agua, o si falta asignárselo en el catálogo.
- Consecuencia para el plan: el sensor de temperatura del agua de `datos_E4_cachama.md` no se puede probar hoy; sí se pueden probar pH (`PH_AGUA`) y oxígeno disuelto (`OXIGENO_DISUELTO`), que tienen código pero no tienen umbral para Cachama en DEV.

## 5. Ciclo de vida de alertas
Alertas 272 (temperatura ambiental, 36 °C) y 273 (humedad, 90 %), ambas CRITICO y ACTIVA al generarse. Mismas transiciones que el bovino: ACTIVA→EN_ATENCION→RESUELTA y ACTIVA→DESCARTADA con motivo funcionan; CERRADA, los retrocesos y un estado inventado dan 422 `TRANSICION_INVALIDA`; un motivo de 501 caracteres da 400. Las alertas 270 y 271 (de las fronteras) quedaron ACTIVAS y vencerán solas.

## 6. Otras observaciones
- Los tres umbrales de Cachama están en `PENDIENTE` de sincronización con el Edge, no `APLICADA` (los del bovino sí estaban aplicados). El backend evaluó las lecturas y generó las alertas igualmente.
- Una lectura con valor dentro del rango físico pero fuera del umbral se guarda como `FUERA_DE_RANGO` y no genera alerta; fuera del rango físico se rechaza y no se guarda.

## 7. Datos que quedan en la finca 3 (QA Pruebas Flujo)
| Tipo | Ids | Estado |
|---|---|---|
| Áreas | 19, 20 | 19 desactivada; **20 activa** (tiene dispositivos) |
| Lotes de peces | 25, 26, 27, 28, 29, 30, 31 | todos con baja |
| Dispositivos | 18, 19 | desactivados |
| Sensores | 37 a 41 | con calibración y asociación al área |
| Lecturas | 23 guardadas | 21 de fronteras y 2 del ciclo de alertas |
| Alertas | 270, 271 (activas), 272 (resuelta), 273 (descartada) | |

## 8. Pendiente
- **Código de la temperatura del agua:** sin él no se pueden probar sus fronteras.
- **Umbrales de pH y oxígeno disuelto para Cachama:** no existen en DEV; el plan los prevé.
- **Capacidad multiespecie:** falta una segunda especie de `ACUICULTURA` (Tortuga no existe en DEV).
- **F9:** hay una cámara (`CAM-ACUI-001`) en La florida; **F10:** `MODELO_ACUICULTURA` está configurado (ventana de 5 minutos, `umbral_score_anomalia` 0.5) y solo se podría revisar en lectura.

## 9. Archivos de esta carpeta
- `capacidad_cachama_dev.py`, `fronteras_cachama_dev.py` y `alertas_ciclo_cachama_dev.py`, con sus `resultados_*_cachama_finca3.json`.
- Para repetir: `QA_FINCA_ID=3 python3 <script> ...`. Los scripts se niegan a correr en las fincas 1 y 2. Los tokens no se guardan en los archivos.
