# TC-M03-G183: OWASP API2 Autenticación y Verificación de Tokens en Auditoría IoT (RF-63)

## 1. Identificación y Objetivos
- **Caso Maestro:** TC-M03-G183
- **Vulnerabilidad Evaluada:** OWASP API2:2023 - Broken Authentication en RF-63
- **Endpoints Protegidos:**
  1. `GET /iot/auditoria`
  2. `GET /iot/auditoria/{id_evento}`
  3. `GET /iot/auditoria/exportar`
  4. `POST /iot/auditoria/verificar-integridad`
- **Subcasos Evaluados:**
  - **TC-M03-349:** Peticiones sin header `Authorization`, con header vacío (`" "`) y con prefijo `Bearer ` sin token. Verificación de rechazo uniforme con HTTP 401 Unauthorized y estructura estándar de error.
  - **TC-M03-350:** Peticiones con token expirado (hace 1 hora y hace 1 segundo). Si `TEST_JWT_SECRET` no está configurado en el entorno, se marca como `[BLOQUEADO]` puro (solo `console.log`, sin `pm.test`).
  - **TC-M03-351:** Manipulación de tokens JWT (`alg=none` sin firma, payload alterado con firma original, y firma realizada con clave ajena). Verificación de rechazo con HTTP 401 y uniformidad de mensajes para mitigar ataques de oráculo de orquestación.
- **Herramienta de Ejecución:** Newman + reporter htmlextra.
- **Entorno de Ejecución:** Sandbox transaccional con regla CERO DML.

---

## 2. Diagnóstico Técnico de Autenticación
En [auditoria_iot_router.py:28](file:///c:/Users/Juansegutt/Integrador/sgpmp-backend/src/telemetry/infrastructure/routers/auditoria_iot_router.py#L28):
- Todos los endpoints inyectan la dependencia `usuario_actual: UsuarioActual = Depends(get_current_user)`.
- La función `get_current_user` valida:
  1. Presencia de cabecera `Authorization: Bearer <token>`.
  2. Decodificación y verificación de firma usando `SECRET_KEY` y algoritmo `HS256`.
  3. Rechazo estricto de tokens con `alg="none"`.
  4. Expiración de claim `exp`.
  5. Respuestas con estructura estándar de error (`error_code`, `message`, `fields`, `timestamp`).

---

## 3. Matriz de Pruebas de Autenticación

| Subcaso | Condición de Cabecera / Token | Código Esperado | Estructura de Error | Estado |
|---|---|---|---|---|
| **TC-349** | Sin cabecera `Authorization` | 401 | `{error_code: "TOKEN_INVALIDO" / "NO_AUTENTICADO", message, ...}` | OK |
| **TC-349** | Cabecera `Authorization: " "` | 401 | Mensaje genérico sin fugar trazas de Python | OK |
| **TC-349** | Cabecera `Authorization: "Bearer "` | 401 | Mensaje genérico estándar | OK |
| **TC-350** | Token expirado hace 1h (`exp = now - 3600`) | 401 | `error_code: "TOKEN_EXPIRADO"` | Condicionado a `TEST_JWT_SECRET` (o `[BLOQUEADO]`) |
| **TC-350** | Token expirado hace 1s (`exp = now - 1`) | 401 | `error_code: "TOKEN_EXPIRADO"` | Condicionado a `TEST_JWT_SECRET` (o `[BLOQUEADO]`) |
| **TC-351** | Token con `alg="none"` sin firma | 401 | `error_code: "TOKEN_INVALIDO"`, mensaje idéntico | OK |
| **TC-351** | Payload alterado (`sub=999999`, `rol=1`) con firma rota | 401 | `error_code: "TOKEN_INVALIDO"`, mensaje idéntico | OK |
| **TC-351** | Firma con clave ajena incorrecta | 401 | `error_code: "TOKEN_INVALIDO"`, sin fugar error criptográfico | OK |

---

## 4. Hallazgos y Regla de Bloqueo Puro
1. `[BLOQUEADO]`: El subcaso TC-M03-350 requiere firmar criptográficamente un token JWT válido con un timestamp `exp` en el pasado. Esto exige que el secreto de firma `TEST_JWT_SECRET` esté disponible en el entorno del runner. Si dicha variable está ausente, el script se abstiene estrictamente de ejecutar aserciones sintéticas o `pm.test`, emitiendo únicamente `console.log` para no generar falsos positivos ni alterar las métricas del escáner QA.
