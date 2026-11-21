# Reporte de Ejecución - TC-M09-G12 (Sub-casos TC-M09-22 a TC-M09-26)

## 📌 Ficha del Caso de Prueba
* **ID Caso**: TC-M09-G12
* **Sub-casos Evaluados**: TC-M09-22, TC-M09-23, TC-M09-24, TC-M09-25 (a/b), TC-M09-26
* **Nombre**: Validación de campos de Etapa productiva (longitud, duración, duplicado)
* **Tipo**: Valores Límite / Validación de Datos / OWASP A03
* **Requisito Funcional**: RF-16 (Parámetros Productivos / CU-02)
* **Especie Base de Prueba**: *Cachama Blanca* (`id_especie = 4`)
* **Entorno de Ejecución**: TEST (`https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test/`)
* **Colección Postman / Newman**: [`tests/Test_Testing/Test_Modulo9/RF-16/TC-M09-G12/test_tc_m09_g12.json`](file:///c:/Users/Juansegutt/Integrador/sgpmp-backend/tests/Test_Testing/Test_Modulo9/RF-16/TC-M09-G12/test_tc_m09_g12.json)
* **Reporte HTML Extra Generado**: [`tests/Test_Testing/Test_Modulo9/RF-16/TC-M09-G12/Resultados/resultado_tc_m09_g12.html`](file:///c:/Users/Juansegutt/Integrador/sgpmp-backend/tests/Test_Testing/Test_Modulo9/RF-16/TC-M09-G12/Resultados/resultado_tc_m09_g12.html)

---

## 📊 Resumen de Resultados por Sub-caso

| Sub-caso | Objetivo / Validación | Valor / Input de Prueba | Status Code Real | `error_code` Real Observado | Mensaje Real de la API | Veredicto |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **TC-M09-22** | Nombre Límite Mínimo (3 caracteres) | `nombre = "Cri"` (3 chars) | **HTTP 201 Created** | N/A | Creado exitosamente (`id=16`) | **OK** |
| **TC-M09-23** | Nombre Límite Máximo (50 caracteres) | `nombre = "Etapa Con Nombre Exacto De Cincuenta Caracteres QA"` | **HTTP 201 Created** | N/A | Creado exitosamente (`id=17`, len=50) | **OK** |
| **TC-M09-24** | Rechazar Duración Cero | `duracion_dias = 0` | **HTTP 400 Bad Request** | **`VAL_ENTRADA`** | `"Value error, La duración estimada debe ser un número entero positivo mayor a 0. Valor recibido: 0."` | **OK** |
| **TC-M09-25a** | Rechazar Duración Negativa | `duracion_dias = -5` | **HTTP 400 Bad Request** | **`VAL_ENTRADA`** | `"Value error, La duración estimada debe ser un número entero positivo mayor a 0. Valor recibido: -5."` | **OK** |
| **TC-M09-25b** | Rechazar Duración Decimal | `duracion_dias = 10.5` | **HTTP 400 Bad Request** | **`VAL_ENTRADA`** | `"Input should be a valid integer, got a number with a fractional part"` | **OK** |
| **TC-M09-26** | Rechazar Duplicado Case-Insensitive | Base `"Engorde"` (`id=18`) vs Intento `"ENGORDE"` | **HTTP 409 Conflict** | **`ETAPA_DUPLICADA`** | `"Ya existe una etapa con el nombre 'ENGORDE' para esta especie."` | **OK** |

---

## 🧹 Limpieza de Datos Post-Prueba
Se ejecutaron 3 solicitudes de desactivación lógica (`PATCH /configuracion/ciclos/{id}/desactivar`) al finalizar la suite:
1. **Etapa ID 16 ("Cri")**: `HTTP 200 OK` (`es_activo = false`).
2. **Etapa ID 17 ("Etapa Con Nombre...")**: `HTTP 200 OK` (`es_activo = false`).
3. **Etapa ID 18 ("Engorde")**: `HTTP 200 OK` (`es_activo = false`).

El catálogo de etapas de *Cachama Blanca* (`id_especie = 4`) quedó ordenado y sin etapas activas residuales.

---

## 🏆 Conclusión Global
* **Peticiones Ejecutadas**: 11/11 (100% exitosas)
* **Aserciones Evaluadas**: 15/15 (100% PASSED)
* **Veredicto del Caso TC-M09-G12**: **OK (ÉXITO TOTAL)**
