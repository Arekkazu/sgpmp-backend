# DISENO_Y_PRECONDICIONES — TC-M04-G083

## 1. Identificación y Metadatos
- **ID Caso / Grupo:** TC-M04-G083 (TC-M04-257, TC-M04-258)
- **Módulo:** Módulo 4 — Predicción e IA (RF-64 a RF-73)
- **Requisito Funcional:** RF-73 (Auditoría de eventos de inferencia, versionado de modelos y OTA) / RF-70 (Distribución OTA a Nodos Edge)
- **Estado Global:** [REDISENO COMPLETO E2E — EJECUTABLE BAJO SANDBOX CON GAP EN SUBCASO 2]
- **Entorno Evaluado:** Backend TEST desplegado (`https://api.inmero.co/api-sgpmp-test`)
- **Herramienta de Ejecución:** Newman + reporter htmlextra bajo Sandbox transaccional con reversibilidad verificada.

---

## 2. Diagnóstico Técnico de Endpoints Productores y Hallazgos

| Subcaso | Tipo Evento Esperado | Endpoint Productor Real en Backend | Mecanismo de Autenticación | Estado Técnico |
|---|---|---|---|---|
| **TC-M04-257** | `MODELO_DISTRIBUIDO_EDGE` | `POST /prediccion/ota/reportes` con `evento="integrity_ok"` | `Authorization: Bearer $env:BROKER_SERVICE_TOKEN` | [EJECUTABLE / PASA] |
| **TC-M04-258** | `HASH_INVALIDO_DETECTADO` | `POST /prediccion/ota/reportes` con `evento="rollback"` | `Authorization: Bearer $env:BROKER_SERVICE_TOKEN` | [GAP CONFIRMADO: FALLA] |

### Justificación Técnica Detallada:

1. **Existencia del Endpoint Productor OTA:**
   - Contrario a hipótesis preliminares, el endpoint de reporte OTA **SÍ EXISTE** en la API REST de FastAPI: `POST /prediccion/ota/reportes` (definido en `src/prediction/infrastructure/routers/ota_router.py:203`).
   - Es invocado originalmente por el broker MQTT (componente M2M) reenviando los eventos `ota/<evento>` emitidos por los nodos Edge (BRK-08).
   - Su autenticación exige la cabecera `Authorization: Bearer <token>`, validada contra la variable de entorno `BROKER_SERVICE_TOKEN` mediante `secrets.compare_digest` en `src/shared/broker_auth.py`.

2. **Aislamiento en Sandbox Transaccional:**
   - El endpoint inyecta la sesión de base de datos vía `get_db_sistema`, el cual depende directamente de `get_db()`.
   - `get_db()` respeta el contexto `test_run_id_context` interceptado por `TestSandboxMiddleware` mediante los encabezados `X-Test-Run-Id` y `X-Sandbox-Secret`.
   - Se verificó empíricamente en diagnóstico previo que cualquier mutación sobre `modulo4.despliegues_ota` es completamente reversible al invocar `DELETE /test-control/runs/{run_id}`.

3. **Catálogo Real de Eventos OTA en `RegistrarReporteOtaUseCase`:**
   - `evento="integrity_ok"` → Emite `MODELO_DISTRIBUIDO_EDGE` (severidad `INFO`, resultado `EXITOSO`).
   - `evento="activated"` → Emite `MODELO_ACTIVADO_EDGE` (severidad `INFO`, resultado `EXITOSO`).
   - `evento="rollback"` → Emite `DISTRIBUCION_FALLIDA` (severidad `ERROR`, resultado `FALLIDO`).
   - `evento="critical_failure"` → Emite `DISTRIBUCION_FALLIDA` (severidad `CRITICAL`, resultado `FALLIDO`).
   - `evento="status"` con `pospuesto=true` → Emite `DISTRIBUCION_POSPUESTA` (severidad `WARNING`).

4. **Identidad del Emisor en Bitácora (`src/prediction/application/use_cases/ota/registrar_reporte_ota_use_case.py:124-125`):**
   - `tipo_actor`: `"DISPOSITIVO_EDGE"` (literal).
   - `id_sistema`: `dto.serial` (el serial del dispositivo IoT que reporta, e.g., `"QA-SEMILLA-ADM-M03-EDGE-01"`).
   - `entidad_referencia`: `"despliegue_ota"`.
   - `id_referencia`: `str(despliegue.id_despliegue_ota)`.

5. **Divergencia y Gap de Diseño en Subcaso 2 (INC-M04-149-G083):**
   - El caso TC-M04-258 espera que al detectar un hash corrupto se registre el evento `HASH_INVALIDO_DETECTADO`.
   - Sin embargo, en el backend dicho evento solo existe en la carga de modelos de RF-71 (`POST /prediccion/modelos`). En el flujo de distribución OTA (RF-70), el caso de uso emite **`DISTRIBUCION_FALLIDA`** con la causa detallada en el payload (`causa="HASH_INVALIDO"`).
   - **Estrategia de Prueba:** El script ejecuta la simulación real de rollback en Sandbox B, formula las aserciones sobre `HASH_INVALIDO_DETECTADO` (las cuales fallan honestamente capturando el gap), y complementariamente consulta `DISTRIBUCION_FALLIDA` (Item 8) para registrar la evidencia exacta de lo que el backend realmente emitió.

---

## 3. Precondiciones y Semilla en TEST

- **Despliegue Semilla:** `id_despliegue_ota = 11`.
- **Estado Inicial:** `PENDIENTE`.
- **Dispositivo Asociado:** `id_dispositivo_iot = 347` (Gateway Edge para despliegues OTA, `es_activo = true`).
- **Serial Legitimo del Nodo:** `QA-SEMILLA-ADM-M03-EDGE-01`.
- **Componente:** `None` (modelo monolitico `MODELO_ESPECIES_MEDIANAS`, version 43).
- **Descubrimiento Dinamico:** La suite consulta `GET /prediccion/despliegues` en el Item 2 para localizar dinamicamente el despliegue en estado `PENDIENTE` (priorizando el ID 11), extrayendo sus valores hacia variables de entorno y fallando controladamente si no existe ningun despliegue elegible.

---

## 4. Estructura de la Suite Rediseñada (10 Items)

La coleccion `test_tc_m04_g083.json` organiza la ejecucion en dos sandboxes independientes para garantizar aislamiento estricto:

```
[01-Login-ADMIN] ──> Obtiene JWT de administrador
       │
[02-Preflight]  ──> Descubre id_despliegue_ota (11), serial y componente
       │
┌──────┴───────────────────────────────────────────────────────┐
│ SANDBOX A: Subcaso 1 (TC-M04-257 - MODELO_DISTRIBUIDO_EDGE)   │
│                                                              │
│ [03-Disparar-Distribucion] ──> POST /ota/reportes (integrity_ok)
│ [04-Verificar-Auditoria]   ──> GET /auditoria (MODELO_DISTRIBUIDO_EDGE)
│ [05-Teardown-Sandbox-A]    ──> DELETE /test-control/runs/{{run_id_A}}
└──────┬───────────────────────────────────────────────────────┘
       │ (Despliegue revertido a PENDIENTE)
┌──────┴───────────────────────────────────────────────────────┐
│ SANDBOX B: Subcaso 2 (TC-M04-258 - HASH_INVALIDO_DETECTADO)  │
│                                                              │
│ [06-Simular-Rollback]      ──> POST /ota/reportes (rollback / HASH_INVALIDO)
│ [07-Verificar-Auditoria]   ──> GET /auditoria (HASH_INVALIDO_DETECTADO - GAP)
│ [08-Evidencia-Real]        ──> GET /auditoria (DISTRIBUCION_FALLIDA)
│ [09-Teardown-Sandbox-B]    ──> DELETE /test-control/runs/{{run_id_B}}
└──────┬───────────────────────────────────────────────────────┘
       │
[10-Verificar-Post-Rollback] ──> Confirma que despliegue 11 volvio a PENDIENTE
```

---

## 5. Teardown y Limpieza

- Cada sandbox genera su propio identificador unico: `run_id_A` y `run_id_B` mediante `pm.variables.replaceIn('{{$guid}}')`.
- Los items 5 y 9 ejecutan el rollback transaccional inmediato con `DELETE /test-control/runs/{run_id}`.
- El item 10 realiza la asercion final de no-contaminacion verificando que el despliegue 11 permanece en estado `PENDIENTE` en la base de datos de TEST.
