# DISENO_Y_PRECONDICIONES — TC-M03-G190

## 1. Identificación y Metadatos
- **ID Caso / Grupo:** TC-M03-G190 (TC-M03-365, TC-M03-366)
- **Módulo:** Módulo 3 — Telemetría, Infraestructura IoT y Bitácora de Auditoría
- **Requisito Funcional:** RF-63 (Bitácora de Auditoría IoT) — Inmutabilidad y Detección de Manipulación
- **Nivel de Automatización:** Newman / Postman Collection (v2.1)
- **Entorno:** Backend TEST (`https://api.inmero.co/back-sigab-test`) bajo Sandbox Transaccional (`ENABLE_TEST_SANDBOX=true`)

---

## 2. Diagnóstico Técnico y Enfoque Preventivo vs Detectivo
1. **TC-M03-365: Enfoque Preventivo por API:**
   - **Rutas Evaluadas:** `PUT /iot/auditoria/{id}`, `PATCH /iot/auditoria/{id}`, `DELETE /iot/auditoria/{id}`.
   - **Comportamiento Esperado:** Rechazo estricto mediante HTTP 405 Method Not Allowed (o 404 Not Found), garantizando que ningún verbo HTTP de mutación altere o elimine registros.
   - **Verificación de Inmutabilidad:** Invocación de `GET /iot/auditoria/{id}` para asegurar que el registro permanece intacto y la `firma_hmac` coincide exactamente.
   - **Verificación FA-09 (Auditar Intentos de Alteración):** Se comprueba si el backend genera un evento `ACCESO_DENEGADO` al intentar métodos no permitidos. Si no se registra, se reporta `[DEFECTO FA-09]`.
2. **TC-M03-366: Enfoque Detectivo por Alteración Directa en BD:**
   - **Estado:** `[BLOQUEADO]` por Regla 2 (CERO DML en BD vía `/test-control/query`).
   - Modificar manualmente filas de `modulo3.bitacora_auditoria_iot` mediante `UPDATE` viola las políticas de calidad y seguridad del proyecto. Requiere un endpoint administrativo mock de corrupción o ejecución en laboratorio local.

---

## 3. Teardown y Limpieza
- Pre-request genera `run_id = "test-" + {{$guid}}`.
- Último request: `DELETE /test-control/runs/{{run_id}}` (200 OK "Rollback exitoso").
- Duración total estimada: ~8 segundos.
