# DISENO_Y_PRECONDICIONES — TC-M04-G083

## 1. Identificación y Metadatos
- **ID Caso / Grupo:** TC-M04-G083 (TC-M04-257, TC-M04-258)
- **Módulo:** Módulo 4 — Predicción e IA (RF-64 a RF-73)
- **Requisito Funcional:** RF-73 (Auditoría de eventos de inferencia, versionado de modelos y OTA) / RF-70 (Distribución OTA a Nodos Edge)
- **Estado Global:** [BLOQUEADO POR AUSENCIA DE ENDPOINT PRODUCTOR DE DISTRIBUCIÓN OTA]
- **Entorno Evaluado:** Backend TEST desplegado (`https://api.inmero.co/back-sigab-test`)
- **Herramienta de Ejecución:** Newman + reporter htmlextra bajo Sandbox transaccional.

---

## 2. Diagnóstico Técnico de Endpoints Productores y Motivo de Bloqueo

| Subcaso | Tipo Evento Esperado | Endpoint Productor Teórico | Endpoint Real en Backend | Estado Técnico |
|---|---|---|---|---|
| **TC-M04-257** | `MODELO_DISTRIBUIDO_EDGE` | RF-70 (Distribución OTA con `hash_verificado=true`) | Inexistente en API REST de backend | [BLOQUEADO] |
| **TC-M04-258** | `HASH_INVALIDO_DETECTADO` | RF-70 (Simulación de hash corrupto en nodo Edge) | Inexistente en API REST de backend | [BLOQUEADO] |

### Justificación Técnica Detallada:
1. **RF-70 (Distribución OTA):**
   - El router `src/prediction/infrastructure/routers/ota_router.py` implementa exclusivamente endpoints de consulta:
     - `GET /prediccion/modelos/{id_version}/ota-status`
     - `GET /prediccion/despliegues`
   - Según la documentación técnica en `anotaciones/modulo_4/curls_m04_cu06_ota.md`:
     > *"Nota de split: Desarrollo solo expone endpoints de consulta (lectura). La tabla `modulo4.despliegues_ota` es escrita exclusivamente por el equipo IoT/IA."*
   - No existe ningún endpoint en la API REST para ordenar activamente la descarga o distribución de un modelo hacia un nodo Edge ni para registrar la confirmación de despliegue desde la capa cliente HTTP.
2. **Simulación de Integridad Corrupta en Edge (TC-M04-258):**
   - El evento `HASH_INVALIDO_DETECTADO` en la distribución requiere que un dispositivo Edge (`id_sistema="nodo_edge"`) rechace el artefacto. Al no haber endpoints de recepción o simulación de telemetría OTA en la API REST de FastAPI, es físicamente imposible inducir dicho estado mediante peticiones HTTP.
   - Conforme a la Regla 4 y Regla 8 de QA: **Queda catalogado como [BLOQUEADO] con registro explícito en console.log sin pm.test**.

---

## 3. Matriz de Esquemas de Auditoría (RF-73)

### Endpoint de Consulta: `GET /prediccion/auditoria`
- Schema de retorno: `AuditoriaM04ListResponse`.
- Permite filtrar por:
  - `tipo_evento=MODELO_DISTRIBUIDO_EDGE`
  - `tipo_evento=HASH_INVALIDO_DETECTADO`
- Campos definidos en el contrato:
  - `id_evento`: UUID
  - `tipo_evento`: string
  - `tipo_actor`: `'SISTEMA'`
  - `id_sistema`: string (`'nodo_edge'` o ID del dispositivo)
  - `severidad_evento`: `'INFO'` (distribución exitosa) | `'CRITICAL'` (hash inválido)
  - `resultado_operacion`: `'EXITOSO'` | `'FALLIDO'`
  - `hash_evento`: SHA-256 (64 hex)

---

## 4. Teardown y Limpieza
- Pre-request genera `run_id = "test-" + {{$guid}}`.
- Último request: `DELETE /test-control/runs/{{run_id}}` (200 OK "Rollback exitoso").
- Duración total estimada: ~6 segundos.
