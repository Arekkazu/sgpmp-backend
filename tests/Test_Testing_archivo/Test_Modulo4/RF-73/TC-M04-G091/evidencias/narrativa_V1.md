# Informe Narrativo de Ejecución (V1) — TC-M04-G091

## 1. Resumen Ejecutivo
- **Caso de Prueba:** TC-M04-G091
- **Requisito Funcional:** RF-73 (Auditoría de eventos de predicción — Resiliencia y Fallback)
- **Fecha de Diseño:** 2026-10-20
- **Entorno:** Backend TEST (`https://api.inmero.co/back-sigab-test`) bajo Sandbox Transaccional SGPMP.
- **Resultado Global:** Suite diseñada y construida contra contrato esperado. Por naturaleza de los subcasos (que involucran detención física de base de datos, simulación de corte WAN en nodos Edge y esperas de 10 min a 72 horas), la suite queda catalogada como `PENDIENTE_DEV` para su ejecución en la FASE DE INFRAESTRUCTURA con orquestación dedicada.

## 2. Diagnóstico Técnico y Subcasos Evaluados
- **TC-M04-281 (Fallback tras caída de BD):** Petición sobre `GET /prediccion/auditoria` validando la presencia de eventos con `origen_registro = "FALLBACK"`.
- **TC-M04-282 (Sincronización FIFO Post-Recuperación):** Comprobación de orden temporal no decreciente en los eventos sincronizados tras el restablecimiento del servicio.
- **TC-M04-283 (Preservación de Timestamp Original):** Verificación de integridad temporal: la propiedad `fecha_evento` debe reflejar el momento exacto de emisión durante la caída y no el momento de la inserción a BD.
- **TC-M04-284 (Fallback Edge y Sincronización Diferida 72h):** Verificación de eventos con `origen_registro = "EDGE"` tras la reconexión de red.

## 3. Conformidad con Reglas de Calidad SGPMP
- **Regla de Oro #1:** Solo diseño y construcción. Cero peticiones ejecutadas contra TEST.
- **Regla de Oro #2:** Directorio `resultados/` en minúscula y completamente vacío.
- **Cero DML en BD:** Verificado por script de integridad. Ningún INSERT/UPDATE/DELETE/DDL ejecutado vía `/test-control/query`.
- **Aislamiento Sandbox:** Pre-request dinámico con `X-Test-Run-Id` y rollback garantizado con `DELETE /test-control/runs/{{run_id}}`.
