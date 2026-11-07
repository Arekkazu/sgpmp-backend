# INFORME DE RESULTADOS DE PRUEBAS DE ACEPTACIÓN
## CASO AGRUPADO: TC-M02-G73 (RF-46: Historial de Eventos del Activo Biológico)

- **Fecha de Ejecución:** 2026-09-09
- **Entorno Objetivo:** TEST (`https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test`)
- **Herramienta:** Newman CLI v6.2.2 + Reporter `htmlextra`
- **Colección Ejecutada:** `tests/Test_Testing/Test_Modulo2/RF-46/TC-M02-G73/test_tc_m02_g73.json`
- **Reporte HTML Generado:** `tests/Test_Testing/Test_Modulo2/RF-46/TC-M02-G73/RESULTADOS/reporte_TC-M02-G73.html`
- **Veredicto Global:** **PASS (100% DE PRUEBAS SUPERADAS — 11/11 ASERCIONES APROBADAS)**

---

## 1. Resumen Ejecutivo de Resultados

El caso agrupado **TC-M02-G73** evalúa la robustez del endpoint `GET /activos-biologicos/{id_activo}/historial` (correspondiente a **RF-46 / CU10A**) ante el envío de parámetros inválidos y recursos inexistentes. La ejecución unificada procesó exitosamente las dos condiciones de prueba en una sola pasada:

| Subcaso | Descripción de la Prueba | Resultado Esperado | Resultado Obtenido | Tiempo Resp. | Veredicto |
| :--- | :--- | :--- | :--- | :---: | :---: |
| **00 - Auth** | Autenticación del usuario Administrador | HTTP 200 OK con JWT válido | `HTTP 200 OK` (Token emitido) | 831 ms | **PASS** |
| **TC-M02-120** | Rechazar rango de fechas invertido (`fecha_inicio > fecha_fin`) | HTTP 400/422, código `PARAMETROS_INVALIDOS`, mensaje indicando que fecha_inicio no puede ser posterior a fecha_fin | `HTTP 400 Bad Request`, `PARAMETROS_INVALIDOS`, *"La fecha de inicio (2025-01-01) no puede ser posterior a la fecha de fin (2024-01-01)."* | 116 ms | **PASS** |
| **TC-M02-122** | Rechazar consulta de activo inexistente (`id_activo = 999999`) | HTTP 404 Not Found, código `ACTIVO_NO_ENCONTRADO`, mensaje indicando activo no encontrado | `HTTP 404 Not Found`, `ACTIVO_NO_ENCONTRADO`, *"El activo biológico con id 999999 no fue encontrado en el sistema."* | 111 ms | **PASS** |

---

## 2. Métricas Generales de la Ejecución

| Métrica | Valor |
| :--- | :--- |
| **Iteraciones ejecutadas** | 1 |
| **Total de peticiones HTTP** | 3 (1 Auth + 2 Validaciones) |
| **Total de aserciones evaluadas** | 11 |
| **Aserciones aprobadas** | 11 (100%) |
| **Aserciones fallidas** | 0 (0%) |
| **Duración total de la ejecución** | 1.34 segundos |
| **Tiempo de respuesta promedio** | 352 ms (Mínimo: 111 ms, Máximo: 831 ms) |
| **Datos transferidos** | ~1.05 KB |

---

## 3. Detalle Técnico por Subcaso

### 3.1. Subcaso TC-M02-120: Rechazar rango de fechas invertido

- **Endpoint Evaluado:** `GET /activos-biologicos/130/historial?fecha_inicio=2025-01-01&fecha_fin=2024-01-01`
- **Código HTTP Obtenido:** `400 Bad Request`
- **Cabeceras Relevantes:**
  - `Content-Type: application/json`
  - `Authorization: Bearer <jwt_token>`
- **Cuerpo de Respuesta Obtenido:**
  ```json
  {
    "error_code": "PARAMETROS_INVALIDOS",
    "message": "La fecha de inicio (2025-01-01) no puede ser posterior a la fecha de fin (2024-01-01).",
    "fields": [],
    "timestamp": "2026-09-09T20:32:48.336125Z"
  }
  ```
- **Aserciones Evaluadas y Superadas:**
  1. `[TC-M02-120] Código de respuesta HTTP debe ser 400 Bad Request o 422 Unprocessable Entity` -> **PASS**
  2. `[TC-M02-120] Estructura estándar de ErrorResponse (error_code, message, timestamp)` -> **PASS**
  3. `[TC-M02-120] Código de error interno es PARAMETROS_INVALIDOS o E-03` -> **PASS**
  4. `[TC-M02-120] Mensaje de error indica que fecha_inicio no puede ser posterior a fecha_fin` -> **PASS**
  5. `[TC-M02-120] Tiempo de respuesta inferior a 1500ms (116 ms)` -> **PASS**

---

### 3.2. Subcaso TC-M02-122: Rechazar consulta de activo inexistente

- **Endpoint Evaluado:** `GET /activos-biologicos/999999/historial`
- **Código HTTP Obtenido:** `404 Not Found`
- **Cabeceras Relevantes:**
  - `Content-Type: application/json`
  - `Authorization: Bearer <jwt_token>`
- **Cuerpo de Respuesta Obtenido:**
  ```json
  {
    "error_code": "ACTIVO_NO_ENCONTRADO",
    "message": "El activo biológico con id 999999 no fue encontrado en el sistema.",
    "fields": [],
    "timestamp": "2026-09-09T20:32:48.448552Z"
  }
  ```
- **Aserciones Evaluadas y Superadas:**
  1. `[TC-M02-122] Código de respuesta HTTP debe ser 404 Not Found` -> **PASS**
  2. `[TC-M02-122] Estructura estándar de ErrorResponse (error_code, message, timestamp)` -> **PASS**
  3. `[TC-M02-122] Código de error interno es ACTIVO_NO_ENCONTRADO o E-01` -> **PASS**
  4. `[TC-M02-122] Mensaje de error indica que el activo 999999 no existe o no fue encontrado` -> **PASS**
  5. `[TC-M02-122] Tiempo de respuesta inferior a 1500ms (111 ms)` -> **PASS**

---

## 4. Hallazgos Técnicos y Arquitectónicos

1. **Alineación con el Modelo de Dominio:**  
   El validador en Pydantic (`ConsultarHistorialDTO`) intercepta oportunamente la inconsistencia de fechas antes de consultar la base de datos, optimizando recursos y evitando lecturas innecesarias.
2. **Estandarización del Esquema `ErrorResponse`:**  
   Ambas respuestas siguen fielmente el contrato canónico definido en `src/shared/schemas.py`, retornando `error_code`, `message`, `fields` y `timestamp` en formato UTC ISO 8601.
3. **Resiliencia de la API:**  
   En ningún escenario se generaron excepciones no controladas (HTTP 500) ni se filtraron trazas de base de datos PostgreSQL, garantizando la seguridad y robustez del backend.

---

## 5. Conclusión y Veredicto Final

El caso agrupado **TC-M02-G73** cumple satisfactoriamente con todos los criterios de aceptación definidos para el **RF-46**.  
**Veredicto Final:** **PASS**.
