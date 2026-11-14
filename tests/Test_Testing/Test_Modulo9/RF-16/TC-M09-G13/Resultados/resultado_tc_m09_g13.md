# Reporte de Ejecución - TC-M09-G13 (Sub-casos TC-M09-28 a TC-M09-30)

## 📌 Ficha del Caso de Prueba
* **ID Caso**: TC-M09-G13
* **Sub-casos Evaluados**: TC-M09-28a, TC-M09-28b, TC-M09-29, TC-M09-30
* **Nombre**: Validación de campos de Patología (longitud nombre/descripción, duplicado)
* **Tipo**: Valores Límite / Validación de Datos / OWASP A03
* **Requisito Funcional**: RF-16 (Parámetros Productivos / CU-02)
* **Especie Base de Prueba**: *Cachama Blanca* (`id_especie = 4`)
* **Entorno de Ejecución**: TEST (`https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test/`)
* **Colección Postman / Newman**: [`tests/Test_Testing/Test_Modulo9/RF-16/TC-M09-G13/test_tc_m09_g13.json`](file:///c:/Users/Juansegutt/Integrador/sgpmp-backend/tests/Test_Testing/Test_Modulo9/RF-16/TC-M09-G13/test_tc_m09_g13.json)
* **Script Verificación DB**: [`tests/Test_Testing/Test_Modulo9/RF-16/TC-M09-G13/verificar_bd_patologias.py`](file:///c:/Users/Juansegutt/Integrador/sgpmp-backend/tests/Test_Testing/Test_Modulo9/RF-16/TC-M09-G13/verificar_bd_patologias.py)
* **Reporte HTML Extra Generado**: [`tests/Test_Testing/Test_Modulo9/RF-16/TC-M09-G13/Resultados/resultado_tc_m09_g13.html`](file:///c:/Users/Juansegutt/Integrador/sgpmp-backend/tests/Test_Testing/Test_Modulo9/RF-16/TC-M09-G13/Resultados/resultado_tc_m09_g13.html)

---

## 📊 Resumen de Resultados por Sub-caso

| Sub-caso | Validación / Input | Longitud Verificada | Status Code Real | `error_code` Real Observado | Campo & Mensaje Real de la API | Veredicto |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **TC-M09-28a** | Rechazar Nombre 2 Caracteres | `len("Ma") = 2` | **HTTP 400 Bad Request** | **`VAL_ENTRADA`** | `field: "nombre"` — *"Value error, El nombre de la patología debe tener entre 3 y 60 caracteres."* | **OK** |
| **TC-M09-28b** | Rechazar Nombre 101 Caracteres | `len(str) = 101` | **HTTP 400 Bad Request** | **`VAL_ENTRADA`** | `field: "nombre"` — *"Value error, El nombre de la patología debe tener entre 3 y 60 caracteres."* | **OK** |
| **TC-M09-29** | Rechazar Descripción 256 Caracteres | `len(str) = 256` | **HTTP 400 Bad Request** | **`VAL_ENTRADA`** | `field: "descripcion"` — *"Value error, La descripción no puede superar los 255 caracteres."* (BD `member_qa`: **0 filas en DB**) | **OK** |
| **TC-M09-30** | Rechazar Duplicado Case-Insensitive | `"Mastitis"` (`id=16`) vs `"MASTITIS"` | **HTTP 409 Conflict** | **`PATOLOGIA_DUPLICADA_EN_ESPECIE`** | `field: "nombre"` — *"Ya existe una patología con el nombre 'MASTITIS' para esta especie."* | **OK** |

---

## 🔍 Confirmación de No Persistencia en BD TEST (`member_qa`)
El script [`verificar_bd_patologias.py`](file:///c:/Users/Juansegutt/Integrador/sgpmp-backend/tests/Test_Testing/Test_Modulo9/RF-16/TC-M09-G13/verificar_bd_patologias.py) confirmó mediante consulta de solo lectura a la tabla `modulo9.especies_patologias`:
* **Registros con descripción > 255 caracteres**: **0 filas**. La petición rechazada con `HTTP 400` no dejó ningún rastro o registro corrupto en la base de datos.

---

## 🧹 Limpieza de Datos Post-Prueba
Se ejecutó la desactivación lógica de la patología creada para el sub-caso de duplicados:
* **Patología ID 16 (`"Mastitis"`)**: `PATCH /configuracion/patologias/16/desactivar` → **HTTP 200 OK** (`es_activo = false`).

El catálogo de patologías de la especie *Cachama Blanca* (`id_especie = 4`) permaneció limpio e intacto.

---

## 🏆 Conclusión Global
* **Peticiones Ejecutadas**: 7/7 (100% exitosas)
* **Aserciones Evaluadas**: 11/11 (100% PASSED)
* **Veredicto del Caso TC-M09-G13**: **OK (ÉXITO TOTAL)**
