# Reporte de Ejecución: TC-M09-G16 (Restricción RBAC sobre RF-16)

## 1. Ficha Técnica del Caso de Prueba

* **ID del Caso / Grupo:** TC-M09-G16 (sub-caso TC-M09-39)
* **Nombre:** Restricción de permisos RBAC para Productor e Ingeniero de Campo sobre RF-16
* **Módulo / Requisito:** Módulo 9 (Configuración / Parámetros Generales) / RF-16 (CU-02)
* **Tipo de Prueba:** Control de Acceso / Seguridad OWASP A01 (Broken Access Control) / RBAC Dinámico
* **Herramientas Utilizadas:** Newman (`cli`, `htmlextra`, `json`), Python 3.13 (`psycopg2` / `member_qa`)
* **Entorno de Ejecución:** TEST (`https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test/`)
* **Roles Evaluados:** Productor (`productor@pecuaria.co`, `id_rol = 2`) e Ingeniero de Campo (`ingeniero@pecuaria.co`, `id_rol = 4`)
* **Resultado Global:** 🟢 **ÉXITO TOTAL / OWASP A01 (100% assertions PASSED - 14/14, 12/12 combinaciones rechazadas con HTTP 403)**

---

## 2. Resumen de Ejecución por Sub-caso (12 Combinaciones)

| Sub-caso ID | Rol Evaluado | Recurso / Entidad Probada | Método HTTP & Endpoint | Código Esperado | Código Real | Error Code Real | Veredicto |
| :--- | :--- | :--- | :--- | :---: | :---: | :---: | :---: |
| **TC-M09-39-A1** | Productor (`id_rol=2`) | Etapas productivas | `POST /configuracion/ciclos` | HTTP 403 | **HTTP 403** | `ACCESO_DENEGADO` | 🟢 PASSED |
| **TC-M09-39-A2** | Productor (`id_rol=2`) | Etapas productivas | `PATCH /configuracion/ciclos/10/desactivar` | HTTP 403 | **HTTP 403** | `ACCESO_DENEGADO` | 🟢 PASSED |
| **TC-M09-39-A3** | Productor (`id_rol=2`) | Patologías por especie | `POST /configuracion/patologias` | HTTP 403 | **HTTP 403** | `ACCESO_DENEGADO` | 🟢 PASSED |
| **TC-M09-39-A4** | Productor (`id_rol=2`) | Patologías por especie | `PATCH /configuracion/patologias/1/desactivar` | HTTP 403 | **HTTP 403** | `ACCESO_DENEGADO` | 🟢 PASSED |
| **TC-M09-39-A5** | Productor (`id_rol=2`) | Métricas productivas | `POST /configuracion/metricas` | HTTP 403 | **HTTP 403** | `ACCESO_DENEGADO` | 🟢 PASSED |
| **TC-M09-39-A6** | Productor (`id_rol=2`) | Métricas productivas | `PATCH /configuracion/metricas/1/desactivar` | HTTP 403 | **HTTP 403** | `ACCESO_DENEGADO` | 🟢 PASSED |
| **TC-M09-39-B1** | Ingeniero (`id_rol=4`) | Etapas productivas | `POST /configuracion/ciclos` | HTTP 403 | **HTTP 403** | `ACCESO_DENEGADO` | 🟢 PASSED |
| **TC-M09-39-B2** | Ingeniero (`id_rol=4`) | Etapas productivas | `PATCH /configuracion/ciclos/10/desactivar` | HTTP 403 | **HTTP 403** | `ACCESO_DENEGADO` | 🟢 PASSED |
| **TC-M09-39-B3** | Ingeniero (`id_rol=4`) | Patologías por especie | `POST /configuracion/patologias` | HTTP 403 | **HTTP 403** | `ACCESO_DENEGADO` | 🟢 PASSED |
| **TC-M09-39-B4** | Ingeniero (`id_rol=4`) | Patologías por especie | `PATCH /configuracion/patologias/1/desactivar` | HTTP 403 | **HTTP 403** | `ACCESO_DENEGADO` | 🟢 PASSED |
| **TC-M09-39-B5** | Ingeniero (`id_rol=4`) | Métricas productivas | `POST /configuracion/metricas` | HTTP 403 | **HTTP 403** | `ACCESO_DENEGADO` | 🟢 PASSED |
| **TC-M09-39-B6** | Ingeniero (`id_rol=4`) | Métricas productivas | `PATCH /configuracion/metricas/1/desactivar` | HTTP 403 | **HTTP 403** | `ACCESO_DENEGADO` | 🟢 PASSED |

---

## 3. Verificación de Integridad y Post-condición BD TEST (`member_qa`)

* **Script ejecutado:** `verificar_bd_rbac_rf16.py`
* **Registros no autorizados en BD TEST:** **0 filas creadas** en `modulo9.ciclos_biologicos`, `modulo9.especies_patologias` y `modulo9.metricas_produccion`.
* **Inmutabilidad de Fixtures Probados en Desactivación:**
  * Etapa ID 10 (*Fase juvenil cachama*): `es_activo = True` (intacto).
  * Patología ID 1 (*Ich/Ichthyophthirius*): `es_activo = True` (intacta).
  * Métrica ID 1 (*Peso promedio individual*): `es_activo = True` (intacta).
* **Confirmación Arquitectónica:** Se confirmó en vivo que la compuerta RBAC (`require_permission` en `src/shared/rbac.py`) intercepta y detiene las peticiones no autorizadas en memoria antes de iniciar transacciones de base de datos o tocar los triggers de auditoría.

---

## 4. Artefactos Generados

* Colección Newman: [`test_tc_m09_g16.json`](file:///c:/Users/Juansegutt/Integrador/sgpmp-backend/tests/Test_Testing/Test_Modulo9/RF-16/TC-M09-G16/test_tc_m09_g16.json)
* Script de Verificación BD: [`verificar_bd_rbac_rf16.py`](file:///c:/Users/Juansegutt/Integrador/sgpmp-backend/tests/Test_Testing/Test_Modulo9/RF-16/TC-M09-G16/verificar_bd_rbac_rf16.py)
* Reporte HTML Newman: [`resultado_tc_m09_g16.html`](file:///c:/Users/Juansegutt/Integrador/sgpmp-backend/tests/Test_Testing/Test_Modulo9/RF-16/TC-M09-G16/Resultados/resultado_tc_m09_g16.html)
* Reporte JSON Newman: [`resultado_tc_m09_g16.json`](file:///c:/Users/Juansegutt/Integrador/sgpmp-backend/tests/Test_Testing/Test_Modulo9/RF-16/TC-M09-G16/Resultados/resultado_tc_m09_g16.json)
* Resumen Markdown: [`resultado_tc_m09_g16.md`](file:///c:/Users/Juansegutt/Integrador/sgpmp-backend/tests/Test_Testing/Test_Modulo9/RF-16/TC-M09-G16/Resultados/resultado_tc_m09_g16.md)
