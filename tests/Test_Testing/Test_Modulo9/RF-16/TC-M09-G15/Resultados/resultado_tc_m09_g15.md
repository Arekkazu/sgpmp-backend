# Reporte de Ejecución: TC-M09-G15 (Integridad de Desactivación de Parámetros)

## 1. Ficha Técnica del Caso de Prueba

* **ID del Caso / Grupo:** TC-M09-G15 (sub-casos TC-M09-36, TC-M09-37, TC-M09-38)
* **Nombre:** Integridad — impedir desactivar parámetros (etapa/patología/métrica) en uso
* **Módulo / Requisito:** Módulo 9 (Configuración / Parámetros Generales) / RF-16 (CU-02)
* **Tipo de Prueba:** Integridad Referencial / Reglas de Negocio / Seguridad y Control de Datos
* **Herramientas Utilizadas:** Newman (`cli`, `htmlextra`, `json`), Python 3.13 (`psycopg2` / `member_qa`), Auditoría de Código
* **Entorno de Ejecución:** TEST (`https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test/`)
* **Resultado TC-M09-36 (Etapa):** 🟢 **EXITOSO (HTTP 422 ETAPA_CON_ACTIVOS - 2/2 assertions PASSED)**
* **Resultado TC-M09-37 & TC-M09-38 (Patología / Métrica):** 🔴 **HALLAZGO DE SEGURIDAD INC-M09-03 (SEVERIDAD ALTA/CRÍTICA)**

---

## 2. Resumen de Estado por Sub-caso

| Sub-caso | Entidad / Condición Probada | Método de Verificación | Resultado Esperado | Resultado Real | Error Code / Estado | Veredicto |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: |
| **TC-M09-36** | Desactivación de ETAPA con activos biológicos asociados (`id_ciclo_biologico = 10`) | Ejecución en vivo (Newman) + BD TEST (`member_qa`) | HTTP 422 | **HTTP 422** | `ETAPA_CON_ACTIVOS` | 🟢 PASSED (Bloqueo OK, `es_activo = true`) |
| **TC-M09-37** | Desactivación de PATOLOGÍA con eventos sanitarios asociados | Auditoría de código (`patologia_router.py`) | HTTP 422 | **HTTP 200 (Vulnerable)** | **`INC-M09-03`** (Stub adaptador incondicional) | 🔴 VULNERABLE (Hallazgo de Seguridad) |
| **TC-M09-38** | Desactivación de MÉTRICA referenciada por eventos productivos | Auditoría de código (`metrica_router.py`) | HTTP 422 | **HTTP 200 (Vulnerable)** | **`INC-M09-03`** (Stub adaptador incondicional) | 🔴 VULNERABLE (Hallazgo de Seguridad) |

---

## 3. Resumen Ejecutivo del Defecto INC-M09-03

> [!CAUTION]
> **DEFECTO DE INTEGRIDAD Y SEGURIDAD ACTIVO — INC-M09-03 (SEVERIDAD ALTA/CRÍTICA):**
> Los endpoints `PATCH /configuracion/patologias/{id}/desactivar` y `PATCH /configuracion/metricas/{id}/desactivar` utilizan adaptadores stub (`StubDependenciaPatologiaAdapter` y `StubDependenciaMetricaAdapter`) que retornan `False` incondicionalmente (`tiene_dependencias_activas() -> False`).
> 
> Si un usuario ejecuta la desactivación de una patología o métrica que posea registros asociados en la aplicación, el sistema **NO BLOQUEA LA OPERACIÓN**, devolviendo **HTTP 200 OK** y realizando la baja lógica del parámetro. Esto permite de forma silenciosa e incontrolada la alteración de parámetros en uso, violando las reglas de integridad FA-04 y FA-09 del RF-16.

---

## 4. Artefactos Generados

* Colección Newman (TC-M09-36): [`test_tc_m09_g15.json`](file:///c:/Users/Juansegutt/Integrador/sgpmp-backend/tests/Test_Testing/Test_Modulo9/RF-16/TC-M09-G15/test_tc_m09_g15.json)
* Script de Verificación BD: [`verificar_bd_ciclo10.py`](file:///c:/Users/Juansegutt/Integrador/sgpmp-backend/tests/Test_Testing/Test_Modulo9/RF-16/TC-M09-G15/verificar_bd_ciclo10.py)
* Reporte HTML Newman: [`resultado_tc_m09_g15.html`](file:///c:/Users/Juansegutt/Integrador/sgpmp-backend/tests/Test_Testing/Test_Modulo9/RF-16/TC-M09-G15/Resultados/resultado_tc_m09_g15.html)
* Reporte JSON Newman: [`resultado_tc_m09_g15.json`](file:///c:/Users/Juansegutt/Integrador/sgpmp-backend/tests/Test_Testing/Test_Modulo9/RF-16/TC-M09-G15/Resultados/resultado_tc_m09_g15.json)
* Resumen Markdown Estándar: [`resultado_tc_m09_g15.md`](file:///c:/Users/Juansegutt/Integrador/sgpmp-backend/tests/Test_Testing/Test_Modulo9/RF-16/TC-M09-G15/Resultados/resultado_tc_m09_g15.md)
* **Reporte Técnico Detallado (INC-M09-03 vs INC-M09-02):** [`resultado_tc_m09_g15_detalle.md`](file:///c:/Users/Juansegutt/Integrador/sgpmp-backend/tests/Test_Testing/Test_Modulo9/RF-16/TC-M09-G15/Resultados/resultado_tc_m09_g15_detalle.md)
