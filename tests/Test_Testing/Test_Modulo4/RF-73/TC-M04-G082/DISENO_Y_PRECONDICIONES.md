# DISENO_Y_PRECONDICIONES — TC-M04-G082

## 1. Identificación y Metadatos
- **ID Caso / Grupo:** TC-M04-G082 (TC-M04-253, TC-M04-254, TC-M04-255, TC-M04-256)
- **Módulo:** Módulo 4 — Predicción e IA (RF-64 a RF-73)
- **Requisito Funcional:** RF-73 (Auditoría de eventos de inferencia, versionado de modelos y OTA) / RF-69 (Validación y Versionado de Modelos)
- **Estado Global:** [PARCIALMENTE BLOQUEADO POR ENDPOINTS INTERNOS DE PIPELINE CI/CD]
- **Entorno Evaluado:** Backend TEST desplegado (`https://api.inmero.co/back-sigab-test`)
- **Herramienta de Ejecución:** Newman + reporter htmlextra bajo Sandbox transaccional.

---

## 2. Diagnóstico Técnico de Endpoints Productores y Motivo de Bloqueo

| Subcaso | Tipo Evento Esperado | Endpoint Productor Teórico | Endpoint Real en Backend | Estado Técnico |
|---|---|---|---|---|
| **TC-M04-253** | `VERSION_REGISTRADA` | RF-71 (Registro automático con métricas) | `POST /prediccion/modelos` (Header `X-RF71-Internal-Key` + ONNX binario) | [BLOQUEADO] |
| **TC-M04-254** | `VERSION_APROBADA` | RF-71 (Validación métricas f1>=0.80, recall>=0.85) | Disparado internamente en `POST /prediccion/modelos` | [BLOQUEADO] |
| **TC-M04-255** | `VERSION_RECHAZADA` | RF-71 (Validación métricas f1=0.70 < 0.80) | Disparado internamente en `POST /prediccion/modelos` | [BLOQUEADO] |
| **TC-M04-256** | `VERSION_ACTIVADA` | RF-71 (Activación atómica v2.0 -> ACTIVO, v1.0 -> DEPRECADO) | `POST /prediccion/modelos/{id_version}/activar` | [EJECUTABLE / CONDICIONADO] |

### Justificación Técnica Detallada:
1. **RF-71 (Registro Interno y Validación Automática):**
   - El endpoint `POST /prediccion/modelos` está definido en `src/prediction/infrastructure/routers/version_modelo_router.py:42`.
   - Según el contrato y el use case `RegistrarVersionModeloUseCase`:
     - Exige la cabecera `X-RF71-Internal-Key`, la cual se compara contra la variable de entorno de infraestructura `RF71_INTERNAL_KEY`. Si la clave es inválida o ausente, el backend rechaza la petición con `400` y emite el evento de auditoría `INTENTO_CARGA_MODELO_EXTERNO`.
     - Exige la carga `multipart/form-data` de un binario ONNX (`archivo_modelo`) con cálculo estricto de SHA-256 (`hash_artefacto_sha256`) y `dataset_entrenamiento_hash`.
   - Dado que `RF71_INTERNAL_KEY` es una clave de infraestructura no expuesta a clientes de prueba y el pipeline RF-71 es un job asíncrono, los subcasos TC-M04-253, TC-M04-254 y TC-M04-255 quedan clasificados como [BLOQUEADO] para evitar falsos positivos.
2. **Activación de Versión (TC-M04-256):**
   - El endpoint `POST /prediccion/modelos/{id_version}/activar` está expuesto vía RBAC (recurso 43, acción 5) para Administradores y Veterinarios.
   - Requiere la existencia de una versión previa en estado `APROBADO`. La suite consulta `GET /prediccion/modelos?estado=APROBADO`. Si encuentra una versión candidata, ejecuta la activación y valida la emisión de `VERSION_ACTIVADA` en `GET /prediccion/auditoria`. Si no existe versión aprobada, registra el bloqueo en logs.

---

## 3. Matriz de Esquemas de Auditoría (RF-73)

### Endpoint de Consulta: `GET /prediccion/auditoria`
- Schema de retorno: `AuditoriaM04ListResponse` conteniendo `EventoAuditoriaM04Response`.
- Campos verificados:
  - `tipo_evento`: `VERSION_ACTIVADA`
  - `tipo_actor`: `USUARIO`
  - `id_usuario`: ID del administrador autenticado
  - `severidad_evento`: `INFO`
  - `resultado_operacion`: `EXITOSO`
  - `hash_evento`: SHA-256 hex-64
  - `payload_evento`: dict JSON conteniendo snapshot de la versión y `id_version_nueva`.

---

## 4. Teardown y Limpieza
- Pre-request genera `run_id = "test-" + {{$guid}}`.
- Último request: `DELETE /test-control/runs/{{run_id}}` (200 OK "Rollback exitoso").
- Duración total estimada: ~10 segundos.
