# Reporte de Rendimiento - TC-M09-G09 (Sub-caso TC-M09-19)

## 📌 Ficha de la Prueba de Rendimiento
* **ID Caso**: TC-M09-G09
* **Sub-caso**: TC-M09-19
* **Nombre**: Rendimiento de la consulta del catálogo de especies
* **Tipo**: Rendimiento (1 Petición / 1 VU)
* **Requisito Funcional**: RF-15 (Catálogo de Especies Productivas / CU-01)
* **Endpoint Evaluado**: `GET /configuracion/especies`
* **Entorno**: TEST (`https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test/`)
* **Script k6**: [`tests/Test_Testing/Test_Modulo9/RF-15/TC-M09-G09/test_tc_m09_g09.js`](file:///c:/Users/Juansegutt/Integrador/sgpmp-backend/tests/Test_Testing/Test_Modulo9/RF-15/TC-M09-G09/test_tc_m09_g09.js)

---

## 📊 Medición de Rendimiento Obtenida

| Métrica | Valor Medido | Umbral de Aceptación | Estado / Veredicto |
| :--- | :--- | :--- | :--- |
| **Tiempo de Respuesta (`http_req_duration`)** | **751.91 ms** (0.752 s) | < 2000.00 ms (2.0 s) | **PASSED (OK)** |
| **Código HTTP de Respuesta** | **200** | HTTP 200 OK | **OK** |
| **Total de Especies Retornadas** | **7** | N/A | **Completado** |

---

## 🔍 Conclusión y Veredicto Final

* **Veredicto Final**: **OK**
* **Observación Técnica**: La consulta del catálogo de especies (`GET /configuracion/especies`) respondió en **751.91 ms**, ubicándose holgadamente por debajo del umbral máximo de 2000 ms exigido por el criterio de aceptación del RF-15.
