# DISENO_Y_PRECONDICIONES — TC-M04-G095

## 1. Identificación y Metadatos
- **ID Caso / Grupo:** TC-M04-G095 (TC-M04-295, TC-M04-296, TC-M04-299)
- **Módulo:** Módulo 4 — Predicción e IA (RF-64 a RF-73)
- **Requisito Funcional:** RF-73 (Auditoría de eventos de predicción — Seguridad OWASP API8: Security Misconfiguration & API10: Unsafe Consumption / Fuzzing)
- **Fase:** DISEÑO TÉCNICO Y AUTOMATIZACIÓN DE PRUEBAS (SOLO DISEÑO Y CONSTRUCCIÓN)
- **Estado Global:** [DISENADO / 100% OPERATIVO EN TEST]
- **Entorno Evaluado:** Backend TEST desplegado (`https://api.inmero.co/back-sigab-test`)
- **Herramienta de Ejecución:** Newman + reporter htmlextra (Sandbox transaccional con aislamiento por `run_id`).

---

## 2. Diagnóstico Técnico y Vulnerabilidades OWASP Evaluadas

| Subcaso | Dimensión Evaluada | Comportamiento Esperado | Implementación en Backend | Estado Técnico |
|---|---|---|---|---|
| **TC-M04-295** | Cabeceras de Seguridad y CORS | Presencia de CSP, HSTS, X-Frame-Options, X-Content-Type-Options; origen malicioso no reflejado en CORS preflight | `SecurityHeadersMiddleware` y `CORSMiddleware` en `main.py` | [OPERATIVO] |
| **TC-M04-296** | Fugas de Información en Errores | HTTP 400/422 con formato estándar `{ error_code, message, fields, timestamp }`; cero stack traces | `register_error_handlers(app)` en `src/shared/error_handlers.py` | [OPERATIVO] |
| **TC-M04-299** | Fuzzing de Tipos, Rangos y Longitudes | Entradas corruptas (`por_pagina="abc"`, `-1`, `999999999`, string 10k) rechazadas con 4XX; **NUNCA 500** | Validador declarativo Pydantic / FastAPI | [OPERATIVO] |

### Análisis de Mecanismos de Protección:
1. **Cabeceras HTTP OWASP (`src/shared/middlewares.py`):**
   - `SecurityHeadersMiddleware` inyecta automáticamente en toda respuesta:
     - `X-Content-Type-Options: nosniff` (previene MIME sniffing).
     - `X-Frame-Options: DENY` (mitiga clickjacking).
     - `Strict-Transport-Security: max-age=63072000; includeSubDomains` (garantiza HTTPS estricto).
     - `Content-Security-Policy: default-src 'none'` (bloquea ejecución de scripts externos).
   - `Referrer-Policy` no está declarado en el middleware, lo cual queda documentado como `[DISCREPANCIA]`.
2. **Política CORS (`main.py`):**
   - El middleware `CORSMiddleware` opera con lista blanca explícita (`allowed_origins`) y regex para localhost.
   - Peticiones preflight con `Origin: https://attacker.example` no reciben cabecera `Access-Control-Allow-Origin`, previniendo consumo no autorizado desde navegadores.
3. **Manejo Centralizado de Excepciones (`src/shared/error_handlers.py`):**
   - El handler intercepta `RequestValidationError` y `AppError`, retornando payloads limpios sin volcados de traza ni referencias a librerías internas (`psycopg2`, `sqlalchemy`).

---

## 3. PENDIENTES DE DESARROLLO

| Subcaso | Endpoint Esperado | Contrato Esperado | Asignado A (Equipo/Área) |
|---|---|---|---|
| **TC-M04-295** | Cabecera `Referrer-Policy` | Inyectar `Referrer-Policy: no-referrer` o `strict-origin-when-cross-origin` en `SecurityHeadersMiddleware` | Equipo Backend Core / Seguridad |

---

## 4. FASE SEPARADA (TC-M04-296: Provocación Forzada de HTTP 500)

> [!NOTE]
> El subcaso TC-M04-296 menciona la evaluación del comportamiento del backend ante excepciones internas HTTP 500 para corroborar la ausencia de stack traces.
> Desde una interfaz REST normal, provocar un error 500 genuino requeriría:
> - Desconectar la base de datos a mitad de transacción.
> - Corromper memoria de proceso o inyectar fallas de I/O en disco.
> 
> Estas acciones violan la **Regla de Oro de Cero Manipulación de Infraestructura en Sandbox** y romperían el estado del entorno de pruebas compartido. Por tanto, la verificación de respuestas 500 se clasifica para ejecución en la **FASE SEPARADA** con inyección de fallas mediante mocks o entorno de caos controlado. La suite actual valida exhaustivamente que todos los errores 4XX cumplan con el estándar de anonimización.

---

## 5. Estrategia de Sandbox y Teardown
- Generación de `run_id` aleatorio en pre-request de colección (`test-{{$guid}}`).
- Inyección de cabeceras de aislamiento `X-Test-Run-Id` y `X-Sandbox-Secret`.
- Teardown con `DELETE /test-control/runs/{{run_id}}` (200 OK con `Rollback exitoso`).
- Cero escrituras directas SQL en base de datos.
