# DISENO_Y_PRECONDICIONES — TC-M04-G084

## 1. Identificación y Metadatos
- **ID Caso / Grupo:** TC-M04-G084 (Subcasos TC-M04-259, TC-M04-260, TC-M04-261)
- **Módulo:** Módulo 4 — Predicción e IA (RF-64 a RF-73)
- **Requisitos Funcionales Evaluados:**
  - **RF-71:** Reentrenamiento de Modelos de Predicción e IA
  - **RF-72:** Detección y Notificación de Degradación de Rendimiento
  - **RF-73:** Auditoría de Eventos de Ciclo de Vida de Modelos
- **Veredicto Técnico Global:** **BLOQUEADO_POR_DISENO**
- **Enfoque de la Suite Rediseñada:** **Test Negativo Honesto de Verificación de Ausencia**
- **Entorno Evaluado:** Backend TEST Desplegado (`https://api.inmero.co/api-sgpmp-test`)
- **Herramienta de Ejecución:** Newman + reporter htmlextra bajo Sandbox Transaccional SGPMP

---

## 2. Diagnóstico Técnico de Arquitectura y Justificación de Bloqueo

### 2.1 Ausencia por Decisión de Alcance (RF-71 y RF-72)
En el backend FastAPI de SGPMP (`src/prediction/`), los requisitos funcionales RF-71 (pipeline de reentrenamiento) y RF-72 (monitoreo periódico de degradación y drift) **no se encuentran implementados en el código de producción**.

Esta ausencia no constituye un defecto fortuito de código, sino una decisión formal de arquitectura documentada en `anotaciones/implementacion_rfc006_rfc009_rfc011.md:162`:
> *"Campos mínimos por paradigma de REENTRENAMIENTO_COMPLETADO y DEGRADACION_DETECTADA: Los emite RF-71, que no existe; se agregan cuando haya emisor"*.

La API REST actúa estrictamente como consumidor pasivo de inferencia ONNX (`onnxruntime_adapter.py`) y registro de versiones precompiladas (`POST /prediccion/modelos` protegido con `X-RF71-Internal-Key`). No existen controladores (`routers`), casos de uso (`use_cases`), tareas en background ni jobs programados (Celery/APScheduler) para disparar reentrenamientos ni computar drift en el servidor web.

### 2.2 Semilla Estática en Bitácora vs Emisión Real
La inspección empírica de la base de datos de TEST (`modulo4.eventos_auditoria_m04`) y de la API de auditoría (`GET /prediccion/auditoria`) reveló:
- `REENTRENAMIENTO_INICIADO`: **0 eventos**.
- `REENTRENAMIENTO_COMPLETADO`: **2 eventos** (ambos con severidad `ERROR` e `id_sistema="cron-reentrenamiento"`).
- `DEGRADACION_DETECTADA`: **2 eventos** (ambos con severidad `CRITICAL` e `id_sistema="motor-drift-m04"`).

Todos estos registros históricos contienen `origen_registro = "DIRECTO"`, lo que demuestra que fueron insertados mediante scripts de inicialización o semillas externas de prueba, y **NO** como producto de una emisión real desde la API REST.

---

## 3. Matriz de Subcasos y Estado Real

| Subcaso | Tipo de Evento | Expectativa Teórica | Realidad en Backend | Veredicto del Subcaso |
|---|---|---|---|:---:|
| **TC-M04-259** | `REENTRENAMIENTO_INICIADO` | Trigger administrativo o batch de reentrenamiento | Inexistente en `src/` (0 eventos en auditoría) | **BLOQUEADO_POR_DISENO** |
| **TC-M04-260** | `REENTRENAMIENTO_COMPLETADO` | Pipeline finaliza y emite métricas | Pipeline inexistente (2 eventos son semilla externa) | **BLOQUEADO_POR_DISENO** |
| **TC-M04-261** | `DEGRADACION_DETECTADA` | Scheduler detecta $F_1 < 0.80$ y emite alerta | Scheduler inexistente; no hay modelos degradados en TEST | **BLOQUEADO_POR_DISENO** |

---

## 4. Análisis de Precondición del Subcaso TC-M04-261

Para que el subcaso 3 pudiera operar en un escenario teórico con scheduler, la regla de negocio exige que un modelo en estado `ACTIVO` presente un rendimiento degradado ($F_1 < 0.80$).

La inspección en TEST arrojó:
- Versión 44 (`MODELO_ESPECIES_MEDIANAS`): Estado `ACTIVO`, $F_1 = 0.8700$, Recall $= 0.9000$ (rendimiento óptimo, $> 0.80$).
- Versión 57 (`MODELO_RIESGO_CONTAGIO`): Estado `ACTIVO`, métricas $F_1$ / Recall en `null` (paradigma META probabilístico).
- Versión 46 (`MODELO_ESPECIES_GRANDES`): $F_1 = 0.5800$, pero en estado `RECHAZADO` (no activo).

**Conclusión:** La precondición funcional tampoco se cumple en el entorno de TEST.

---

## 5. Diseño del Test Negativo Honesto

A diferencia del diseño pasivo preliminar (que carecía de aserciones y reportaba un falso aprobado), la suite rediseñada `test_tc_m04_g084.json` evalúa honestamente el estado del backend mediante 7 items estructurados:

1. `01-Login-ADMIN`: Obtención controlada de JWT administrativo.
2. `02-Preflight-Bitacora-Accesible`: Inicialización de `run_id` y verificación de conectividad a la bitácora bajo sandbox.
3. `03-Sonda-REENTRENAMIENTO_INICIADO-Ausencia-Confirmada`: Aserta explícitamente `body.total === 0` confirmando la ausencia de eventos de reentrenamiento en el backend actual.
4. `04-Sonda-REENTRENAMIENTO_COMPLETADO-Documentar-Estado-Real`: Aserta HTTP 200 y documenta el total de registros en bitácora sin validar cumplimiento activo.
5. `05-Sonda-DEGRADACION_DETECTADA-Documentar-Estado-Real`: Aserta HTTP 200 y documenta el total de registros en bitácora sin validar cumplimiento activo.
6. `06-Verificar-Precondicion-Subcaso3-F1-Degradado`: Aserta que `count_activos_bajo_umbral === 0`, demostrando que ningún modelo activo en TEST sufre degradación.
7. `07-Teardown-Sandbox-Rollback`: Invoca `DELETE /test-control/runs/{{run_id}}` con `X-Sandbox-Secret` para garantizar la higiene transaccional.

**Veredicto Formal:** El caso de prueba refleja **BLOQUEADO_POR_DISENO**. No se generan aserciones engañosas de éxito sobre componentes que no han sido construidos.
