# DISENO_Y_PRECONDICIONES — TC-M04-G094

## 1. Identificación y Metadatos
- **ID Caso / Grupo:** TC-M04-G094 (TC-M04-293, TC-M04-294)
- **Módulo:** Módulo 4 — Predicción e IA (RF-64 a RF-73) / Módulo 1 (RF-02)
- **Requisito Funcional:** RF-73 (Auditoría de eventos de predicción — Seguridad OWASP API2: Broken Authentication & Session Management)
- **Fase:** DISEÑO TÉCNICO Y AUTOMATIZACIÓN DE PRUEBAS (SOLO DISEÑO Y CONSTRUCCIÓN)
- **Estado Global:** [DISENADO / 100% OPERATIVO EN TEST]
- **Entorno Evaluado:** Backend TEST desplegado (`https://api.inmero.co/back-sigab-test`)
- **Herramienta de Ejecución:** Newman + reporter htmlextra (Sandbox transaccional con aislamiento por `run_id`).

---

## 2. Diagnóstico Técnico y Vulnerabilidades OWASP API2 Evaluadas

| Subcaso | Escenario de Ataque / Prueba | Endpoint Objetivo | Comportamiento Esperado | Estado Técnico |
|---|---|---|---|---|
| **TC-M04-293a** | Petición sin header `Authorization` | `GET /prediccion/auditoria`<br>`GET /prediccion/auditoria/exportar`<br>`GET /prediccion/auditoria/{id}` | HTTP 401 Unauthorized con `{ error_code: "NO_AUTENTICADO", message: "..." }` | [OPERATIVO] |
| **TC-M04-293b** | Header `Authorization: Bearer ` vacío | `GET /prediccion/auditoria` | HTTP 401 Unauthorized con formato de error controlado | [OPERATIVO] |
| **TC-M04-293c** | Token manipulado (firma criptográfica alterada) | `GET /prediccion/auditoria` | HTTP 401 Unauthorized (rechazo criptográfico antes de tocar dominio/BD) | [OPERATIVO] |
| **TC-M04-294** | Reutilización de token tras cierre de sesión (`DELETE /sesiones/`) | `GET /prediccion/auditoria` | HTTP 401 Unauthorized con `error_code: "TOKEN_REVOCADO"` | [OPERATIVO] |

### Análisis de Mecanismo de Seguridad:
1. **Validación de Autenticación (`dependencies.py`):**
   - La dependencia `get_current_user` valida el formato del JWT. Si la cabecera está ausente o vacía, Starlette/FastAPI genera HTTP 401 de forma inmediata.
   - Si la firma del token no coincide con `SECRET_KEY`, la librería `PyJWT` genera `InvalidSignatureError` que se traduce en HTTP 401 genérico sin revelar detalles internos.
2. **Invalidación de Sesión (`DELETE /sesiones/` y Tabla `Tokens`):**
   - El endpoint `DELETE /sesiones/` invoca `LogoutUseCase`, actualizando la columna `fecha_uso` en la tabla `Tokens`.
   - Cualquier consulta posterior con ese mismo `id_token` es rechazada con `error_code: "TOKEN_REVOCADO"`, mitigando completamente la persistencia zombie de credenciales.

---

## 3. PENDIENTES DE DESARROLLO

| Subcaso | Endpoint Esperado | Contrato Esperado | Asignado A (Equipo/Área) |
|---|---|---|---|
| **TC-M04-293** | Endpoints de Auditoría M04 | Totalmente implementados con autenticación obligatoria | Ninguno (Completado) |
| **TC-M04-294** | `DELETE /sesiones/` | Totalmente implementado con revocación en base de datos | Ninguno (Completado) |

*Nota:* No existen pendientes de desarrollo para este caso; los endpoints evaluados se encuentran 100% operativos.

---

## 4. Limitaciones Técnicas y Supuestos

- **Uniformidad de Mensajes de Error:**
  - Según el estándar de seguridad OWASP API2, los mensajes de error 401 no deben permitir enumeración de cuentas ni distinguir entre un token expirado y un token con firma forjada para no asistir a potenciales atacantes.
- **Generación de Token Manipulado en Pre-request:**
  - Para evaluar la robustez de la verificación criptográfica sin requerir `TEST_JWT_SECRET`, el script altera deterministamente los últimos 8 caracteres de la firma Base64URL del token legítimo obtenido en login.

---

## 5. Estrategia de Sandbox y Teardown
- Generación de `run_id` aleatorio en pre-request de colección (`test-{{$guid}}`).
- Inyección de cabeceras de aislamiento `X-Test-Run-Id` y `X-Sandbox-Secret`.
- Teardown con `DELETE /test-control/runs/{{run_id}}` (200 OK con `Rollback exitoso`).
- Cero escrituras directas SQL en base de datos.
