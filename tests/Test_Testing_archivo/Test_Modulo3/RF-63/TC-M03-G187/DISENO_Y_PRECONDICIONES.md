# DISENO_Y_PRECONDICIONES — TC-M03-G187

## 1. Identificación y Metadatos
- **ID Caso / Grupo:** TC-M03-G187 (TC-M03-355, TC-M03-356)
- **Módulo:** Módulo 3 — Telemetría, Infraestructura IoT y Bitácora de Auditoría
- **Requisito Funcional:** RF-63 (Bitácora de Auditoría IoT) / OWASP API Security Top 10 — API8: Security Misconfiguration
- **Nivel de Automatización:** Automatizado vía Newman / Postman Collection (v2.1)
- **Entorno:** Backend TEST (`https://api.inmero.co/back-sigab-test`) bajo Sandbox Transaccional (`ENABLE_TEST_SANDBOX=true`)

---

## 2. Diagnóstico Técnico de Arquitectura y Manejo de Errores
- **Cabeceras de Seguridad:** Implementadas en `src/shared/middlewares.py:93` (`SecurityHeadersMiddleware`).
  - Cabeceras inyectadas: `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Strict-Transport-Security`, `Content-Security-Policy`.
  - Ausencia de cabeceras reveladoras: Se verifica que no se expongan `X-Powered-By`, `X-AspNet-Version`, `X-Debug-Token`.
- **Manejo Centralizado de Excepciones:** `src/shared/error_handlers.py:32` (`_respuesta_error`).
  - Todas las excepciones no capturadas devuelven un JSON estándar `{error_code, message, fields, timestamp}`.
  - No expone trazas de Python (`Traceback`, `line X`, `.py`), nombres de drivers (`psycopg2`, `sqlalchemy`) ni sentencias SQL (`SELECT`, `INSERT`).
- **Limitación de Prueba (TC-356 Forzar 500 por Caída de DB):**
  - Forzar la desconexión física de PostgreSQL o corromper el runtime en TEST es imposible mediante peticiones HTTP.
  - Subcaso marcado como `[BLOQUEADO]` con motivo explícito.
  - Cobertura compensatoria: Inspección de respuestas 4xx generadas por validación de esquemas (Pydantic) y evaluación de la estructura de error.

---

## 3. Subcasos Evaluados
1. **TC-M03-355: Fuzzing e Inyecciones:**
   - **UUID Malformado:** Path `GET /iot/auditoria/{bad_uuid}` -> Exige HTTP 422. Si devuelve 200, reporta `[DISCREPANCIA]`.
   - **Formato de Fecha Inválido:** `fecha_desde=not-a-date` -> Exige HTTP 422.
   - **Cross-Site Scripting (XSS):** Payload `<script>alert(1)</script>` en query `severidad_log` -> Exige HTTP 400/422 y verifica no-reflejo en el body.
   - **SQL Injection (SQLi):** Payload `' UNION SELECT null...; DROP TABLE` en query `tipo_evento` -> Exige sanitización sin error de sintaxis SQL.
   - **Paginación Inválida:** `pagina=-1&por_pagina=999999` -> Exige HTTP 422.
   - **Tipos de Datos Corruptos:** Body inválido en `POST /iot/auditoria/verificar-integridad` -> Exige HTTP 422.
   - **Caracteres Unicode Extremos:** Emojis y caracteres de control RTL -> Exige manejo controlado (sin error 500).
   - **Buffer Overflow Simulator:** Path con 10,000 caracteres -> Exige HTTP 414/422/404 con tiempo <2000 ms.
2. **TC-M03-356: Hardening y Ausencia de Internals:**
   - Verificación de Content-Type `application/json`.
   - Ausencia de cabeceras divulgadoras (`X-Powered-By`, `X-AspNet-Version`, `X-Debug-Token`).
   - Ausencia de trazas internas en el cuerpo de error.
3. **Verificación de Integridad:**
   - Consulta GET posterior para constatar que la bitácora opera de forma íntegra tras el fuzzing.

---

## 4. Teardown y Limpieza
- Pre-request genera `run_id = "test-" + {{$guid}}`.
- Último request: `DELETE /test-control/runs/{{run_id}}` (200 OK "Rollback exitoso").
- Duración total estimada: ~8 segundos.
