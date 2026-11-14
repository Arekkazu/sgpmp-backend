# Resultados generales - pruebas del flujo de tortuga en DEV

Fecha: 2026-11-02 (hora local; el servidor ya estaba en el 3 de noviembre UTC). Ambiente: DEV (`https://api.inmero.co/api-sgpmp-dev`), sin sandbox. Finca de QA: **QA Pruebas Flujo (id 3)**; no se escribió en El rosal ni en La florida. Especie: **Tortuga Qa (id 6)**, creada para estas pruebas porque la tortuga no existía en DEV: grupo `ACUICULTURA` (propuesto, pendiente de confirmar por Desarrollo), `MODELO_ACUICULTURA`, paradigma POBLACIONAL, densidad 2 (valor de prueba `[QA]`, no un dato real de la especie). Plan de origen: `planes_multiespecie/plan_E5_tortuga.md` y `datos_E5_tortuga.md`.

## 1. Resumen

| Bloque | Resultado |
|---|---|
| Capacidad, incluida la **multiespecie** con Cachama | 14 de 14 pasan |
| Lecturas en fronteras (pH y oxígeno disuelto, umbrales propios de QA) | 14 pasan y 9 informativas, 0 fallan |
| Ciclo de vida de alertas | 10 de 10 pasan |
| Calibración de visión (F9) y predicción (F10) | No ejecutadas |

## 2. Capacidad (área de 5.05 m² tipo Estanque, capacidad `floor(2 × 5.05)` = 10)

| Prueba | Resultado |
|---|---|
| Crear el área | 201, capacidad 10 |
| Lote de 11 tortugas en el área vacía | 422 `CAPACIDAD_EXCEDIDA` |
| Lote de 9 y de 1 (total 10, límite exacto) | 201 |
| Tercer lote de 1 (total 11) | 422 `CAPACIDAD_EXCEDIDA` |
| Reducir a 5.0 m² / a 4.99 m² con 10 tortugas | 200 / 422 `CAPACIDAD_EXCEDIDA` |
| Área con Tortuga + Bovino | 422 `GRUPOS_MANEJO_INCOMPATIBLES` |
| **Área con Tortuga (2) + Cachama (5)** | 201, capacidad **10** = `floor(MIN(2, 5) × 5.05)`; la cachama sola daría 25 |
| Mismas especies en orden inverso | 201, capacidad 10: el orden no importa |
| Lote de 10 en el área multiespecie / una tortuga más | 201 / 422 `CAPACIDAD_EXCEDIDA` |

Es la primera prueba de la regla de la menor densidad (RF-20) en DEV.

## 3. Lecturas en fronteras
Como la especie es nuestra, se le crearon dos umbrales de QA (no afectan a ninguna finca de la entrega): pH 5-10 (crítico 5-6.5, normal 6.5-8.5, precaución 8.5-10) y oxígeno disuelto 0-15 mg/L (crítico 0-5, precaución 5-6, normal 6-15). Quedaron en `PENDIENTE` de sincronización porque la especie no tiene Gateway Edge. Fixture: un dispositivo y dos sensores, cada uno con su propio lote de 1 tortuga.

| Valor | Semáforo | Calidad |
|---|---|---|
| pH 5.0 (mínimo), 6.49 y **6.5** | ROJO | `LECTURA_VALIDA` |
| pH 6.51, 8.49 y **8.5** | VERDE | `LECTURA_VALIDA` |
| pH 8.51, 9.99 y 10.0 | AMARILLO | `LECTURA_VALIDA` |
| O₂ 0.0, 4.99 y **5.0** | ROJO | `LECTURA_VALIDA` |
| O₂ 5.01, 5.99 y **6.0** | AMARILLO | `LECTURA_VALIDA` |
| O₂ 6.01, 14.99 y 15.0 | VERDE | `LECTURA_VALIDA` |
| pH 4.99 y 10.01; O₂ 15.01 | AMARILLO | `FUERA_DE_RANGO` |
| O₂ 20.0 | **ROJO** | `FUERA_DE_RANGO` |
| O₂ 20.5 | - | rechazada 422 `ERROR_SENSOR` |

La regla de inclusividad se confirma con una banda crítica *baja*: el límite superior de cada banda pertenece a ella, es decir (inferior, superior] (6.5 de pH es ROJO; 5.0 de O₂ es ROJO; 6.0 de O₂ es AMARILLO).

## 4. Hallazgos para confirmar con Desarrollo
1. **El semáforo fuera de rango escala con la distancia:** el código aplica una tolerancia por defecto del 10 % del rango del umbral (RF-58). Dentro de esa tolerancia sale AMARILLO y más allá sale ROJO. Para el oxígeno (rango 15, tolerancia 1.5): 15.01 es AMARILLO y 20.0 es ROJO. Esto aclara la duda que dejé abierta en el bovino (ver nota allá). Falta confirmar que ese comportamiento es el previsto.
2. **Alertas según la variable:** el oxígeno en ROJO generó alerta (`RIESGO_HIDRICO`, CRITICO, alerta 277), pero **el pH en ROJO no generó ninguna** (3 lecturas ROJO). Puede ser que el pH solo alerte en la regla compuesta pH + oxígeno (RF-55), o que falte el tipo de alerta; hay que confirmarlo.
3. **Tolerancia no configurada:** los umbrales se crearon sin `tolerancia_semaforo` (queda el 10 % por defecto).
4. Las reglas de la cachama se repiten: un lote solo admite un sensor poblacional, y la temperatura del agua no se puede enviar (sin código de telemetría).

## 5. Ciclo de vida de alertas
Dos sensores de oxígeno (el pH no alerta) generaron las alertas 279 y 280, ambas CRITICO y ACTIVA. Mismas transiciones que en las demás especies: ACTIVA→EN_ATENCION→RESUELTA y ACTIVA→DESCARTADA con motivo funcionan; CERRADA, los retrocesos y un estado inventado dan 422 `TRANSICION_INVALIDA`; un motivo de 501 caracteres da 400.

## 6. Problema durante las pruebas
En la primera ejecución de capacidad, mi script quedó con la especie equivocada (usó la 1, Cachama) y por eso salieron falsos fallos; esa corrida se guardó como `resultados_capacidad_tortuga_finca3_corrida1_INVALIDA.json` y no cuenta. La limpieza sí corrió: lotes 32 a 35 con baja y área 21 desactivada.

## 7. Datos que quedan en DEV
| Tipo | Ids | Estado |
|---|---|---|
| **Especie (catálogo global)** | 6 (Tortuga Qa) | **desactivada**, pero sigue apareciendo en el listado de especies marcada como `INACTIVA` |
| Umbrales de la especie 6 | 8 (pH), 9 (oxígeno) | desactivados |
| Áreas (finca 3) | 21, 22, 23, 24, 25 | 21 a 24 desactivadas; **25 activa** (tiene dispositivos) |
| Lotes | 32 a 42 | todos con baja |
| Dispositivos | 20, 21 | desactivados |
| Sensores | 42 a 45 | con calibración y asociación al área |
| Lecturas | 24 guardadas | 22 de fronteras (la de O₂ 20.5 se rechazó) y 2 del ciclo de alertas |
| Alertas | 277 (activa), 279 (resuelta), 280 (descartada) | |

## 8. Pendiente
- Confirmar con Desarrollo el grupo de manejo de la tortuga.
- Temperatura del agua (sin código de telemetría) y temperatura ambiental/humedad (la especie no tiene umbrales para ellas).
- F9 (cámara de acuicultura en La florida) y F10 (`MODELO_ACUICULTURA` está configurado y solo se podría revisar en lectura).

## 9. Archivos de esta carpeta
- `capacidad_tortuga_dev.py`, `fronteras_tortuga_dev.py` y `alertas_ciclo_tortuga_dev.py`, con sus `resultados_*_tortuga_finca3.json`.
- Para repetir: `QA_FINCA_ID=3 python3 <script> ...`. Los scripts se niegan a correr en las fincas 1 y 2. Los tokens no se guardan en los archivos.
