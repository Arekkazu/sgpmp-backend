# TC-M03-G98 — preparación local de reevaluación V3

Orden vigente ORD-G98-015: la reevaluación V3 de TC-M03-191 queda preparada, sin RUN nuevo ni acceso a TEST. El lanzador debe solicitar `REEVALUAR`, versión 3, `version_anterior: 2` y guardar la evidencia en `EvaluacionV3/Resultados/RUN-G98-V3-<timestamp>/`, con un único `TC-M03-G98_reevaluacion_V3.md`. V2 conserva sus rutas y evidencias.

El oráculo de `minutos_transcurridos` usa el inicio registrado del RUN, un margen de 120 s y la cabecera Date de la respuesta o la hora del cliente al recibirla; admite un minuto de tolerancia en cada extremo. Exige un entero dentro de esa ventana y `fecha_generacion` no posterior a la respuesta más 60 s. Un minuto negativo por el `now()` fijo del sandbox queda aprobado con observación; valores fuera de ventana siguen rechazados. El ejecutor pasa `inicio_run` a Newman y aplica la misma fórmula al leer su reporte. El ensayo de loopback simula `now()` fijo. Ningún otro oráculo, canario E7, presupuesto de tres POST ni cierre cambia.

El RUN oficial V2 `RUN-G98-V2-20261031-183417` mostró total 3, orden y activo correctos; su único rechazo fue por el antiguo oráculo de tiempo. La lectura local de `src/telemetry/infrastructure/repositories/indicadores_alertas_repository.py:70` y `src/telemetry/application/use_cases/alertas/generar_alerta_use_case.py:110` explica el falso positivo. El informe V3 generado anula INC-M03-191-G98-02 como problema técnico QA y solo declara corregida INC-M03-191-G98-01 si V3 lo confirma oficialmente.

## Preparación histórica V2

Orden ORD-G98-008. Caso TC-M03-191, RF-58 CU04 Salida 2 y CA-11. Se preservan los RUN históricos de V1 y V2. Esta fase preparar no crea RUN ni consulta TEST.

**Resultado esperado literal:** «HTTP 200. Se devuelve el total de alertas activas y la lista ordenada por severidad con CRITICO primero, indicando tipo de alerta, variable afectada y tiempo transcurrido, con navegación al detalle del activo biológico afectado.» **Precondición literal:** «Alertas activas de severidad CRITICO, ALTA y MEDIA sobre distintos sensores de la misma unidad.» La decisión QA previa acepta la escala RF-57 CRITICO > MODERADO > LEVE. Fuentes: Casos_Prueba(Modulo3 Agrupado).csv, fila G98, y Especificacion-Requerimientos-Modulo3 (1).md, RF-58 CA-11/Salida 2.

## Inventario y cobertura

Un ejecutor canónico `g98.mjs`, una colección `G98.postman_collection.json`, módulos `lib/` y pruebas locales `pruebas/`. TC-M03-191 es API Postman/Newman: no requiere Cypress. `Resultados/` y `EvaluacionV2/Resultados/` son evidencias históricas. No se mueve ni retira ningún archivo.

API-191-01 comprueba HTTP 200, eco del RUN, panel, total ACTIVA y lista del área, orden CRITICO→MODERADO→LEVE, tipo, variable, tiempo y alcance. API-191-02 acredita tres severidades y sensores distintos. API-191-03 comprueba `id_activo_biologico` e `identificador_activo`; API-191-04 observa `severidad_alerta` de sensores. Newman ejecuta una vez el GET filtrado.

## Vías de precondición

Para el tercer intento V2, la búsqueda consulta primero la finca 184 y prioriza el área 702 `QA-G98-PANEL`, dispositivo 789, sensores 1210/1211/1212 y activo 928. Estos IDs ordenan la exploración; los GET públicos deben comprobar de nuevo área visible con 200 y eco, activo vinculado, dispositivo activo con serial, sensores activos, lecturas con telemetría y activo del área, y canario E7. Si el área no es visible, continúa el descubrimiento normal de dos fincas. Los nombres del historial `pH del agua`, `Amoniaco (NH3)` y `Temperatura Corporal` se convierten en los códigos del POST `PH_AGUA`, `NH3` y `TEMPERATURA_CORPORAL`; se aceptan además los códigos directos y `TEMP_CORPORAL`. Un nombre desconocido se descarta con observación.

Revisión local de `src/configuration/infrastructure/routers/dispositivo_iot_router.py`, `src/configuration/application/use_cases/dispositivos_iot/consultar_dispositivos_iot_use_case.py` y `src/configuration/infrastructure/repositories/dispositivo_iot_repository.py`: el GET de dispositivos activos no pagina ni limita, y el repositorio devuelve `.all()` según las fincas visibles. Se prioriza el dispositivo 789 dentro de esa respuesta; no se añade otro GET. La verificación del área 702 añade como máximo un GET de infraestructura por rol; si la finca 184 ya está entre las dos primeras, se reutiliza la respuesta. El límite global de 224 solicitudes conserva margen y no cambia. No se modificó la colección Newman porque solo valida el dashboard.

Primero se reutilizan alertas ACTIVA existentes por GET públicos, Productor primero y Administrador si hay credenciales. Si falta área apta con activo, la vía de creación está **habilitada** por la decisión QA de 2026-10-31: hasta tres POST `/iot/alertas` en el sandbox, con token `BROKER_SERVICE_TOKEN` del lanzador. El ejecutor exige área autorizada, activo vinculado, tres sensores activos de variables distintas y `id_telemetria` real del historial filtrado. Los 27 modelos DTO/RF-57 se validan localmente; M09 y las relaciones de TEST solo se acreditan por API pública durante el RUN.

Cada POST exige 201, eco, `es_duplicado=false`, ID distinto y severidad esperada. Cada GET de detalle exige ACTIVA, sensor, severidad, área y activo resuelto. Un listado ACTIVA confirma los tres IDs antes de Newman. Un 422, duplicado o detalle incoherente es problema técnico de semilla y no RECHAZADO. Sin activo o sin sensores/lecturas aptos, el caso queda BLOQUEADO sin POST, con causa concreta.

## Corrección del bloqueo de ORD-G98-007

`src/telemetry/infrastructure/repositories/alerta_repository.py:516-534` reclama alertas sin filtrar un supuesto estado CONFIRMADA; «confirmada» en la orden anterior significaba COMMIT. `main.py:176-191` llama `sesion_sistema()`; `src/shared/database.py:218,274-302` muestra que usa otra conexión y que la sesión sandbox se entrega por `get_db()` con `X-Test-Run-Id` y `ENABLE_TEST_SANDBOX=true`. Las filas del RUN no hacen COMMIT y PostgreSQL MVCC impide que el worker las vea. La misma separación de transacciones se observó en G92 para RF-17 postcommit. Esta es lectura del código local y del hecho aportado por la orden, no verificación del despliegue TEST.

Tras `DELETE /test-control/runs/<RUN>`, cada ID creado se consulta sin cabeceras del RUN. Rollback solo verificado si DELETE=200 y los tres IDs responden 404 o dejan de estar ACTIVA. Login y posibles efectos E7 del dashboard no se declaran revertidos.

Presupuesto: hasta **224 solicitudes directas en RUN**, incluyendo máximo **3 POST** de alerta; una ejecución Newman con un GET; **1 DELETE** de cierre; hasta **3 GET** posteriores; **900 s**. Se inspeccionan hasta dos fincas, seis áreas, ocho dispositivos por área y 24 historiales por rol. Hasta dos POST de login pueden ocurrir fuera del RUN.

## Peticiones TEST previstas, solo por lanzador autorizado

1. `POST /sesiones/` Productor y opcional Administrador, fuera del RUN.
2. Por rol: `GET /configuracion/infraestructuras?finca_id=184&solo_activas=true` para priorizar el área 702; `GET /configuracion/fincas?solo_activas=true`; hasta dos GET de infraestructuras de las fincas normales, reutilizando el de 184 si corresponde; hasta seis `GET /iot/alertas?estado=ACTIVA&id_infraestructura=<ID>&pagina=1&por_pagina=200`; canarios `GET /iot/monitoreo/dashboard/<ID>?pagina=1&por_pagina=1`.
3. Si falta área reutilizable: `GET /configuracion/dispositivos-iot?solo_activos=true`; por área `GET /activos-biologicos?id_infraestructura=<ID>&pagina=1&page_size=100`; por dispositivo `GET /configuracion/dispositivos-iot/<ID>/sensores`; por sensor `GET /iot/monitoreo/historial?fecha_inicio=<YYYY-MM-DD>&fecha_fin=<YYYY-MM-DD>&sensor_id=<ID>&pagina=1&por_pagina=100`; canario del área. El ejecutor filtra cada lectura por sensor, área, activo, telemetría válida y variable normalizada. Un HTTP distinto de 200 se registra con código saneado en observaciones y problemas técnicos; si todas las consultas de historial fallan por HTTP, el caso queda NO_CONCLUYENTE técnico.
4. **Únicas escrituras de escenario:** máximo tres `POST /iot/alertas` con token broker, `X-Test-Run-Id` y `X-Sandbox-Secret`; cada uno seguido de `GET /iot/alertas/<ID>`. Luego `GET /iot/alertas?estado=ACTIVA&id_infraestructura=<ID>&pagina=1&por_pagina=200`.
5. Newman una vez: `GET /iot/monitoreo/dashboard/<ID>?pagina=1&por_pagina=50`; `DELETE /test-control/runs/<RUN>`; hasta tres `GET /iot/alertas/<ID>` sin cabeceras RUN.

Sin SQL ni `/test-control/query`. Comandos locales: `node --check g98.mjs`, `node --check pruebas/g98_ensayo.mjs`, `node g98.mjs --capacidades`, `node g98.mjs --comprobar`, `node --experimental-test-isolation=none --test pruebas/g98.test.mjs`, `node pruebas/g98_ensayo.mjs` y `.venv/Scripts/python.exe -B pruebas/validar_semilla_g98.py`. El ensayo usa solo loopback y temporales, no TEST.
