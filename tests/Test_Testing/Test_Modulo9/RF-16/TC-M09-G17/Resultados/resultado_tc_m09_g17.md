# Reporte de Ejecución: TC-M09-G17 (Integridad Referencial por id_especie sobre RF-16)

## 1. Ficha Técnica del Caso de Prueba

* **ID del Caso / Grupo:** TC-M09-G17 (sub-caso TC-M09-40)
* **Nombre:** Integridad referencial: rechazo de creación de parámetros con id_especie inexistente, inactivo o inválido
* **Módulo / Requisito:** Módulo 9 (Configuración / Parámetros Generales) / RF-16 (CU-02 — Dependencia declarada de RF-15)
* **Tipo de Prueba:** Integración / Integridad Referencial / Validación de Dominio y DTO
* **Herramientas Utilizadas:** Newman (`cli`, `htmlextra`, `json`), Python 3.13 (`psycopg2` / `member_qa`)
* **Entorno de Ejecución:** TEST (`https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test/`)
* **Rol Evaluado:** Administrador (`admin@pecuaria.co`, `id_rol = 1`)
* **Resultado Global:** 🟢 **ÉXITO TOTAL / INTEGRIDAD REFERENCIAL (100% assertions PASSED - 18/18, 8/8 sub-casos verificados, 0 filas huérfanas en BD TEST)**

---

## 2. Resumen de Ejecución por Sub-caso (8 Sub-casos)

| Sub-caso ID | Descripción / Escenario Probado | Entidad Evaluada | Payload (`id_especie`) | Código Esperado | Código Real | Error Code Real | Veredicto |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| **TC-M09-40-A1** | Crear Etapa con especie inexistente | Etapas (`/ciclos`) | `999` | HTTP 404 | **HTTP 404** | `ESPECIE_NO_ENCONTRADA` | 🟢 PASSED |
| **TC-M09-40-A2** | Crear Patología con especie inexistente | Patologías (`/patologias`) | `999` | HTTP 404 | **HTTP 404** | `ESPECIE_NO_ENCONTRADA` | 🟢 PASSED |
| **TC-M09-40-A3** | Crear Métrica con especie inexistente | Métricas (`/metricas`) | `999` | HTTP 404 | **HTTP 404** | `ESPECIE_NO_ENCONTRADA` | 🟢 PASSED |
| **TC-M09-40-B1** | Crear Etapa con especie inactiva | Etapas (`/ciclos`) | `1` (*Tilapia Roja*) | HTTP 422 | **HTTP 422** | `ESPECIE_INACTIVA` | 🟢 PASSED |
| **TC-M09-40-B2** | Crear Patología con especie inactiva | Patologías (`/patologias`) | `1` (*Tilapia Roja*) | HTTP 422 | **HTTP 422** | `ESPECIE_INACTIVA` | 🟢 PASSED |
| **TC-M09-40-B3** | Crear Métrica con especie inactiva | Métricas (`/metricas`) | `1` (*Tilapia Roja*) | HTTP 422 | **HTTP 422** | `ESPECIE_INACTIVA` | 🟢 PASSED |
| **TC-M09-40-C1** | Crear Etapa con `id_especie` negativo | Etapas (`/ciclos`) | `-1` | HTTP 404 | **HTTP 404** | `ESPECIE_NO_ENCONTRADA` | 🟢 PASSED |
| **TC-M09-40-C2** | Crear Etapa con `id_especie` no entero | Etapas (`/ciclos`) | `"abc"` | HTTP 400 | **HTTP 400** | `VAL_ENTRADA` | 🟢 PASSED |

---

## 3. Verificación de Integridad y Post-condición BD TEST (`member_qa`)

* **Script ejecutado:** `verificar_bd_integridad_especie.py`
* **Registros huérfanos / inconsistentes en BD TEST:** **0 filas creadas** en `modulo9.ciclos_biologicos`, `modulo9.especies_patologias` y `modulo9.metricas_produccion`.
* **Detalle por tabla:**
  1. `modulo9.ciclos_biologicos`: **0 filas huérfanas**.
  2. `modulo9.especies_patologias`: **0 filas huérfanas**.
  3. `modulo9.metricas_produccion`: **0 filas huérfanas**.
* **Confirmación Arquitectónica:**
  * Para `id_especie` inexistente (`999`, `-1`), la capa de aplicación (`RegistrarCicloUseCase`, etc.) valida la presencia en el repositorio de especies y lanza `NotFoundError` (`HTTP 404`).
  * Para `id_especie` inactiva (`1`), el caso de uso verifica `especie.es_activo` y aplica la regla de negocio del RF-16 lanzando `BusinessRuleError` (`HTTP 422`).
  * Para `id_especie` no entérico (`"abc"`), Pydantic intercepta la estructura en la capa DTO y retorna `RequestValidationError` (`HTTP 400`) sin invocar la capa de negocio ni el repositorio.

---

## 4. Artefactos Generados

* Colección Newman: [`test_tc_m09_g17.json`](file:///c:/Users/Juansegutt/Integrador/sgpmp-backend/tests/Test_Testing/Test_Modulo9/RF-16/TC-M09-G17/test_tc_m09_g17.json)
* Script de Verificación BD: [`verificar_bd_integridad_especie.py`](file:///c:/Users/Juansegutt/Integrador/sgpmp-backend/tests/Test_Testing/Test_Modulo9/RF-16/TC-M09-G17/verificar_bd_integridad_especie.py)
* Reporte HTML Newman: [`resultado_tc_m09_g17.html`](file:///c:/Users/Juansegutt/Integrador/sgpmp-backend/tests/Test_Testing/Test_Modulo9/RF-16/TC-M09-G17/Resultados/resultado_tc_m09_g17.html)
* Reporte JSON Newman: [`resultado_tc_m09_g17.json`](file:///c:/Users/Juansegutt/Integrador/sgpmp-backend/tests/Test_Testing/Test_Modulo9/RF-16/TC-M09-G17/Resultados/resultado_tc_m09_g17.json)
* Resumen Markdown: [`resultado_tc_m09_g17.md`](file:///c:/Users/Juansegutt/Integrador/sgpmp-backend/tests/Test_Testing/Test_Modulo9/RF-16/TC-M09-G17/Resultados/resultado_tc_m09_g17.md)
