# Resultado de Ejecución: TC-M03-G170 — Reevaluación Explícita de Calidad (RF-62 / RF-63)

- **Identificador de Caso:** TC-M03-G170 (TC-324, TC-325, TC-326)
- **Fecha y Hora:** 2026-10-23T23:31:33Z
- **Veredicto:** **RECHAZADO POR BLOQUEO EXTERNO**
- **Estrategia Aplicada:** Fallback a **Camino 1 (Autosiembra Canónica)** tras descartar **Camino 2 (Sensor 7 Preexistente)** en diagnóstico Bloque A.

---

## 1. Resumen Ejecutivo de Diagnóstico Bloque A (A.7)

El intento de **Camino 2 (Sensor 7 Preexistente)** fue descartado por inviabilidad técnica basada en las siguientes decisiones verificadas en base de datos y use case:

1. **¿El sensor 7 existe en `modulo9.sensores`?**  
   **No.** `modulo9.sensores` se encuentra completamente vacía (`0` filas). El `id_sensor = 7` presente en `modulo3.telemetria_calidad` y `modulo3.telemetrias` es un residuo de semillas previas sin contraparte en catálogo.
2. **¿Las 5 evaluaciones tienen `id_telemetria` válidas con telemetrías existentes?**  
   **Sí.** Existen 5 telemetrías asociadas en `modulo3.telemetrias` con `id_variable = 3`.
3. **¿Tiene calibraciones el sensor 7?**  
   **0.** `modulo9.calibraciones` no tiene registros para `id_sensor = 7`.
4. **¿El rango de fechas de las 5 evaluaciones es utilizable?**  
   **No.** Las 5 evaluaciones existentes se encuentran en estado `SUPERADA` (0 en estado `VIGENTE`). Al invocar `POST /iot/calidad/reevaluar`, la consulta de dominio filtra explícitamente `WHERE estado_evaluacion = 'VIGENTE'`, retornando `422 SIN_EVALUACIONES_EN_RANGO`. Además, el endpoint de ingesta `POST /iot/telemetrias/batch` valida la existencia del dispositivo/sensor contra `modulo9.sensores` vía `modulo3.fn_validar_dispositivo`, rechazando nuevas telemetrías con `401 ERROR_AUTENTICACION`.
5. **¿Es viable ejecutar TC-324 con sensor 7?**  
   **No es viable.** Se activa el fallback inmediato al **Camino 1 (Autosiembra Canónica)**.
6. **Parámetros correctos para el payload (si hubiera sido viable):**  
   `offset: 0.10, ganancia: 1.05`.

---

## 2. Resumen de Ejecución de Newman (Camino 1)

- **Total Requests Ejecutados:** 23
- **Total Aserciones:** 24
- **Aserciones Aprobadas (OK):** 14
- **Aserciones Fallidas:** 10
- **Duración Total:** 6.2s
- **Estado de Sandbox:** 100% Cerrado / Revertido (HTTP 200 OK en `99.01-Rollback-Sandbox`)

### Detalle de Checkpoints y Fallas

| Fase / Subcaso | Aserciones | Estado | Causa Raíz / Observación |
|---|---|---|---|
| **00.01 – 00.06 Preflight** | 6 / 6 OK | **OK** | Login admin, consulta de catálogos y creación de finca, área y dispositivo IoT completados satisfactoriamente. |
| **00.07 Crear Sensor** | 0 / 1 OK | **FALLA** | Bloqueo externo por **`INC-M03-G167-SENSOR-500`** (`es_activo NOT NULL` sin default en `SensorModel`). |
| **00.08 Asociar Sensor** | 0 / 1 OK | **FALLA** | 404 Not Found debido a la falla previa en 00.07. |
| **TC-324 Reevaluación Exitosa** | 0 / 8 OK | **FALLA** | Cascada de fallas (400/405/422/404) al no existir el sensor creado en preflight. |
| **TC-325 Rechazos por Causa** | 4 / 4 OK | **OK** | Validaciones negativas de schema (causa omitida, vacía, <10 caracteres) retornan 400 Bad Request como espera el manejador global. |
| **TC-326 Rechazos por Fechas** | 3 / 3 OK | **OK** | Validación negativa (`fecha_desde > fecha_hasta`) rechazada con 400 Bad Request. |
| **99 Teardown** | 1 / 1 OK | **OK** | Reversión exitosa del sandbox sin dejar datos residuales. |

---

## 3. Evidencias Generadas

- **Reporte HTML Newman:** [`resultados/resultado_TC-M03-G170.html`](file:///c:/Users/Juansegutt/Integrador/sgpmp-backend/tests/Test_Testing/Test_Modulo3/RF-62/TC-M03-G170/resultados/resultado_TC-M03-G170.html)
- **Registro de Consola:** [`evidencias/console_run.log`](file:///c:/Users/Juansegutt/Integrador/sgpmp-backend/tests/Test_Testing/Test_Modulo3/RF-62/TC-M03-G170/evidencias/console_run.log)
- **Resumen JSON:** [`resultados/resultado_TC-M03-G170.json`](file:///c:/Users/Juansegutt/Integrador/sgpmp-backend/tests/Test_Testing/Test_Modulo3/RF-62/TC-M03-G170/resultados/resultado_TC-M03-G170.json)
- **Especificación y Precondiciones:** [`DISENO_Y_PRECONDICIONES.md`](file:///c:/Users/Juansegutt/Integrador/sgpmp-backend/tests/Test_Testing/Test_Modulo3/RF-62/TC-M03-G170/DISENO_Y_PRECONDICIONES.md)
