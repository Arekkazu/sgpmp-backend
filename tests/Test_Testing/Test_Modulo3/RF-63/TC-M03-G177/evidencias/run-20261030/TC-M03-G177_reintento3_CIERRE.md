# Informe de Cierre de Pruebas: TC-M03-G177 (Reintento 3)

## 1. Identificación y Metadatos de Ejecución
- **Caso de Prueba Maestro:** TC-M03-G177 (Agrupa subcasos nominales TC-M03-336 y TC-M03-337 + verificación de integridad de bitácora)
- **Requisito Funcional:** RF-63 (Auditoría y Trazabilidad de Telemetría IoT y Decisiones Automatizadas — Módulo 3)
- **Fecha y Hora de Ejecución:** 2026-10-30T12:55:20Z (07:55:20 COT)
- **Entorno Evaluado:** TEST (`https://api.inmero.co/api-sgpmp-test`)
- **Herramienta:** Newman 6.x + htmlextra reporter + JUnit reporter + conversor JSON
- **Aislamiento Transaccional:** Sandbox activo (`ENABLE_TEST_SANDBOX=true`), `Run ID: test-g177-0086b670`
- **Veredicto Final:** **APROBADO (20/20 Checkpoints PASS — 0 FAIL)**

---

## 2. Estado de Incidencias Previas y Fix #730

### Cierre Definitivo de INC-M03-135-G177 (y reclasificación INC-M03-137-G177-A)
* **Defecto original (CRÍTICO):** Invocación de `POST /iot/auditoria/verificar-integridad` sin parámetros de query recorría síncronamente toda la tabla de auditoría (~1.57M - 3.18M registros), bloqueando el worker durante 5m33s, detonando `HTTP 502 Bad Gateway` y degradando el servidor TEST.
* **Resolución verificada (Fix PR #730):**
  1. **Sin fechas:** Responde estrictamente `HTTP 400 Bad Request` en **127 ms** con `error_code: VAL_ENTRADA` y detalle de campos requeridos (`fecha_desde` y `fecha_hasta`).
  2. **Rango invertido:** Responde `HTTP 400 Bad Request` en **117 ms** con `error_code: RANGO_FECHAS_INVALIDO`.
  3. **Ventana grande (>50.000 eventos):** Responde `HTTP 422 Unprocessable Entity` en **4.1 s** con `error_code: RANGO_VERIFICACION_EXCEDIDO` sin saturar la base de datos ni bloquear conexiones.
  4. **Ventana válida (30 minutos):** Responde `HTTP 200 OK` en **251 ms** validando exitosamente la integridad criptográfica (`total_verificados: 50+, comprometidos: 0`).
* **Dictamen de QA:** Incidencias **`INC-M03-135-G177`** e **`INC-M03-137-G177-A`** se certifican como **RESUELTAS Y CERRADAS**.

---

## 3. Resumen Consolidado de la Corrida

```text
┌─────────────────────────┬─────────────────────┬────────────────────┐
│                         │            executed │             failed │
├─────────────────────────┼─────────────────────┼────────────────────┤
│              iterations │                   1 │                  0 │
├─────────────────────────┼─────────────────────┼────────────────────┤
│                requests │                  13 │                  0 │
├─────────────────────────┼─────────────────────┼────────────────────┤
│              assertions │                  22 │                  0 │
└─────────────────────────┴─────────────────────┴────────────────────┘
Duración total: 9.0s | Latencia promedio: 600ms (min: 101ms, max: 4.1s)
```

### Detalle de Checkpoints Evaluados (20/20):
1. `[08-TC-M03-336]` Status 200 - Listado de auditoría obtenido: **PASS**
2. `[08-TC-M03-336]` Estructura de paginación conforme a contrato (`total, pagina, por_pagina, items`): **PASS**
3. `[08-TC-M03-336]` 11 campos base RF-10 y 8 extensión IoT presentes: **PASS**
4. `[08-TC-M03-336]` Ordenamiento consistente DESC por `fecha_hora`: **PASS**
5. `[08-TC-M03-336]` `id_usuario` nulo en eventos automáticos de sistema: **PASS**
6. `[09-TC-M03-336]` Status 200 - Paginación personalizada (`por_pagina=2`) respetada: **PASS**
7. `[10-TC-M03-336]` Status 200 - Paginación máxima `por_pagina=200` aceptada: **PASS**
8. `[11-TC-M03-336]` Status 400 - `por_pagina > 200` rechazado con `VAL_ENTRADA`: **PASS**
9. `[12-TC-M03-337]` Status 200 - Detalle de evento obtenido: **PASS**
10. `[12-TC-M03-337]` ID de evento coincide con el solicitado: **PASS**
11. `[12-TC-M03-337]` Estructura completa de evento (base + extensión): **PASS**
12. `[12-TC-M03-337]` `accion_detallada` es objeto/dict JSON estructurado: **PASS**
13. `[12-TC-M03-337]` Invariante de seguridad: `componente_origen` NO expuesto en HTTP: **PASS**
14. `[12-TC-M03-337]` `hash_integridad` es SHA-256 hex de 64 caracteres: **PASS**
15. `[13-TC-M03-337]` Status 200 - Verificación de integridad SHA-256 en backend: **PASS**
16. `[14-TC-M03-337]` Status 404 - UUID inexistente responde `EVENTO_NO_ENCONTRADO`: **PASS**
17. `[15-TC-M03-337]` Status 400 - UUID malformado responde `VAL_ENTRADA`: **PASS**
18. `[20-Casos-Borde]` Status 400 - Sin fechas rechazado con `VAL_ENTRADA` (`fields` requeridos): **PASS**
19. `[21-Casos-Borde]` Status 400 - Rango invertido rechazado con `RANGO_FECHAS_INVALIDO`: **PASS**
20. `[22-Casos-Borde]` Status 422 - Ventana > 50.000 eventos rechazada con `RANGO_VERIFICACION_EXCEDIDO`: **PASS**

*(Adicionales de soporte: Login único inicial: **PASS**; Rollback transaccional de teardown: **PASS**)*.

---

## 4. Estado del Sandbox y Zero-Pollution
* La corrida completa se ejecutó bajo la transacción aislada `test-g177-0086b670`.
* El paso final `99-Teardown-Rollback-Sandbox` ejecutó `DELETE /test-control/runs/test-g177-0086b670` respondiendo `HTTP 200 OK {"status":"Rollback exitoso"}` en 101 ms.
* Comprobación post-ejecución confirmó `HTTP 404 {"detail":"Run ID no encontrado."}`, certificando que **cero conexiones quedaron retenidas y cero datos residuales persisten en la BD**.

---

## 5. Artefactos de Reporte Generados
* **HTML interactivo:** [`resultados/resultado_TC-M03-G177_reintento3.html`](file:///c:/Users/Juansegutt/Integrador/sgpmp-backend/tests/Test_Testing/Test_Modulo3/RF-63/TC-M03-G177/resultados/resultado_TC-M03-G177_reintento3.html) (0.56 MB, 0 fallos).
* **JUnit XML:** [`resultados/resultado_TC-M03-G177_reintento3.xml`](file:///c:/Users/Juansegutt/Integrador/sgpmp-backend/tests/Test_Testing/Test_Modulo3/RF-63/TC-M03-G177/resultados/resultado_TC-M03-G177_reintento3.xml).
* **JSON computable:** [`resultados/resultado_TC-M03-G177_reintento3.json`](file:///c:/Users/Juansegutt/Integrador/sgpmp-backend/tests/Test_Testing/Test_Modulo3/RF-63/TC-M03-G177/resultados/resultado_TC-M03-G177_reintento3.json) (20 checkpoints OK, veredicto `APROBADO`).
* **Consola de ejecución:** [`evidencias/run-20261030/console_execution.log`](file:///c:/Users/Juansegutt/Integrador/sgpmp-backend/tests/Test_Testing/Test_Modulo3/RF-63/TC-M03-G177/evidencias/run-20261030/console_execution.log).

---

## 6. Dictamen Final
El caso **TC-M03-G177** queda **CERRADO Y APROBADO** en su **Reintento 3**.

**Firma:**  
*Antigravity AI Pair Programmer & QA Automation Specialist*

