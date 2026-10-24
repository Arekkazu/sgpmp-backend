# DISENO_Y_PRECONDICIONES — TC-M04-G093

## 1. Identificación y Metadatos
- **ID Caso / Grupo:** TC-M04-G093 (TC-M04-288, TC-M04-289, TC-M04-290, TC-M04-291, TC-M04-292)
- **Módulo:** Módulo 4 — Predicción e IA (RF-64 a RF-73)
- **Requisito Funcional:** RF-73 (Auditoría de eventos de predicción — Pruebas de Carga y Volumen)
- **Fase:** DISEÑO TÉCNICO Y AUTOMATIZACIÓN DE PRUEBAS (SOLO DISEÑO Y CONSTRUCCIÓN)
- **Estado Global:** [DISENADO / REQUIERE FASE DE CARGA SEPARADA]
- **Entorno Evaluado:** Backend TEST (`https://api.inmero.co/back-sigab-test`) bajo Sandbox Transaccional SGPMP.
- **Herramienta de Ejecución:** k6 (reporte computable `resultados/resultado_TC-M04-G093.json` generado vía `--summary-export`).

---

## 2. Diagnóstico Técnico y Umbrales de Rendimiento

| Subcaso | Carga Objetivo Teórica | Escalado en Sandbox | Umbral de Aceptación | Estado Técnico |
|---|---|---|---|---|
| **TC-M04-288** | 1,000 req/min sostenidas (10 min) | Escalado a ~30 s con rampa progresiva (≤ 5 VUs) | P95 ≤ 2,000 ms (`p(95)<2000`) | [DISEÑADO ESCALADO] |
| **TC-M04-289** | 5,000 req/min pico sostenidas (5 min) | Escalado a ráfagas con concurrencia máxima permitida | P95 ≤ 5,000 ms (`p(95)<5000`) | [DISEÑADO ESCALADO] |
| **TC-M04-290** | Sin pérdida de eventos bajo carga | Verificación de respuestas 200 OK y estructura íntegra (`items`) | Tasa de error < 5% (`http_req_failed < 0.05`) | [DISEÑADO ESCALADO] |
| **TC-M04-291** | Exportación masiva (>10,000 registros) | Petición a `GET /prediccion/auditoria/exportar?formato=json` | HTTP 200 directo o 202 con cola | [OPERATIVO / ESCALADO] |
| **TC-M04-292** | 100 usuarios concurrentes | Escalado a ≤ 5 VUs (techo operativo del sandbox transaccional) | HTTP 200 sin degradación 5xx | [DISEÑADO ESCALADO] |

---

## 3. PENDIENTES DE DESARROLLO

| Subcaso | Endpoint Esperado | Contrato Esperado | Asignado A (Equipo/Área) |
|---|---|---|---|
| **TC-M04-291** | `GET /auditoria/exportaciones/{id_cola}` | Polling asíncrono para exportaciones de volumen superior a 10,000 registros | Equipo Backend Core / Infraestructura |

---

## 4. FASE DE CARGA SEPARADA (Restricciones del Sandbox Transaccional)

> [!WARNING]
> Las cargas sostenidas a escala real estipuladas por la especificación original de QA:
> - **1,000 req/min durante 10 minutos continuos (TC-M04-288)**
> - **5,000 req/min durante 5 minutos de pico continuo (TC-M04-289)**
> - **100 usuarios concurrentes simultáneos (TC-M04-292)**
> - **Exportación masiva de >10,000 registros reales en BD (TC-M04-291)**
> 
> **NO son ejecutables dentro del sandbox transaccional HTTP de SGPMP** por los siguientes motivos técnicos:
> 1. **Timeout del Sandbox (180 s):** Toda corrida de sandbox está atada a una sola transacción PostgreSQL con un tiempo de vida máximo estricto de 180 segundos. Una prueba de 10 o 15 minutos provoca un timeout forzado y aborto por rollback.
> 2. **Límite de Concurrencia Transaccional (`MAX_CONCURRENT_RUNS=5`):** El middleware de sandbox `TestSandboxMiddleware` restringe la concurrencia a un máximo de 5 transacciones activas para proteger la integridad del pool de conexiones. Intentar 100 VUs en el sandbox saturaría el pool con errores 503/429.
> 3. **Principio Zero-Pollution:** Insertar 10,000 registros de prueba en una sola corrida sandbox excede los límites de memoria de transacción y saturaría el log WAL.
> 
> Por tanto, el script de k6 entregado valida la funcionalidad bajo una **carga escalada representativa (≤ 5 VUs, ≤ 60 s)**, y las cargas sostenidas a escala completa se catalogan para ejecución en la **FASE DE CARGA SEPARADA**, en un entorno dedicado de staging o performance sin capa de sandbox.

---

## 5. Estrategia de Sandbox y Teardown
- En la función `setup()` de k6 se genera un `runId` único (`test-m04-g093-...`) y se obtienen credenciales administrativas válidas (`POST /sesiones/`).
- Todas las peticiones HTTP del test inyectan cabeceras `X-Test-Run-Id` y `X-Sandbox-Secret`.
- En la función `teardown(data)` se ejecuta invariablemente `DELETE /test-control/runs/{runId}` con aserción de rollback transaccional exitoso.
- Cumplimiento de regla de CERO DML directa a base de datos.
