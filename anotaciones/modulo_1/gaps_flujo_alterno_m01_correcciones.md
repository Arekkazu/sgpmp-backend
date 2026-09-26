# Corrección de los gaps de flujo alterno — Módulo 1 (Identity Access)

Fecha: 2026-09-22 · Rama: `fix/gaps-flujo-alterno-m01` → PR a `fix/m01`

Cierra los **9 ❌** que la auditoría dejó en
[`gaps_flujo_alterno_modulo1.md`](gaps_flujo_alterno_modulo1.md), contra el texto de
`anotaciones/Requerimientos/Especificacion-Requerimientos-Modulo1.md`. Sin cambios de
esquema: no hay migración Alembic ni DDL/DML que aplicar en ninguna base.

## Qué cambió, caso por caso

| # | RF | Antes | Ahora | Dónde |
|---|---|---|---|---|
| 1 | RF-01 | Token ya usado → 422 `FlowError` | 400 `ValidationError`, mismo caso que "token inexistente" | `registro/activar_cuenta_use_case.py` |
| 2 | RF-01 | SMTP caído → siempre 201 (correo en `BackgroundTasks`) | 503 `ServiceUnavailableError` tras los 3 intentos reales; el usuario queda registrado | `registro/crear_usuario_use_case.py`, `routers/usuarios_routers.py` |
| 3 | RF-03 | Renombrar el rol protegido → 422 (trigger `P0004`) | 403 `AuthorizationError` en el use case y en la traducción del pgcode | `roles/editar_rol_use_case.py`, `repositories/rol_repository.py` |
| 4 | RF-04 | Acción 'E' sobre cualquier recurso → aceptada | 400 `ValidationError` si el recurso no es `es_proceso_especial` | `permisos/asignar_permiso_use_case.py`, `repositories/permiso_repository.py` |
| 5 | RF-05 | Enviar rol/estado por `/usuarios/me` → 400 de Pydantic, sin rastro | 403 `AuthorizationError` con el intento auditado (`exitoso=False`) | `perfil/editar_perfil_use_case.py`, `dto/perfil_dto.py` |
| 6 | RF-06 | Transición inválida → 422 | 409 `ConflictError` | `cuentas/gestionar_cuenta_use_case.py` |
| 7 | RF-06 | Último administrador activo → 422 | 400 `ValidationError` | `cuentas/gestionar_cuenta_use_case.py` |
| 8 | RF-11 | Eliminación lógica concurrente → 404/422 según el flujo | 410 `GoneError` al editar un usuario ELIMINADO | `perfil/editar_perfil_use_case.py` |
| 9 | RF-14 | `LOGIN_FALLIDO` llegaba a cuentas INACTIVAS | INACTIVO solo admite `CAMBIO_ESTADO_CUENTA` | `shared/notificacion_service.py` |

Extra (anotado fuera de tabla en la auditoría): el mensaje de `PERMISO_SOLO_ADMIN` decía
"HTTP 403" dentro de una respuesta 422. Se quitó el prefijo; el código HTTP no cambió.

## Decisiones que conviene revisar

**RF-01 — el correo de activación vuelve a ser síncrono.** El flujo alterno pide 503 y una
tarea en segundo plano no puede alterar una respuesta que ya salió: son incompatibles. Se
revierte así la decisión de
[`rf01_validaciones_registro_correo_asincrono`](rf01_validaciones_registro_correo_asincrono/resumen.md),
que movió el envío a `BackgroundTasks` para que los 3 intentos y sus pausas de 5 s no
bloquearan el request. Consecuencia: con SMTP caído, `POST /usuarios/` puede tardar hasta
~34 s antes de responder 503. El camino feliz sigue costando un envío normal. El propio RF
se contradice en esto —el paso 7 del *Proceso* pide reintento "de forma asíncrona" con 201,
el *Flujo alterno* pide 503—; se implementó el flujo alterno porque es el gap anotado.
Si Análisis prefiere conservar el 201 asíncrono, hay que cerrar el gap en el RF, no en el código.

El mensaje del RF ("Su token se enviará automáticamente en los próximos 10 minutos") se
cambió por una instrucción real —usar `POST /usuarios/activar/reenviar`— porque no existe
cola durable que reintente: prometer un reenvío automático sería falso. El criterio de la
auditoría no exige el texto literal del mensaje.

**RF-04 — solo se pudo implementar la mitad del caso.** La regla "acción 'E' únicamente en
procesos especiales" se apoya en `modulo1.recursos.es_proceso_especial`, que ya existía. La
otra mitad ("una acción CRUD a un recurso que no las soporta") no tiene dato de respaldo: el
catálogo no declara qué CRUD admite cada recurso, y en DEV hay recursos marcados como proceso
especial que legítimamente usan R/C/U (todo el módulo 5). Inventar ese modelo excede el gap y
requiere decisión de Análisis.

Además, en DEV hay **18 permisos ya concedidos con acción 'E' sobre recursos que no están
marcados `es_proceso_especial`**: `usuarios` (el permiso de identificación completa de RF-12),
`plantillas`, `activos_biologicos`, `historial_telemetria`, `calidad_telemetria`,
`bitacora_auditoria_iot`, `version_modelo` y `auditoria_m04`. Siguen funcionando —RBAC solo
lee la tabla—, pero **volver a concederlos por API ahora se rechaza**. Son recursos de otros
módulos, por eso no se tocó el catálogo desde aquí. Hay dos salidas: marcar esos recursos como
proceso especial (si de verdad lo son) o reconciliar RF-04 con RF-12.

**RF-14 — INACTIVO conserva una excepción.** La letra del RF dice que un usuario INACTIVO "no
recibe notificación por ningún canal", pero su propio flujo alterno describe el caso concreto
de `LOGIN_FALLIDO` y lo justifica por privacidad ("no confirmar la existencia de la cuenta").
Bloquear también `CAMBIO_ESTADO_CUENTA` reabriría INC-M01-18-092: ese aviso va dirigido al
titular para decirle que su cuenta acaba de ser inactivada, y se envía *después* del commit,
cuando la cuenta ya figura como INACTIVA. Se corrigió el caso anotado (LOGIN_FALLIDO) y se
conservó el aviso del incidente. Si Análisis quiere la lectura estricta, es cambiar un
conjunto de una línea —y cerrar el incidente como "no se notifica".

**RF-11 — el 410 vive en la edición, no en la consulta.** El RF habla de "interactuar" con un
usuario recién eliminado y de detectarlo "mediante la validación de concurrencia". El único
endpoint con control de concurrencia es `PATCH /usuarios/{id}` (viaja con `version`), así que
ahí se emite el 410. `GET /usuarios/{id}/detalle` sigue devolviendo el usuario eliminado a
propósito: un administrador tiene que poder inspeccionar cuentas dadas de baja.
`POST /usuarios/{id}/gestionar` conserva el 409 que pide RF-06.

## Lo que NO se tocó (⚠️ de la auditoría)

- **RF-01, correo/ID duplicado con condición más amplia que el RF.** Exige índice único parcial
  (`WHERE estado <> 'ELIMINADO'`), migración Alembic con autorización del DBA y una decisión de
  negocio: permitir que el correo de una cuenta eliminada se vuelva a registrar.
- **RF-13, BD caída da 503 y el RF pide 500.** Decisión sistémica de todo el backend
  (`db_no_disponible_handler`), documentada como Patrón 4; corregirla afectaría a los cinco módulos.
- **RF-14, "sin reintentos automáticos".** Los 3 reintentos viven en `shared/email.py`, compartida
  por todos los módulos, y son justamente lo que sostiene el 503 de RF-01, RF-05 y RF-08.

## Verificación

- `pytest tests/identity_access` → **175 pasan** (10 nuevas en
  `tests/identity_access/test_gaps_flujo_alterno_m01.py`, una por gap).
- `pytest tests --ignore=tests/integration` → 773 pasan; los 2 fallos de
  `tests/biological_assets/test_registrar_transferencia_use_case.py` ya venían de `dev`.
- Integración: no se pudo correr en local (`psycopg2` no carga `libz.so.1` en este venv y
  `TEST_DATABASE_URL` no está definida). Se ajustaron las dos pruebas que fijaban los códigos
  viejos —`test_rf05_rf06_rbac_perfil_gestion_integration.py`— para que CI las valide.
