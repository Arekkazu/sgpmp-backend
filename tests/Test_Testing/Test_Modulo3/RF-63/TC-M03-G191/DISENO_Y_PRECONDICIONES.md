# DISENO_Y_PRECONDICIONES — TC-M03-G191

## 1. Identificación y Metadatos
- **ID Caso / Grupo:** TC-M03-G191 (TC-M03-367)
- **Módulo:** Módulo 3 — Telemetría, Infraestructura IoT y Bitácora de Auditoría
- **Requisito Funcional:** RF-63 (Bitácora de Auditoría IoT) — Robustez e Integridad ante Inyecciones de Eventos
- **Nivel de Automatización:** Newman / Postman Collection (v2.1)
- **Entorno:** Backend TEST (`https://api.inmero.co/back-sigab-test`) bajo Sandbox Transaccional (`ENABLE_TEST_SANDBOX=true`)

---

## 2. Diagnóstico Técnico y Alcance por Subcaso
1. **Subcasos (a), (b), (c), (e): Inyección Directa en Bus Interno con Campos Faltantes:**
   - **Estado:** `[BLOQUEADO]`.
   - **Motivo:** El bus interno de eventos y la cola asíncrona no están expuestos vía API REST pública. Intentar simular esto violaría la Regla 2 (cero DML directo a BD). Requiere infraestructura de pruebas unitarias o de laboratorio con mocks del bus de eventos.
2. **Subcaso (d): Rechazo de Inyección Manual Directa por API:**
   - **Endpoint Evaluado:** `POST /iot/auditoria` y `POST /iot/auditoria/eventos`.
   - **Comportamiento Esperado:** La bitácora de auditoría es de generación automática impulsada por el dominio; ningún usuario (incluido el Administrador) debe poder inyectar eventos manualmente por HTTP. Se exige HTTP 404 Not Found o 405 Method Not Allowed.
   - **Comprobación Posterior:** `GET /iot/auditoria?tipo_evento=INYECCION_MANUAL_ILEGITIMA` confirma que la colección no fue contaminada.

---

## 3. Teardown y Limpieza
- Pre-request genera `run_id = "test-" + {{$guid}}`.
- Último request: `DELETE /test-control/runs/{{run_id}}` (200 OK "Rollback exitoso").
- Duración total estimada: ~6 segundos.
