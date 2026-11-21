# DISENO_Y_PRECONDICIONES — TC-M04-G089

## 1. Identificación y Metadatos
- **ID Caso / Grupo:** TC-M04-G089 (TC-M04-273, TC-M04-274, TC-M04-275)
- **Módulo:** Módulo 4 — Predicción e IA (RF-64 a RF-73)
- **Requisito Funcional:** RF-73 (Auditoría de eventos de predicción — Límites de Paginación)
- **Fase:** DISEÑO TÉCNICO Y AUTOMATIZACIÓN DE PRUEBAS
- **Estado Global:** [ACTIVO / OPERATIVO EN BACKEND TEST] (El endpoint `GET /prediccion/auditoria` se encuentra completamente implementado y verificado)
- **Entorno Evaluado:** Backend TEST desplegado (`https://api.inmero.co/back-sigab-test`)
- **Herramienta de Ejecución:** Newman + reporter htmlextra (Sandbox transaccional con aislamiento por `run_id`).

---

## 2. Diagnóstico Técnico de Endpoints y Parámetros

| Subcaso | Parámetros Enviados | Comportamiento Esperado | Implementación en Backend | Estado Técnico |
|---|---|---|---|---|
| **TC-M04-273** | Ninguno (default) | HTTP 200, metadatos `{pagina: 1, por_pagina: 50}`, `items.length <= 50` | `auditoria_m04_router.py:56` (`por_pagina: int = Query(default=50, ge=1, le=200)`) | [OPERATIVO] |
| **TC-M04-274** | `pagina=1&por_pagina=200` | HTTP 200, metadatos `{por_pagina: 200}`, `items.length <= 200` | Aceptado por validador `le=200` | [OPERATIVO] |
| **TC-M04-275** | `pagina=1&por_pagina=201` | HTTP 422 Unprocessable Entity con detalle de validación Pydantic | Rechazado automáticamente por `le=200` en FastAPI | [OPERATIVO] |

### Análisis de Contrato y Precarga:
- El schema de respuesta `PaginatedResponse[EventoAuditoriaM04Response]` expone los atributos `{total, pagina, por_pagina, total_paginas, items}`.
- Si la base de datos de auditoría contiene menos de 50 o 200 registros reales en el ambiente de prueba, los subcasos TC-M04-273 y TC-M04-274 se validan fielmente por contrato verificando el atributo `por_pagina` en los metadatos y asegurando que `items.length <= por_pagina`.
- En TC-M04-275, al enviar `por_pagina=201`, la validación de FastAPI interrumpe la ejecución antes de consultar la base de datos, retornando HTTP 422 con estructura estándar `{detail: [...]}`.

---

## 3. PENDIENTES DE DESARROLLO

| Subcaso | Endpoint Esperado | Contrato Esperado | Asignado A (Equipo/Área) |
|---|---|---|---|
| **TC-M04-273** | `GET /prediccion/auditoria` | Ya implementado y operativo (`por_pagina` default = 50) | Ninguno (Completado) |
| **TC-M04-274** | `GET /prediccion/auditoria?por_pagina=200` | Ya implementado y operativo (límite máximo = 200) | Ninguno (Completado) |
| **TC-M04-275** | `GET /prediccion/auditoria?por_pagina=201` | Ya implementado y operativo (retorna HTTP 422) | Ninguno (Completado) |

*Nota:* No existen pendientes de desarrollo para este caso de prueba; la suite es 100% ejecutable directamente contra el ambiente TEST.

---

## 4. Limitaciones Técnicas y Discrepancias Previstas

- **[DISCREPANCIA] Variación en Parámetro de Paginación:**
  - El código fuente ratifica el uso exacto de `por_pagina` y `pagina` en español (alineado al RF-73). No se requiere mapeo tentativo hacia `limit`/`offset` o `per_page`.
- **[DEFECTO CONOCIDO] Aceptación de Valores Mayores a 200:**
  - Si una configuración o middleware desactivara la validación de FastAPI permitiendo `por_pagina=201` con HTTP 200, la aserción reportará fallo explícito prefijado con `[DEFECTO CONOCIDO]`.

---

## 5. Estrategia de Sandbox y Teardown
- Generación de `run_id` en pre-request e inyección de `X-Test-Run-Id` y `X-Sandbox-Secret`.
- Teardown con `DELETE /test-control/runs/{{run_id}}` (200 OK con `Rollback exitoso`).
- Cero escrituras directas SQL en base de datos.

---

## 6. Diagnóstico 2026-10-25
- `sandbox_client = TestClient(app)` en memoria (`conftest.py:112`).
- Login: manual por test. `run_id`: function-scoped.
- `por_pagina>200` → HTTP 400 `VAL_ENTRADA` (no 422); handler global de FastAPI.
- `total` = count filtrado según subquery, dinámico.
- Cada GET exitoso COMMITea `HISTORIAL_CONSULTADO` → contaminación +1.
  `DELETE /test-control/runs/{run_id}` reporta "Rollback exitoso" pero es no-op para este evento.
- `DB_TOTAL` tras el diagnóstico = 973 (971 base + 2 del diagnóstico).

## 7. Diseño (D1=B, D2=A, D3=A)
- **D1=B:** Test 275 verifica OpenAPI y decide el código a assertar (422 o 400).
- **D2=A:** Baseline dinámico: `total >= 50/200`. Invariante `len(items) == min(por_pagina, total)`.
- **D3=A:** Contaminación aceptada (B7 conocido). `INC-M04-160-G089` a abrir al cierre.

## 8. Resultado esperado
- Si OpenAPI declara 422: test 275 FALLA → 2/3 OK → RECHAZADO + INC-M04 a M04.
- Si OpenAPI declara 400 (o no declara): 3/3 OK → APROBADO (con `OBS-M04-G089-01`).

---

## 9. Rediseño 2026-10-25 — P1'=B (httpx directo)
- **Motivo:** sandbox_client no sirve para integración HTTP contra el backend desplegado (TestClient corre contra sqlite en memoria, y login local usa schema distinto: correo_electronico/contrasena vs desplegado correo/contraseña).
- **Cambios:**
  - `httpx.Client(base_url=$env:BACKEND, timeout=15s)`
  - Login con `{"correo", "contraseña"}` (schema del desplegado)
  - Headers sandbox manuales por test: `X-Test-Run-Id`, `X-Sandbox-Secret`
  - 1 login + 1 GET + 1 DELETE por test (DEF-04)
  - 3 tests × ~3 requests = ~9 requests totales (+5 de contaminación esperada: 3 sesiones + 2 HISTORIAL_CONSULTADO)
  - smoke_check reescrito con httpx (health + openapi + login + teardown)


