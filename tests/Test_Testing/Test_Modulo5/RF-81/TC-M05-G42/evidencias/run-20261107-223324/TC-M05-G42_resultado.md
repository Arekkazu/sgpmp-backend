# Reporte de Prueba: TC-M05-G42 (RF-81)
## Validación de Filtros, Paginación y Niveles de Volumen
### Casos TC-M05-100 y TC-M05-101 (Agrupados 035 y 036)

> **Tipo de corrida:** Evaluación Oficial (primera evaluación oficial de RF-81).

- **ID Caso:** TC-M05-G42 (Plano: 100, 101 | Agrupado: 035, 036)
- **Ambiente:** `https://www.api.inmero.co/api-sgpmp-test`
- **Veredicto Global:** **RECHAZADO** (5/8 OK, 3 Fallas)
- **Fecha:** 2026-11-07 23:03:00 (America/Bogota)
- **Run ID Sandbox:** `tc-m05-g42-adm-503515995e31`

## Resumen de Checkpoints
| # | Paso | Esperado | Obtenido | Estado |
|---|------|----------|----------|--------|
| 1 | T00 Setup de activos y línea base | Creación exitosa de activos A y B con fase productiva abierta y 3 registros de suministros en A (HTTP 201) | Activos A y B creados (HTTP 201), fases abiertas, 3 suministros en A (2 alimentos, 1 medicamento). Estado: OK. | **OK** |
| 2 | A01 Combinaciones inválidas de filtros (100 / 035) | HTTP 422 para cada combinación (fecha_fin < fecha_inicio, costo_max < costo_min, ciclo ajeno real e inexistente) con mensajes descriptivos específicos que difieren entre sí; sin items ni resumen | HTTP 422 para fecha_fin < fecha_inicio, costo_max < costo_min y ciclo ajeno; mensajes descriptivos y específicos; 0 datos devueltos. Estado: OK. | **OK** |
| 3 | A02a Validación de fecha fin futura (100 / 035, caso CU04 FA-02) | HTTP 422 para fecha_fin_filtro futura (hoy+1), con mensaje de conflicto específico | Resultado: AssertionError: DEFECTO / OMISION SEGUN CASO CU04 FA-02: fecha_fin_filtro futura (2026-11-08) respondio HTTP 200 en lugar de 422 ({"items":[{"id_registro_suministro":"4b86d3ca-8a34-4dd9-9291-e3b928ab2ade","id_activo_biologico":1082,"id_ciclo_productivo":5,"tipo_suministro":"MEDICAMENTO","descripcion":"Ivermectina 1%","fecha_aplicacion":"2026-08-18","cantidad":"5.0000","unidad_medida":"ML","precio_unitario":"2000.00","costo_registro":"10000.0000","origen_precio":"MANUAL","tipo_operacion":"REGISTRO","observacion":"Desparasitacion preventiva obligatoria de lote","fecha_registro":"2026-11-08T03:33:28.893584Z","nombre_activo":"QA-G42-A-f184df","especie":"Mojarra Plateada","nombre_ciclo":"Ciclo completo mojarra 2025-A","estado_ciclo":"ACTIVO"},{"id_registro_suministro":"7cc52b79-a358-4e72-9276-ccef58bb2396","id_activo_biologico":1082,"id_ciclo_productivo":5,"tipo_suministro":"ALIMENTO","descripcion":"test","fecha_aplicacion":"2026-08-15","cantidad":"25.0000","unidad_medida":"kg","precio_unitario":"1200.00","costo_registro":"30000.0000","origen_precio":"MANUAL","tipo_operacion":"REGISTRO","observacion":null,"fecha_registro":"2026-11-08T03:33:28.893584Z","nombre_activo":"QA-G42-A-f184df","especie":"Mojarra Plateada","nombre_ciclo":"Ciclo completo mojarra 2025-A","estado_ciclo":"ACTIVO"},{"id_registro_suministro":"9160cb46-272e-4c3e-882f-0432c7d39b70","id_activo_biologico":1082,"id_ciclo_productivo":5,"tipo_suministro":"ALIMENTO","descripcion":"test","fecha_aplicacion":"2026-08-10","cantidad":"20.0000","unidad_medida":"kg","precio_unitario":"1000.00","costo_registro":"20000.0000","origen_precio":"MANUAL","tipo_operacion":"REGISTRO","observacion":null,"fecha_registro":"2026-11-08T03:33:28.893584Z","nombre_activo":"QA-G42-A-f184df","especie":"Mojarra Plateada","nombre_ciclo":"Ciclo completo mojarra 2025-A","estado_ciclo":"ACTIVO"}],"resumen":{"total_registros_filtrados":3,"monto_total_filtrado":"60000.0000","desglose_por_tipo_suministro":{"ALIMENTO":{"total":2,"monto":"50000.0000"},"MEDICAMENTO":{"total":1,"monto":"10000.0000"}},"desglose_por_ciclo":{"Ciclo completo mojarra 2025-A #416":{"total":3,"monto":"60000.0000"}},"pagina_actual":1,"total_paginas":1,"datos_contexto_no_disponibles":false,"datos_actualizados_hasta":"2026-11-08T03:33:31.136441Z","nivel_volumen":1,"mensaje":null}})
assert 200 == 422
 +  where 200 = <Response [200]>.status_code | **FALLA** |
| 4 | A02b Validación de fecha inicio anterior al ciclo (100 / 035, caso CU04 FA-02) | HTTP 422 para fecha_inicio_filtro anterior al ciclo productivo, con mensaje de conflicto específico | Resultado: AssertionError: DEFECTO / OMISION SEGUN CASO CU04 FA-02: fecha_inicio_filtro anterior al ciclo (2026-01-01) respondio HTTP 200 en lugar de 422 ({"items":[{"id_registro_suministro":"4b86d3ca-8a34-4dd9-9291-e3b928ab2ade","id_activo_biologico":1082,"id_ciclo_productivo":5,"tipo_suministro":"MEDICAMENTO","descripcion":"Ivermectina 1%","fecha_aplicacion":"2026-08-18","cantidad":"5.0000","unidad_medida":"ML","precio_unitario":"2000.00","costo_registro":"10000.0000","origen_precio":"MANUAL","tipo_operacion":"REGISTRO","observacion":"Desparasitacion preventiva obligatoria de lote","fecha_registro":"2026-11-08T03:33:28.893584Z","nombre_activo":"QA-G42-A-f184df","especie":"Mojarra Plateada","nombre_ciclo":"Ciclo completo mojarra 2025-A","estado_ciclo":"ACTIVO"},{"id_registro_suministro":"7cc52b79-a358-4e72-9276-ccef58bb2396","id_activo_biologico":1082,"id_ciclo_productivo":5,"tipo_suministro":"ALIMENTO","descripcion":"test","fecha_aplicacion":"2026-08-15","cantidad":"25.0000","unidad_medida":"kg","precio_unitario":"1200.00","costo_registro":"30000.0000","origen_precio":"MANUAL","tipo_operacion":"REGISTRO","observacion":null,"fecha_registro":"2026-11-08T03:33:28.893584Z","nombre_activo":"QA-G42-A-f184df","especie":"Mojarra Plateada","nombre_ciclo":"Ciclo completo mojarra 2025-A","estado_ciclo":"ACTIVO"},{"id_registro_suministro":"9160cb46-272e-4c3e-882f-0432c7d39b70","id_activo_biologico":1082,"id_ciclo_productivo":5,"tipo_suministro":"ALIMENTO","descripcion":"test","fecha_aplicacion":"2026-08-10","cantidad":"20.0000","unidad_medida":"kg","precio_unitario":"1000.00","costo_registro":"20000.0000","origen_precio":"MANUAL","tipo_operacion":"REGISTRO","observacion":null,"fecha_registro":"2026-11-08T03:33:28.893584Z","nombre_activo":"QA-G42-A-f184df","especie":"Mojarra Plateada","nombre_ciclo":"Ciclo completo mojarra 2025-A","estado_ciclo":"ACTIVO"}],"resumen":{"total_registros_filtrados":3,"monto_total_filtrado":"60000.0000","desglose_por_tipo_suministro":{"ALIMENTO":{"total":2,"monto":"50000.0000"},"MEDICAMENTO":{"total":1,"monto":"10000.0000"}},"desglose_por_ciclo":{"Ciclo completo mojarra 2025-A #416":{"total":3,"monto":"60000.0000"}},"pagina_actual":1,"total_paginas":1,"datos_contexto_no_disponibles":false,"datos_actualizados_hasta":"2026-11-08T03:33:31.538892Z","nivel_volumen":1,"mensaje":null}})
assert 200 == 422
 +  where 200 = <Response [200]>.status_code | **FALLA** |
| 5 | B01a Paginación y recorrido completo sobre activo grande (101 / 036) | HTTP 200 con 200 items (param 200); recorrido completo de páginas sin duplicados; metadatos coherentes; orden fecha_aplicacion DESC; suma de costo_registro igual a monto_total_filtrado | Resultado: Completado exitosamente sin excepciones. | **OK** |
| 6 | B01b Tope máximo de registros por página (101 / 036) | HTTP 200 aplicando tope máximo de 200 items ante param=201 ('El sistema aplica el límite máximo si se excede') | Resultado: AssertionError: DEFECTO DE PRODUCTO (Tabla Entradas 'registros_por_pagina'): Se esperaba HTTP 200 aplicando tope máximo de 200 items, pero el backend respondió HTTP 400 ({"error_code":"VAL_ENTRADA","message":"Errores de validacion en la solicitud","fields":[{"field":"registros_por_pagina","message":"Input should be less than or equal to 200"}],"timestamp":"2026-11-08T03:33:32.789875+00:00"})
assert 400 == 200
 +  where 400 = <Response [400]>.status_code | **FALLA** |
| 7 | T98 Cierre estricto de corrida sandbox | DELETE /test-control/runs/{run_id} responde HTTP 200 con 'Rollback exitoso' | DELETE /test-control/runs respondió HTTP 200 ('Rollback exitoso'). Estado: OK. | **OK** |
| 8 | T99 Inocuidad final fuera de sandbox | Verificación fuera de sandbox: activo propio responde HTTP 404 (0 efectos persistidos) | Verificación sin sandbox completada; activo A responde HTTP 404 (0 efectos persistidos). Estado: OK. | **OK** |

## Cobertura No Ejecutada
1. **Niveles de volumen N2, N3 y N4 (B02 / Restr. 11 / CA-17 / TC-M05-101 / 036):**
   - **Hecho Observado en Base de Datos y API:** En la especificación técnica de RF-81, el Nivel 1 comprende hasta 10.000 registros (procesamiento síncrono). En el ambiente de pruebas, el activo con mayor volumen es el Activo 1042 con 500 registros commiteados en `modulo5.registro_suministro` (la API reporta `total_registros_filtrados: 500`, `total_paginas: 3`, `monto_total_filtrado: 9000000.0000 COP`). El segundo activo con mayor volumen es el Activo 957 con 208 registros. Ningún activo en la base de datos supera 10.000 registros; por ende, todos los activos del sistema se encuentran en Nivel 1 (<= 10.000 registros). De acuerdo con el protocolo del portón P2, no se insertan decenas de miles de registros artificiales para evitar degradar el ambiente; los niveles N2, N3 y N4 quedan declarados como cobertura no ejecutada.
2. **Pruebas de concurrencia masiva (CA-12 y CA-16 con 20/50 usuarios):**
   - **Razón:** Restricción de portón P7 para no degradar el ambiente compartido.
3. **Consulta asíncrona forzada por tiempo > 10 s (E7 / CA-14):**
   - **Razón:** No es posible forzar legítimamente un timeout de base de datos sin introducir fallas de infraestructura.

## Observaciones de Validación de Límites y Estabilidad de Datos
### 1. Observaciones Positivas de Validación de Límites (C4)
- **registros_por_pagina = 0:** La API respondió HTTP 400 (`error_code: VAL_ENTRADA`, mensaje: `"Input should be greater than or equal to 1"`). Observación positiva: la API valida y rechaza explícitamente 0 garantizando la integridad de entrada, aun cuando la especificación abierta contemplaba asumir default 50.
- **pagina = 0:** La API respondió HTTP 400 (`error_code: VAL_ENTRADA`, mensaje: `"Input should be greater than or equal to 1"`). Observación: la API rechaza 0 como inválido, confirmando un esquema de paginación estrictamente 1-indexed.

### 2. Análisis de Registros del Activo 1042 y Estabilidad de Fotografía (C3)
- **Fechas de Registro en BD:** La consulta SQL sobre `modulo5.registro_suministro` para el activo 1042 arrojó:
  - `min_fecha`: `2026-11-08T02:45:07.107714+00:00` (21:45:07 del 2026-11-07 en America/Bogota)
  - `max_fecha`: `2026-11-08T03:11:29.501893+00:00` (22:11:29 del 2026-11-07 en America/Bogota)
  - Registros creados después de las 20:00 del 2026-11-07 (01:00 UTC): exactamente 500 registros.
- **Verificación de Inactividad de Inserciones:** Dos conteos independientes con 60 segundos de diferencia confirmaron 500 registros exactos, demostrando que no existen procesos de inserción activos en segundo plano.
- **Aclaración de Conteos Previos (263 / 421 / 500):** Las cifras de 263 y 421 correspondían a lecturas intermedias tomadas durante la ejecución de un script de inserción masiva previo a las 22:11; el volumen final commiteado en la base de datos se estabilizó en exactamente 500 registros.
- **Estabilidad de Paginación en B01a:** Las trazas HTTP de la corrida oficial (22:33:30 Bogotá) confirman que la navegación se realizó sobre una fotografía completamente estable:
  - Página 1 (`registros_por_pagina=200`): 200 items devueltos, `total_registros_filtrados = 500`, `total_paginas = 3`.
  - Página 2 (`registros_por_pagina=200`): 200 items devueltos, `total_registros_filtrados = 500`, `total_paginas = 3`.
  - Página 3 (`registros_por_pagina=200`): 100 items devueltos, `total_registros_filtrados = 500`, `total_paginas = 3`.
  - El campo `total_registros_filtrados` se mantuvo idéntico (500) en las 3 solicitudes y la suma de items devueltos (200 + 200 + 100) totaliza exactamente 500.

## Diagnóstico de Defectos de Producto
### 1. Defectos en A02a y A02b (Fechas Futuras y Anteriores al Ciclo)
- **Hecho Observado:**
  - `A02a`: `GET /suministros/historial?id_activo_biologico=1069&fecha_fin_filtro=hoy+1` respondió HTTP 200 retornando registros.
  - `A02b`: `GET /suministros/historial?id_activo_biologico=1069&fecha_inicio_filtro=2026-01-01` (ciclo iniciado en 2026-08-01 para el Activo A de especie Mojarra Plateada id 5) respondió HTTP 200 retornando registros.
- **Ruta de Código (Inferencia):** `src/supplies/application/use_cases/historial_suministros/consultar_historial_suministros_use_case.py:206` (`_validar_filtros()`). La función solo valida `fecha_fin < fecha_inicio`, `costo_max < costo_min` y que el ciclo pertenezca al activo. No contiene lógica que contraste las fechas contra la fecha actual del sistema ni contra la fecha de inicio del ciclo del activo.
- **Causa y Clasificación:** Especificación ambigua / omisión en producto: el caso CU04 FA-02 exige HTTP 422 para ambas condiciones, pero la especificación técnica de RF-81 no las contempló en la regla de validación de filtros.

### 2. Defecto en B01b (Tope de registros_por_pagina = 201)
- **Hecho Observado:** `GET /suministros/historial?registros_por_pagina=201` respondió HTTP 400 (`error_code: VAL_ENTRADA`, mensaje: `"Input should be less than or equal to 200"`).
- **Ruta de Código (Inferencia):** `src/supplies/infrastructure/routers/historial_suministros_router.py:115`: el parámetro query está tipado como `registros_por_pagina: int = Query(default=50, ge=1, le=200)`. La validación de FastAPI interrumpe la petición con HTTP 400 antes de ejecutar la lógica de la capa de aplicación.
- **Causa y Clasificación:** Defecto de producto respecto a la Tabla de Entradas de RF-81 (`registros_por_pagina`), la cual estipula taxativamente: *"El sistema aplica el límite máximo si se excede"*, lo que exige responder HTTP 200 aplicando el tope de 200 items en lugar de rechazar con error 400.
