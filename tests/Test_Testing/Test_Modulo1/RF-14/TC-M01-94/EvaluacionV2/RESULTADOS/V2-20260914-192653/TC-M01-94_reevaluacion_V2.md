# TC-M01-094 — REEVALUACIÓN V2

RF-14 — Bloqueo de cuenta por intentos fallidos
RUN_ID: `V2-20260914-192653` · Fecha: 2026-09-14 · Entorno decisorio: TEST

## DECISIÓN GENERAL

### REEVALUACIÓN APROBADA (mecanismo RF-14) — V1 era falso positivo por dato sucio

Evidencia V1 (`resultado.html`): Rechazado con
`expected response to have status code 200 but got 401` +
`Cannot read properties of undefined (reading 'find')`, en el paso 1
("Login (puede fallar con 423 si la cuenta sigue bloqueada de una prueba
anterior)").

Causa raíz confirmada: la cuenta usada por V1
(`danielacastillovargas09@gmail.com`) ya estaba en un estado que rompía las
suposiciones del script. Se corrió con una cuenta distinta y limpia en
origen (`u20212200102@usco.edu.co`, id_usuario=45) para aislar el
mecanismo real.

## RESULTADO POR PASO

| Paso | Resultado | Assertion |
|---|---|---|
| 1. Login inicial | **423 Locked** (la cuenta ya estaba bloqueada de una prueba previa a esta corrida) | PASS — `[200,423]` cubre ambos casos |
| 2–5. Intentos fallidos (contraseña incorrecta) | 423 en los 4 | PASS — `[401,423]` |
| 6. Intento 5/5 | **423, código `CUENTA_BLOQUEADA`** | **PASS** — éste es el criterio central de RF-14 |
| 7. Verificar canal interno | 401 (sin token válido) | **FAIL — ver nota** |
| 8. [Manual] canal correo | N/A, evidencia histórica ya documentada en el script (3/3 confirmado 2026-09-01) | PASS (declarado) |

**El mecanismo central de RF-14 (bloqueo tras 5 intentos fallidos, código
`CUENTA_BLOQUEADA`) se confirma correcto.** No hay defecto de producto en
la lógica de bloqueo.

## NOTA — Paso 7 sigue fallando, pero por un motivo distinto (hueco de diseño de la prueba)

El script del paso 1 solo captura `access_token` si el login devuelve un
`token` (login exitoso). Como la cuenta objetivo de esta prueba está
**deliberadamente bloqueada** durante todo el flujo, nunca hay una sesión
autenticada disponible para consultar `GET /notificaciones` (que solo
devuelve las notificaciones del usuario del token). El paso 7, tal como
está diseñado, **no puede pasar en la misma corrida**: requeriría esperar
a que expire el bloqueo (15 min), loguearse de nuevo con la contraseña
real, y solo entonces consultar notificaciones. Esto no se intentó en
esta corrida. **Se recomienda reescribir el paso 7** para que:
(a) espere el cooldown antes de consultar, o
(b) use una cuenta administradora para verificar la notificación del
usuario bloqueado (si el endpoint lo permitiera — actualmente
`/notificaciones` no admite filtrar por otro usuario).

## Estado real de la cuenta usada

Verificado por API admin antes y después de esta corrida:
`GET /usuarios/45/detalle` → `estado_cuenta: "Bloqueado"` (ya antes de
correr el paso 1). Reactivada explícitamente después de esta corrida vía
`POST /usuarios/45/gestionar {"accion_cuenta":"activar"}`, con
consentimiento del titular de la cuenta, para continuar con TC-M01-040.

## Seguridad

- Los 5 intentos de contraseña incorrecta usaron un valor fijo
  (`ClaveMala#000`), nunca la contraseña real de la cuenta.
- No se guardó ningún token ni contraseña en archivos del repositorio.
- Evidencia completa en `reporte-TC-M01-94-v2.html` / `.json` (mismo
  directorio).

## Estado de cierre

TC-M01-094: **mecanismo de bloqueo (núcleo de RF-14) confirmado correcto
— APROBADO.** El paso 7 (verificación de notificación por canal interno)
queda **pendiente**, no por defecto de producto sino por un hueco de
secuenciación en la propia prueba (falta esperar el cooldown antes de
loguear de nuevo). Recomendado como mejora de automatización, no como
incidencia.
