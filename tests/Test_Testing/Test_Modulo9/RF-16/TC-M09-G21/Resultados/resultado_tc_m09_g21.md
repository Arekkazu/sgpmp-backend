# Reporte de Ejecución: TC-M09-G21 (Prueba de Rendimiento sobre RF-16)

## 1. Ficha Técnica del Caso de Prueba

* **ID del Caso / Grupo:** TC-M09-G21 (sub-caso TC-M09-45)
* **Nombre:** Medición del tiempo de respuesta del catálogo de configuración por especie (Etapas, Patologías y Métricas)
* **Módulo / Requisito:** Módulo 9 (Configuración / Parámetros Generales) / RF-16 (CU-02 — Requisito No Funcional)
* **Tipo de Prueba:** Rendimiento / Tiempo de Respuesta / Desglose Individual por Endpoint (k6 `Trend`)
* **Herramienta Utilizada:** `k6` v2.2.0 (`GrafanaLabs.k6` en Windows CLI)
* **Entorno de Ejecución:** TEST (`https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test/`)
* **Perfil de Carga:** 1 VU (Usuario Virtual), ejecución secuencial, 10 iteraciones compartidas (31 peticiones HTTP totales: 10 por endpoint + 1 setup login)
* **Especie Fixture Evaluada:** ID `4` (*Cachama Blanca*, especie activa con catálogo poblado)
* **Umbral Exigido:** Tiempo de respuesta `p(95) < 2000 ms` (2.0 segundos) por endpoint
* **Resultado Global:** 🟢 **ÉXITO TOTAL / CUMPLIMIENTO SLA DE RENDIMIENTO (100% checks PASSED - 61/61, 31/31 requests HTTP 200 OK, p95 individual entre 121.16 ms y 124.91 ms)**

---

## 2. Resumen de Medición Desglosada por Sub-caso / Endpoint (`k6 Trend`)

| Sub-caso ID | Endpoint / Catálogo Consultado | Método HTTP | Muestra (Reqs) | p95 Medido (ms) | p100 / Máx Medido (ms) | Promedio `avg` (ms) | Umbral Exigido (p95) | Veredicto |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **TC-M09-45-A** | `/configuracion/ciclos?id_especie=4` | GET | 10 | **121.16 ms** | **122.58 ms** | 114.61 ms | < 2000.00 ms (2.0s) | 🟢 PASSED (OK) |
| **TC-M09-45-B** | `/configuracion/patologias?id_especie=4` | GET | 10 | **124.91 ms** | **130.29 ms** | 113.38 ms | < 2000.00 ms (2.0s) | 🟢 PASSED (OK) |
| **TC-M09-45-C** | `/configuracion/metricas?id_especie=4` | GET | 10 | **121.20 ms** | **123.05 ms** | 114.39 ms | < 2000.00 ms (2.0s) | 🟢 PASSED (OK) |

> **Nota de Precisión:** La medición utiliza métricas de tendencia personalizadas de k6 (`Trend('duracion_ciclos')`, `Trend('duracion_patologias')`, `Trend('duracion_metricas')`), garantizando un desglose estadístico exacto e independiente para cada uno de los 3 endpoints del RF-16.

---

## 3. Métricas Estadísticas Globales de Rendimiento (k6 Output)

* **Checks Totales Ejecutados:** 61/61 (100.00% exitosos, 0.00% fallos).
* **Peticiones HTTP Totales:** 31 (1 autenticación Admin en `setup()` + 30 consultas de catálogo).
* **Tasa de Errores HTTP (`http_req_failed`):** `0.00%` (0 de 31 peticiones fallidas).
* **Métrica Global HTTP (`http_req_duration` - incluyendo setup):**
  * **Mínimo (`min`):** `101.98 ms`
  * **Mediana (`med`):** `114.53 ms`
  * **Promedio (`avg`):** `123.31 ms`
  * **Percentil 90 (`p90`):** `122.57 ms`
  * **Percentil 95 (`p95`):** `126.67 ms`
  * **Máximo (`p100` / `max`):** `398.96 ms` (correspondiente al request inicial de login Admin en `setup()`).
* **Duración Promedio de Iteración Completa (3 Endpoints):** `365.39 ms` (0.365 s).

---

## 4. Análisis Arquitectónico y Conclusión

1. **Homogeneidad y Desempeño Excelente de la Capa de Consulta:**  
   Los tres endpoints presentaron una latencia idénticamente óptima: `GET /ciclos` (p95: 121.16 ms), `GET /patologias` (p95: 124.91 ms) y `GET /metricas` (p95: 121.20 ms). Ningún endpoint se alejó del comportamiento general.
2. **Cumplimiento Holgado del Requisito No Funcional:**  
   Todos los percentiles p95 y máximos absolutos (p100 <= 130.29 ms en catálogo) se ubican **más de 15 veces por debajo del límite de 2000 ms** (2.0 s) exigido por el criterio de aceptación del RF-16.
3. **Estabilidad del Entorno TEST:**  
   31/31 peticiones HTTP respondieron `HTTP 200 OK` con 0.00% de errores o degradación.

---

## 5. Artefactos Generados

* Script de Rendimiento k6 (con Trends): [`test_tc_m09_g21.js`](file:///c:/Users/Juansegutt/Integrador/sgpmp-backend/tests/Test_Testing/Test_Modulo9/RF-16/TC-M09-G21/test_tc_m09_g21.js)
* Resumen Exportado JSON: [`resultado_tc_m09_g21.json`](file:///c:/Users/Juansegutt/Integrador/sgpmp-backend/tests/Test_Testing/Test_Modulo9/RF-16/TC-M09-G21/Resultados/resultado_tc_m09_g21.json)
* Resumen Markdown: [`resultado_tc_m09_g21.md`](file:///c:/Users/Juansegutt/Integrador/sgpmp-backend/tests/Test_Testing/Test_Modulo9/RF-16/TC-M09-G21/Resultados/resultado_tc_m09_g21.md)
* Guía General de Pruebas: [`GUIA_PRUEBAS_Y_ESTRUCTURA.md`](file:///c:/Users/Juansegutt/Integrador/sgpmp-backend/GUIA_PRUEBAS_Y_ESTRUCTURA.md)
