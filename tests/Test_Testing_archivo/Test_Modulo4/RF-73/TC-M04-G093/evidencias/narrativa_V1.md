# Informe Narrativo de Ejecución (V1) — TC-M04-G093

## 1. Resumen Ejecutivo
- **Caso de Prueba:** TC-M04-G093
- **Requisito Funcional:** RF-73 (Auditoría de eventos de predicción — Pruebas de Carga y Rendimiento)
- **Herramienta:** k6
- **Fecha de Diseño:** 2026-10-20
- **Entorno:** Backend TEST (`https://api.inmero.co/back-sigab-test`) bajo Sandbox Transaccional SGPMP.
- **Resultado Global:** Suite diseñada y construida (sin ejecución por directriz estricta de entrega). La suite se ajusta a los límites de capacidad del sandbox transaccional (≤ 5 VUs, ≤ 60 s), catalogando las cargas sostenidas de 10 min y 100 usuarios como `FASE DE CARGA SEPARADA`.

## 2. Diagnóstico Técnico y Subcasos Evaluados
- **TC-M04-288 (Carga Normal Escalada):** Consulta a `GET /prediccion/auditoria` con umbral de latencia P95 ≤ 2,000 ms.
- **TC-M04-289 (Carga Pico Escalada):** Ráfaga controlada con umbral de latencia P95 ≤ 5,000 ms.
- **TC-M04-290 (Sin Pérdida de Eventos):** Verificación de integridad en las respuestas y ausencia de pérdida de paquetes o caídas bajo carga.
- **TC-M04-291 (Exportación Masiva):** Petición de descarga masiva de bitácora mediante `GET /prediccion/auditoria/exportar?formato=json`.
- **TC-M04-292 (Concurrencia de Consultas):** Evaluación de estabilidad bajo múltiples usuarios concurrentes respetando la cuota máxima del sandbox transaccional.

## 3. Conformidad con Reglas de Calidad SGPMP
- **Regla de Oro #1:** Solo diseño y construcción. Ninguna prueba ejecutada contra TEST.
- **Regla de Oro #2:** Directorio `resultados/` en minúscula y completamente vacío.
- **Cero DML en BD:** Ninguna sentencia SQL directa ejecutada.
- **Aislamiento Sandbox en k6:** Pre-request dinámico con `run_id` en `setup()`, cabeceras `X-Test-Run-Id` / `X-Sandbox-Secret` en cada iteración y rollback garantizado en `teardown()`.
