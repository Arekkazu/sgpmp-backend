# INC-M01-08-38 — RF-07: conservar contraseña ante fallo de invalidación

## Problema y decisión

TC-M01-038 reporta dos fallos: rollback de la contraseña cuando falla el
cierre de sesiones y propagación de una excepción sin el contrato del caso
alterno. Reproducidos contra el caso de uso de `dev` en `9a57da7`.

Rama hija de `dev` actualizado: `fix/rf07-inc-m01-08-38-fallo-invalidacion-sesiones`.

La primera transacción confirma contraseña, reinicio de intentos y auditoría
del cambio. La segunda invalida sesiones y tokens de acceso/refresco. Si falla
la segunda operación o su commit, su rollback no deshace la primera.
Se registra el fallo en el logger, se intenta la notificación de contraseña
cambiada mediante el servicio existente y se devuelve HTTP 500 controlado.
El servicio de notificaciones existente captura sus propios fallos.

Código: `CAMBIO_CONTRASENA_INVALIDACION_FALLIDA`.
Mensaje de la ficha de QA (más detallado que el resumen de RF-07):

> Contraseña actualizada, pero ocurrió un error al cerrar las sesiones en otros dispositivos. Se recomienda cerrar sesión manualmente en todos sus equipos para garantizar la seguridad.

RF-09 conserva su transacción única y rollback de contraseña/token si falla
la invalidación. No se cambia el repositorio compartido de sesiones.

## BD, autorización y frontend

No cambian tablas, columnas, modelos, puertos, permisos ni seeds. La migración
`b7e19f07a038` elimina el trigger y la función que comparaban hashes bcrypt y
daban una falsa garantía de no reutilización. Se probó `upgrade`, `downgrade`
y un segundo `upgrade`: el trigger quedó ausente, se restauró y volvió a quedar
ausente, respectivamente. La BD local `test-captcha-dev-leandro` quedó en la
cabeza `b7e19f07a038`. No se consultó ni modificó la BD remota de desarrollo.

La autorización de RF-07 sigue derivando de la sesión y del control de
propiedad del usuario. No se agrega un permiso administrativo al cambio propio.
El frontend ya conserva `message` en `mapToApiError` y lo presenta mediante
`pwError.message` en `CambiarContrasenaForm`; no necesita cambios de contrato.
Se documentó HTTP 500 en el router/OpenAPI. No se hizo E2E de navegador.

## Matriz de verificación

| Criterio | Verificación |
|---|---|
| Fallo antes de invalidar | Nueva contraseña y auditoría persistidas; HTTP 500 y mensaje exacto |
| Fallo después de flush | Rollback de modificaciones parciales a sesiones/tokens; contraseña conservada |
| Error SQL con transacción abortada | Rollback permite continuar y consultar contraseña confirmada |
| Fallo en commit de sesiones | HTTP 500; contraseña conservada |
| Flujo exitoso | Dos commits; sesiones y tokens invalidados; una notificación |
| Fallo en persistencia/auditoría/primer commit | No se intenta invalidar ni notificar; rollback inicial |
| Contraseña incorrecta, confirmación, política, otro usuario | Rechazo y contraseña original intacta |
| Reutilización en RF-07 | HTTP 409 antes de cifrar o producir efectos |
| Fallo del cifrado en RF-07 | HTTP 500 controlado; contraseña anterior vigente |
| Cinco claves actuales incorrectas | Bloqueo de 30 minutos; HTTP 423 desde el quinto intento |
| RF-09 | Fallo de invalidación revierte contraseña y consumo de token |
| Reutilización en RF-09 | HTTP 409; conserva contraseña y token de recuperación |
| Recuperación, refresh, login y bloqueo | Suites de regresión existentes |

Pruebas nuevas:

- `tests/identity_access/test_rf07_fallo_invalidacion.py`
- `tests/integration/test_rf07_fallo_invalidacion_integration.py`

Las pruebas PostgreSQL usan la fixture del repositorio: transacción exterior
por prueba y commits convertidos en savepoints. No dejan usuarios de prueba
persistidos ni llaman proveedores externos en los casos nuevos.

## Precisión sobre la prueba adjunta

La prueba original de QA obtiene **1 passed, 1 failed** con la corrección.
Pasa el status 500 y mensaje exacto. Falla `assert not db.rollback.called`,
porque considera incorrecto cualquier rollback, incluso el de la segunda
transacción. Eliminar ese rollback dejaría una sesión SQL abortada o cambios
parciales pendientes. Las pruebas nuevas verifican commit previo y persistencia
real, en lugar de ausencia absoluta de rollback. Los adjuntos se conservaron intactos.

## Hallazgo adicional corregido en la misma rama

Reutilizar la contraseña actual devolvía 200, en vez del 409 requerido.
Se reprodujo con el código original de `dev 9a57da7`.
El baseline contiene `trg_fn_no_reutilizar_contrasena`, que compara igualdad
de hashes; bcrypt genera un salt nuevo y por ello dos hashes de la misma clave
pueden diferir.

La corrección compara el texto transitorio mediante `bcrypt.checkpw` antes de
generar el hash nuevo. Se aplica a RF-07 y RF-09, responde 409 y no escribe,
audita, consume tokens, invalida sesiones ni notifica. Alembic retira el
trigger que daba una falsa garantía; su downgrade lo restaura. También se
eliminó el `rollback()` que el repositorio ejecutaba por su cuenta.

## Reproducción de la regresión

Resultado final con la migración aplicada: **206 passed**, en 33,89 s. Las 15
pruebas de integración específicas de la incidencia también pasaron de forma
aislada. Solo se emitió una advertencia de deprecación de Starlette/httpx, sin
fallos ni casos esperados como `xfail`. `git diff --check` no reportó errores.

Configurar `DATABASE_URL` y `TEST_DATABASE_URL` con una BD PostgreSQL de pruebas,
sin copiar credenciales a esta anotación, y ejecutar:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/identity_access tests/shared tests/integration/test_rf07_fallo_invalidacion_integration.py tests/integration/test_recuperacion_contrasena.py tests/integration/test_refresh_token.py tests/integration/test_sesiones_jwt.py tests/integration/test_rf06_bloqueo_invalida_sesiones.py -q -p no:cacheprovider
```
