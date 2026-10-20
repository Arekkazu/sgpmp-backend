# DISENO_Y_PRECONDICIONES — TC-M04-G086

## 1. Identificación y Metadatos
- **ID Caso / Grupo:** TC-M04-G086 (TC-M04-264, TC-M04-268, TC-M04-269)
- **Módulo:** Módulo 4 — Predicción e IA (RF-64 a RF-73)
- **Requisito Funcional:** RF-73 (Auditoría de eventos de inferencia, versionado de modelos, reentrenamiento y OTA) / RF-10 (Validación de Esquema e Integridad de Auditoría)
- **Estado Global:** [BLOQUEADO POR INEXISTENCIA DE ENDPOINT DE INGESTA DIRECTA DE AUDITORÍA]
- **Entorno Evaluado:** Backend TEST desplegado (`https://api.inmero.co/back-sigab-test`)
- **Herramienta de Ejecución:** Newman + reporter htmlextra bajo Sandbox transaccional.

---

## 2. Diagnóstico Técnico de Endpoints Productores y Motivo de Bloqueo

| Subcaso | Tipo Prueba Negativa | Endpoint Productor Teórico | Endpoint Real en Backend | Estado Técnico |
|---|---|---|---|---|
| **TC-M04-264** | Payload sin campos obligatorios | Ingesta de auditoría con payload incompleto | Inexistente en API REST (solo GET) | [BLOQUEADO] |
| **TC-M04-268** | Sin `id_referencia` | Ingesta de auditoría sin referencia | Inexistente en API REST (solo GET) | [BLOQUEADO] |
| **TC-M04-269** | `payload_evento` vacío o null | Ingesta de auditoría con payload vacío | Inexistente en API REST (solo GET) | [BLOQUEADO] |
| **Seguridad** | Intento de inyección manual | `POST /prediccion/auditoria` | Rechazado con 404 / 405 Method Not Allowed | [EJECUTABLE / PASS] |

### Justificación Técnica Detallada:
1. **Ausencia de Endpoint de Ingesta Directa:**
   - La bitácora de auditoría M04 (`src/prediction/infrastructure/routers/auditoria_m04_router.py`) expone exclusivamente métodos de consulta de solo lectura (`GET /prediccion/auditoria`, `GET /prediccion/auditoria/exportar`, `GET /prediccion/auditoria/{id}`).
   - Los eventos de auditoría son registrados únicamente por los use cases de dominio interno a través del repositorio `SqlAlchemyEventoAuditoriaM04Repository:113` cuando ocurren transiciones legítimas del negocio.
   - Conforme a la advertencia crítica de la especificación: *"Si NO existe tal endpoint de ingesta directa → los 3 subcasos son BLOQUEADOS con motivo (console.log, sin pm.test). NO simular el rechazo con SQL ni con monkeypatch."*
2. **Rechazo de Inyección Manual Directa:**
   - Para verificar la seguridad y robustez del endpoint de auditoría, se incluye un intento de invocación `POST /prediccion/auditoria`. FastAPI rechaza la petición con `404 Not Found` o `405 Method Not Allowed`, confirmando que ningún actor puede inyectar eventos de auditoría arbitrarios o malformados desde la capa HTTP.

---

## 3. Matriz de Esquemas de Auditoría (RF-73)

### Endpoint de Consulta: `GET /prediccion/auditoria`
- Schema de retorno: `AuditoriaM04ListResponse`.
- Permite verificar que tras los intentos de inyección manual ilegítima, la bitácora permanece intacta y libre de eventos malformados.

---

## 4. Teardown y Limpieza
- Pre-request genera `run_id = "test-" + {{$guid}}`.
- Último request: `DELETE /test-control/runs/{{run_id}}` (200 OK "Rollback exitoso").
- Duración total estimada: ~6 segundos.
