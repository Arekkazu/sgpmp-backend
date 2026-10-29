# TC-M03-G166 — Informe Narrativo V1 (Evaluación Original Válida)

**Caso**: TC-M03-G166 — Detección de sensor congelado, fronteras exactas (LEVE/MODERADO/CRITICO)
**RF**: RF-62 (side-effects: RF-57 Alertas Técnicas, RF-63 Bitácora IoT)
**Casos agrupados**: TC-M03-309, TC-M03-310, TC-M03-311
**Módulo**: 3 — Telemetría IoT / Monitoreo
**Fecha**: 2026-10-23
**Entorno**: TEST — `https://www.api.inmero.co/api-sgpmp-test`
**Modalidad**: Pytest + `sandbox_client` (`X-Test-Run-Id`, `X-Sandbox-Secret`) — Rollback transaccional confirmado
**Ejecutor**: QA Senior

---

## 1. Veredicto V1

**RECHAZADO**

La corrida del 2026-10-23 constituye la **primera evaluación funcional válida del caso** tras la resolución del bloqueo por broker MQTT (INC-M03-01-G166 resuelto con el despliegue del PR #654). 
El veredicto final es **RECHAZADO** debido a la presencia de defectos backend vigentes confirmados normativamente.

---

## 2. Resumen Cuantitativo de Ejecución

| Estado | Cantidad | Descripción |
|---|---|---|
| **passed** | 94 | Pruebas de fronteras matemáticas R=4, 5, 9, 10, 19, 20, índices de calidad, aptitud IA/NIC-41 y persistencia en RF-63 |
| **failed** | 6 | Defecto en transición de ciclo de vida (`test_g166_transicion_superada` en R=4, 5, 9, 10, 19, 20) |
| **xfailed** | 5 | Alertas técnicas RF-57 no emitidas (`test_efectos_rf57_alerta_tecnica_emitida` en R=5, 9, 10, 19, 20) |
| **skipped** | 1 | Prueba de diagnóstico condicional |
| **Total** | **106** | Duración: 95.53s |

---

## 3. Defectos Backend Confirmados

1. **INC-M03-104-G165 (Punto 3) — Transición a SUPERADA no ejecutada:**
   * `POST /iot/calidad/{id_telemetria}/evaluar` no marca la evaluación previa como `SUPERADA`. Ambas evaluaciones coexisten con `estado_evaluacion='VIGENTE'` e `id_evaluacion_superada=None`, violando el invariante de máximo 1 evaluación vigente por lectura.
   * Manifestación: 6 fallas en `test_g166_transicion_superada`.

2. **INC-M03-RF57-NOT-EMITTED — Alertas técnicas RF-57 desconectadas:**
   * La Fase 8 de `EvaluarCalidadTelemetriaUseCase` no invoca la generación de alertas técnicas ante flags de sensor congelado.
   * Manifestación: 5 fallas esperadas marcadas con `xfail` estricto en `test_efectos_rf57_alerta_tecnica_emitida`.

---

## 4. Inocuidad y Aislamiento

* **Sandbox transaccional:** Cada prueba operó bajo `X-Test-Run-Id` y ejecutó `DELETE /test-control/runs/{run_id}` retornando `200 "Rollback exitoso"`.
* **Contaminación de base de datos:** Cero registros residuales en `modulo3.telemetrias`, `modulo3.calidad_evaluaciones` ni `modulo3.alertas`.

---

## 5. Trazabilidad de Artefactos V1

* Computables oficiales:
  - `resultados/resultado_TC-M03-G166.html` (pytest-html)
  - `resultados/resultado_TC-M03-G166.xml` (JUnit XML)
  - `resultados/resultado_TC-M03-G166.json` (Checkpoints QA Dashboard: 106 items)
* Evidencia de ejecución:
  - `evidencias/run-20261023/console_execution.log` (log completo de pytest)
