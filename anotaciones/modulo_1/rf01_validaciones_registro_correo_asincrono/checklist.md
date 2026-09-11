# RF-01 — Validaciones de registro y correo asíncrono

Issue #1601 · PR #48 · rama `feature/rf01-validaciones-registro-correo-asincrono`

Documento de trabajo: se va cerrando a medida que avanza la implementación.
El resumen definitivo queda en `resumen.md` de esta misma carpeta.

---

## Alcance de la issue

1. Campo `confirmar_contraseña` en el registro.
2. `numero_identificacion` validado por formato.
3. Envío del correo de activación fuera del request (los 3 reintentos con
   pausas de 5 s bloqueaban hasta ~15 s la respuesta al usuario).

Fuera del alcance histórico de este PR: CAPTCHA. Fue resuelto posteriormente
en la implementación dedicada de la issue #1600; consultar
`anotaciones/modulo_1/rf01_captcha_registro.md`.

---

## Revisión del PR #48 — qué estaba bien

- [x] `confirmar_contrasena` obligatorio y con verificación de coincidencia.
- [x] `CorreoActivacionPort` + `CorreoActivacionBackgroundAdapter`: el correo se
      agenda con `BackgroundTasks` sobre una sesión `SessionLocal` propia.
      `src/shared/email.py` conserva intactos los 3 intentos y las pausas de 5 s.
- [x] Respuesta del registro = `"Registro exitoso, envío de correo en proceso."`
      (literal del RF) y `503` retirado de `responses`. Correcto: `NotificacionService.notificar`
      ya capturaba toda excepción, así que ese 503 nunca llegaba al cliente.
- [x] SSO AgroFusion (Mecanismo A) no se rompe: usa `Usuario.crear_minimo_sso`,
      una fábrica distinta de `registrar_nuevo`.

## Revisión del PR #48 — hallazgos a corregir

- [x] **BLOQUEANTE.** La migración `e7b31f4a6c20` cuelga de `d4e2f8a15c9b`, que ya
      no es la cabeza de `dev` (`c8e4a5b13d72`). Tras el merge quedan dos cabezas y
      `alembic upgrade head` falla con *Multiple head revisions are present*.
- [x] La validación `^[0-9]+$` se aplica sin mirar `tipo_identificacion`, lo que
      hace imposible registrar un `Pasaporte` — tipo que el propio RF-01 y el
      `CHECK chk_usuario_tipo_identificacion` de la BD declaran válido.
      **Decisión: numérico solo para CC y CE; `Pasaporte` acepta alfanumérico.**
- [x] `EditarPerfilDTO` no puede decidir la regla: ambos campos son opcionales, así
      que en una edición parcial el DTO no conoce el tipo efectivo.
- [x] Los DTO usan `field_validator` + `info.data` para la confirmación; la casa ya
      tiene `@model_validator(mode="after")` en `contrasena_dto.py`.
- [x] `tipo_identificacion` es `str` libre en los DTO; solo lo restringe la BD.

---

## Base de datos

- [x] Reescribir `alembic/versions/e7b31f4a6c20_rf01_identificacion_numerica.py`:
      `down_revision = "c8e4a5b13d72"`.
- [x] Trigger sensible al tipo (`'Pasaporte'` → `^[A-Za-z0-9]+$`, resto → `^[0-9]+$`)
      y disparo en `UPDATE OF numero_identificacion, tipo_identificacion`.
- [x] Normalizar en `sgpmp` las 5 filas sucias (ids 22, 24, 26, 45, 46).
      Se conservan intactas 30 y 31 (`TEST-GESTOR-01`, `TEST-REVFISCAL-01`,
      fixtures de módulo 9).
- [x] `alembic upgrade head` sobre `sgpmp`.
- [x] `alembic upgrade head` sobre `pruebas` (base de integración).

RBAC: sin cambios. No hay recurso ni permiso nuevo.

## Código

- [x] `src/shared/regex.py` — `IDENTIFICACION_NUMERICA` e `IDENTIFICACION_PASAPORTE`
      en lugar del `NUMERO_IDENTIFICACION` único del PR.
- [x] `src/identity_access/domain/value_objects/identificacion.py` (nuevo) —
      `identificacion_valida(tipo, numero) -> bool`.
- [x] `domain/entities/usuario.py` — `registrar_nuevo` usa el helper con el tipo.
- [x] `infrastructure/dto/usuario_dto.py` — `Literal` en el tipo y un único
      `model_validator` para confirmación + identificación.
- [x] `infrastructure/dto/agrofusion_dto.py` — mismo tratamiento.
- [x] `infrastructure/dto/perfil_dto.py` — quitar el validador de formato.
- [x] `application/use_cases/perfil/editar_perfil_use_case.py` — validar el par ya
      fusionado antes de `usuarios_repo.actualizar`.

## Pruebas

- [x] Unitarias `tests/identity_access/test_rf01_validaciones_registro.py`
      parametrizadas por tipo, con casos de pasaporte válido e inválido.
- [x] Integración `tests/integration/test_rf01_validaciones_registro_integration.py`:
      alta con pasaporte y cambios CC↔Pasaporte contra el trigger.
- [x] Caso de edición administrativa con identificación inválida → 400.
- [x] `pytest tests -m "not integration" -q` en verde.
- [x] `pytest tests/integration -m integration -q` en verde.

## Documentación

- [x] Absorber `anotaciones/modulo_1/rf01_confirmacion_identificacion_correo_asincrono.md`
      en esta carpeta y borrarlo de la raíz de `modulo_1/`.
- [x] `identity_access_curls.md` — payload de registro con `confirmar_contrasena`,
      mensaje de respuesta nuevo y regla por tipo de identificación.
- [x] `estado_M01.md` — reflejar que la regla numérica aplica a CC/CE, no a `Pasaporte`.
- [x] `resumen.md` final.

## Entrega

- [x] Merge de `dev` en la rama (necesario para encadenar la migración).
- [x] Push a `feature/rf01-validaciones-registro-correo-asincrono` (PR #48).
