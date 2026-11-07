# TC-M03-G166 — Informe Narrativo V1

**Caso**: TC-M03-G166 — Detección de sensor congelado, fronteras exactas (LEVE/MODERADO/CRITICO)
**RF**: RF-62 (impacto colateral: RF-57, RF-63)
**Módulo**: 3 — Telemetría IoT
**Fecha**: 2026-10-22
**Entorno**: TEST — `https://www.api.inmero.co/api-sgpmp-test`
**Modalidad**: Sandbox transaccional (`X-Test-Run-Id`) — cero contaminación verificada
**Ejecutor**: QA

---

## Veredicto V1

**RECHAZADO (BLOQUEADO POR INFRAESTRUCTURA)**

El caso no falla por defecto propio ni por lógica de negocio. Falla porque el entorno TEST no tiene configurado `BROKER_SERVICE_TOKEN`, lo que impide ejecutar la precondición bloqueante: sembrar las 41 lecturas de telemetría necesarias para evaluar la detección de sensor congelado.

Según guía §5.1.3: "NO existe el estado 'Bloqueado': Un caso bloqueado por ambiente es Pendiente (o Rechazado si el reporte trae aserciones fallidas)." → **Rechazado**.

---

## Resultado

| Categoría | Cantidad | Motivo |
|---|---|---|
| passed | 1 | `TestDiagnosticoBloqueo::test_diagnostico_bloqueo_broker` |
| failed | 100 | `BLOQUEO EXTERNO EN SETUP: POST /iot/telemetria devuelve 503 TOKEN_SERVICIO_NO_CONFIGURADO` |
| xfailed | 5 | RF-57 (defecto backend vigente) |
| **Total** | **106** | |

---

## Causa raíz

`POST /iot/telemetria` → HTTP 503 `TOKEN_SERVICIO_NO_CONFIGURADO`.
Origen: `src/shared/broker_auth.py:36` — `os.getenv("BROKER_SERVICE_TOKEN", "")` retorna vacío en el proceso Python del deploy TEST.

**Hipótesis descartadas con evidencia**:
- URL equivocada → mismo 503 en `www.api.inmero.co/api-sgpmp-test` y `api.inmero.co/api-sgpmp-test`
- Backend caído → `GET /health` responde 200 en ~1 s
- Auth usuario → `POST /sesiones/` responde 200 con JWT válido
- Sandbox roto → `DELETE /test-control/runs/{run_id}` retorna 200 "Rollback exitoso"

**INC asociado**: INC-M03-01-G166 (Abierto, Crítico, Implementación TEST)

---

## Evidencia

- `resultado_TC-M03-G166.json` — checkpoints para scanner (106 checkpoints, 1 OK, 105 FALLA)
- `resultado_TC-M03-G166.html` — reporte pytest-html interactivo
- `resultado_TC-M03-G166.xml` — JUnit XML estructurado
- `console_execution.log` — log completo (157 KB)

**Script de diagnóstico**: `tests/Test_Testing/Test_Modulo3/diagnostico_completo_m03.py`
**Último run**: 11/12 verificaciones OK. Único FAIL en [05] Broker token.

---

## Defectos backend documentados (para V2)

1. **INC-M03-RF57-NOT-EMITTED** — `POST /iot/calidad/{id}/evaluar` no dispara alerta técnica RF-57 en Fase 8. `@pytest.mark.xfail` en 5 tests.
2. **Gap CATALOGO_I3P1** — 5 variables HIDRICAS ausentes (`"Temperatura del agua"`, `"Amoniaco total"`, `"Nitrito"`, `"Salinidad"`, `"Turbidez"`).

---

## Precondiciones para V2 (reevaluación)

| Acción | Responsable | Estado |
|---|---|---|
| Configurar `BROKER_SERVICE_TOKEN` en TEST + restart | Implementación (TEST) | INC-M03-01-G166 abierto |
| Seed 187 lecturas en sensor 2 (6 bloques R=4,5,9,10,19,20) | DBA | INC-M03-02-SEED abierto |

---

## Próximos pasos (V2)

1. Verificar con `diagnostico_completo_m03.py` que [05] pase a OK.
2. Ejecutar suite: `pytest test_tc_m03_g166.py --html=.../resultado_TC-M03-G166_reintento1.html --junitxml=.../resultado_TC-M03-G166_reintento1.xml`
3. Regenerar JSON con `generar_json_resultado.py`.
4. Guardar en `EvaluacionV2/RESULTADOS/G166-REEVAL-V2-<timestamp>/`.
5. Veredicto esperado: **APROBADO** (~100 passed, 0 failed, 5 xfailed).
