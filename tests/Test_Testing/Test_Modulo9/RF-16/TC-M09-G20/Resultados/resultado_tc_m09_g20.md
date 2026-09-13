# Reporte de Ejecución: TC-M09-G20 (Auditoría sobre RF-16)

## 1. Ficha Técnica del Caso de Prueba

* **ID del Caso / Grupo:** TC-M09-G20 (sub-caso TC-M09-44)
* **Nombre:** Auditoría de operaciones sobre parámetros de RF-16 (Etapas, Patologías y Métricas por Especie)
* **Módulo / Requisito:** Módulo 9 (Configuración / Parámetros Generales) / RF-16 (CU-02)
* **Tipo de Prueba:** Auditoría / OWASP A09 (Security Logging and Monitoring Failures)
* **Herramientas Utilizadas:** Newman (`cli`, `htmlextra`, `json`), Python 3.13 (`psycopg2` / `member_qa`)
* **Entorno de Ejecución:** TEST (`https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test/`)
* **Rol Evaluado:** Administrador (`admin@pecuaria.co`, `id_usuario = 1`, `id_rol = 1`)
* **Resultado Global:** 🟢 **ÉXITO EN REGISTRO DE AUDITORÍA BD (100% assertions PASSED - 10/10, 5/5 requests, 3 eventos válidos en BD TEST, 0 en fallidos)** | ⚠️ **REGISTRADOS HALLAZGO OBS-M09-01 E INCIDENTES DE SEGURIDAD BD INC-M09-04 E INC-M09-05**

---

## 2. Resumen de Ejecución por Sub-caso (Tabla Consolidada)

| Sub-caso ID | Operación / Escenario Probado | Entidad Evaluada | Método HTTP & Endpoint | Código Esperado | Código Real | Registros Auditoría Generados en BD | Veredicto |
| :--- | :--- | :--- | :--- | :---: | :---: | :---: | :---: |
| **TC-M09-44-1** | Registrar nueva etapa (`CREATE`) | Etapas (`/ciclos`) | `POST /configuracion/ciclos` | HTTP 201 | **HTTP 201** | **1 fila** (`tipo_operacion='CREATE'`, `id_usuario=1`, `val_ant=NULL`) | 🟢 PASSED |
| **TC-M09-44-2** | Editar etapa existente (`UPDATE`) | Etapas (`/ciclos`) | `PATCH /configuracion/ciclos/20` | HTTP 200 | **HTTP 200** | **1 fila** (`tipo_operacion='UPDATE'`, `id_usuario=1`, snapshots coherentes) | 🟢 PASSED |
| **TC-M09-44-3** | Desactivar etapa (`DEACTIVATE`) | Etapas (`/ciclos`) | `PATCH /configuracion/ciclos/20/desactivar` | HTTP 200 | **HTTP 200** | **1 fila** (`tipo_operacion='DEACTIVATE'`, `id_usuario=1`, `es_activo=False`) | 🟢 PASSED |
| **TC-M09-44-4** | Intento duplicado fallido (Edge Case) | Etapas (`/ciclos`) | `POST /configuracion/ciclos` | HTTP 409 | **HTTP 409** | **0 filas** (Sin contaminación por fallas) | 🟢 PASSED |

---

## 3. Registro de Hallazgos e Incidentes de Seguridad

> [!WARNING]
> ### **HALLAZGO ARQUITECTÓNICO: OBS-M09-01**
> **Nombre:** Ausencia de endpoint API para la consulta de auditoría de parámetros de Módulo 9.  
> **Requisito Afectado:** CU-02 / RF-16 (Sub-caso TC-M09-44 — "Auditoría consultable vía API").  
> **Descripción Técnica:** La capa de aplicación de Módulo 9 registra correctamente las operaciones de escritura (`CREATE`, `UPDATE`, `DEACTIVATE`) en la tabla de dominio append-only `modulo9.auditorias_ciclos_biologicos` (y sus homologas para patologías y métricas). Sin embargo, la API Backend **no expone ningún router ni endpoint HTTP GET** (ej. `GET /configuracion/ciclos/auditoria` ni `GET /configuracion/ciclos/{id}/auditoria`) para consultar estos eventos. La única vía actual para auditar estas operaciones es consultar directamente la base de datos PostgreSQL via SQL (`member_qa`).

> [!CAUTION]
> ### **INCIDENTE DE SEGURIDAD BD: INC-M09-04 (Severidad: Alta / Crítica)**
> **Nombre:** Usuario `member_qa` posee privilegios excesivos DML (`DELETE`/`UPDATE`) sobre el esquema `modulo9` en BD TEST.  
> **Componente Afectado:** Motor PostgreSQL (`sgpmp_test` / `member_qa`).  
> **Descripción Técnica:** Se verificó empíricamente que la cuenta de base de datos `member_qa` (destinada a ser de solo-lectura para auditoría y verificación de QA) cuenta con privilegios `DELETE` y `UPDATE` otorgados a nivel de tabla sobre el esquema `modulo9`. Esto permite que una conexión de verificación pueda alterar o borrar datos directamente en la base de datos sin restricción por parte del motor PostgreSQL.

> [!CAUTION]
> ### **INCIDENTE DE SEGURIDAD BD: INC-M09-05 (Severidad: Alta)**
> **Nombre:** Ausencia de salvaguardas a nivel de base de datos para la inmutabilidad de tablas de auditoría en Módulo 9.  
> **Componente Afectado:** Base de Datos PostgreSQL / Esquema `modulo9`.  
> **Descripción Técnica:** A diferencia de `modulo1.eventos` (que cuenta con triggers de BD que bloquean de forma incondicional sentencias `UPDATE` o `DELETE`), las tablas de auditoría de Módulo 9 (`modulo9.auditorias_ciclos_biologicos`, `auditorias_especies_patologias`, `auditorias_metricas_produccion`) **no poseen triggers de inmutabilidad ni reglas `REVOKE DELETE/UPDATE`**. La propiedad append-only de Módulo 9 depende exclusivamente de la disciplina de la capa de aplicación Python, sin ninguna garantía o enforcing a nivel de motor de base de datos.

---

## 4. Verificación de Post-condición en BD TEST (`verificar_bd_auditoria_rf16.py` contra `member_qa`)

* **Confirmación en Vivo en Base de Datos TEST:**  
  Se realizó una consulta en tiempo real contra `member_qa` confirmando que la etapa ID `20` (`"Etapa Auditoria QA Editada"`, `es_activo = False`) y sus **3 registros de auditoría originales** permanecen **100% presentes, intactos e inalterados** en `modulo9.auditorias_ciclos_biologicos`:
  1. `ID_Auditoria=13` | `id_usuario=1` | `tipo_operacion='CREATE'` | `fecha_gestion=2026-09-05 09:26:59.219709+00:00` | `val_nuev['nombre']='Etapa Auditoria QA'` | `val_ant=NULL`
  2. `ID_Auditoria=14` | `id_usuario=1` | `tipo_operacion='UPDATE'` | `fecha_gestion=2026-09-05 09:26:59.487901+00:00` | `val_ant['nombre']='Etapa Auditoria QA'`, `val_nuev['nombre']='Etapa Auditoria QA Editada'`
  3. `ID_Auditoria=15` | `id_usuario=1` | `tipo_operacion='DEACTIVATE'` | `fecha_gestion=2026-09-05 09:26:59.703541+00:00` | `val_ant['es_activo']=True`, `val_nuev['es_activo']=False`
* **Limpieza de Intentos Fallidos:** Se confirmó que la petición fallida `TC-M09-44-4` (`HTTP 409 Conflict`) generó **0 filas** de auditoría en la BD.

---

## 5. Artefactos Generados

* Colección Newman: [`test_tc_m09_g20.json`](file:///c:/Users/Juansegutt/Integrador/sgpmp-backend/tests/Test_Testing/Test_Modulo9/RF-16/TC-M09-G20/test_tc_m09_g20.json)
* Script de Verificación BD: [`verificar_bd_auditoria_rf16.py`](file:///c:/Users/Juansegutt/Integrador/sgpmp-backend/tests/Test_Testing/Test_Modulo9/RF-16/TC-M09-G20/verificar_bd_auditoria_rf16.py)
* Reporte HTML Newman: [`resultado_tc_m09_g20.html`](file:///c:/Users/Juansegutt/Integrador/sgpmp-backend/tests/Test_Testing/Test_Modulo9/RF-16/TC-M09-G20/Resultados/resultado_tc_m09_g20.html)
* Reporte JSON Newman: [`resultado_tc_m09_g20.json`](file:///c:/Users/Juansegutt/Integrador/sgpmp-backend/tests/Test_Testing/Test_Modulo9/RF-16/TC-M09-G20/Resultados/resultado_tc_m09_g20.json)
* Resumen Markdown: [`resultado_tc_m09_g20.md`](file:///c:/Users/Juansegutt/Integrador/sgpmp-backend/tests/Test_Testing/Test_Modulo9/RF-16/TC-M09-G20/Resultados/resultado_tc_m09_g20.md)
