# TC-M01-040 — REEVALUACIÓN V2

RF-08 — Recuperación de contraseña
Fecha: 2026-09-14/15 · Entorno decisorio: TEST

## DECISIÓN GENERAL

### REEVALUACIÓN APROBADA — V1 era falso positivo

La evidencia V1 (`Resultados/resultado.html`) marcaba Rechazado con:
- `expected 'PEGAR_AQUI_EL_TOKEN_DEL_CORREO' to not deeply equal 'PEGAR_AQUI_EL_TOKEN_DEL_CORREO'`
- `expected response to have status code 200 but got 401`
- `expected 'Error de autenticidad...' to include 'restablecida exitosamente'`

Causa raíz confirmada: el paso 2 de la colección original ("(Manual) Revisar
el correo y pegar el token en la variable token_recuperacion") nunca se
ejecutó — el token quedó con el valor placeholder literal, por lo que el
paso 3 envió un token inválido y el 401 es el comportamiento correcto del
producto ante un token que nunca existió. **No es un defecto del producto.**

## EVIDENCIA DE LA REEVALUACIÓN (correo real, cuenta u20212200102@usco.edu.co, id_usuario=45)

| Paso | Endpoint | Resultado | Evidencia |
|---|---|---|---|
| 1. Solicitar recuperación | `POST /contrasena/recuperar` | 202 — "Si el correo está registrado, recibirás instrucciones..." | Correo real recibido con enlace de token |
| 2. (Manual) Revisar correo y obtener token | — | Token real obtenido: `Sy-21fn37lHxUJpri7sMP-q1VFK52Bow5xoksn0gRrw` | Confirmado por el titular de la cuenta |
| 3. Restablecer con token real | `POST /contrasena/restablecer` | 200 — "Contraseña restablecida exitosamente" | — |
| 4. Login con contraseña nueva | `POST /sesiones/` | 200, token de sesión válido | — |
| 5. Verificar notificaciones | `GET /notificaciones` | Ambos eventos presentes: tipo_evento 7 ("recuperación iniciada", 02:00:01Z) y tipo_evento 8 ("restablecida exitosamente", 02:01:09Z) | id_notificacion 2922 y 2924 |

**No se verificó** "contraseña anterior ya no funciona" (paso 4 del original):
no se dispone de la contraseña real previa de esta cuenta (es la cuenta
personal del usuario, no una cuenta QA dedicada); verificarlo requeriría
adivinar/forzar un valor, lo cual está fuera de alcance. El resto del flujo
queda demostrado de extremo a extremo con credenciales y correo reales.

## Efecto colateral

La contraseña de la cuenta `u20212200102@usco.edu.co` (id_usuario=45) en
**TEST** quedó fijada en `Confirmada#44` como resultado de esta prueba,
con consentimiento explícito del titular de la cuenta antes de ejecutar.

## Seguridad

- Token de recuperación fue de un solo uso real, obtenido por el propio
  titular desde su bandeja de correo.
- Todas las llamadas fueron HTTPS directas a TEST; no se guardó el token
  ni la contraseña nueva en ningún archivo del repositorio.
- No se modificó código, infraestructura ni datos de otras cuentas.

## Estado de cierre

TC-M01-040 reevaluado y cerrado: **APROBADO**. El rechazo original fue un
falso positivo de ejecución (paso manual omitido), no un defecto de
producto.
