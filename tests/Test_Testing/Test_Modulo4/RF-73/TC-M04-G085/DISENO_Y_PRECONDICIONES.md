# DISENO_Y_PRECONDICIONES — TC-M04-G085

## 1. Identificación y Metadatos
- **ID Caso / Grupo:** TC-M04-G085 (TC-M04-262, TC-M04-263)
- **Módulo:** Módulo 4 — Predicción e IA (RF-64 a RF-73)
- **Requisito Funcional:** RF-73 (Auditoría de eventos de inferencia, versionado de modelos, reentrenamiento y OTA) / RF-72 (Retroalimentación Clínica y Conflictos)
- **Estado Global:** [BLOQUEADO POR FALTA DE PRECONDICIÓN DE INFERENCIA POR API]
- **Entorno Evaluado:** Backend TEST desplegado (`https://api.inmero.co/back-sigab-test`)
- **Herramienta de Ejecución:** Newman + reporter htmlextra bajo Sandbox transaccional.

---

## 2. Diagnóstico Técnico de Endpoints Productores y Motivo de Bloqueo

| Subcaso | Tipo Evento Esperado | Endpoint Productor Teórico | Endpoint Real en Backend | Estado Técnico |
|---|---|---|---|---|
| **TC-M04-262** | `RETROALIMENTACION_REGISTRADA` | RF-72 (`POST /prediccion/retroalimentacion`) | Requiere `id_resultado_inferencia` válido | [BLOQUEADO] |
| **TC-M04-263** | `CONFLICTO_RETROALIMENTACION` | RF-72 (Dos feedbacks contradictorios) | Requiere `id_resultado_inferencia` válido | [BLOQUEADO] |

### Justificación Técnica Detallada:
1. **Precondición Ineludible de Inferencia:**
   - El endpoint `POST /prediccion/retroalimentacion` ([`retroalimentacion_clinica_router.py:35`](file:///c:/Users/Juansegutt/Integrador/sgpmp-backend/src/prediction/infrastructure/routers/retroalimentacion_clinica_router.py#L35)) exige un `id_resultado_inferencia` de tipo UUID4.
   - En [`registrar_retroalimentacion_use_case.py:46`](file:///c:/Users/Juansegutt/Integrador/sgpmp-backend/src/prediction/application/use_cases/retroalimentacion/registrar_retroalimentacion_use_case.py#L46), el backend consulta `self._resultado_port.obtener_por_id(dto.id_resultado_inferencia)`. Si la fila no existe en la tabla `modulo4.resultados_inferencia`, lanza de inmediato `NotFoundError(code="RESULTADO_INFERENCIA_NO_ENCONTRADO")`.
   - Dado que el motor de inferencia (RF-66) no está expuesto vía API REST en FastAPI y la Regla 2 prohíbe terminantemente realizar escrituras directas (INSERT) sobre PostgreSQL mediante `/test-control/query`, es imposible aprovisionar una inferencia válida mediante la API.
   - Conforme a la instrucción explícita del estándar QA: *"Precondición: necesita un id_resultado_inferencia válido. Si NO se puede generar por API (RF-66 no operativo), BLOQUEADO el caso completo con motivo."*

---

## 3. Matriz de Esquemas de Auditoría (RF-73)

### Endpoint de Consulta: `GET /prediccion/auditoria`
- Schema de retorno: `AuditoriaM04ListResponse`.
- Permite filtrar por:
  - `tipo_evento=RETROALIMENTACION_REGISTRADA`
  - `tipo_evento=CONFLICTO_RETROALIMENTACION`
- Campos esperados en el registro:
  - `id_evento`: UUID
  - `tipo_evento`: string
  - `tipo_actor`: `'USUARIO'` (para registro veterinario) | `'SISTEMA'` (para detección de conflicto)
  - `severidad_evento`: `'INFO'` | `'WARNING'` (para conflicto)
  - `resultado_operacion`: `'EXITOSO'` | `'DETECTADO'`
  - `hash_evento`: SHA-256 (64 hex)

---

## 4. Teardown y Limpieza
- Pre-request genera `run_id = "test-" + {{$guid}}`.
- Último request: `DELETE /test-control/runs/{{run_id}}` (200 OK "Rollback exitoso").
- Duración total estimada: ~6 segundos.
