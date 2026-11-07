# DIAGNÓSTICO PRE-EJECUCIÓN TC-M03-G164 (RF-62)
**Caso de Prueba:** TC-M03-G164 — Consulta y filtrado de evaluaciones de calidad de telemetría IoT  
**Requerimiento Funcional:** RF-62 (Evaluación de Calidad de Datos Telemétricos)  
**Módulo:** Módulo 3 — Telemetría e Internet de las Cosas (`src/telemetry/`)  
**Fecha de Diagnóstico:** 2026-10-20  
**Entorno Evaluado:** Entorno TEST oficial (`https://api.inmero.co/api-sgpmp-test`)  

---

## 1. Resumen Ejecutivo

Se realizó la inspección estática, sintáctica y dinámica (pre-vuelo con queries sandbox transaccionales de solo lectura y validación live de autenticación/endpoints) sobre los artefactos del grupo **TC-M03-G164**.

### Veredicto por Subcaso

| Subcaso | Nombre / Objetivo | Veredicto | Resumen de Situación |
| :--- | :--- | :---: | :--- |
| **TC-M03-301** | Listar evaluaciones sin filtros, paginación y orden DESC | 🟢 **EJECUTABLE** | Router implementa paginación defaults (1, 50), orden `timestamp_evaluacion.desc()`, estructura `{total, pagina, por_pagina, items}` conforme. Existen 18 registros en TEST ($\ge 10$). |
| **TC-M03-302** | Detalle por `id_telemetria` y contrato `CalidadEvaluacion` | 🟢 **EJECUTABLE** | Endpoint `GET /iot/calidad/{id_telemetria}` operativo y verificado en vivo con `id_telemetria=62` (HTTP 200). Contrato Pydantic coincide al 100%. |
| **TC-M03-304** | Filtrado por `id_sensor`, aislamiento y paginación | 🟢 **EJECUTABLE** | Sensor 1 tiene 10 evaluaciones ($\ge 5$) y Sensor 53 tiene 3. El filtrado por query `id_sensor` está implementado y opera en el repositorio. |
| **TC-M03-305** | Filtrado por `clasificacion_calidad` (4 valores) y rechazo inválido | 🟡 **EJECUTABLE CON OBSERVACIONES** | En BD TEST solo existen evaluaciones `INDETERMINADA` (0 para `APTO`, `APTO_CON_RESERVA`, `NO_APTO`). Los 3 valores sin datos se omiten parcialmente o retornan array vacío. El valor inválido responde HTTP 200 con total 0 porque el router no valida enum en query string (riesgo de falla en aserción 422). |
| **TC-M03-306** | Rango de fechas, frontera `desde==hasta` y rechazo `desde>hasta` | 🟡 **EJECUTABLE CON OBSERVACIONES** | Rango válido y frontera operan contra los 18 timestamps en BD TEST. Rechazo `desde>hasta` responde HTTP 200 con total 0 en lugar de 422 (riesgo de falla en aserción de rechazo). |
| **TC-M03-307** | Filtrado por `estado_evaluacion` (`VIGENTE` / `SUPERADA`) | 🔴 **BLOQUEADO EN MODO EXISTENTES** | En TEST existen 18 registros `VIGENTE` y **0 registros `SUPERADA`**. Se requiere ejecución de `POST /iot/calidad/reevaluar` en modo sandbox para generar al menos una evaluación `SUPERADA`, o de lo contrario el subcaso es omitido y el reporte final falla en NW-98 por falta de cobertura. |
| **TC-M03-308** | Límites OWASP API4 (`por_pagina=200`, `201` $\rightarrow$ 422, `pagina=0` $\rightarrow$ 422) | 🟢 **EJECUTABLE** | Validado en código: `calidad_router.py` aplica `pagina: int = Query(1, ge=1)` y `por_pagina: int = Query(50, ge=1, le=200)`. FastAPI emite HTTP 422 nativo ante desbordamiento. |

### Top 3 Bloqueantes / Hallazgos Críticos

1. **[H-1 BLOQUEANTE] URL Base Obsoleta en Artefactos**: La URL antigua `https://api.inmero.co/[host-antiguo-obsoleto]` (que responde HTTP 404 Not Found) se encontraba definida como default en [build_collection.cjs](file:///c:/Users/Juansegutt/Integrador/sgpmp-backend/tests/Test_Testing/Test_Modulo3/RF-62/TC-M03-G164/build_collection.cjs#L65), [ejecutar_tc_m03_g164.ps1](file:///c:/Users/Juansegutt/Integrador/sgpmp-backend/tests/Test_Testing/Test_Modulo3/RF-62/TC-M03-G164/ejecutar_tc_m03_g164.ps1#L13) y [.env.test](file:///c:/Users/Juansegutt/Integrador/sgpmp-backend/.env.test#L10). La URL activa del entorno de pruebas es `https://api.inmero.co/api-sgpmp-test`.
2. **[H-2 BLOQUEANTE] Error de Esquema en Script de Seed SQL**: [seed_datos_tc_m03_g164.sql](file:///c:/Users/Juansegutt/Integrador/sgpmp-backend/tests/Test_Testing/Test_Modulo3/RF-62/TC-M03-G164/seed_datos_tc_m03_g164.sql#L50-L56) consulta la columna inexistente `id_variable` sobre la tabla `modulo9.sensores`. Esto provoca un fallo fatal inmediato de PostgreSQL (`UndefinedColumn: column "id_variable" does not exist`) si el DBA intenta aplicar la semilla masiva.
3. **[H-3 BLOQUEANTE] Brecha de Datos de Prueba para `SUPERADA` y Clasificaciones**: La base de datos TEST solo cuenta con 18 registros en `modulo3.telemetria_calidad`, todos en estado `VIGENTE` y con clasificación `INDETERMINADA`. No existe ninguna fila `SUPERADA`, lo cual bloquea la validación funcional de TC-M03-307 a menos que se utilice la vía dinámica de reevaluación.

---

## 2. Inventario de Artefactos y Fuente de Verdad

Ubicación: `tests/Test_Testing/Test_Modulo3/RF-62/TC-M03-G164/`

| Archivo | Tamaño (bytes) | Rol / Responsabilidad | ¿Fuente de Verdad? |
| :--- | :---: | :--- | :---: |
| [build_collection.cjs](file:///c:/Users/Juansegutt/Integrador/sgpmp-backend/tests/Test_Testing/Test_Modulo3/RF-62/TC-M03-G164/build_collection.cjs) | 69,301 | Generador algorítmico de la colección Postman (1,483 líneas). Contiene la lógica oracular de aserciones, variables y 36 ítems. | **SÍ (Fuente de verdad primaria)** |
| [test_tc_m03_g164.json](file:///c:/Users/Juansegutt/Integrador/sgpmp-backend/tests/Test_Testing/Test_Modulo3/RF-62/TC-M03-G164/test_tc_m03_g164.json) | 90,383 | Colección Postman generada v5. Contiene 36 requests configurados. | **NO (Artefacto compilado derivado)** |
| [DISENO_Y_PRECONDICIONES.md](file:///c:/Users/Juansegutt/Integrador/sgpmp-backend/tests/Test_Testing/Test_Modulo3/RF-62/TC-M03-G164/DISENO_Y_PRECONDICIONES.md) | 25,113 | Documento de diseño técnico, matriz de subcasos, correcciones C1–C6 y precondiciones declaradas. | Documentación normativa |
| [ejecutar_tc_m03_g164.ps1](file:///c:/Users/Juansegutt/Integrador/sgpmp-backend/tests/Test_Testing/Test_Modulo3/RF-62/TC-M03-G164/ejecutar_tc_m03_g164.ps1) | 6,839 | Runner PowerShell que ejecuta Newman con htmlextra, gestiona variables de entorno y escanea fugas de secretos L6. | Runner de automatización |
| [verificar_hardcode_tc_m03_g164.cjs](file:///c:/Users/Juansegutt/Integrador/sgpmp-backend/tests/Test_Testing/Test_Modulo3/RF-62/TC-M03-G164/verificar_hardcode_tc_m03_g164.cjs) | 10,262 | Verificador estático de ausencia de tokens, passwords o IDs quemados en la colección. | Script QA de seguridad |
| [auditar_literales.cjs](file:///c:/Users/Juansegutt/Integrador/sgpmp-backend/tests/Test_Testing/Test_Modulo3/RF-62/TC-M03-G164/auditar_literales.cjs) | 3,641 | Validador de enums (`VIGENTE`, `SUPERADA`) y ausencia del literal obsoleto `ACTIVA`. | Script QA de consistencia |
| [vista_coleccion_tc_m03_g164.cjs](file:///c:/Users/Juansegutt/Integrador/sgpmp-backend/tests/Test_Testing/Test_Modulo3/RF-62/TC-M03-G164/vista_coleccion_tc_m03_g164.cjs) | 2,919 | Utilidad para imprimir la jerarquía y estructura de peticiones de la colección. | Utilidad auxiliar |
| [seed_datos_tc_m03_g164.sql](file:///c:/Users/Juansegutt/Integrador/sgpmp-backend/tests/Test_Testing/Test_Modulo3/RF-62/TC-M03-G164/seed_datos_tc_m03_g164.sql) | 7,832 | Script SQL de inserción masiva (>200 telemetrías y calidades, 3 sensores, 4 clasificaciones y 3 filas SUPERADA). | Datos de prueba (DBA) |
| [cleanup_seed_tc_m03_g164.sql](file:///c:/Users/Juansegutt/Integrador/sgpmp-backend/tests/Test_Testing/Test_Modulo3/RF-62/TC-M03-G164/cleanup_seed_tc_m03_g164.sql) | 2,904 | Script SQL de purga determinista por marcador `seed_id = 'TC_M03_G164_SEED'`. | Limpieza de datos (DBA) |
| [openapi_test_snapshot.json](file:///c:/Users/Juansegutt/Integrador/sgpmp-backend/tests/Test_Testing/Test_Modulo3/RF-62/TC-M03-G164/openapi_test_snapshot.json) | 642,017 | Snapshot oficial de especificación OpenAPI descargado desde `https://api.inmero.co/api-sgpmp-test/openapi.json`. | Snapshot de verificación |

> **Regla de mantenimiento:** Si se requiere ajustar URLs, aserciones o parámetros de la colección, se debe editar **exclusivamente `build_collection.cjs`** y regenerar `test_tc_m03_g164.json` ejecutando `node build_collection.cjs`.

---

## 3. Tabla de Endpoints Usados vs. OpenAPI

Contraste directo entre los requests definidos en `build_collection.cjs` / `test_tc_m03_g164.json` y la especificación OpenAPI activa de TEST (`openapi_test_snapshot.json`):

| Ítem | Nombre en Colección | Método | Ruta en Colección | Query Params / Body | Status Esperado | Estado en OpenAPI TEST | Observación Técnica |
| :---: | :--- | :---: | :--- | :--- | :---: | :---: | :--- |
| **01** | NW-00-Setup-Login-Admin | POST | `{{baseUrl}}/sesiones/` | JSON: `correo_electronico`, `contrasena` | 200 | **Existe** | Login operativo; token retornado satisfactoriamente. |
| **02** | NW-00-Setup-Login-Productor | POST | `{{baseUrl}}/sesiones/` | JSON: `correo_electronico`, `contrasena` | 200 | **Existe** | Login operativo. |
| **03** | NW-00-Setup-Login-Ingeniero | POST | `{{baseUrl}}/sesiones/` | JSON: `correo_electronico`, `contrasena` | 200 | **Existe** | Login operativo. |
| **04** | NW-01-PreflightA-Inventario | GET | `{{baseUrl}}/iot/calidad` | `pagina=1&por_pagina=200` | 200 | **Existe** | Responde HTTP 200 con `{total: 18, pagina: 1, por_pagina: 200, items: [...]}`. |
| **05** | NW-01-PreflightA-DB-Query-Count | POST | `{{baseUrl}}/test-control/query` | JSON: `{"query": "SELECT count(*) FROM modulo3.telemetria_calidad"}` | 200 | **Existe** | Endpoint de sandbox operativo bajo secreto `X-Sandbox-Secret`. |
| **06** | NW-02-Generar-Reevaluacion-Sandbox | POST | `{{baseUrl}}/iot/calidad/reevaluar` | JSON: `id_sensor`, `fecha_desde`, `fecha_hasta`, `causa_documentada` | 200 / 422 | **Existe** | Endpoint de FA-08 presente en router. |
| **07** | NW-03-PreflightB-Recalcular-Gating | GET | `{{baseUrl}}/iot/calidad` | `pagina=1&por_pagina=200` | 200 | **Existe** | Recalcula contadores tras siembra sandbox. |
| **08** | NW-TC-M03-301-Listar-Sin-Filtros | GET | `{{baseUrl}}/iot/calidad` | Ninguno (defaults) | 200 | **Existe** | Estructura paginada `{total, pagina: 1, por_pagina: 50, items}` validada. |
| **09** | NW-TC-M03-301-Sonda-Tenant-Productor | GET | `{{baseUrl}}/iot/calidad` | `pagina=1&por_pagina=1` | 200 | **Existe** | Sonda con credenciales de Productor; responde 200. |
| **10** | NW-TC-M03-301-Sonda-Tenant-Ingeniero | GET | `{{baseUrl}}/iot/calidad` | `pagina=1&por_pagina=1` | 200 | **Existe** | Sonda con credenciales de Ingeniero; responde 200. |
| **11** | NW-TC-M03-302-Detalle-Telemetria | GET | `{{baseUrl}}/iot/calidad/{id_telemetria}` | Path param: `id_telemetria` (entero) | 200 | **Existe** | Path param coincide exactamente (`id_telemetria`). Validado con `id=62`. |
| **12** | NW-TC-M03-304-Filtrar-Sensor-Candidato | GET | `{{baseUrl}}/iot/calidad` | `id_sensor={{sensor_candidato}}&pagina=1&por_pagina=200` | 200 | **Existe** | Parámetro `id_sensor` existe en OpenAPI. |
| **13** | NW-TC-M03-304-Aislamiento-Segundo-Sensor | GET | `{{baseUrl}}/iot/calidad` | `id_sensor={{sensor_segundo}}&pagina=1&por_pagina=200` | 200 | **Existe** | Parámetro `id_sensor` existe en OpenAPI. |
| **14** | NW-TC-M03-304-Paginacion-Combinada-Pag1 | GET | `{{baseUrl}}/iot/calidad` | `id_sensor={{sensor_candidato}}&pagina=1&por_pagina=3` | 200 | **Existe** | Parámetros `pagina`, `por_pagina` existen. |
| **15** | NW-TC-M03-304-Paginacion-Combinada-Pag2 | GET | `{{baseUrl}}/iot/calidad` | `id_sensor={{sensor_candidato}}&pagina=2&por_pagina=3` | 200 | **Existe** | Parámetros `pagina`, `por_pagina` existen. |
| **16** | NW-TC-M03-305-Enum-INDETERMINADA | GET | `{{baseUrl}}/iot/calidad` | `clasificacion=INDETERMINADA&pagina=1&por_pagina=50` | 200 | **Existe** | Parámetro se llama `clasificacion` en OpenAPI (coincide). |
| **17** | NW-TC-M03-305-Enum-APTO | GET | `{{baseUrl}}/iot/calidad` | `clasificacion=APTO&pagina=1&por_pagina=50` | 200 | **Existe** | Parámetro se llama `clasificacion`. |
| **18** | NW-TC-M03-305-Enum-APTO_CON_RESERVA | GET | `{{baseUrl}}/iot/calidad` | `clasificacion=APTO_CON_RESERVA&pagina=1&por_pagina=50` | 200 | **Existe** | Parámetro se llama `clasificacion`. |
| **19** | NW-TC-M03-305-Enum-NO_APTO | GET | `{{baseUrl}}/iot/calidad` | `clasificacion=NO_APTO&pagina=1&por_pagina=50` | 200 | **Existe** | Parámetro se llama `clasificacion`. |
| **20** | NW-TC-M03-305-Invalido-Rechazo | GET | `{{baseUrl}}/iot/calidad` | `clasificacion=VALOR_NO_CATALOGADO_ENUM` | 422 / 4xx | **Existe** | **Riesgo:** router no valida enum en Query; devuelve HTTP 200 con total 0. |
| **21** | NW-TC-M03-305-Sonda-Clasificacion-Calidad | GET | `{{baseUrl}}/iot/calidad` | `clasificacion=APTO` | 200 | **Existe** | Sonda informativa. |
| **22** | NW-TC-M03-306-Rango-Fechas-Valido | GET | `{{baseUrl}}/iot/calidad` | `fecha_desde={{f1}}&fecha_hasta={{f2}}` | 200 | **Existe** | Parámetros `fecha_desde` y `fecha_hasta` (ISO-8601) existen. |
| **23** | NW-TC-M03-306-Frontera-Exacta | GET | `{{baseUrl}}/iot/calidad` | `fecha_desde={{f}}&fecha_hasta={{f}}` | 200 | **Existe** | Coincide con OpenAPI. |
| **24** | NW-TC-M03-306-Offset-Bogota | GET | `{{baseUrl}}/iot/calidad` | `fecha_desde=...-05:00&fecha_hasta=...-05:00` | 200 | **Existe** | Parser FastAPI soporta offsets ISO. |
| **25** | NW-TC-M03-306-Fechas-Invertidas-Rechazo | GET | `{{baseUrl}}/iot/calidad` | `fecha_desde={{f_mayor}}&fecha_hasta={{f_menor}}` | 422 / 4xx | **Existe** | **Riesgo:** router no valida inversión; devuelve HTTP 200 con total 0. |
| **26** | NW-TC-M03-307-Filtrar-SUPERADA | GET | `{{baseUrl}}/iot/calidad` | `estado_evaluacion=SUPERADA` | 200 | **Existe** | Parámetro `estado_evaluacion` existe en OpenAPI. |
| **27** | NW-TC-M03-307-Complemento-VIGENTE | GET | `{{baseUrl}}/iot/calidad` | `estado_evaluacion=VIGENTE` | 200 | **Existe** | Parámetro `estado_evaluacion` existe en OpenAPI. |
| **28** | NW-TC-M03-307-Sonda-ACTIVA | GET | `{{baseUrl}}/iot/calidad` | `estado_evaluacion=ACTIVA` | 200 | **Existe** | Sonda informativa tras Decisión D7. |
| **29** | NW-TC-M03-308-Limite-Maximo-200 | GET | `{{baseUrl}}/iot/calidad` | `pagina=1&por_pagina=200` | 200 | **Existe** | `por_pagina=200` es el límite superior permitido por OpenAPI. |
| **30** | NW-TC-M03-308-Exceso-PorPagina-201 | GET | `{{baseUrl}}/iot/calidad` | `pagina=1&por_pagina=201` | 422 | **Existe** | `Query(..., le=200)` en backend rechaza con HTTP 422. |
| **31** | NW-TC-M03-308-Pagina-Cero-Rechazo | GET | `{{baseUrl}}/iot/calidad` | `pagina=0&por_pagina=50` | 422 | **Existe** | `Query(..., ge=1)` en backend rechaza con HTTP 422. |
| **32** | NW-TC-M03-308-PorPagina-Cero-Rechazo | GET | `{{baseUrl}}/iot/calidad` | `pagina=1&por_pagina=0` | 422 | **Existe** | `Query(..., ge=1)` en backend rechaza con HTTP 422. |
| **33** | NW-TC-M03-308-Pagina-Mayor-Ultima | GET | `{{baseUrl}}/iot/calidad` | `pagina=9999&por_pagina=50` | 200 | **Existe** | Retorna HTTP 200 con array vacío `items: []`. |
| **34** | NW-TC-M03-308-Frontera-PorPagina-1 | GET | `{{baseUrl}}/iot/calidad` | `pagina=1&por_pagina=1` | 200 | **Existe** | `por_pagina=1` es la frontera mínima permitida. |
| **35** | NW-98-Cobertura | GET | `{{baseUrl}}/health` | Ninguno | 200 | **Existe** | Checkpoint de control de cobertura de la suite. |
| **36** | NW-99-Teardown-Cierre-Sandbox | DELETE | `{{baseUrl}}/test-control/runs/{{run_id}}` | Header: `X-Sandbox-Secret` | 200 | **Existe** | Rollback del sandbox ejecutado en servidor. |

---

## 4. Tabla de Enums, Contratos y Flags Detectados

### Comparativa de Esquema `TelemetriaCalidadSchema`

| Campo en Schema | Tipo en OpenAPI TEST | Tipo en Colección Newman | Estado / Coherencia |
| :--- | :--- | :--- | :---: |
| `id_evaluacion` | `string (uuid)` | `string (uuid)` | ✅ Coincide |
| `id_telemetria` | `integer` | `integer` | ✅ Coincide |
| `id_sensor` | `integer` | `integer` | ✅ Coincide |
| `timestamp_evaluacion` | `string (date-time)` | `string (ISO-8601)` | ✅ Coincide |
| `indice_calidad` | `integer \| null` | `integer \| null` | ✅ Coincide (null solo en `INDETERMINADA`) |
| `clasificacion_calidad` | `string` | Enum 4 valores (`APTO`, `NO_APTO`, `APTO_CON_RESERVA`, `INDETERMINADA`) | ✅ Coincide |
| `apto_para_ia` | `boolean` | `boolean` | ✅ Coincide |
| `apto_para_nic41` | `boolean` | `boolean` | ✅ Coincide |
| `flags_detectados` | `object` (`dict[str, Any]`) | `object` | ✅ Coincide (escalares y visión) |
| `version_limites_fisicos_aplicada` | `string \| null` | `string \| null` | ✅ Coincide |
| `parametros_aplicados` | `object` (`dict[str, Any]`) | `object` (`k`, `M`, `N`, `umbral_drift`) | ✅ Coincide |
| `parametros_calibracion_aplicados`| `object \| null` | `object \| null` (`ganancia`, `offset`) | ✅ Coincide |
| `estado_evaluacion` | `string` | Enum 2 valores (`VIGENTE`, `SUPERADA`) | ✅ Coincide (D7 RESUELTO) |
| `motivo_reevaluacion` | `string \| null` | `string \| null` (obligatorio si `SUPERADA`) | ✅ Coincide |
| `id_evaluacion_superada` | `string (uuid) \| null` | `string (uuid) \| null` | ✅ Coincide |
| `version_evaluacion` | `string \| null` | `string \| null` | ✅ Coincide |
| `fecha_creacion` | `string (date-time) \| null`| `string (ISO-8601) \| null` | ✅ Coincide |

### Cobertura de `flags_detectados`
El schema contempla un contenedor JSONB flexible (`additionalProperties: true`), lo que da cabida a:
* **Flags escalares (telemetría estándar):** `outlier_estadistico`, `sensor_congelado`, `deriva_drift`, `ruido_excesivo`, `gap_temporal`.
* **Flags de visión por computador (cámaras AIoT):** `cobertura_baja`, `tracking_inestable`, `fps_insuficiente`, `calibracion_no_apta`, `camara_sin_senal`.

---

## 5. Precondiciones de Datos (Seeds) y Simetría con Cleanup

### Diagnóstico de Datos Reales en TEST
La consulta directa a la base de datos de pruebas arrojó:
* `modulo3.telemetria_calidad`: **18 registros existentes**.
  * `estado_evaluacion = 'VIGENTE'`: 18 registros.
  * `estado_evaluacion = 'SUPERADA'`: **0 registros**.
  * `clasificacion_calidad = 'INDETERMINADA'`: 18 registros.
  * `clasificacion_calidad IN ('APTO', 'APTO_CON_RESERVA', 'NO_APTO')`: **0 registros**.
* Distribución por sensor:
  * Sensor 1: 10 registros.
  * Sensor 53: 3 registros.
  * Sensor 7: 3 registros.
  * Sensor 3: 1 registro.
  * Sensor 31: 1 registro.

### Análisis del Script `seed_datos_tc_m03_g164.sql`
El script busca sembrar 213 registros (210 `VIGENTE` con las 4 clasificaciones y 3 `SUPERADA`), pero contiene un **defecto bloqueante de sintaxis SQL**:
```sql
-- Líneas 50-56 en seed_datos_tc_m03_g164.sql:
SELECT array_agg(s.id_sensores), array_agg(s.id_dispositivo_iot), array_agg(s.id_variable)
INTO v_sensores_arr, v_dispositivo_arr, v_variables_arr
FROM (
    SELECT DISTINCT id_sensores, id_dispositivo_iot, id_variable
    FROM modulo9.sensores
    WHERE id_dispositivo_iot IS NOT NULL AND id_variable IS NOT NULL
    LIMIT 3
) s;
```
* **Causa raíz:** En la base de datos de TEST, la tabla `modulo9.sensores` **NO tiene la columna `id_variable`** (sus columnas son `id_sensores`, `id_dispositivo_iot`, `es_activo`, `nombre`, `categoria`). La columna `id_variable` reside en `modulo3.telemetrias` o en asociaciones de variables.
* **Impacto:** Si se ejecuta, la transacción aborta con `ERROR: column "id_variable" does not exist`.

### Simetría Seed vs. Cleanup
* `seed_datos_tc_m03_g164.sql`: Marca los registros insertados con `metadatos->>'seed_id' = 'TC_M03_G164_SEED'` en `modulo3.telemetrias`.
* `cleanup_seed_tc_m03_g164.sql`:
  1. Elimina en `modulo3.telemetria_calidad` donde `id_telemetria IN (SELECT id_telemetria FROM modulo3.telemetrias WHERE metadatos->>'seed_id' = 'TC_M03_G164_SEED')`.
  2. Elimina en `modulo3.telemetrias WHERE metadatos->>'seed_id' = 'TC_M03_G164_SEED'`.
* **Evaluación Zero-Pollution:** La simetría lógica de limpieza es **100% correcta y determinista**, pero el seed no puede ejecutarse hasta corregir el query de obtención de sensores.

---

## 6. Seguridad y RBAC

1. **Requerimiento de Autenticación:** Ambos endpoints `GET /iot/calidad` y `GET /iot/calidad/{id_telemetria}` exigen cabecera `Authorization: Bearer <token_jwt>`. Si se omite, FastAPI retorna `HTTP 401 Unauthorized` (`TOKEN_INVALIDO` / `CREDENCIALES_NO_PROVISTAS`).
2. **Control de Acceso Basado en Roles (RBAC):**
   * Recurso: `38` (`calidad_telemetria`).
   * Acción: `2` (`READ` / `CONSULTAR`).
   * Dependencia en código: `dependencies=[Depends(require_permission(38, 2))]`.
3. **Verificación en Vivo por Rol:**
   * **Administrador (`administador.dev@gmail.com`)**: Autenticación exitosa $\rightarrow$ `GET /iot/calidad` responde **HTTP 200 OK**.
   * **Productor (`productor@pecuaria.co`)**: Autenticación exitosa $\rightarrow$ `GET /iot/calidad` responde **HTTP 200 OK**.
   * **Ingeniero de Campo (`ingeniero@pecuaria.co`)**: Autenticación exitosa $\rightarrow$ `GET /iot/calidad` responde **HTTP 200 OK**.
4. **Aislamiento por Tenant:**
   * La especificación original de TC-M03-301 planteaba aislamiento territorial por tenant.
   * Sin embargo, el endpoint `GET /iot/calidad` no aplica filtro por finca o usuario en la consulta a la base de datos (diseñado como catálogo de telemetría a nivel de plataforma o infraestructura asignada).
   * La colección maneja esto adecuadamente mediante una **sonda informativa** (`NW-TC-M03-301-Sonda-Tenant-Productor` e `Ingeniero`), sin aserción de rechazo.

---

## 7. Sandbox Transaccional

1. **Inyección de Encabezados:**
   * Todas las peticiones funcionales (ítems 04 al 34) inyectan:
     * `X-Test-Run-Id: {{run_id}}`
     * `X-Sandbox-Secret: {{sandbox_secret}}`
   * **[H-4 MENOR] Exclusión en Setup Login:** Las peticiones 01, 02 y 03 (`NW-00-Setup-Login-*`) **NO** inyectan `X-Test-Run-Id`, ya que `run_id` es inicializado en el script de pre-solicitud del ítem 04 (`NW-01-PreflightA-Inventario`). Aunque el login es de solo lectura y no muta el catálogo de calidad, la directiva del sandbox estipula que **todas** las peticiones deben viajar identificadas.
2. **Teardown Obligatorio (Ítem 36 - `NW-99-Teardown-Cierre-Sandbox`):**
   * Ejecuta `DELETE {{baseUrl}}/test-control/runs/{{run_id}}` con `X-Sandbox-Secret`.
   * Aserción: `pm.response.to.have.status(200)` y `pm.expect(res.status).to.equal("Rollback exitoso")`.
   * Verificado en vivo durante este diagnóstico: el backend confirma `{"status": "Rollback exitoso"}` liberando la conexión en PostgreSQL.
3. **Manejo de Expiración por Timeout:**
   * Si Newman aborta a mitad de corrida, `testing_sandbox.py` en el servidor aplica un timeout automático de 180 segundos para cerrar la transacción huérfana.
4. **Ruta y Nombre de Resultados (Cumplimiento de Scanner de QA):**
   * El runner PowerShell [ejecutar_tc_m03_g164.ps1](file:///c:/Users/Juansegutt/Integrador/sgpmp-backend/tests/Test_Testing/Test_Modulo3/RF-62/TC-M03-G164/ejecutar_tc_m03_g164.ps1#L28-L86) escribe en:
     `tests/Test_Testing/Test_Modulo3/RF-62/TC-M03-G164/resultados/resultado_TC-M03-G164.html`
   * Genera nombres incrementales `resultado_TC-M03-G164_reintento1.html` ante reintentos.
   * **Cumple con las reglas R1 a R5** de la guía y es 100% reconocible por `scanner.py`.

---

## 8. Inventario de Hallazgos y Bloqueantes (H-1 a H-8)

| ID | Tipo | Archivo Afectado / Ubicación | Descripción del Hallazgo | Acción Correctiva Requerida |
| :---: | :---: | :--- | :--- | :--- |
| **H-1** | 🔴 **BLOQUEANTE** | [build_collection.cjs:65](file:///c:/Users/Juansegutt/Integrador/sgpmp-backend/tests/Test_Testing/Test_Modulo3/RF-62/TC-M03-G164/build_collection.cjs#L65)<br>[ejecutar_tc_m03_g164.ps1:13](file:///c:/Users/Juansegutt/Integrador/sgpmp-backend/tests/Test_Testing/Test_Modulo3/RF-62/TC-M03-G164/ejecutar_tc_m03_g164.ps1#L13)<br>[.env.test:10](file:///c:/Users/Juansegutt/Integrador/sgpmp-backend/.env.test#L10) | URL desactualizada `https://api.inmero.co/[host-antiguo-obsoleto]` configurada como default. Responde 404. | Cambiar el valor por defecto a `https://api.inmero.co/api-sgpmp-test` en los 3 archivos. |
| **H-2** | 🔴 **BLOQUEANTE** | [seed_datos_tc_m03_g164.sql:50-56](file:///c:/Users/Juansegutt/Integrador/sgpmp-backend/tests/Test_Testing/Test_Modulo3/RF-62/TC-M03-G164/seed_datos_tc_m03_g164.sql#L50-L56) | Consulta a columna inexistente `id_variable` en `modulo9.sensores`. | Modificar el query para obtener `id_sensores` y `id_dispositivo_iot` de `modulo9.sensores`, y vincular `id_variable` mediante `JOIN` con la tabla de variables o seleccionando un `id_variable` válido de `modulo9.variables_ambientales`. |
| **H-3** | 🔴 **BLOQUEANTE** | Base de datos TEST (`modulo3.telemetria_calidad`) | Ausencia de evaluaciones en estado `SUPERADA` (0 registros) y clasificaciones `APTO`/`NO_APTO`/`APTO_CON_RESERVA`. | En modo `existentes`, TC-307 y TC-305 sufren omisiones. Se debe habilitar la ruta dinámica de `POST /iot/calidad/reevaluar` en sandbox (ítem NW-02) o ejecutar el seed corregido. |
| **H-4** | 🟡 **MENOR** | [build_collection.cjs:154-209](file:///c:/Users/Juansegutt/Integrador/sgpmp-backend/tests/Test_Testing/Test_Modulo3/RF-62/TC-M03-G164/build_collection.cjs#L154-L209) | Los ítems de Setup Login (NW-00-Setup-Login-*) no envían `X-Test-Run-Id` ni `X-Sandbox-Secret` porque `run_id` se crea en el ítem 04. | Mover la generación de `run_id` al Pre-request script de la colección (a nivel global) para que el login también viaje con el header del sandbox. |
| **H-5** | 🟡 **MENOR** | Backend: [calidad_router.py:52-54](file:///c:/Users/Juansegutt/Integrador/sgpmp-backend/src/telemetry/infrastructure/routers/calidad_router.py#L52-L54) | La API no valida el enum de `clasificacion` ni la coherencia cronológica `fecha_desde <= fecha_hasta`; ante valores inválidos responde HTTP 200 con `total: 0`. | En la colección ya se mitiga con aserción dual: valida que no rompa el servidor (`200` o `4xx`), pero debe quedar registrado como deuda técnica del backend. |
| **H-6** | 🟡 **MENOR** | [ejecutar_tc_m03_g164.ps1:89-108](file:///c:/Users/Juansegutt/Integrador/sgpmp-backend/tests/Test_Testing/Test_Modulo3/RF-62/TC-M03-G164/ejecutar_tc_m03_g164.ps1#L89-L108) | Si Newman se cancela bruscamente (Ctrl+C o fallo de nodo), PowerShell no invoca el teardown `DELETE /test-control/runs/{run_id}`. | Envolver la ejecución en un bloque `try { ... } finally { ... }` en PowerShell que invoque el `DELETE` de respaldo. |
| **H-7** | 🟢 **INFORMATIVO** | Decisión D7 (Ciclo de Vida) | La ficha histórica mencionaba `ACTIVA`/`SUPERADA`. | Se verificó que `build_collection.cjs` ya implementa exclusivamente `VIGENTE` y `SUPERADA` (D7 RESUELTO). |
| **H-8** | 🟢 **INFORMATIVO** | Aserción de no repetidos en paginación | En conjuntos paginados con timestamps idénticos, la no repetición no es determinista sin criterio de desempate por ID. | La colección ya incluye la guarda de desempate L5 / M12 emitiendo `OBS-DETERMINISMO` sin fallar. |

---

## 9. Recomendación del Siguiente Paso (Prompt #2)

Para dejar la suite en estado **100% EJECUTABLE y confiable**:

1. **Corregir H-1**: Actualizar la URL base a `https://api.inmero.co/api-sgpmp-test` en `build_collection.cjs`, `ejecutar_tc_m03_g164.ps1` y `.env.test`.
2. **Corregir H-2**: Reparar el script SQL [seed_datos_tc_m03_g164.sql](file:///c:/Users/Juansegutt/Integrador/sgpmp-backend/tests/Test_Testing/Test_Modulo3/RF-62/TC-M03-G164/seed_datos_tc_m03_g164.sql) asociando `id_variable` de forma válida desde el catálogo maestro.
3. **Corregir H-4**: Elevar la generación de `run_id` a nivel de colección para que cubra los requests de Setup Login.
4. **Regenerar la colección**: Ejecutar `node build_collection.cjs` para actualizar [test_tc_m03_g164.json](file:///c:/Users/Juansegutt/Integrador/sgpmp-backend/tests/Test_Testing/Test_Modulo3/RF-62/TC-M03-G164/test_tc_m03_g164.json).
5. **Re-verificar con el scanner**: Comprobar estáticamente antes de la corrida oficial.

---

## 10. FASE 0 — Ampliación Técnica Detallada (Sub-pasos 0.8 a 0.14)

### 0.8 Schema CalidadEvaluacion — Desglose de Campos (G-1, G-2, G-3, G-10)
En OpenAPI TEST (`openapi_test_snapshot.json`), el esquema conceptual `CalidadEvaluacion` está definido bajo `components.schemas.TelemetriaCalidadSchema`.

Contraste 1:1 de los 17 campos requeridos:

| Campo Exigido | Tipo en OpenAPI TEST | Path en OpenAPI / Definición Exacta | Nullable | Estado / Cumplimiento |
| :--- | :--- | :--- | :---: | :---: |
| `flags_detectados` | `object` (`JSONB`) | `components.schemas.TelemetriaCalidadSchema.properties.flags_detectados` (`{"additionalProperties": true, "type": "object"}`) | No | ✅ **PRESENTE**. Es un objeto JSONB anidado extensible. Contempla flags escalares y de visión: `cobertura_baja`, `tracking_inestable`, `fps_insuficiente`, `calibracion_no_apta`, `camara_sin_senal`, `outlier_estadistico`, `sensor_congelado`, `posible_drift`, `gap_temporal_anomalo`, `serie_insuficiente`. |
| `version_limites_fisicos_aplicada` | `string \| null` | `components.schemas.TelemetriaCalidadSchema.properties.version_limites_fisicos_aplicada` (`{"anyOf": [{"type": "string"}, {"type": "null"}]}`) | Sí | ✅ **PRESENTE** |
| `parametros_aplicados` | `object` (`JSONB`) | `components.schemas.TelemetriaCalidadSchema.properties.parametros_aplicados` (`{"additionalProperties": true, "type": "object"}`) | No | ✅ **PRESENTE** |
| `parametros_calibracion_aplicados` | `object \| null` (`JSONB`) | `components.schemas.TelemetriaCalidadSchema.properties.parametros_calibracion_aplicados` (`{"anyOf": [{"additionalProperties": true, "type": "object"}, {"type": "null"}]}`) | Sí | ✅ **PRESENTE** |
| `version_evaluacion` | `string \| null` | `components.schemas.TelemetriaCalidadSchema.properties.version_evaluacion` (`{"anyOf": [{"type": "string"}, {"type": "null"}]}`) | Sí | ✅ **PRESENTE** |
| `estado_evaluacion` | `string` | `components.schemas.TelemetriaCalidadSchema.properties.estado_evaluacion` (`{"type": "string"}`). En DB y dominio: Enum `{'VIGENTE', 'SUPERADA'}`. | No | ✅ **PRESENTE** (D7 RESUELTO) |
| `motivo_reevaluacion` | `string \| null` | `components.schemas.TelemetriaCalidadSchema.properties.motivo_reevaluacion` (`{"anyOf": [{"type": "string"}, {"type": "null"}]}`) | Sí | ✅ **PRESENTE** (Obligatorio cuando `estado_evaluacion = 'SUPERADA'`) |
| `id_evaluacion_superada` | `string (uuid) \| null` | `components.schemas.TelemetriaCalidadSchema.properties.id_evaluacion_superada` (`{"anyOf": [{"type": "string", "format": "uuid"}, {"type": "null"}]}`). En DB es FK hacia `modulo3.telemetria_calidad(id_evaluacion)`. | Sí | ✅ **PRESENTE** (FK verificada en constraints de DB) |
| `clasificacion_calidad` | `string` | `components.schemas.TelemetriaCalidadSchema.properties.clasificacion_calidad` (`{"type": "string"}`). En dominio: Enum `{'APTO', 'APTO_CON_RESERVA', 'NO_APTO', 'INDETERMINADA'}`. | No | ✅ **PRESENTE** |
| `indice_calidad` | `integer \| null` | `components.schemas.TelemetriaCalidadSchema.properties.indice_calidad` (`{"anyOf": [{"type": "integer"}, {"type": "null"}]}`) | Sí | ✅ **PRESENTE** (null solo si `clasificacion_calidad == 'INDETERMINADA'`) |
| `timestamp_evaluacion` | `string (date-time)` | `components.schemas.TelemetriaCalidadSchema.properties.timestamp_evaluacion` (`{"type": "string", "format": "date-time"}`) | No | ✅ **PRESENTE** |
| `id_evaluacion` | `string (uuid)` | `components.schemas.TelemetriaCalidadSchema.properties.id_evaluacion` (`{"type": "string", "format": "uuid"}`) | No | ✅ **PRESENTE** |
| `id_telemetria` | `integer` | `components.schemas.TelemetriaCalidadSchema.properties.id_telemetria` (`{"type": "integer"}`) | No | ✅ **PRESENTE** |
| `id_sensor` | `integer` | `components.schemas.TelemetriaCalidadSchema.properties.id_sensor` (`{"type": "integer"}`) | No | ✅ **PRESENTE** |
| `apto_para_ia` | `boolean` | `components.schemas.TelemetriaCalidadSchema.properties.apto_para_ia` (`{"type": "boolean"}`) | No | ✅ **PRESENTE** |
| `apto_para_nic41` | `boolean` | `components.schemas.TelemetriaCalidadSchema.properties.apto_para_nic41` (`{"type": "boolean"}`) | No | ✅ **PRESENTE** |
| `fecha_creacion` | `string (date-time) \| null` | `components.schemas.TelemetriaCalidadSchema.properties.fecha_creacion` (`{"anyOf": [{"type": "string", "format": "date-time"}, {"type": "null"}]}`) | Sí | ✅ **PRESENTE** |

* **Veredicto 0.8:** ✅ **TODOS LOS 17 CAMPOS ESTÁN PRESENTES EN OPENAPI**. Cero ausencias. No hay bloqueo de contrato en este punto.

---

### 0.9 Schema del Response de `GET /iot/calidad` (G-8)
En OpenAPI TEST (`components.schemas.ListaCalidadSchema`):
```json
{
  "properties": {
    "total": { "type": "integer", "title": "Total" },
    "pagina": { "type": "integer", "title": "Pagina" },
    "por_pagina": { "type": "integer", "title": "Por Pagina" },
    "items": {
      "items": { "$ref": "#/components/schemas/TelemetriaCalidadSchema" },
      "type": "array",
      "title": "Items"
    }
  },
  "type": "object",
  "required": ["total", "pagina", "por_pagina", "items"],
  "title": "ListaCalidadSchema"
}
```
* **Veredicto 0.9:** ✅ **CONFORME**. Los 4 nombres son exactamente `total`, `pagina`, `por_pagina` e `items`. No existen discrepancias de envoltura (`data`, `results` o `evaluaciones`). Las aserciones de la colección coinciden exactamente con la respuesta.

---

### 0.10 Tipos de `fecha_desde` / `fecha_hasta` (G-9)
En OpenAPI TEST (`paths['/iot/calidad'].get.parameters`):
* `fecha_desde`: `in: query`, schema: `{"anyOf": [{"type": "string", "format": "date-time"}, {"type": "null"}]}`.
* `fecha_hasta`: `in: query`, schema: `{"anyOf": [{"type": "string", "format": "date-time"}, {"type": "null"}]}`.
* **Formato en Colección:** [build_collection.cjs](file:///c:/Users/Juansegutt/Integrador/sgpmp-backend/tests/Test_Testing/Test_Modulo3/RF-62/TC-M03-G164/build_collection.cjs) toma `fecha_desde_sample` y `fecha_hasta_sample` de timestamps reales devueltos por el backend en formato ISO-8601 con zona horaria UTC (`Z` o `+00:00`, ej. `2026-10-08T17:14:04.444590Z`). Para el subcaso de offset Bogotá, convierte explícitamente a `-05:00` usando `.toISOString().replace("Z", "-05:00")`.
* **Veredicto 0.10:** ✅ **CONFORME**. Se utiliza siempre ISO-8601 con timezone explícito, nunca timestamps "naive".

---

### 0.11 Aislamiento Tenant / Usuario (G-4)
Ejecución en PostgreSQL TEST (`modulo3.telemetria_calidad`):
```sql
SELECT column_name, data_type FROM information_schema.columns 
WHERE table_schema='modulo3' AND table_name='telemetria_calidad';
```
* **Columnas detectadas:** `id_evaluacion`, `id_telemetria`, `id_sensor`, `timestamp_evaluacion`, `indice_calidad`, `clasificacion_calidad`, `apto_para_ia`, `apto_para_nic41`, `flags_detectados`, `version_limites_fisicos_aplicada`, `parametros_aplicados`, `parametros_calibracion_aplicados`, `estado_evaluacion`, `motivo_reevaluacion`, `id_evaluacion_superada`, `version_evaluacion`, `fecha_creacion`.
* **Hallazgo:** **NO existe columna de tenant** (`id_finca`, `id_usuario`, `id_tenant` ni `propietario`) en `modulo3.telemetria_calidad`.
* **Inspección en Router ([calidad_router.py:42-79](file:///c:/Users/Juansegutt/Integrador/sgpmp-backend/src/telemetry/infrastructure/routers/calidad_router.py#L42-L79)):** `ConsultarCalidadUseCase.listar` no recibe `usuario_actual` ni filtra por finca/usuario. Todos los usuarios con permiso RBAC `(38, 2)` (incluidos Productor e Ingeniero) ven el mismo catálogo de evaluaciones.
* **Veredicto 0.11:** ✅ **CONFORME A DISEÑO DE COLECCIÓN**. La colección ya contempló esto en la corrección **C3** mediante sondas informativas (`NW-TC-M03-301-Sonda-Tenant-Productor` e `Ingeniero`), registrando en consola `OBS-TENANT` sin aserción de fallo.

---

### 0.12 Orden DESC Verificable (G-7)
Ejecución en PostgreSQL TEST (`modulo3.telemetria_calidad`):
```sql
SELECT timestamp_evaluacion FROM modulo3.telemetria_calidad 
ORDER BY timestamp_evaluacion DESC LIMIT 5;
```
* **Resultado obtenido en vivo:**
  1. `2026-10-08T17:14:04.444590+00:00`
  2. `2026-10-08T17:12:26.639363+00:00`
  3. `2026-10-08T17:12:26.020591+00:00`
  4. `2026-10-08T06:37:20.445841+00:00`
  5. `2026-10-08T06:37:19.772076+00:00`
* **Conteo global:** De los 18 registros en la base de datos TEST, existen **18 timestamps distintos** (`distinct_ts = 18`).
* **Veredicto 0.12:** ✅ **CONFORME**. Hay más de 3 timestamps estrictamente decrecientes en los datos existentes, por lo que la precondición de orden descendente es plenamente verificable en el entorno TEST.

---

### 0.13 Frontera `desde == hasta` (G-5)
Inspección en [build_collection.cjs:1067-1097](file:///c:/Users/Juansegutt/Integrador/sgpmp-backend/tests/Test_Testing/Test_Modulo3/RF-62/TC-M03-G164/build_collection.cjs#L1067-L1097):
* El ítem 23 de la colección es **`NW-TC-M03-306-Frontera-Exacta`**.
* URL enviada: `{{baseUrl}}/iot/calidad?fecha_desde={{fecha_exacta_sample}}&fecha_hasta={{fecha_exacta_sample}}`.
* Aserciones: Verifica que `res.total` sea igual al oráculo para ese timestamp, que `res.items.length >= 1`, y que cada `it.timestamp_evaluacion === fecha_exacta_sample`.
* **Veredicto 0.13:** ✅ **PRESENTE Y CONFORME**. Ya existe el subcaso exacto de frontera idéntica en la colección; no requiere ser agregado en Fase 3.

---

### 0.14 Endpoint Real de Reevaluación (G-6)
Búsqueda de patrones `evaluar` y `reevaluar` en los paths de OpenAPI TEST (`openapi_test_snapshot.json`):
1. **`POST /iot/calidad/{id_telemetria}/evaluar`**:
   * Summary: `"Disparar evaluación de calidad puntual (RF-62)"`
   * Path param: **`id_telemetria`** (entero). *Nota: NO es `{id}` conceptual.*
2. **`POST /iot/calidad/reevaluar`**:
   * Summary: `"Re-evaluación explícita ante error de configuración (FA-08)"`
   * Body: `SolicitarReevaluacionDTO` (`id_sensor`, `fecha_desde`, `fecha_hasta`, `causa_documentada`, `parametros_correctos`).
* **Veredicto 0.14:** ✅ **IDENTIFICADO**. Para reevaluación por lote/rango el endpoint canónico es **`POST /iot/calidad/reevaluar`** (FA-08). Para evaluación puntual es **`POST /iot/calidad/{id_telemetria}/evaluar`**. Esto aclara y despeja la arquitectura para la ejecución de G164 (ítem NW-02), G165 y G166.

---

### F-5 Ampliaciones por FASE 0 Aplicadas al Seed y Cleanup

En cumplimiento estricto de las directivas **F-5a (HG-5)**, **F-5b (HG-6)** y **F-5c (HG-7)**, se actualizaron [seed_datos_tc_m03_g164.sql](file:///c:/Users/Juansegutt/Integrador/sgpmp-backend/tests/Test_Testing/Test_Modulo3/RF-62/TC-M03-G164/seed_datos_tc_m03_g164.sql) y [cleanup_seed_tc_m03_g164.sql](file:///c:/Users/Juansegutt/Integrador/sgpmp-backend/tests/Test_Testing/Test_Modulo3/RF-62/TC-M03-G164/cleanup_seed_tc_m03_g164.sql):

1. **F-5a (HG-5) — Generación estricta de UUIDs**:
   * Se parametrizaron explícitamente `id_evaluacion` e `id_evaluacion_superada` con UUIDs válidos usando la función nativa `gen_random_uuid()` (formato canónico 8-4-4-4-12).
   * Se descartan completamente enteros o identificadores no conformes con el tipo `uuid` de PostgreSQL y la entidad `TelemetriaCalidad`.

2. **F-5b (HG-6) — Coherencia estricta de `indice_calidad`**:
   * Tras verificar las reglas de dominio en [telemetria_calidad.py:65-81](file:///c:/Users/Juansegutt/Integrador/sgpmp-backend/src/telemetry/domain/entities/telemetria_calidad.py#L65-L81) y los umbrales de la colección en [build_collection.cjs:12-16](file:///c:/Users/Juansegutt/Integrador/sgpmp-backend/tests/Test_Testing/Test_Modulo3/RF-62/TC-M03-G164/build_collection.cjs#L12-L16) (`apto: 80, reserva: 40, reserva_max: 79`), se establecieron valores deterministas que satisfacen ambas especificaciones:
     * **`APTO`**: `indice_calidad = 95` ($\ge 90$ y $\ge 80$), `apto_para_ia = true`, `apto_para_nic41 = true`, `flags = {}`.
     * **`APTO_CON_RESERVA`**: `indice_calidad = 75` ($70 \le 75 < 90$ y $40 \le 75 \le 79$), `apto_para_ia = true`, `apto_para_nic41 = false`, flag `outlier_estadistico`.
     * **`NO_APTO`**: `indice_calidad = 25` ($< 70$ y $< 40$), `apto_para_ia = false`, `apto_para_nic41 = false`, flag `sensor_congelado`.
     * **`INDETERMINADA`**: `indice_calidad = NULL`, `apto_para_ia = false`, `apto_para_nic41 = false`, flag `serie_insuficiente`.
   * Con esto, las aserciones de [TC-M03-302](file:///c:/Users/Juansegutt/Integrador/sgpmp-backend/tests/Test_Testing/Test_Modulo3/RF-62/TC-M03-G164/build_collection.cjs#L665-L682) y [TC-M03-305](file:///c:/Users/Juansegutt/Integrador/sgpmp-backend/tests/Test_Testing/Test_Modulo3/RF-62/TC-M03-G164/build_collection.cjs#L816-L950) se validan sin falsos negativos.

3. **F-5c (HG-7) — Evaluaciones `SUPERADA` con FK válida del MISMO sensor**:
   * Para cada uno de los 3 sensores seleccionados, el script siembra primero una evaluación base `VIGENTE` determinista y captura su `v_id_eval_base` (UUID).
   * Acto seguido, inserta el registro `SUPERADA` configurando:
     * `id_evaluacion = gen_random_uuid()`
     * `id_sensor = v_sensor_id` (mismo sensor)
     * `id_evaluacion_superada = v_id_eval_base` (referencia foránea válida a la evaluación base previa)
     * `motivo_reevaluacion = 'Re-evaluación zootécnica documentada: actualización de parámetros y umbrales'` (no nulo ni vacío)
     * `estado_evaluacion = 'SUPERADA'`

4. **Resolución de Bloqueo RLS y Columna Inexistente en `modulo9.sensores`**:
   * El seed original intentaba consultar `id_variable` en `modulo9.sensores` (columna inexistente) y fallaba por RLS (`rowsecurity: true`). Se actualizó para derivar las 3 ternas `(id_sensor, id_dispositivo_iot, id_variable)` dinámicamente de `modulo3.telemetrias`, garantizando existencia de claves foráneas e inmunidad a políticas de seguridad por fila.

5. **Robustez en Limpieza (`cleanup_seed_tc_m03_g164.sql`)**:
   * Se agregó un paso previo que ejecuta `UPDATE modulo3.telemetria_calidad SET id_evaluacion_superada = NULL` para romper la auto-referencia foránea antes del `DELETE`, asegurando que la limpieza nunca aborte por restricción de clave foránea.

