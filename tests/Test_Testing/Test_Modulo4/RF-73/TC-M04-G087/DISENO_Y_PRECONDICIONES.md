# DISENO_Y_PRECONDICIONES — TC-M04-G087

## 1. Identificación y Metadatos
- **ID Caso / Grupo:** TC-M04-G087 (TC-M04-265, TC-M04-266, TC-M04-267)
- **Módulo:** Módulo 4 — Predicción e IA (RF-64 a RF-73)
- **Requisito Funcional:** RF-73 (Auditoría de eventos de predicción)
- **Fase:** DISEÑO TÉCNICO Y AUTOMATIZACIÓN DE PRUEBAS
- **Estado Global:** [PENDIENTE_DEV] (Pendiente de exposición de endpoint de ingesta en router REST)
- **Entorno Evaluado:** Backend TEST desplegado (`https://api.inmero.co/back-sigab-test`)
- **Herramienta de Ejecución:** Newman + reporter htmlextra (Sandbox transaccional con aislamiento por `run_id`).

---

## 2. Diagnóstico Técnico y Estado de Endpoints

| Subcaso | Nombre Técnico | Validación Requerida | Endpoint Real en Backend | Estado Técnico |
|---|---|---|---|---|
| **TC-M04-265** | Catálogo Inválido | Rechazo HTTP 400/422 ante `tipo_evento="EVENTO_INVENTADO"` | `POST /prediccion/auditoria/eventos` (no expuesto en FastAPI router) | [PENDIENTE_DEV] |
| **TC-M04-266** | Fuentes Nulas | Rechazo HTTP 400/422 ante `id_usuario=null` e `id_sistema=null` | `POST /prediccion/auditoria/eventos` (no expuesto en FastAPI router) | [PENDIENTE_DEV] |
| **TC-M04-267** | Doble Fuente (Viola XOR) | Rechazo HTTP 400/422 ante `id_usuario=5` e `id_sistema="motor_inferencia"` simultáneos | `POST /prediccion/auditoria/eventos` (no expuesto en FastAPI router) | [PENDIENTE_DEV] |

### Análisis de Dominio y Base de Datos (Regla XOR y Catálogo)
1. **Regla de Catálogo (`tipo_evento`):**
   - El catálogo de eventos del Módulo 4 en `src/prediction/domain/value_objects.py` / `alembic/versions/` define eventos tipificados (e.g., `CATALOGO_PATOLOGIA_AGREGADA`, `INFERENCIA_EJECUTADA`, `INFERENCIA_RECHAZADA`, `MODELO_VERSION_REGISTRADA`, etc.).
   - Cualquier valor no tipificado como `"EVENTO_INVENTADO"` debe ser rechazado en el schema Pydantic de entrada con error 422 Unprocessable Entity o 400 Bad Request.
2. **Regla de Exclusión Mutua XOR de Actores:**
   - La entidad `EventoAuditoriaM04` exige que todo evento provenga de exactamente un actor: un usuario humano (`id_usuario`) o un componente de software (`id_sistema`).
   - A nivel de base de datos (`modulo4.eventos_auditoria_m04`), ambas columnas son nulables individualmente, pero a nivel de invariante de dominio se impone la restricción XOR:
     `CHECK ((id_usuario IS NOT NULL AND id_sistema IS NULL) OR (id_usuario IS NULL AND id_sistema IS NOT NULL))`
   - Ambos nulos (`TC-M04-266`) implica evento huérfano sin trazabilidad (rechazo inmediato).
   - Ambos presentes (`TC-M04-267`) viola la exclusividad de actor (rechazo inmediato).

---

## 3. PENDIENTES DE DESARROLLO

| Subcaso | Endpoint Esperado | Contrato Esperado | Asignado A (Equipo/Área) |
|---|---|---|---|
| **TC-M04-265** | `POST /prediccion/auditoria/eventos` | Body con `tipo_evento: str` fuera de enum -> HTTP 400 o 422 con código `VALOR_CATALOGO_INVALIDO` | Equipo Backend Core / Módulo 4 |
| **TC-M04-266** | `POST /prediccion/auditoria/eventos` | Body con `id_usuario: null` e `id_sistema: null` -> HTTP 400 o 422 con código `ACTOR_NO_IDENTIFICADO` | Equipo Backend Core / Módulo 4 |
| **TC-M04-267** | `POST /prediccion/auditoria/eventos` | Body con `id_usuario: int` e `id_sistema: str` simultáneos -> HTTP 400 o 422 con código `VIOLACION_XOR_ACTORES` | Equipo Backend Core / Módulo 4 |

### Ajustes Menores al Publicarse el Endpoint Real:
- Si el router expone la ruta bajo `/prediccion/auditoria` (directo) en lugar de `/prediccion/auditoria/eventos`, ajustar únicamente el path en `build_collection.cjs`.
- Los scripts ya cuentan con guardas condicionales: si el endpoint retorna 404/405 registra traza `[PENDIENTE_DEV]` informativa sin romper el runner ni falsear la suite. En cuanto retorne 400/422, las aserciones se activan automáticamente.

---

## 4. Limitaciones Técnicas y Supuestos

- **[LIMITACION API] Verificación de Logs Técnicos y Alertas al Administrador:**
  - Los casos 265, 266 y 267 mencionan emisión de log técnico con severidad WARNING/CRITICAL/ERROR y alerta al Administrador.
  - El backend actual no expone un endpoint REST para inspección de logs internos de aplicación ni cola de notificaciones del Administrador en vivo vía HTTP.
  - Estas verificaciones quedan marcadas como `[LIMITACION API]` en traza de ejecución sin aserción HTTP bloqueante.
- **Fechas Pasadas y Correlación:**
  - Se utilizan fechas dentro del rango permitido (10 a 18 de octubre de 2026), e.g. `2026-10-15T10:00:00Z`.
  - Cada solicitud cuenta con `correlacion_id` sufijado con el `{{run_id}}` para trazabilidad única e inmunidad contra colisiones.

---

## 5. Estrategia de Sandbox y Teardown
- Toda la ejecución se realiza bajo Sandbox transaccional inyectando `X-Test-Run-Id` y `X-Sandbox-Secret`.
- El paso final invoca `DELETE /test-control/runs/{{run_id}}` garantizando reversión total (`Rollback exitoso`).
- Cumplimiento estricto de la regla CERO DML: ninguna sentencia SQL directa es ejecutada.
