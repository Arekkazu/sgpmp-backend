# TC-M03-G173: OWASP API2 Autenticación y Tokens (RF-62)

## 1. Alcance y Objetivos
Validar los controles de autenticación, integridad y formato de tokens JWT (OWASP API2) aplicados sobre la totalidad de los endpoints expuestos por el módulo de calidad de telemetría IoT (`/iot/calidad`):
- `GET /iot/calidad`
- `GET /iot/calidad/{id_telemetria}`
- `POST /iot/calidad/{id_telemetria}/evaluar`
- `POST /iot/calidad/reevaluar`

## 2. Herramienta y Enfoque QA
- **Herramienta:** Newman / Postman v2.1.0 con reporte oficial en `resultados/resultado_TC-M03-G173.html` (consumido por el scanner).
- **CERO DML:** Todas las requests evalúan directamente la API REST. No se ejecuta ninguna consulta DML a la base de datos.
- **Aislamiento Sandbox:** Cada request lleva los encabezados de sandbox `X-Test-Run-Id` y `X-Sandbox-Secret`, y la suite finaliza con `DELETE /test-control/runs/{{run_id}}`.

## 3. Subcasos Evaluados
1. **TC-M03-331 (Ausencia y Malformación de Cabecera Authorization):**
   - **(a) Sin cabecera `Authorization`:** en los 4 endpoints -> HTTP 401.
   - **(b) Cabecera vacía / malformada:** **Advertencia Técnica de Postman:** Si se configura `Authorization: ""` (cadena vacía), las librerías cliente HTTP de Postman/Newman suelen descartar el encabezado antes de enviarlo por el socket TCP, solapándolo indistinguiblemente con el subcaso 331(a). Para evitar este comportamiento y forzar la emisión explícita del header en la petición HTTP, se envía `Authorization: " "` (un espacio en blanco).
   - **(c) Cabecera `Authorization: Bearer ` sin token:** -> HTTP 401.
   - **Mensaje de Error:** Estructura JSON estándar `{error_code, message, fields, timestamp}` que no expone detalles técnicos internos, nombres de tablas, sentencias SQL ni versiones del framework.
2. **TC-M03-332 (Manipulación de Tokens JWT sobre GET /iot/calidad):**
   - **(a) Token Expirado [Condicionado / Bloqueado Puro]:** Si la variable de entorno `TEST_JWT_SECRET` no está disponible en el entorno del runner, el subcaso 332(a) queda en estado **`[BLOQUEADO]` PURO** (se emite `console.log` y se suprimen todas las aserciones `pm.test` para evitar falsos positivos). Está prohibido utilizar tokens sintéticos o firmas arbitrarias como sustituto, ya que una firma inválida provocaría un rechazo por `TOKEN_INVALIDO` y no aislaría la regla de expiración temporal.
   - **(b) Algoritmo "none":** Se sustituye la cabecera por `{"alg": "none", "typ": "JWT"}` sin firma. El backend responde HTTP 401 `TOKEN_INVALIDO`.
   - **(c) Payload Alterado:** Modificación de claims `sub` o `rol` preservando la firma de otra sesión legítima. El backend detecta la firma rota y responde HTTP 401 `TOKEN_INVALIDO`.
   - **(d) Firma con Clave Espuria:** Token firmado con una clave secreta HMAC falsa desconocida. Responde HTTP 401 `TOKEN_INVALIDO`.
   - **Uniformidad de Mensajes:** La comparación de uniformidad del mensaje de error (`"El token es inválido o ha expirado."`) se realiza de forma estricta entre los subcasos **b, c y d** (los que no dependen de la clave secreta del servidor), garantizando que no se filtre al atacante la causa puntual del rechazo.
