# DISENO_Y_PRECONDICIONES — TC-M04-G096

## 1. Identificación y Metadatos
- **ID Caso / Grupo:** TC-M04-G096 (TC-M04-048, TC-M04-049, TC-M04-051, TC-M04-052)
- **Módulo:** Módulo 4 — Predicción e IA (RF-64 a RF-73)
- **Requisito Funcional:** RF-73 (Auditoría de eventos de predicción — Control de Acceso, IDOR y RBAC)
- **Fase:** DISEÑO TÉCNICO Y AUTOMATIZACIÓN DE PRUEBAS (SOLO DISEÑO Y CONSTRUCCIÓN)
- **Estado Global:** [DISENADO / PENDIENTE_DEV PARCIAL] (RBAC e IDOR para PRODUCTOR operativos; rol AUDITOR_EXTERNO y logs técnicos en desarrollo)
- **Entorno Evaluado:** Backend TEST desplegado (`https://api.inmero.co/back-sigab-test`)
- **Herramienta de Ejecución:** Newman + reporter htmlextra (Sandbox transaccional con aislamiento por `run_id`).

---

## 2. Diagnóstico Técnico y Matriz RBAC

| Subcaso | Escenario Evaluado | Endpoint Objetivo | Rol Utilizado | Comportamiento Esperado | Estado Técnico |
|---|---|---|---|---|---|
| **TC-M04-048** | Prevención de IDOR / BOLA | `GET /prediccion/auditoria/{id_evento}` | `PRODUCTOR` | HTTP 403 Forbidden (nunca 200) ante eventos existentes y fuerza bruta | [OPERATIVO] |
| **TC-M04-049** | Enmascaramiento en logs técnicos | `GET /logs/tecnicos` | `ADMINISTRADOR` | No expone tokens JWT, PII ni contraseñas | [LIMITACION API] |
| **TC-M04-051** | Control RBAC estricto | `GET /prediccion/auditoria` | `PRODUCTOR` | HTTP 403 Forbidden interceptado antes de consultar base de datos | [OPERATIVO] |
| **TC-M04-052** | Acceso acotado a períodos cerrados | `GET /prediccion/auditoria` | `AUDITOR_EXTERNO` | HTTP 403 ante período abierto; HTTP 200 ante período histórico cerrado | [PENDIENTE_DEV] |

### Análisis de Autorización y Prevención de IDOR:
1. **Recurso RBAC:** En `src/prediction/infrastructure/routers/auditoria_m04_router.py` se protege tanto el listado como el detalle mediante:
   `dependencies=[Depends(require_permission(_RECURSO, 2))]` donde `_RECURSO = 46` (`auditoria_m04`) y la acción `2` representa `CONSULTAR`.
2. **Rol PRODUCTOR:** No cuenta con la tupla `(recurso=46, accion=2)`. La dependencia `require_permission` intercepta la petición en la capa HTTP arrojando `HTTP 403 Forbidden` (`error_code: "PERMISO_DENEGADO"`).
3. **Mitigación de IDOR (OWASP API1):** Al interceptarse la autorización antes de invocar el caso de uso y antes de evaluar la existencia del registro en base de datos, un atacante con rol no autorizado jamás puede determinar si un `id_evento` existe o no mediante ataques de oráculo o fuerza bruta.

---

## 3. PENDIENTES DE DESARROLLO

| Subcaso | Endpoint / Cuenta Esperada | Contrato Esperado | Asignado A (Equipo/Área) |
|---|---|---|---|
| **TC-M04-049** | `GET /logs/tecnicos` | Endpoint para auditoría de bitácora técnica con sanitización de tokens y credenciales | Backend Core / DevOps |
| **TC-M04-052** | Rol `AUDITOR_EXTERNO` y filtro de períodos cerrados | Provisión de rol y restricción temporal en use case para períodos históricos cerrados | Módulo 1 (Identidad) / Módulo 4 |

---

## 4. Limitaciones Técnicas y Supuestos

- **Cuentas de Prueba Utilizadas:**
  - `ADMINISTRADOR`: `administador.dev@gmail.com` (`$TEST_ADMIN_PASSWORD`).
  - `PRODUCTOR`: `productor@pecuaria.co` (`$TEST_PRODUCER_PASSWORD` o fallback `Test1234!`).
  - `AUDITOR_EXTERNO`: Cuenta no existente en la base de datos de pruebas; el subcaso se documenta y prepara contra contrato esperado.

---

## 5. Estrategia de Sandbox y Teardown
- Generación de `run_id` aleatorio en pre-request de colección (`test-{{$guid}}`).
- Inyección de cabeceras de aislamiento `X-Test-Run-Id` y `X-Sandbox-Secret`.
- Teardown con `DELETE /test-control/runs/{{run_id}}` (200 OK con `Rollback exitoso`).
- Cero escrituras directas SQL en base de datos.
