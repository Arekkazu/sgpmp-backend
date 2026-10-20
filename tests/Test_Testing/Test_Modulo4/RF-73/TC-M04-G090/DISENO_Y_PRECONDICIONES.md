# DISENO_Y_PRECONDICIONES — TC-M04-G090

## 1. Identificación y Metadatos
- **ID Caso / Grupo:** TC-M04-G090 (TC-M04-276, TC-M04-277, TC-M04-278, TC-M04-279, TC-M04-280)
- **Módulo:** Módulo 4 — Predicción e IA (RF-64 a RF-73)
- **Requisito Funcional:** RF-73 (Auditoría de eventos de predicción — Inmutabilidad e Integridad WORM)
- **Fase:** DISEÑO TÉCNICO Y AUTOMATIZACIÓN DE PRUEBAS (SOLO DISEÑO Y CONSTRUCCIÓN)
- **Estado Global:** [DISENADO / PENDIENTE_DEV PARCIAL] (Inmutabilidad por 405 y exportación disponibles; endpoint de verificación de integridad en desarrollo)
- **Entorno Evaluado:** Backend TEST desplegado (`https://api.inmero.co/back-sigab-test`)
- **Herramienta de Ejecución:** Newman + reporter htmlextra (Sandbox transaccional con aislamiento por `run_id`).

---

## 2. Diagnóstico Técnico y Estado de Endpoints

| Subcaso | Operación / Verificación | Comportamiento Esperado | Implementación en Backend | Estado Técnico |
|---|---|---|---|---|
| **TC-M04-276** | PUT y PATCH sobre `/prediccion/auditoria/{id}` | HTTP 405 Method Not Allowed; registro inalterado verificado por GET posterior | No existen métodos PUT ni PATCH en `auditoria_m04_router.py` (FastAPI emite 405) | [OPERATIVO] |
| **TC-M04-277** | DELETE sobre `/prediccion/auditoria/{id}` | HTTP 405 Method Not Allowed; registro sigue existiendo verificado por GET posterior | No existe método DELETE en router (FastAPI emite 405) | [OPERATIVO] |
| **TC-M04-278** | Recálculo de Hash SHA-256 en GET | HTTP 200; `hash_evento` coincide exactamente con SHA-256 (64 hex) del `payload_evento` | `auditoria_m04_router.py:129` expone `hash_evento` y `payload_evento` conjuntamente | [OPERATIVO] |
| **TC-M04-279** | Verificación de integridad HTTP | POST `/prediccion/auditoria/{id}/verificar` -> HTTP 200 `{ estado: "INTEGRO", es_integro: true }` | Inexistente en API REST | [PENDIENTE_DEV] |
| **TC-M04-280** | Exportación de bitácora en JSON | GET `/prediccion/auditoria/exportar?formato=json` -> HTTP 200 con archivo JSON adjunto | `auditoria_m04_router.py:84` totalmente implementado | [OPERATIVO] |

---

## 3. PENDIENTES DE DESARROLLO

| Subcaso | Endpoint Esperado | Contrato Esperado | Asignado A (Equipo/Área) |
|---|---|---|---|
| **TC-M04-279** | `POST /prediccion/auditoria/{id_evento}/verificar` | Retorna HTTP 200 con `{ estado: "INTEGRO" \| "CORRUPTO", es_integro: bool, hash_almacenado: str, hash_calculado: str }` | Equipo Backend Core / Módulo 4 |

### Ajustes Menores al Publicarse el Endpoint Real:
- El subcaso TC-M04-279 cuenta con guardas: si responde 404/405 registra console.log `[PENDIENTE_DEV]` sin romper la suite. Al desplegarse el endpoint, las aserciones de estado se activan inmediatamente.

---

## 4. Limitaciones Técnicas y Supuestos

- **[LIMITACION API] Verificación de Log Técnico de Seguridad:**
  - Los intentos no autorizados de modificación o eliminación (PUT/PATCH/DELETE) deben generar alertas en log de seguridad.
  - Al no haber un endpoint HTTP para inspección de logs en tiempo real, se registra mediante `console.log('[LIMITACION API]')`.
- **Regla Estricta CERO DML en TC-M04-279:**
  - El diseño original de Pytest contemplaba alterar manualmente un registro en PostgreSQL para forzar un hash mismatch.
  - Bajo las reglas de arquitectura SGPMP, está **estrictamente prohibido modificar la base de datos vía SQL directo**. Por tanto, TC-M04-279 se diseña y valida como contrato de verificación de integridad sin corrupción inducida artificialmente por DML.

---

## 5. Estrategia de Sandbox y Teardown
- Generación de `run_id` aleatorio en pre-request de colección (`test-{{$guid}}`).
- Inyección de cabeceras de aislamiento `X-Test-Run-Id` y `X-Sandbox-Secret`.
- Teardown con `DELETE /test-control/runs/{{run_id}}` (200 OK con `Rollback exitoso`).
- Cero escrituras directas SQL en base de datos.
