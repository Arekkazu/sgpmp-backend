# Gaps de Flujo Alterno — Módulo 1 (Identity Access)

Auditoría de solo lectura: compara cada caso de **Flujo alterno** documentado en
`anotaciones/Requerimientos/Especificacion-Requerimientos-Modulo1.md` contra el
comportamiento real del código en `src/identity_access`.

> **Estado (2026-09-22): los 9 ❌ de este módulo están corregidos** en la rama
> `fix/gaps-flujo-alterno-m01` (PR hacia `fix/m01`). Cada caso corregido queda
> marcado ✅ **(corregido)** con la nota de qué se cambió. El detalle de la
> implementación está en
> [`gaps_flujo_alterno_m01_correcciones.md`](gaps_flujo_alterno_m01_correcciones.md).
> Los ⚠️ parciales se conservan como estaban: la justificación de por qué no se
> tocaron está en ese mismo documento.

Criterio de veredicto:
- ✅ **Cumple** — mismo HTTP y misma condición de negocio que el RF (el texto exacto del mensaje no se exige idéntico).
- ⚠️ **Parcial** — el HTTP coincide pero la condición de negocio es más amplia/estrecha que el RF, o viceversa.
- ❌ **Gap** — HTTP distinto al que pide el RF, o el caso no está implementado en absoluto.
- ➖ **No aplica** — el mecanismo que pide el RF (ej. WebSocket) no existe en la arquitectura actual, pero la restricción de fondo que ese mecanismo perseguía sí se cumple por otra vía; o es un caso interno sin respuesta HTTP.

RF-08 y RF-09 no tienen ficha detallada en el documento fuente (ver nota de
conversión en la línea ~1755) — se documentan solo contra el código, sin
veredicto de cumplimiento.

## Resumen

| RF | Casos revisados | ❌ Gaps | ❌ Pendientes hoy | ⚠️ Parciales |
|---|---|---|---|---|
| RF-01 Registro de usuarios | 9 | 2 | **0** | 1 |
| RF-02 Autenticación | 7 | 0 | 0 | 0 |
| RF-03 Gestión de roles | 7 | 1 | **0** | 0 |
| RF-04 Gestión de permisos | 8 | 1 | **0** | 0 |
| RF-05 Edición de datos de usuario | 8 | 1 | **0** | 0 |
| RF-06 Gestión de cuentas de usuario | 7 | 2 | **0** | 0 |
| RF-07 Cambio de contraseña | 8 | 0 | 0 | 0 |
| RF-08/RF-09 Recuperación/Restablecimiento | 5 | — (sin ficha) | — | — |
| RF-10 Historial de auditoría | 7 | 0 | 0 | 0 |
| RF-11 Visualización de usuarios | 7 | 1 | **0** | 0 |
| RF-12 Detalle de usuario | 5 | 0 | 0 | 0 |
| RF-13 Perfil propio | 6 | 0 | 0 | 1 |
| RF-14 Notificaciones | 6 | 1 | **0** | 0 |

La columna "❌ Gaps" conserva el hallazgo original de la auditoría; "Pendientes
hoy" es lo que sigue abierto después de las correcciones.

---

## RF-01 — Registro de usuarios

| Caso | HTTP esperado | HTTP real | Archivo:línea | Veredicto |
|---|---|---|---|---|
| Número de identificación duplicado | 409 | 409 `ConflictError` | `infrastructure/repositories/usuario_repository.py:112-124` | ✅ |
| Correo electrónico duplicado | 409 | 409 `ConflictError` | `infrastructure/repositories/usuario_repository.py:112-124`, `infrastructure/models/usuarios_model.py:34` | ⚠️ |
| Incumplimiento de política de contraseñas | 400 | 400 `ValidationError` | `domain/value_objects/contrasena.py:54` | ✅ |
| Token de activación expirado | 410 | 410 `GoneError` | `application/use_cases/registro/activar_cuenta_use_case.py:70-75` | ✅ |
| Token inválido/inexistente **o ya utilizado** | 400 (ambos casos) | 400 `ValidationError` en ambos | `application/use_cases/registro/activar_cuenta_use_case.py:63-87` | ✅ (corregido) |
| Fallo crítico SMTP (tras 3 intentos) | 503 | 503 `ServiceUnavailableError` (usuario registrado) | `application/use_cases/registro/crear_usuario_use_case.py:150-175` | ✅ (corregido) |
| Fallo validación CAPTCHA | 400 | 400 `ValidationError` | `application/use_cases/registro/crear_usuario_use_case.py:91-99` | ✅ |
| Usuario menor de edad | 403 | 403 `AuthorizationError` | `application/use_cases/registro/crear_usuario_use_case.py:120-125` | ✅ |
| Error de formato (ID alfabético / correo inválido) | 400 | 400 (Pydantic → handler global) | `infrastructure/dto/usuario_dto.py`, `domain/value_objects/email.py` | ✅ |

**⚠️ Correo/ID duplicado — condición más amplia que el RF.**
El RF exige bloquear solo si el correo "está asociado a otro usuario **activo o
pendiente de activación**". El constraint real (`uq_usuario_correo_electronico`,
`uq_usuario_numero_identificacion`) es único a nivel de toda la tabla, sin
`WHERE estado != 'ELIMINADO'`. Un correo de una cuenta ELIMINADA/INACTIVA sigue
bloqueando el registro, contradiciendo la letra del RF (aunque el HTTP 409 es
correcto).

**✅ CORREGIDO — Token "ya utilizado" ahora cae en el caso 400 que pide el RF.**
`ActivarCuentaUseCase` lanza `ValidationError` (400) con el mensaje del RF
también cuando la cuenta ya está ACTIVA. Diagnóstico original:
El RF agrupa "token inexistente" y "token ya usado" en el mismo caso 400. El
código solo da 400 cuando el hash no existe en absoluto; si el token existe
pero la cuenta ya está `ACTIVA` (activación repetida), lanza `FlowError` → 422.
Un test que reactive una cuenta ya activada y espere 400 fallará.

**✅ CORREGIDO — el 503 por SMTP agotado ya es reproducible.**
El correo de activación se despacha con `NotificacionService` dentro del
request, justo después del commit: los 3 reintentos de `shared/email.py` son
reales y, si se agotan, el endpoint responde 503 con el mensaje del RF
("Registro exitoso, pero el servicio de notificaciones no está disponible…").
El usuario queda registrado igual y puede pedir el reenvío. `CorreoActivacionPort`
y su adaptador en segundo plano se eliminaron. Diagnóstico original:
El correo de activación se agenda vía `BackgroundTasks`
(`CorreoActivacionBackgroundAdapter.programar_envio`), que corre **después**
de que el response 201 ya salió. `procesar_correo_activacion_background`
captura cualquier excepción y solo la loguea (`logger.exception`) — no hay
3 reintentos (los intenta 1 vez), y jamás puede devolver 503 al cliente
porque el cliente ya recibió su respuesta. El endpoint `POST /usuarios/`
siempre devuelve 201 "Registro exitoso, envío de correo en proceso",
funcione o no el SMTP. Contrasta con RF-05 (ver abajo), donde el reenvío de
verificación por cambio de correo sí usa `shared/email.py::send_email`
(3 reintentos síncronos reales, 503 genuino tras agotarlos).

---

## RF-02 — Autenticación de usuarios

| Caso | HTTP esperado | HTTP real | Archivo:línea | Veredicto |
|---|---|---|---|---|
| Credenciales inválidas | 401 | 401 `AuthenticationError` | `application/use_cases/sesiones/login_use_case.py:87-91,158-164` | ✅ |
| Cuenta bloqueada por intentos fallidos | 423 | 423 `LockedError` | `application/use_cases/sesiones/login_use_case.py:149-156` | ✅ |
| Cuenta pendiente de activación | 403 | 403 `AuthorizationError` | `application/use_cases/sesiones/sesion_comun.py:77-85` | ✅ |
| Cuenta deshabilitada (INACTIVO/"SUSPENDIDO") | 403 | 403 `AuthorizationError` | `application/use_cases/sesiones/sesion_comun.py:87-94` | ✅* |
| Conflicto de sesión única (login exitoso) | 200 | 200, mismo mensaje | `infrastructure/routers/sesiones_routers.py:118-121` | ✅ |
| Formato de correo inválido | 400 | 400 (`EmailStr` + handler global) | `infrastructure/dto/usuario_dto.py:29` | ✅ |
| Indisponibilidad del servicio de identidad | 503 | 503 (`OperationalError` → handler global) | `shared/error_handlers.py:db_no_disponible_handler` | ✅ |

\* El RF menciona un estado `SUSPENDIDO` que no existe en el modelo de
`Cuenta` (`domain/entities/cuenta.py:37-42` solo define PENDIENTE, ACTIVO,
INACTIVO, BLOQUEADO, ELIMINADO, PENDIENTE_DATOS). Es una inconsistencia del
propio documento de requerimientos, no del código — no se cuenta como gap.

Sin gaps relevantes en este RF.

---

## RF-03 — Gestión de roles

| Caso | HTTP esperado | HTTP real | Archivo:línea | Veredicto |
|---|---|---|---|---|
| Nombre de rol duplicado | 409 | 409 `ConflictError` (mensaje casi verbatim) | `infrastructure/repositories/rol_repository.py:79-91,125-133` | ✅ |
| Rol sin permisos asociados | 400 | 400 `ValidationError` | `infrastructure/repositories/rol_repository.py:92-99` | ✅ |
| Eliminar rol con usuarios vinculados | 422 | 422 `BusinessRuleError` | `application/use_cases/roles/eliminar_rol_use_case.py:61-70` | ✅ |
| **Eliminar** rol protegido (Administrador) | 403 | 403 `AuthorizationError` | `application/use_cases/roles/eliminar_rol_use_case.py:51-58` | ✅ |
| **Modificar** rol protegido | 403 | 403 `AuthorizationError` | `application/use_cases/roles/editar_rol_use_case.py:59-76`, `infrastructure/repositories/rol_repository.py:119-127` | ✅ (corregido) |
| Fallo sincronización sesiones activas (WS) | 500 | No existe canal WS | — | ➖ |
| Integridad de lista de permisos (IDs inexistentes) | 400 | 400 `ValidationError` | `infrastructure/repositories/rol_repository.py:100-104` | ✅ |

**✅ CORREGIDO — editar el rol Administrador da 403.**
`EditarRolUseCase` valida `rol.es_protegido` antes de tocar el repositorio,
igual que `EliminarRolUseCase`, y el repositorio traduce el pgcode `P0004` a
`AuthorizationError`. La descripción del rol protegido sigue siendo editable:
el trigger solo protege el nombre (el "identificador base" del que habla el RF).
Diagnóstico original:
`EliminarRolUseCase` sí valida `rol.es_protegido` en capa de aplicación antes
de tocar el repositorio → 403 limpio. `EditarRolUseCase`, en cambio, **no
valida nada** antes de llamar a `roles_repo.guardar()`; solo el trigger de BD
(pgcode `P0004`) frena el intento, y el repositorio lo traduce a
`BusinessRuleError` (422), no a `AuthorizationError` (403). El RF exige 403
para "modificación **o** eliminación" del rol protegido — el código solo lo
cumple para la mitad del caso.

**➖ Sincronización WS.** No hay infraestructura de WebSocket/Redis para
propagar cambios de permisos a sesiones activas. La restricción real del RF
("los cambios se aplican en la siguiente solicitud") sí se cumple, porque
`require_permission` consulta `modulo1.permisos` en cada request — no hay
caché que invalidar. El caso de error específico (500 por fallo del canal)
no puede darse porque el canal no existe.

---

## RF-04 — Gestión de permisos

| Caso | HTTP esperado | HTTP real | Archivo:línea | Veredicto |
|---|---|---|---|---|
| Rol no encontrado | 404 | 404 `NotFoundError` | `application/use_cases/permisos/asignar_permiso_use_case.py:60-64` | ✅ |
| Recurso no válido/inexistente | 400 | 400 `ValidationError` | `application/use_cases/permisos/asignar_permiso_use_case.py:66-74` | ✅ |
| Permiso duplicado | 409 | 409 `ConflictError` | `application/use_cases/permisos/asignar_permiso_use_case.py:87-93` | ✅ |
| Acción 'E' en recurso no especial / CRUD no soportado | 400 | 400 `ValidationError` para 'E'; el sub-caso CRUD sigue sin validarse | `application/use_cases/permisos/asignar_permiso_use_case.py:88-104` | ⚠️ (corregido a medias, ver nota) |
| Violación de integridad (rol huérfano al retirar) | 422 | 422 `BusinessRuleError` (trigger `P0006`) | `infrastructure/repositories/permiso_repository.py:135-143` | ✅ |
| Usuario sin privilegios administrativos | 403 | 403 (RBAC `require_permission`) | `infrastructure/routers/roles_routers.py` | ✅ |
| Fallo sincronización tiempo real / persistencia transaccional | 500 | No hay canal WS; fallo de persistencia sí cae a 500 genérico | — | ➖ |

**⚠️ CORREGIDO A MEDIAS — la acción 'E' ya se valida; el sub-caso CRUD no es exigible hoy.**
`AsignarPermisoUseCase` rechaza con 400 (`ACCION_NO_PERMITIDA_PARA_RECURSO`) la
acción Ejecutar sobre un recurso que no está marcado `es_proceso_especial` en
`modulo1.recursos`. La otra mitad del caso del RF —"una acción CRUD a un recurso
que no las soporta"— **no se implementó**: el catálogo no declara qué acciones
CRUD admite cada recurso, así que no hay dato contra el cual validar. Requiere
decisión de Análisis antes de inventar ese modelo.

Efecto colateral que QA debe conocer: en DEV hay 18 permisos ya concedidos con
acción 'E' sobre recursos que **no** están marcados como proceso especial
(`usuarios` —el permiso de identificación completa de RF-12—, `plantillas`,
`activos_biologicos`, `historial_telemetria`, `calidad_telemetria`,
`bitacora_auditoria_iot`, `version_modelo`, `auditoria_m04`). Esas filas siguen
funcionando —RBAC solo lee la tabla—, pero **volver a concederlas por API ahora
se rechaza**. O esos recursos se marcan `es_proceso_especial = TRUE` (son de
otros módulos, por eso no se tocaron aquí), o RF-04 y RF-12 tienen que
reconciliarse. Diagnóstico original:
`existe_accion()` solo comprueba que el `id_accion` exista en el catálogo
genérico (C/R/U/D/E). No hay ninguna regla que rechace asignar la acción `E`
(Ejecutar) a un recurso que no sea un "proceso especial", ni que restrinja
qué acciones CRUD admite cada recurso. Cualquier combinación rol+recurso+acción
válida en catálogo se acepta, aunque el RF explícitamente pide rechazar esa
combinación con 400.

**Nota fuera de tabla (no es un caso de flujo alterno de este RF, pero es
llamativo):** al asignar un permiso administrativo a un rol distinto de
Administrador, `permiso_repository.py:112-119` lanza `BusinessRuleError`
(422) con un mensaje que dice literalmente `"HTTP 403: Acción denegada..."` —
el texto del mensaje contradice el código HTTP real de la respuesta.

---

## RF-05 — Edición de datos de usuario

| Caso | HTTP esperado | HTTP real | Archivo:línea | Veredicto |
|---|---|---|---|---|
| Correo ya registrado | 409 | 409 `ConflictError` (mensaje casi verbatim) | `infrastructure/repositories/usuario_repository.py:135-170` | ✅ |
| Conflicto de concurrencia (optimista) | 412 | 412 `PreconditionFailedError` (mensaje verbatim) | `infrastructure/repositories/usuario_repository.py:136-145` | ✅ |
| Escalada de privilegios (usuario no-admin envía `rol_usuario`/`estado_usuario`) | 403 + auditoría | 403 `AuthorizationError` + evento `exitoso=False` | `application/use_cases/perfil/editar_perfil_use_case.py:107-152`, `infrastructure/dto/perfil_dto.py:19-95` | ✅ (corregido) |
| Autogestión administrativa (admin cambia su propio rol) | 400 | 400 `ValidationError` | `application/use_cases/perfil/editar_perfil_use_case.py:138-146` | ✅ |
| Formato de nombres/apellidos inválido | 400 | 400 (regex `NOMBRE`) | `infrastructure/dto/perfil_dto.py:44-51` | ✅ |
| Fallo SMTP en verificación por cambio de correo | 503 | 503 `ServiceUnavailableError` (3 reintentos reales) | `shared/email.py:send_email`, `application/use_cases/perfil/editar_perfil_use_case.py:398-406` | ✅ |
| Usuario no encontrado | 404 | 404 `NotFoundError` | `application/use_cases/perfil/editar_perfil_use_case.py:116-123` | ✅ |
| Formato de teléfono inválido | 400 | 400 (regex `TELEFONO`, mensaje casi idéntico) | `infrastructure/dto/perfil_dto.py:53-59` | ✅ |

**✅ CORREGIDO — la escalada de privilegios da 403 y queda auditada.**
`EditarPerfilDTO` declara los campos críticos (`id_rol`, `rol_usuario`,
`estado_usuario`, `id_estado_cuenta`) únicamente para que la petición llegue al
caso de uso: `EditarPerfilUseCase` registra el evento `ACTUALIZACION_PERFIL` con
`exitoso=False` y detalle `ESCALADA_PRIVILEGIOS`, hace commit de esa bitácora y
recién entonces lanza `AuthorizationError` (403). Los campos nunca se aplican por
esa vía. El DTO administrativo dejó de heredar del propio (ambos cuelgan de
`PerfilBaseDTO`), así que sigue rechazando con 400 cualquier campo fuera de su
alcance. Diagnóstico original:
`EditarPerfilDTO` (usado por `/usuarios/me`) no declara los campos `id_rol`
ni `estado_usuario`, y su `model_config` tiene `extra="forbid"`. Si un
usuario no-administrador los envía igual, Pydantic los rechaza con "Extra
inputs are not permitted" → 400 genérico vía
`request_validation_error_handler`, **antes** de que el use case pueda
ejecutarse — por lo tanto nunca se registra el evento de auditoría que el
RF exige ("Esta acción ha sido reportada al sistema de auditoría"). El RF
pide 403; el sistema da 400 sin trazabilidad del intento.

Nota: `estado_usuario` no es un campo de este endpoint en absoluto — su
gestión vive enteramente en RF-06 (`POST /usuarios/{id}/gestionar`), lo cual
es una separación arquitectónica razonable, pero significa que el caso de
flujo alterno "envía valores para rol_usuario **o** estado_usuario" tal como
está descrito en el RF no se puede reproducir vía este endpoint para la
mitad del caso (`estado_usuario`).

---

## RF-06 — Gestión de cuentas de usuario

| Caso | HTTP esperado | HTTP real | Archivo:línea | Veredicto |
|---|---|---|---|---|
| Transición de estado no permitida | 409 | 409 `ConflictError` | `application/use_cases/cuentas/gestionar_cuenta_use_case.py:141-158` | ✅ (corregido) |
| Eliminar/desactivar al último administrador activo | 400 | 400 `ValidationError` | `application/use_cases/cuentas/gestionar_cuenta_use_case.py:169-180` | ✅ (corregido) |
| Usuario no encontrado | 404 | 404 `NotFoundError` | `application/use_cases/cuentas/gestionar_cuenta_use_case.py:104-116` | ✅ |
| Acceso no autorizado | 403 | 403 (RBAC `require_permission(4,3)`) | `infrastructure/routers/usuarios_routers.py` | ✅ |
| Acción inconsistente con estado actual | 400 | 400 `ValidationError` (`ESTADO_SIN_CAMBIO`) | `application/use_cases/cuentas/gestionar_cuenta_use_case.py:135-139` | ✅ |
| Fallo en invalidación de sesiones (blacklist) | 500 | 500 (excepción no capturada → handler genérico) | `application/use_cases/cuentas/gestionar_cuenta_use_case.py:176-178` | ✅ |
| Ausencia de motivo en acción crítica | 400 | 400 `ValidationError` (mensaje casi verbatim) | `application/use_cases/cuentas/gestionar_cuenta_use_case.py:120-128` | ✅ |

**✅ CORREGIDO — los dos códigos HTTP centrales de este RF ya coinciden.**
La transición inválida (incluido "ELIMINADO es irreversible") lanza
`ConflictError` → 409 y el intento de dejar el sistema sin administradores
activos lanza `ValidationError` → 400. Diagnóstico original:
Tanto la transición de estado inválida (incluido el caso "ELIMINADO es
irreversible") como el intento de dejar el sistema sin administradores
activos usan `BusinessRuleError` (422) en el código. El RF pide 409 para el
primer caso y 400 para el segundo. Ninguno de los dos coincide — son de los
endpoints más probados de todo el módulo (`POST /usuarios/{id}/gestionar`),
así que cualquier suite de pruebas que valide literalmente el código HTTP
fallará en ambos.

---

## RF-07 — Cambio de contraseña

| Caso | HTTP esperado | HTTP real | Archivo:línea | Veredicto |
|---|---|---|---|---|
| Contraseña actual incorrecta | 401 | 401 `AuthenticationError` (mensaje verbatim) | `application/use_cases/contrasena/cambiar_contrasena_use_case.py:151-158` | ✅ |
| Nueva contraseña no cumple políticas | 400 | 400 (regex de política) | `infrastructure/dto/contrasena_dto.py:26-31` | ✅ |
| Confirmación no coincide | 400 | 400 (mensaje verbatim) | `infrastructure/dto/contrasena_dto.py:33-38` | ✅ |
| Reutilización de contraseña actual | 409 | 409 `ConflictError` | `application/use_cases/contrasena/cambiar_contrasena_use_case.py:164-171` | ✅ |
| Bloqueo por exceso de intentos (30 min) | 423 | 423 `LockedError` (mismos minutos) | `application/use_cases/contrasena/cambiar_contrasena_use_case.py:142-149` | ✅ |
| ID de sesión no coincide con el token (`id_usuario` ajeno) | 403 | 403 `AuthorizationError` (mensaje casi verbatim) | `application/use_cases/contrasena/cambiar_contrasena_use_case.py:80-87` | ✅ |
| Fallo en invalidación masiva de sesiones | 500 | 500 `InfrastructureError` (mensaje verbatim) | `application/use_cases/contrasena/cambiar_contrasena_use_case.py:204-239` | ✅ |
| Fallo en el proceso de hashing | 500 | 500 `InfrastructureError` | `application/use_cases/contrasena/cambiar_contrasena_use_case.py:174-185` | ✅ |

Sin gaps. Es la implementación más fiel al RF de todo el módulo.

---

## RF-08 / RF-09 — Recuperación y restablecimiento de contraseña

Sin ficha detallada en el documento fuente (el Excel original salta de RF-07
a RF-10; ver nota de conversión). Se documenta únicamente lo que el código
hace hoy, sin comparar contra un RF:

| Caso (según código) | HTTP real | Archivo:línea |
|---|---|---|
| Token de recuperación inexistente | 401 `AuthenticationError` | `application/use_cases/contrasena/restablecer_contrasena_use_case.py:87-95` |
| Token ya utilizado en un restablecimiento previo | 409 `ConflictError` | `application/use_cases/contrasena/restablecer_contrasena_use_case.py:98-106` |
| Bloqueo por intentos (cuenta, o por IP tras 5 tokens inválidos / 30 min) | 423 `LockedError` | `application/use_cases/contrasena/restablecer_contrasena_use_case.py:108-121,178-210` |
| Token expirado (15 minutos desde generación) | 410 `GoneError` | `application/use_cases/contrasena/restablecer_contrasena_use_case.py:123-136` |
| Nueva contraseña igual a la anterior | 409 `ConflictError` | `application/use_cases/contrasena/restablecer_contrasena_use_case.py:142-146` |
| Límite de solicitudes de recuperación por correo/IP | 429 `TooManyRequestsError` | `application/use_cases/contrasena/solicitar_recuperacion_use_case.py:112` |

Cobertura completa y consistente con el patrón del resto del módulo — buen
candidato para que Análisis redacte la ficha formal usando esto como base.

---

## RF-10 — Historial de acceso y auditoría

| Caso | HTTP esperado | HTTP real | Archivo:línea | Veredicto |
|---|---|---|---|---|
| Fallo de integridad del registro (hash SHA-256 no coincide) | 500 | 500 `InfrastructureError` (mensaje casi verbatim) | `application/use_cases/auditoria/consultar_auditoria_use_case.py:132-142` | ✅ |
| Fallo de persistencia obligatoria del evento (rollback) | 500 | 500 (patrón commit/rollback consistente en todo el módulo) | — | ✅ |
| Acceso denegado a la consulta | 403 | 403 `AuthorizationError`, **con auditoría del intento denegado** | `infrastructure/routers/auditoria_routers.py:66-104` | ✅ |
| Intento de modificación/eliminación (inmutabilidad) | 405 | 405 `MethodNotAllowedError`, ruta dedicada | `infrastructure/routers/auditoria_routers.py:446-464` | ✅ |
| Filtro de búsqueda inválido (rango de fechas, usuario inexistente) | 400 | 400 `ValidationError` (mensaje casi verbatim) | `application/use_cases/auditoria/consultar_auditoria_use_case.py:88-97` | ✅ |
| Exceso de resultados (saturación, >10.000) | 206 | 206 (`response.status_code = 206`) | `infrastructure/routers/auditoria_routers.py:168` | ✅ |
| Fallo en archivado automático | Notificación interna (no HTTP) | Notificación interna | `application/use_cases/auditoria/notificar_fallo_archivado_use_case.py` | ➖ |

Sin gaps. Segunda implementación más fiel al RF del módulo, incluyendo
detalles finos como el 206 explícito y la auditoría del propio 403.

---

## RF-11 — Visualización de usuarios del sistema

| Caso | HTTP esperado | HTTP real | Archivo:línea | Veredicto |
|---|---|---|---|---|
| Búsqueda sin coincidencias | 200 | 200 con mensaje informativo | `application/use_cases/usuarios/listar_usuarios_use_case.py:82-88` | ✅ |
| Parámetros de paginación fuera de rango | 400 | 400 (`Query(ge=1)`, `Query(le=50)`) | `infrastructure/routers/usuarios_routers.py:117-118` | ✅ |
| Fallo del canal de actualización en tiempo real (WS/SSE) | 503 (en el canal) | No existe canal WS/SSE | — | ➖ |
| Conflicto por eliminación lógica concurrente | 410 | 410 `GoneError` al editar un usuario ELIMINADO | `application/use_cases/perfil/editar_perfil_use_case.py:264-279` | ✅ (corregido) |
| Parámetros de filtro con tipo inválido | 400 | 400 (coerción de tipos de FastAPI) | `infrastructure/routers/usuarios_routers.py:113-131` | ✅ |
| Exposición de datos sensibles en la respuesta | 500 (si se detecta) | No aplica: `response_model` tipado impide el campo | `infrastructure/schema/gestion_schema.py` | ➖ |
| Acceso denegado | 403 | 403 (RBAC `require_permission(1,2)`) | `infrastructure/routers/usuarios_routers.py:112` | ✅ |

**✅ CORREGIDO — el 410 "registro eliminado por otro admin mientras se veía" ya existe.**
`EditarPerfilUseCase` responde `GoneError` (410) cuando la cuenta del usuario
objetivo está en ELIMINADO. Se eligió ese punto porque es donde la validación de
concurrencia ya actúa (`PATCH /usuarios/{id}` viaja con `version`), que es
exactamente lo que el RF describe. `POST /usuarios/{id}/gestionar` conserva su
409 de RF-06: ahí la petición es un cambio de estado deliberado, no una vista
desactualizada. Diagnóstico original:
Ningún endpoint del módulo devuelve 410 al interactuar con un usuario que
otro administrador acaba de marcar `ELIMINADO`. El estado ELIMINADO se
maneja como 422 (`TRANSICION_INVALIDA`, ver RF-06) o simplemente no se
distingue de "no encontrado" en otros flujos — pero nunca como 410 Gone.
Es un caso de UI colaborativa específico que el RF pide explícitamente y
el backend no contempla.

**➖ WS/SSE.** El propio RF ofrece "refresco manual" como alternativa válida
al tiempo real; sin canal WS, esa alternativa es la única disponible, lo
cual satisface la letra del RF aunque no la mención específica de WebSockets.

---

## RF-12 — Visualización de detalles del usuario

| Caso | HTTP esperado | HTTP real | Archivo:línea | Veredicto |
|---|---|---|---|---|
| Usuario inexistente | 404 | 404 `NotFoundError` (mensaje verbatim) | `application/use_cases/usuarios/consultar_detalle_usuario_use_case.py:80-84` | ✅ |
| Acceso denegado (sin privilegios) | 403 | 403 (RBAC `require_permission(1,2)`) | `infrastructure/routers/usuarios_routers.py:274` | ✅ |
| Fallo en el registro de auditoría obligatoria | 500 | 500 `InfrastructureError` (mensaje verbatim) | `application/use_cases/usuarios/consultar_detalle_usuario_use_case.py:97-118` | ✅ |
| Patrón de consulta inusual (scraping) | 429 | 429 `TooManyRequestsError` (mensaje verbatim, umbral 20/min) | `application/use_cases/usuarios/consultar_detalle_usuario_use_case.py:169-213` | ✅ |
| Fallo al verificar permiso de identificación completa | Enmascara por defecto (preventivo) | Enmascara por defecto (`try/except` → `False`) | `application/use_cases/usuarios/consultar_detalle_usuario_use_case.py:159-167` | ✅ |

Sin gaps. Implementación calcada del RF, incluyendo los tres controles de
protección de datos personales adicionales que describe (auditoría
bloqueante, rate limiting, fail-safe de enmascaramiento).

---

## RF-13 — Visualización de perfil del usuario

| Caso | HTTP esperado | HTTP real | Archivo:línea | Veredicto |
|---|---|---|---|---|
| Token de sesión inválido/malformado | 401 | 401 `AuthenticationError` | `infrastructure/dependencies.py:59-63` | ✅ |
| Sesión expirada (TTL, incluye inactividad 30 min) | 401 | 401 `AuthenticationError` | `infrastructure/dependencies.py:117-124` | ✅ |
| Usuario inexistente en persistencia | 404 | 404 `NotFoundError` (mensaje verbatim) | `application/use_cases/perfil/consultar_perfil_use_case.py:52-56` | ✅ |
| Bypass por parámetros externos (`id_usuario` en URL/body) | 400 si el endpoint no acepta el parámetro | El endpoint no tiene ningún parámetro — estructuralmente imposible enviarlo | `infrastructure/routers/usuarios_routers.py` (`GET /usuarios/me`) | ✅ |
| Fallo en el servicio de enmascaramiento | Ocultar campo (preventivo) | No puede fallar: longitudes cortas ya se manejan sin excepción | `application/use_cases/perfil/consultar_perfil_use_case.py:86-101` | ✅ |
| Fallo de conexión con la base de datos | 500 | 503 (`OperationalError` → handler global) | `shared/error_handlers.py:db_no_disponible_handler` | ⚠️ |

**⚠️ DB caída da 503, el RF pide 500.**
Es una divergencia sistémica (aplica a todo el backend, no solo a este
endpoint): el proyecto decidió tratar la caída de conectividad de base de
datos como 503 "Service Unavailable" en vez de 500 "Internal Server Error",
lo cual es semánticamente más correcto, pero no coincide con la letra
literal de este RF. Severidad baja — no es un bug, es una decisión de
diseño consistente en todo el sistema que el RF no anticipó.

---

## RF-14 — Notificar a los usuarios

| Caso | Comportamiento esperado | Comportamiento real | Archivo:línea | Veredicto |
|---|---|---|---|---|
| Descarte por política anti-spam (5 min por tipo+usuario+canal) | No se encola ni se envía | No se encola ni se envía | `shared/notificacion_service.py:222-228` (`VENTANA_ANTI_SPAM_MINUTOS = 5`) | ✅ |
| Restricción por usuario BLOQUEADO (solo eventos de seguridad) | Se aborta silenciosamente si no es evento de seguridad | Igual | `shared/notificacion_service.py:159-163` | ✅ |
| Evento de seguridad (LOGIN_FALLIDO) en usuario INACTIVO | Ignorar la notificación por completo (privacidad) | No se envía | `shared/notificacion_service.py:160-176` (`TIPOS_EVENTO_PERMITIDOS_INACTIVO = {10}`) | ✅ (corregido) |
| Fallo en el proveedor de correo (SMTP) | Estado FAILED, **sin reintentos automáticos** | Estado FAILED, pero `send_email()` ya reintentó 3 veces internamente antes de fallar | `shared/email.py:_MAX_RETRIES = 3`, `shared/notificacion_service.py:262-273` | ⚠️ |
| Usuario sin correo válido | Estado FAILED | Estado FAILED (sin intento de envío si `correo` es `None`) | `shared/notificacion_service.py:263-269` | ✅ |
| Fallo en el servicio de notificaciones internas (BD no disponible) | Estado FAILED, la notificación se pierde | Igual — el `INSERT` falla, se hace rollback, no queda fila | `shared/notificacion_service.py:255-260` | ✅ |

**✅ CORREGIDO — las cuentas INACTIVAS ya no reciben avisos de intentos de acceso.**
`NotificacionService` separa las dos reglas: BLOQUEADO conserva los dos eventos
de seguridad que el propio RF le permite (intento fallido y bloqueo), mientras
que INACTIVO solo admite `CAMBIO_ESTADO_CUENTA`
(`TIPOS_EVENTO_PERMITIDOS_INACTIVO`). `LOGIN_FALLIDO` deja de salir, que es el
caso de privacidad del RF; el aviso de "tu cuenta fue inactivada" sigue llegando
a su titular, que es lo que exigía INC-M01-18-092 y que el propio RF-14 no
prohíbe (va dirigido al dueño de la cuenta, no a quien intenta entrar).
Diagnóstico original:
El RF-14 dedica un caso completo a esto: *"Evento de seguridad en Usuario
Inactivo... el sistema ignora la petición de notificación por completo"*
(razón: no confirmar la existencia de la cuenta). El código, en cambio,
trata INACTIVO y BLOQUEADO de forma idéntica
(`if id_estado in (ESTADO_INACTIVO, ESTADO_BLOQUEADO) and tipo_evento not in
TIPOS_EVENTO_SEGURIDAD: return None`), dejando pasar `LOGIN_FALLIDO` (tipo 4)
y `CAMBIO_ESTADO` (tipo 10) también para cuentas INACTIVAS. El comentario en
el código explica que esto es deliberado para poder notificar "tu cuenta
acaba de pasar a INACTIVO" — una necesidad real, pero que choca de frente
con la regla de privacidad que el RF pide para el caso `LOGIN_FALLIDO`
específicamente.

**⚠️ Reintento de SMTP contradice la restricción "sin reintentos automáticos".**
La restricción general de RF-14 es explícita: *"No se deben generar
reintentos automáticos en caso de fallo (evita duplicidad y mantiene
simplicidad del sistema)"*. `shared/email.py::send_email` —compartida por
todo el sistema, no exclusiva de notificaciones— reintenta 3 veces con 5s de
espera antes de darse por vencida. El resultado final (FAILED, sin reintento
a nivel de notificación) es correcto, pero técnicamente sí hay reintentos
automáticos ocurriendo por debajo. Severidad baja: no genera duplicidad
observable (todos los intentos son la misma llamada a `send_email`, no
notificaciones separadas).

---

## Top 5 — más probables de romper una primera revisión de QA (todos corregidos)

1. ✅ **RF-06**: transición de estado inválida daba 422 en vez de 409, y el
   bloqueo del último administrador daba 422 en vez de 400 — dos de los
   endpoints más probados del módulo. Ahora 409 y 400.
2. ✅ **RF-01**: el caso "SMTP falla 3 veces → 503" era irreproducible; el
   registro devolvía 201 pasara lo que pasara con el correo. Ahora el envío
   ocurre dentro del request y el fallo se traduce a 503.
3. ✅ **RF-05**: enviar `id_rol`/`estado_usuario` como usuario no-admin daba 400
   genérico de Pydantic en vez de 403, sin el registro de auditoría que el RF
   exige. Ahora 403 con el intento auditado.
4. ✅ **RF-03**: editar (no eliminar) el rol Administrador daba 422 en vez de 403
   — inconsistente con el propio endpoint de eliminación. Ahora 403 en ambos.
5. ✅ **RF-14**: las notificaciones de `LOGIN_FALLIDO` llegaban a cuentas
   INACTIVAS, violando la regla de privacidad del RF. Ahora se descartan.

## Qué queda abierto en M01

- **⚠️ RF-04 (mitad del caso)**: sin catálogo de acciones CRUD por recurso no hay
  cómo validar "acción CRUD que el recurso no soporta". Decisión de Análisis.
- **⚠️ RF-01 (correo/ID duplicado)**: el índice único cubre toda la tabla y el RF
  solo quiere bloquear cuentas activas o pendientes. Cambiarlo implica índice
  parcial y habilitar la reutilización del correo de una cuenta ELIMINADA:
  migración Alembic + autorización del DBA + decisión de negocio.
- **⚠️ RF-13 (503 vs 500)**: decisión de diseño sistémica de todo el backend
  (`db_no_disponible_handler`), no un defecto de este módulo.
- **⚠️ RF-14 (reintentos SMTP)**: viven en `shared/email.py`, compartida por los
  cinco módulos; quitarlos por RF-14 rompería RF-01/RF-05/RF-08, que dependen de
  los 3 intentos para su propio 503.
