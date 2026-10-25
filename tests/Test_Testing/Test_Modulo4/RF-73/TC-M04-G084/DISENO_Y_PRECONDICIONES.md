# DISENO_Y_PRECONDICIONES — TC-M04-G084

## 1. Identificación y Metadatos
- **ID Caso / Grupo:** TC-M04-G084 (TC-M04-259, TC-M04-260, TC-M04-261)
- **Módulo:** Módulo 4 — Predicción e IA (RF-64 a RF-73)
- **Requisito Funcional:** RF-73 (Auditoría de eventos de inferencia, versionado de modelos, reentrenamiento y OTA) / RF-71 (Reentrenamiento y Degradación)
- **Estado Global:** [BLOQUEADO POR AUSENCIA DE ENDPOINT PRODUCTOR DE REENTRENAMIENTO]
- **Entorno Evaluado:** Backend TEST desplegado (`https://api.inmero.co/back-sigab-test`)
- **Herramienta de Ejecución:** Newman + reporter htmlextra bajo Sandbox transaccional.

---

## 2. Diagnóstico Técnico de Endpoints Productores y Motivo de Bloqueo

| Subcaso | Tipo Evento Esperado | Endpoint Productor Teórico | Endpoint Real en Backend | Estado Técnico |
|---|---|---|---|---|
| **TC-M04-259** | `REENTRENAMIENTO_INICIADO` | RF-71 (Trigger manual por Administrador) | Inexistente en API REST de backend | [BLOQUEADO] |
| **TC-M04-260** | `REENTRENAMIENTO_COMPLETADO` | RF-71 (Completación con métricas evaluadas) | Inexistente en API REST de backend | [BLOQUEADO] |
| **TC-M04-261** | `DEGRADACION_DETECTADA` | RF-71 (Validación con $F_1=0.78 < 0.80$) | Inexistente en API REST de backend | [BLOQUEADO] |

### Justificación Técnica Detallada:
1. **RF-71 (Reentrenamiento de Modelos):**
   - En el backend FastAPI de Módulo 4 (`src/prediction/infrastructure/routers/`), no existe ningún endpoint para disparar o consultar el ciclo de reentrenamiento de modelos de IA.
   - El use case `RegistrarVersionModeloUseCase:198` documenta explícitamente que el reentrenamiento es ejecutado internamente por procesos batch/workers del subsistema AIoT externo.
   - Por regla estricta de QA (Regla 2 y Regla 4): **PROHIBIDO simular eventos insertando directamente en PostgreSQL**. Por tanto, al no haber endpoints productores en la API REST, los tres subcasos quedan formalmente bloqueados.

---

## 3. Matriz de Esquemas de Auditoría (RF-73)

### Endpoint de Consulta: `GET /prediccion/auditoria`
- Schema de retorno: `AuditoriaM04ListResponse`.
- Permite filtrar por:
  - `tipo_evento=REENTRENAMIENTO_INICIADO`
  - `tipo_evento=REENTRENAMIENTO_COMPLETADO`
  - `tipo_evento=DEGRADACION_DETECTADA`
- Campos esperados en el registro:
  - `id_evento`: UUID
  - `tipo_evento`: string
  - `modulo`: `'MODULO4'`
  - `fecha_evento`: ISO-8601 UTC
  - `tipo_actor`: `'USUARIO'` (para trigger manual) | `'SISTEMA'` (para degradación/completación)
  - `severidad_evento`: `'INFO'` | `'CRITICAL'` (para degradación)
  - `resultado_operacion`: `'EXITOSO'`
  - `hash_evento`: SHA-256 (64 hex)

---

## 4. Teardown y Limpieza
- Pre-request genera `run_id = "test-" + {{$guid}}`.
- Último request: `DELETE /test-control/runs/{{run_id}}` (200 OK "Rollback exitoso").
- Duración total estimada: ~6 segundos.
