# Reporte de Ejecución - TC-M09-G08 (Sub-caso TC-M09-18)

## 📌 Ficha del Caso de Prueba
* **ID Caso**: TC-M09-G08
* **Sub-caso**: TC-M09-18
* **Nombre**: Auditoría de creación, edición y desactivación de especies
* **Tipo**: Auditoría / OWASP A09 (Security Logging and Monitoring Failures)
* **Requisito Funcional**: RF-15 (Catálogo de Especies Productivas)
* **Entorno de Ejecución**: TEST (`https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test/`)
* **Base de Datos**: PostgreSQL TEST (`158.69.200.27:5448 / sgpmp_test`, usuario `member_qa`)
* **Colección Postman / Newman**: [`tests/Test_Testing/Test_Modulo9/RF-15/TC-M09-G08/test_tc_m09_g08.json`](file:///c:/Users/Juansegutt/Integrador/sgpmp-backend/tests/Test_Testing/Test_Modulo9/RF-15/TC-M09-G08/test_tc_m09_g08.json)
* **Reporte HTML Extra Generado**: [`tests/Test_Testing/Test_Modulo9/RF-15/TC-M09-G08/Resultados/resultado_tc_m09_g08.html`](file:///c:/Users/Juansegutt/Integrador/sgpmp-backend/tests/Test_Testing/Test_Modulo9/RF-15/TC-M09-G08/Resultados/resultado_tc_m09_g08.html)

---

## 📊 Resumen de Resultados

| Paso / Operación | Método & Endpoint | Resultado Esperado (RF-15) | Resultado Real (API TEST) | Veredicto Checkpoint |
| :--- | :--- | :--- | :--- | :--- |
| **Paso 0 - Autenticación** | `POST /sesiones/` | HTTP 200 OK + Token JWT | HTTP 200 OK | **OK** |
| **Paso 1 - CREATE Especie** | `POST /configuracion/especies` | HTTP 201 Created | **HTTP 500 Internal Server Error** | **FALLA (Bloqueado)** |
| **Paso 2 - Auditoría API CREATE** | `GET /auditoria/?id_usuario=1` | HTTP 200 OK + Eventos | HTTP 200 OK | **OK** |
| **Paso 3 - UPDATE Especie** | `PATCH /configuracion/especies/{id}` | HTTP 200 OK | **HTTP 404 / 500** | **FALLA (Bloqueado)** |
| **Paso 4 - Auditoría API UPDATE** | `GET /auditoria/?id_usuario=1` | HTTP 200 OK | OMITIDO/N-A | **OMITIDO** |
| **Paso 5 - DEACTIVATE Especie** | `PATCH /configuracion/especies/{id}/desactivar` | HTTP 200 OK | **HTTP 400 / 500** | **FALLA (Bloqueado)** |
| **Paso 6 - Auditoría API DEACTIVATE** | `GET /auditoria/?id_usuario=1` | HTTP 200 OK | OMITIDO/N-A | **OMITIDO** |
| **Paso 7 - Verificación BD TEST** | Query a `modulo9.auditorias_especies` | Presencia de `valores_anteriores` y `valores_nuevos` | Conexión exitosa, 5 registros históricos verificados | **OBSERVACION** |

---

## 🔍 Hallazgos y Diagnóstico Técnico

1. **Confirmación Defecto INC-M09-02-G02 en `INSERT` / `CREATE`**:
   * Al intentar registrar la especie sintética en el Paso 1 (`POST /configuracion/especies`), la API TEST respondió **`HTTP 500 Internal Server Error`**.
   * **Causa raíz**: El trigger de base de datos `modulo9.trg_especies_audit` en la tabla `modulo9.especies` está configurado como `AFTER INSERT OR UPDATE`. Al ejecutarse cualquier `INSERT` o `UPDATE`, invoca a `modulo9.trg_fn_especies_audit()`, la cual falla inmediatamente con excepción de PL/pgSQL al no encontrar la variable de sesión `app.usuario_id` en la conexión de PostgreSQL.

2. **Doble Capa de Auditoría Verificada**:
   * **`modulo1.eventos` (API `GET /auditoria/`)**: Responde `HTTP 200 OK` registrando accesos y consultas de auditoría general (ej. `tipo_evento = 16`).
   * **`modulo9.auditorias_especies` (BD TEST `member_qa`)**: Se verificó la estructura de la tabla mediante consulta directa de solo lectura. La tabla almacena correctamente los snapshots JSONB en `valores_anteriores` y `valores_nuevos` para transacciones completadas (ej. `id_auditoria_especie = 14`, `13`, `12`).

3. **Prueba de Regresión Futura**:
   * La colección [`test_tc_m09_g08.json`](file:///c:/Users/Juansegutt/Integrador/sgpmp-backend/tests/Test_Testing/Test_Modulo9/RF-15/TC-M09-G08/test_tc_m09_g08.json) fue construida sin interceptar o enmascarar el error 500. Sirve como suite de regresión 100% automatizada que pasará en verde una vez que el equipo de desarrollo elimine el trigger huérfano o configure `SET LOCAL app.usuario_id`.

---

## 🗑️ Listado de Datos Sintéticos Pendientes de Limpieza Post-Fix
* Dado que `POST` falló con `HTTP 500`, **no se crearon filas huérfanas en `modulo9.especies` durante esta corrida**.
* Estado del catálogo de especies en TEST: **Limpio e Intacto**.
