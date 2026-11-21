# Resultados generales - pruebas del flujo de cerdo en DEV

Fecha: 2026-11-02 (hora local; el servidor ya estaba en el 3 de noviembre UTC). Ambiente: DEV (`https://api.inmero.co/api-sgpmp-dev`), sin sandbox. Finca de QA: **QA Pruebas Flujo (id 3)**; no se escribió en El rosal ni en La florida. Especie: Porcino (id 4, `PORCINOS`, `MODELO_PORCINOS`, paradigma POBLACIONAL, densidad 1.0). Plan de origen: `planes_multiespecie/plan_E2_cerdo.md` y `datos_E2_cerdo.md`.

## 1. Resumen

| Bloque | Resultado |
|---|---|
| Capacidad (lotes con conteo) | 10 de 10 pasan |
| Lecturas en fronteras de umbral | **No ejecutadas**: Porcino no tiene ningún umbral en DEV |
| Lecturas sin umbral (opción elegida) | 14 aceptadas, 6 rechazadas por salirse del rango físico; sin alertas, semáforo GRIS |
| Ciclo de vida de alertas | **No ejecutado**: sin umbral no se generan alertas |
| Calibración de visión (F9) y predicción (F10) | No ejecutadas |

## 2. Capacidad (área de 10.5 m², capacidad `floor(1.0 × 10.5)` = 10)

El cerdo es poblacional: cada tanda es un lote con conteo, no un activo por animal.

| Prueba | Resultado |
|---|---|
| Crear el área | 201, capacidad 10 |
| Lote de 11 cerdos en el área vacía | 422 `CAPACIDAD_EXCEDIDA` |
| Lote de 9 cerdos | 201 |
| Segundo lote de 1 cerdo (total 10, límite exacto) | 201 |
| Tercer lote de 1 cerdo (total 11) | 422 `CAPACIDAD_EXCEDIDA` |
| Leer el área | capacidad 10 |
| Reducir a 10.0 m² con 10 cerdos | 200 |
| Reducir a 9.99 m² (capacidad 9) con 10 cerdos | 422 `CAPACIDAD_EXCEDIDA`; la superficie no cambia |
| Área con Porcino + Bovino | 422 `GRUPOS_MANEJO_INCOMPATIBLES` |

## 3. Comportamiento sin umbrales (Porcino)

Se creó un fixture propio (área 16, lote de 5 cerdos, dispositivo y tres sensores: temperatura ambiental, humedad y amoniaco) y se enviaron 20 lecturas con el token de servicio del broker.

| Hecho observado | Detalle |
|---|---|
| El semáforo es siempre GRIS | Los tres sensores salen con `sin_umbral=true`, sin importar el valor (por ejemplo 35 °C, 95 % de humedad o 40 ppm de NH₃) |
| No se genera ninguna alerta | Ni siquiera con valores extremos dentro del rango físico |
| El estado general de la unidad es GRIS | Por la misma razón |
| Los valores se guardan como `LECTURA_VALIDA` | Con `valor_ajustado` igual al valor |
| Rango físico (inclusivo) | Se acepta el valor en el límite y se rechaza apenas pasado: temperatura -50 y 100 °C (se rechazan -50.5 y 100.5); humedad 0 y 100 % (se rechazan -0.5 y 100.5); NH₃ 0 y 500 ppm (se rechaza -0.5 y 500.5) |
| Fuera del rango físico | 422 `ERROR_SENSOR` y la lectura **no se guarda** |

Diferencia con el bovino: allí una lectura fuera del umbral (pero dentro del rango físico) se guardaba como `FUERA_DE_RANGO`. Aquí, sin umbral, el único filtro es el rango físico de la variable y lo que lo excede se rechaza.

## 4. Hallazgos para confirmar con Desarrollo
1. **Un lote solo admite un sensor poblacional:** asociar un segundo sensor al mismo lote da 409 `ACTIVO_YA_TIENE_SENSOR_POBLACIONAL` ("El activo 21 ya tiene el sensor 31…"). Los otros dos sensores quedaron asociados al área pero no al lote, y aun así sus lecturas se aceptaron y aparecen en el historial como de un activo POBLACIONAL. Hay que confirmar si esa regla es la esperada (el plan de cerdo prevé varios sensores por área).
2. **Falta de umbrales:** Porcino, y también Pollo, no tienen ningún umbral en DEV. Sin ellos el flujo de monitoreo y alertas de esas especies no se puede probar.
3. **Tipos de área:** el catálogo no incluye «Porqueriza» (hay Corral, Estanque, Galpón, Invernadero, Potrero y otros), y el área existente de cerdos de La florida usa uno de esos tipos.
4. **Reglas ya vistas en el bovino que se repiten:** la baja de un lote completo se hace con `eventos/baja` sin `cantidad_afectada`; un área con dispositivos no se puede desactivar; las altas exigen `soporte_documental` si el origen es «compra»; y la fecha de la baja debe ser en UTC.

## 5. Datos que quedan en la finca 3 (QA Pruebas Flujo)
| Tipo | Ids | Estado |
|---|---|---|
| Áreas | 15, 16 | 15 desactivada; **16 activa** (tiene dispositivo) |
| Lotes de cerdos | 19, 20, 21 | todos con baja |
| Dispositivo | 16 | desactivado |
| Sensores | 31, 32, 33 | con calibración y asociación al área; el 31 estaba asociado al lote (inactivo) |
| Lecturas | 14 guardadas | las 6 fuera de rango físico se rechazaron |
| Alertas | ninguna | |

## 6. Pendiente
- **Umbrales de Porcino:** crearlos afecta a Porqueriza 1 (La florida), por eso no se hizo. Con ellos se podrían ejecutar las lecturas en fronteras y el ciclo de alertas.
- **Motor de IA:** `MODELO_PORCINOS` sí está configurado en DEV (ventana de 5 minutos, `umbral_score_anomalia` 0.5); F10 solo se podría revisar en lectura.
- **Calibración de visión (F9):** hay una cámara de porcinos (`CAM-PORC-001`) en La florida, finca que no usamos.
- **Capacidad multiespecie:** no probada; falta una segunda especie del grupo `PORCINOS` (en TEST existe `Marranos`, en DEV no).

## 7. Archivos de esta carpeta
- `capacidad_cerdo_dev.py` y `resultados_capacidad_cerdo_finca3.json`.
- `sin_umbral_cerdo_dev.py` y `resultados_sin_umbral_cerdo_finca3.json`.
- Para repetir: `QA_FINCA_ID=3 python3 <script> ...`. Los scripts se niegan a correr en las fincas 1 y 2. Los tokens no se guardan en los archivos.
