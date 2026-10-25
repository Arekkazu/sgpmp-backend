# Informe Narrativo de Ejecución (V1) — TC-M04-G086

## 1. Resumen Ejecutivo
- **Caso de Prueba:** TC-M04-G086
- **Requisito Funcional:** RF-73 (Auditoría de eventos de inferencia, versionado de modelos, reentrenamiento y OTA) / RF-10 (Validación de Esquema e Integridad de Auditoría)
- **Fecha de Ejecución:** 2026-10-20
- **Entorno:** Backend TEST desplegado (`https://api.inmero.co/back-sigab-test`) bajo Sandbox Transaccional SGPMP.
- **Resultado Global:** Suite estructurada y sanitizada. Los subcasos negativos de validación de esquema están clasificados como BLOQUEADOS debido a que el backend no expone ningún endpoint de ingesta directa de eventos de auditoría (el repositorio es append-only interno). Se verifica adicionalmente que el intento de `POST` manual sobre `/prediccion/auditoria` es rechazado con 404/405.

## 2. Diagnóstico Técnico de Bloqueos
- **TC-M04-264 (Payload incompleto):** No hay endpoint de ingesta pública de auditoría para probar rechazo de payloads incompletos.
- **TC-M04-268 (Sin id_referencia):** Mismo motivo por inexistencia de endpoint de ingesta directa.
- **TC-M04-269 (Payload_evento vacío):** Mismo motivo por inexistencia de endpoint de ingesta directa.

## 3. Conformidad con Reglas de Calidad SGPMP
- **Regla de Oro #0:** Reporte computable ubicado exclusivamente en `resultados/` (minúscula).
- **Cero DML en BD:** Verificado por `verificar_sin_dml.cjs`.
- **Aislamiento Sandbox:** Pre-request dinámico con `X-Test-Run-Id` y rollback garantizado con `DELETE /test-control/runs/{{run_id}}`.
