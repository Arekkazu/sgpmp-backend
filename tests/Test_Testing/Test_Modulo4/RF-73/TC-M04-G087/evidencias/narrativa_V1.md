# Informe Narrativo de Ejecución (V1) — TC-M04-G087

## 1. Resumen Ejecutivo
- **Caso de Prueba:** TC-M04-G087
- **Requisito Funcional:** RF-73 (Auditoría de eventos de predicción)
- **Fecha de Diseño:** 2026-10-20
- **Entorno:** Backend TEST desplegado (`https://api.inmero.co/back-sigab-test`) bajo Sandbox Transaccional SGPMP.
- **Resultado Global:** Suite diseñada, construida y ejecutable contra contrato esperado. Subcasos clasificados como `PENDIENTE_DEV` a la espera de la exposición del endpoint `POST /prediccion/auditoria/eventos`.

## 2. Diagnóstico Técnico y Subcasos Evaluados
- **TC-M04-265 (Catálogo Inválido):** Se valida el rechazo ante `tipo_evento="EVENTO_INVENTADO"` con HTTP 400/422. En el backend actual, el endpoint de ingesta está en fase de desarrollo (`PENDIENTE_DEV`).
- **TC-M04-266 (Fuentes Nulas):** Se valida el rechazo ante `id_usuario=null` e `id_sistema=null` con HTTP 400/422 (evento huérfano sin trazabilidad). Estado: `PENDIENTE_DEV`.
- **TC-M04-267 (Doble Fuente / Violación XOR):** Se valida el rechazo ante presencia concurrente de `id_usuario=5` e `id_sistema="motor_inferencia"` con HTTP 400/422 (violación de exclusividad de actor). Estado: `PENDIENTE_DEV`.

## 3. Conformidad con Reglas de Calidad SGPMP
- **Regla de Oro #0:** Reporte computable ubicado exclusivamente en `resultados/` (minúscula).
- **Cero DML en BD:** Verificado por script de integridad. Ningún INSERT/UPDATE/DELETE/DDL ejecutado vía `/test-control/query`.
- **Aislamiento Sandbox:** Pre-request dinámico con `X-Test-Run-Id` y rollback garantizado con `DELETE /test-control/runs/{{run_id}}` (200 + Rollback exitoso).
- **Transición Automática:** Al implementarse el endpoint en FastAPI, el script ejecutará las aserciones funcionales sin requerir reescritura.
