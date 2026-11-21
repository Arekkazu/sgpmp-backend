# Resultados generales - pruebas del flujo de pollo en DEV

Fecha: 2026-11-02 (hora local; el servidor ya estaba en el 3 de noviembre UTC). Ambiente: DEV (`https://api.inmero.co/api-sgpmp-dev`), sin sandbox. Finca de QA: **QA Pruebas Flujo (id 3)**; no se escribió en El rosal ni en La florida. Especie: Pollo De Engorde (id 5, `AVES`, `MODELO_AVES`, paradigma POBLACIONAL, densidad 10). Plan de origen: `planes_multiespecie/plan_E3_pollo.md` y `datos_E3_pollo.md`. Las reglas generales del paradigma poblacional están explicadas en `../Cerdo/RESULTADOS_GENERALES_CERDO.md`.

## 1. Resumen

| Bloque | Resultado |
|---|---|
| Capacidad (lotes con conteo) | 10 de 10 pasan |
| Lecturas en fronteras de umbral | **No ejecutadas**: Pollo De Engorde no tiene ningún umbral en DEV |
| Lecturas sin umbral | 14 aceptadas, 6 rechazadas por salirse del rango físico; sin alertas, semáforo GRIS |
| Ciclo de vida de alertas | **No ejecutado**: sin umbral no se generan alertas |
| Calibración de visión (F9) y predicción (F10) | No ejecutadas |

## 2. Capacidad (área de 3.05 m², capacidad `floor(10 × 3.05)` = 30)

| Prueba | Resultado |
|---|---|
| Crear el área (tipo Galpón) | 201, capacidad 30 |
| Lote de 31 pollos en el área vacía | 422 `CAPACIDAD_EXCEDIDA` |
| Lote de 29 pollos | 201 |
| Segundo lote de 1 pollo (total 30, límite exacto) | 201 |
| Tercer lote de 1 pollo (total 31) | 422 `CAPACIDAD_EXCEDIDA` |
| Leer el área | capacidad 30 |
| Reducir a 3.0 m² con 30 pollos | 200 |
| Reducir a 2.99 m² (capacidad 29) con 30 pollos | 422 `CAPACIDAD_EXCEDIDA`; la superficie no cambia |
| Área con Pollo + Bovino | 422 `GRUPOS_MANEJO_INCOMPATIBLES` |

La limpieza automática funcionó completa (lotes con baja y área 17 desactivada).

## 3. Lecturas sin umbral
Fixture propio en el área 18: lote de 5 pollos, dispositivo y tres sensores (temperatura ambiental, humedad y amoniaco); 20 lecturas con el token del broker. Mismo comportamiento que el cerdo:

- Semáforo GRIS (`sin_umbral=true`) con cualquier valor; ninguna alerta; estado general de la unidad GRIS.
- Rango físico inclusivo: se aceptan −50 y 100 °C, 0 y 100 % de humedad, 0 y 500 ppm de NH₃. Se rechazan con 422 `ERROR_SENSOR` (y no se guardan) −50.5, 100.5, −0.5, 100.5, −0.5 y 500.5.
- Un lote solo admite un sensor poblacional: el segundo y el tercero dieron 409 `ACTIVO_YA_TIENE_SENSOR_POBLACIONAL`, igual que en el cerdo, así que la regla se confirma en otra especie.

## 4. Diferencias con el plan de pollo
- La densidad en DEV es 10, como en el plan, y la especie se llama «Pollo De Engorde».
- El plan prevé un sensor de CO₂, pero el catálogo de categorías de sensor (humedad, temperatura, oxígeno, pH, amoniaco, salinidad, luminosidad) no incluye CO₂, así que no se probó.
- La especie de apoyo del plan (Avicola) no existe en DEV, por lo que la capacidad multiespecie no se probó.

## 5. Datos que quedan en la finca 3 (QA Pruebas Flujo)
| Tipo | Ids | Estado |
|---|---|---|
| Áreas | 17, 18 | 17 desactivada; **18 activa** (tiene dispositivo) |
| Lotes de pollos | 22, 23, 24 | todos con baja |
| Dispositivo | 17 | desactivado |
| Sensores | 34, 35, 36 | con calibración y asociación al área |
| Lecturas | 14 guardadas | las 6 fuera de rango físico se rechazaron |
| Alertas | ninguna | |

## 6. Pendiente
- **Umbrales de Pollo:** crearlos afecta a Galpón 1 (La florida); por eso no se hizo. Con ellos se podrían ejecutar las fronteras y el ciclo de alertas.
- **Motor de IA:** `MODELO_AVES` sí está configurado en DEV (ventana de 12 minutos, `umbral_score_anomalia` 0.5).
- **Calibración de visión (F9):** hay una cámara de aves (`CAM-AVES-001`) en La florida.
- **CO₂:** falta una categoría de sensor para probarlo.

## 7. Archivos de esta carpeta
- `capacidad_pollo_dev.py` y `resultados_capacidad_pollo_finca3.json`.
- `sin_umbral_pollo_dev.py` y `resultados_sin_umbral_pollo_finca3.json`.
- Para repetir: `QA_FINCA_ID=3 python3 <script> ...`. Los scripts se niegan a correr en las fincas 1 y 2. Los tokens no se guardan en los archivos.
