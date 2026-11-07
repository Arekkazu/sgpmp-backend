# DISENO_Y_PRECONDICIONES — TC-M04-G081

## 1. Identificación y Metadatos
- **ID Caso / Grupo:** TC-M04-G081 (TC-M04-250, TC-M04-251, TC-M04-252)
- **Módulo:** Módulo 4 — Predicción e IA (RF-64 a RF-73)
- **Requisito Funcional:** RF-73 (Auditoría de eventos de inferencia, versionado de modelos y OTA)
- **Estado Global:** [BLOQUEADO POR AUSENCIA DE ENDPOINT PRODUCTOR]
- **Entorno Evaluado:** Backend TEST desplegado (`https://api.inmero.co/back-sigab-test`)
- **Herramienta de Ejecución:** Newman + reporter htmlextra (desviación justificada respecto al diseño original Pytest+Postman para operar bajo Sandbox transaccional sin acceso directo a proceso).

---

## 2. Diagnóstico Técnico de Endpoints Productores y Motivo de Bloqueo

| Subcaso | Tipo Evento Esperado | Endpoint Productor Teórico | Endpoint Real en Backend | Estado Técnico |
|---|---|---|---|---|
| **TC-M04-250** | `INFERENCIA_EJECUTADA` | RF-66 (Motor de inferencia, payload válido) | Inexistente en API REST de backend | [BLOQUEADO] |
| **TC-M04-251** | `INFERENCIA_RECHAZADA` | RF-66 (Motor de inferencia, payload corrupto) | Inexistente en API REST de backend | [BLOQUEADO] |
| **TC-M04-252** | `ALERTA_PREDICCION_GENERADA` | RF-57 (Alerta con `nivel_riesgo=3`) | `POST /iot/alertas` en M03 no emite hacia M04 | [BLOQUEADO] |

### Justificación Técnica Detallada:
1. **RF-66 (Motor de Inferencia):**
   - El router `src/prediction/infrastructure/routers/motor_ia_router.py` únicamente implementa endpoints de configuración (`POST /prediccion/motor-ia`, `GET /prediccion/motor-ia`, `GET /prediccion/motor-ia/{tipo_modelo}`).
   - No existe ningún endpoint REST (`POST /prediccion/inferencia` o similar) para disparar inferencias de patologías desde la API externa.
   - Según la documentación arquitectónica en `anotaciones/implementacion_rfc006_rfc009_rfc011.md`: *"El motor de inferencia no vive en el backend. Pertenece al subsistema AIoT / IA externo"*.
   - Por regla estricta de QA (Regla 2 y Regla 4): **PROHIBIDO simular eventos insertando directamente en PostgreSQL**. Por tanto, al no haber endpoint productor REST, los subcasos TC-M04-250 y TC-M04-251 quedan bloqueados.
2. **RF-57 (Alertas Sanitarias de Predicción):**
   - La tabla `modulo4.alertas_patologicas` está documentada en el baseline como generada por el motor al detectar $P(\text{riesgo\_alto}) \ge \text{umbral}$, pero el módulo M03 (`src/telemetry/infrastructure/routers/alerta_router.py`) gestiona únicamente alertas ambientales telemétricas (umbrales de temperatura, humedad, etc.).
   - No existe endpoint expuesto para generar alertas sanitarias de predicción con severidad CRITICAL hacia la bitácora `modulo4.eventos_auditoria_m04`.

---

## 3. Matriz de Esquemas y Contratos de Auditoría (RF-73)

### Endpoint de Consulta: `GET /prediccion/auditoria`
- **Filtros expuestos por OpenAPI:** `tipo_evento`, `fecha_desde`, `fecha_hasta`, `id_usuario`, `id_sistema`, `id_referencia`, `severidad_evento`, `pagina`, `por_pagina`.
- **Campos del Schema `EventoAuditoriaM04Response`:**
  - `id_evento`: UUID v4
  - `tipo_evento`: string
  - `modulo`: `'M04'`
  - `fecha_evento`: ISO-8601 UTC
  - `tipo_actor`: string (`'SISTEMA'`, `'USUARIO'`)
  - `correlacion_id`: UUID
  - `payload_evento`: dict JSON
  - `es_payload_truncado`: boolean
  - `severidad_evento`: `'INFO'` | `'WARNING'` | `'ERROR'` | `'CRITICAL'`
  - `origen_registro`: string
  - `resultado_operacion`: `'EXITOSO'` | `'FALLIDO'`
  - `hash_evento`: string SHA-256 (64 hex)

---

## 4. Estrategia de Ejecución y Aislamiento en Colección

- **Sandbox Transaccional:** Cada corrida genera dinámicamente un `run_id` en el pre-request e inyecta `X-Test-Run-Id` y `X-Sandbox-Secret`.
- **Teardown Garantizado:** Invocación final a `DELETE /test-control/runs/{{run_id}}` con aserción 200 y mensaje `Rollback exitoso`.
- **Tratamiento de Subcasos Bloqueados:** Siguiendo la Regla 4 y Regla 8 del estándar SGPMP, las peticiones hacia los endpoints inexistentes **NO ejecutan `pm.test` que puedan maquillar el veredicto**, sino que registran trazas detalladas mediante `console.log("[BLOQUEADO] ...")` explicando la causa técnica.
