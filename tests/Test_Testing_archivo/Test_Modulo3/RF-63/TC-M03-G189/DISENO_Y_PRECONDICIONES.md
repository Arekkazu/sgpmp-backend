# DISENO_Y_PRECONDICIONES — TC-M03-G189

## 1. Identificación y Metadatos
- **ID Caso / Grupo:** TC-M03-G189 (TC-M03-360, TC-M03-361, TC-M03-362, TC-M03-368)
- **Módulo:** Módulo 3 — Telemetría, Infraestructura IoT y Bitácora de Auditoría
- **Requisito Funcional:** RF-63 (Bitácora de Auditoría IoT) — Rendimiento, Escalabilidad y Concurrencia
- **Herramienta:** k6 (`test_tc_m03_g189.js`)
- **Entorno:** Backend TEST (`https://api.inmero.co/back-sigab-test`) bajo Sandbox Transaccional (`ENABLE_TEST_SANDBOX=true`)

---

## 2. Diagnóstico Técnico y Adaptación al Sandbox
1. **Restricciones del Sandbox:**
   - Una corrida sandbox posee timeout de 180 s y vive en una sola transacción PostgreSQL aislada.
   - Cargas de 50 VUs x 5 min o 5,000 eventos/min x 3 min son imposibles en sandbox sin saturar los recursos compartidos de TEST.
2. **Estrategia por Subcaso:**
   - **TC-M03-360 (Verificación de integridad):**
     - Endpoint: `POST /iot/auditoria/verificar-integridad`.
     - Se evalúa sobre el volumen activo en sandbox.
     - **SLA $\le 10$ s sobre 10,000 eventos:** Marcado como `[BLOQUEADO]` por requerir precarga masiva de eventos.
   - **TC-M03-361 (Concurrencia de consultas):**
     - Baseline 1 VU durante 10 s, seguido de rampa a 5 VUs sostenidos por 20 s.
     - Umbral de comparación 1.2x marcado como `[PROPUESTO]`.
   - **TC-M03-362 (Ingesta masiva y persistencia):**
     - Ráfaga reducida (~600 eventos/min x 30 s).
     - **SLA P95 $\le 5$ s:** Marcado como `[BLOQUEADO]`.
   - **TC-M03-368 (Priorización de severidad en cola):**
     - **Marcado como `[BLOQUEADO]`:** Requiere endpoints de métricas de cola interna que no existen en la API del backend.

---

## 3. Teardown y Limpieza
- Pre-request genera `run_id = "test-k6-g189-" + timestamp`.
- Teardown en k6 invoca `DELETE /test-control/runs/${runId}` con aserción de HTTP 200.
- Duración total de la prueba: ~45 segundos.
