# INC-M01-16-057 — reutilización de contraseña en RF-09

## Hallazgo

La evidencia Newman de `TC-M01-057` muestra que el entorno probado respondió
HTTP 200 al intentar restablecer una cuenta con su contraseña actual, cuando
debía devolver HTTP 409.

Al actualizar la rama base antes de implementar `#101`, `dev` avanzó hasta
`64cb3be` y ya contenía la corrección funcional incorporada por el merge
`9ec4519` (PR #119). `RestablecerContrasenaUseCase` compara el texto transitorio
contra el hash vigente mediante `bcrypt.checkpw` antes de cifrar o persistir.

La migración `b7e19f07a038`, también integrada en `dev`, elimina el trigger que
comparaba directamente dos hashes bcrypt con salts diferentes y no podía
garantizar la regla.

## Comportamiento verificado

- Respuesta `409 CONTRASENA_REUTILIZADA`.
- Contraseña y hash vigentes sin cambios.
- Token de recuperación sin consumir.
- Sesiones activas sin invalidar.
- Intentos y bloqueo de la cuenta sin cambios.
- Sin auditoría ni notificación de restablecimiento exitoso.
- El login continúa funcionando con la contraseña vigente.
- El mismo token puede utilizarse después con una contraseña diferente.
- En el restablecimiento válido se consume el token, se invalidan las sesiones,
  se registra la auditoría y se genera la notificación esperada.

## Paso 0 — base de datos y RBAC

Este incidente no requiere otra migración, DML ni cambios de RBAC. La migración
que retira el trigger defectuoso ya forma parte de `dev`. La validación se
ejecuta en aplicación antes de cualquier escritura.

No se modifica la base remota `sgpmp_dev`.

## Validación

- Evidencia Newman original: 1 aserción fallida porque esperaba 409 y recibió
  200; el login posterior con la misma contraseña respondió 200.
- Prueba ya integrada en `dev`: `1 passed` para rechazo y conservación del
  token.
- Prueba unitaria específica de `INC-M01-16-057`: `1 passed`.
- Prueba HTTP/PostgreSQL específica con continuación del flujo: `1 passed`.
- Suite completa sin integración: `413 passed`.
- Regresión PostgreSQL del Módulo 1: `76 passed`.
- Compilación y `git diff --check`: sin errores.

La integración usa `test_rf09_reutilizacion_057`, clonada de la base local
`test-captcha-dev-leandro`, con una transacción exterior revertida por prueba.
La base temporal se elimina al finalizar.

## Hallazgo de infraestructura separado

`alembic heads` sobre el `dev` actualizado reporta cuatro cabezas:

```text
52b86f7385bd
543cddec52a7
a1c3f6e0b2d4
b7e19f07a038
```

La base temporal utilizada por RF-09 está en `b7e19f07a038` y ya no contiene
el trigger defectuoso. La multiplicidad de cabezas proviene de ramas integradas
previamente y no se modifica en esta corrección.
