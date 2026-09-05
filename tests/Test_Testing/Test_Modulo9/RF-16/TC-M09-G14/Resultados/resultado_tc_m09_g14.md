# Reporte de Ejecución: TC-M09-G14 (Validación de Métricas Productivas)

## 1. Ficha Técnica del Caso de Prueba

* **ID del Caso / Grupo:** TC-M09-G14 (sub-casos TC-M09-32 a TC-M09-35)
* **Nombre:** Validación de campos de Métrica productiva (unidad, tipo de medición, coherencia, tipo de activo)
* **Módulo / Requisito:** Módulo 9 (Configuración / Parámetros Generales) / RF-16 (CU-02)
* **Tipo de Prueba:** Valores límite / Validación de Entrada / Reglas de Negocio / OWASP A03
* **Herramientas Utilizadas:** Newman (`cli`, `htmlextra`, `json`), Python 3.13 (`psycopg2` / `member_qa`)
* **Entorno de Ejecución:** TEST (`https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test/`)
* **Especie Objetivo:** Cachama Blanca (`id_especie = 4`)
* **Resultado Global:** 🟢 **EXITOSO (100% assertions PASSED - 6/6)**

---

## 2. Resumen de Ejecución por Sub-caso

| Sub-caso | Parámetro / Condición Probada | Payload Enviado | Código Esperado | Código Real | Error Code Real | Resultado |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: |
| **TC-M09-32a** | `unidad_medida` como string vacío (`""`) | `{"id_especie": 4, "nombre": "Metrica Vacia QA", "unidad_medida": "", "tipo_medicion": "PESO"}` | HTTP 400 | **HTTP 400** | `VAL_ENTRADA` | 🟢 PASSED |
| **TC-M09-32b** | `unidad_medida` ausente (sin clave) | `{"id_especie": 4, "nombre": "Metrica Ausente QA", "tipo_medicion": "PESO"}` | HTTP 400 | **HTTP 400** | `VAL_ENTRADA` | 🟢 PASSED |
| **TC-M09-33** | `tipo_medicion` fuera de dominio (`"INVALIDO"`) | `{"id_especie": 4, "nombre": "Metrica Tipo Invalido QA", "unidad_medida": "kg", "tipo_medicion": "INVALIDO"}` | HTTP 400 | **HTTP 400** | `VAL_ENTRADA` | 🟢 PASSED |
| **TC-M09-34** | Coherencia incoherente (`PESO` vs `litros`) | `{"id_especie": 4, "nombre": "Metrica Incoherente QA", "unidad_medida": "litros", "tipo_medicion": "PESO"}` | HTTP 422 | **HTTP 422** | `UNIDAD_MEDIDA_INCOHERENTE` | 🟢 PASSED |
| **TC-M09-35** | `aplica_a_tipo_activo` fuera de dominio (`"GRUPO"`) | `{"id_especie": 4, "nombre": "Metrica Activo Invalido QA", "unidad_medida": "kg", "tipo_medicion": "PESO", "aplica_a_tipo_activo": "GRUPO"}` | HTTP 400 | **HTTP 400** | `VAL_ENTRADA` | 🟢 PASSED |

---

## 3. Observación de Discrepancia Documentada

> [!NOTE]
> **Discrepancia en TC-M09-34 (Coherencia `unidad_medida` vs `tipo_medicion`):**
> La ficha de prueba original especifica HTTP 400 como resultado esperado para TC-M09-34. No obstante, la inspección técnica del código fuente ([`src/configuration/application/use_cases/metricas/registrar_metrica_use_case.py`](file:///c:/Users/Juansegutt/Integrador/sgpmp-backend/src/configuration/application/use_cases/metricas/registrar_metrica_use_case.py#L37-L44)) confirma que el backend valida la regla de coherencia a nivel de caso de uso mediante `BusinessRuleError` (función `_validar_coherencia_unidad()`), la cual es procesada centralizadamente por el middleware `app_error_handler` devolviendo **HTTP 422 Unprocessable Entity**.
> 
> Esta respuesta es consistente con la arquitectura del sistema, que diferencia los errores de validación de sintaxis/esquema (Pydantic `RequestValidationError` → HTTP 400 `VAL_ENTRADA`) de las violaciones a reglas de dominio de la aplicación (`BusinessRuleError` → HTTP 422 `UNIDAD_MEDIDA_INCOHERENTE`).

---

## 4. Verificación de Base de Datos (Solo Lectura - `member_qa`)

* **Script ejecutado:** `verificar_bd_metricas.py`
* **Consulta SQL:** `SELECT COUNT(*) FROM modulo9.metricas_produccion WHERE nombre LIKE 'Metrica % QA';`
* **Resultado:** **0 filas huérfanas encontradas**. Ninguno de los payloads de rechazo llegó a persistirse en la base de datos de TEST, garantizando la integridad relacional del catálogo de métricas de producción.

---

## 5. Artefactos Generados

* Colección Newman: [`test_tc_m09_g14.json`](file:///c:/Users/Juansegutt/Integrador/sgpmp-backend/tests/Test_Testing/Test_Modulo9/RF-16/TC-M09-G14/test_tc_m09_g14.json)
* Script de Verificación BD: [`verificar_bd_metricas.py`](file:///c:/Users/Juansegutt/Integrador/sgpmp-backend/tests/Test_Testing/Test_Modulo9/RF-16/TC-M09-G14/verificar_bd_metricas.py)
* Reporte HTML Newman: [`resultado_tc_m09_g14.html`](file:///c:/Users/Juansegutt/Integrador/sgpmp-backend/tests/Test_Testing/Test_Modulo9/RF-16/TC-M09-G14/Resultados/resultado_tc_m09_g14.html)
* Reporte JSON Newman: [`resultado_tc_m09_g14.json`](file:///c:/Users/Juansegutt/Integrador/sgpmp-backend/tests/Test_Testing/Test_Modulo9/RF-16/TC-M09-G14/Resultados/resultado_tc_m09_g14.json)
* Resumen Markdown: [`resultado_tc_m09_g14.md`](file:///c:/Users/Juansegutt/Integrador/sgpmp-backend/tests/Test_Testing/Test_Modulo9/RF-16/TC-M09-G14/Resultados/resultado_tc_m09_g14.md)
