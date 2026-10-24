# TC-M03-G172: Rendimiento y Capacidad (RF-62)

## 1. Alcance y Objetivos
Evaluar el rendimiento, throughput y latencia P95 del flujo de ingesta y evaluación de calidad de telemetría IoT (RF-62 / RF-53).

## 2. Herramienta y Enfoque QA
- **Herramienta:** k6 (v2.2.0). Genera el reporte computable oficial en `resultados/resultado_TC-M03-G172.json` con `metrics.checks`.
- **Concurrencia y VUs:** Se configuran **5 VUs concurrentes** pre-asignados (con escalado dinámico de hasta 15 VUs). Todos los VUs comparten de forma segura el mismo `run_id` transaccional dentro del sandbox.
- **Teardown Garantizado:** La función `teardown()` de k6 está encapsulada en bloque `try/catch` y se ejecuta obligatoriamente al finalizar el ciclo de prueba, incluso si se presentan fallos de umbral o checks fallidos, garantizando la eliminación del `run_id` (`DELETE /test-control/runs/${data.runId}`) y el rollback en la base de datos.
- **Restricción Crítica de Sandbox:**
  - El sandbox transaccional de pruebas vive bajo una sola transacción con un timeout de 180 segundos.
  - Las cargas sostenidas de 10 a 15 minutos por escalón requeridas en el diseño teórico original son técnica y arquitectónicamente imposibles dentro del sandbox, ya que provocarían abortos por timeout (180 s), y ejecutarlas fuera del sandbox contaminaría la base de datos de pruebas.
  - Por esta razón, se implementa una versión ESCALADA y acotada (30 segundos de duración a 10 req/s = 600 req/min) que valida la capacidad sin saturar ni expirar la transacción.
  - Los umbrales que no provienen taxativamente de la especificación funcional de RF-62 se catalogan explícitamente como `[PROPUESTO]` en el script.

## 3. Subcasos Evaluados
1. **TC-M03-330 (Sobrecarga de Evaluación RF-62 en Ingesta):**
   - En el backend actual no existe un switch o endpoint de API que permita deshabilitar selectivamente el cómputo de RF-62 en tiempo de ejecución.
   - La comparación directa ON vs OFF queda `[BLOQUEADO]`. Se mide en su lugar la latencia P95 de la ingesta real (`http_req_duration: p(95)<1500ms` [PROPUESTO]) y la tasa de error (debe ser 0%).
2. **TC-M03-363 (Latencia de Pipeline y Colas) [CASO PROPUESTO]:**
   - Caso propuesto sin responsable asignado en la especificación base.
   - El backend opera la evaluación de forma sincrónica puntual mediante `POST /iot/calidad/{id}/evaluar`. No existe un endpoint público de métricas de cola (`/iot/metrics/queue`), por lo que la inspección de colas <=5,000 queda `[BLOQUEADO]`.
3. **TC-M03-364 (Capacidad Sostenida y Alertas de Degradación) [CASO PROPUESTO]:**
   - La prueba sostenida (>5 minutos continuos) y la alerta de degradación quedan `[BLOQUEADO]` por limitación de tiempo de sandbox (180 s).
   - Se ejecuta una ráfaga corta a 10 req/s (equivalente a 600 req/min) verificando que el backend no emita errores HTTP 500 y mantenga la persistencia íntegra.
