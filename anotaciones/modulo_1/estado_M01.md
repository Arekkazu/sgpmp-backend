# Estado de cumplimiento — Módulo 1 (Identity & Access)

**Fecha de la auditoría:** 2026-08-05
**Alcance:** RF-01 a RF-14, contra el código real de `src/identity_access/` y el estado real de la base de datos (schema `modulo1`), verificado con exploración de código y consultas directas vía MCP de Postgres (catálogos, triggers, permisos sembrados).

**Nota metodológica importante:** esta auditoría encontró que partes de `CLAUDE.md` (el documento de arquitectura del proyecto) están desactualizadas respecto al código actual — en particular sobre gestión de roles/permisos y sobre `audit_sdk`. Este documento describe lo que el código y la base de datos hacen **hoy**, no lo que `CLAUDE.md` supone. Cada afirmación está respaldada por archivo:línea o por una consulta directa a la base de datos.

Los porcentajes son una estimación orientativa de cuánto del RF está cubierto, no una medición exacta — sirven para priorizar, no como cifra oficial.

---

## Resumen ejecutivo

| RF | Título | Veredicto | Cobertura aprox. |
|----|--------|-----------|-------------------|
| RF-01 | Registro de usuarios | ⚠️ Cumple parcialmente | ~80% |
| RF-02 | Autenticación de usuarios | ⚠️ Cumple parcialmente | ~85% |
| RF-03 | Gestión de roles | ✅ Cumple | ~95% |
| RF-04 | Gestión de permisos | ✅ Cumple (con salvedad) | ~90% |
| RF-05 | Edición de datos de usuario | ⚠️ Cumple parcialmente | ~85% |
| RF-06 | Gestión de cuentas de usuario | ⚠️ Cumple parcialmente | ~75% |
| RF-07 | Cambio de contraseña | ✅ Cumple | ~100% |
| RF-08 | Recuperación de contraseña | ⚠️ Cumple parcialmente | ~70% |
| RF-09 | Restablecimiento de contraseña | ⚠️ Cumple parcialmente | ~75% |
| RF-10 | Historial de acceso y auditoría | ✅ Cumple | ~100% |
| RF-11 | Visualización de usuarios (listado) | ✅ Cumple | ~95% |
| RF-12 | Visualización de detalle de usuario | ⚠️ Cumple parcialmente | ~90% |
| RF-13 | Visualización de perfil propio | ✅ Cumple | ~100% |
| RF-14 | Notificar a los usuarios | ✅ Cumple | ~100% |

**Lectura rápida:** el módulo está bastante más avanzado de lo que sugeriría el estado "Pendiente" marcado en cada ficha de requerimiento — la mayoría de los flujos centrales (registro, login, roles, permisos, contraseñas, auditoría, notificaciones) tienen implementación real y no trivial, con triggers de base de datos como segunda capa de defensa. Los gaps que aparecen no son "no se hizo nada", sino puntos concretos y acotados. Los dos más serios que encontró esta auditoría — el endpoint sin protección de RF-11 y el sobre-permisionamiento RBAC de `leer_usuario` (RF-11/RF-12) — ya fueron corregidos (PR #13 y issue #17 respectivamente, ver esas secciones). El almacenamiento de tokens en texto plano (RF-08/RF-09) también fue corregido — ver `rf01_rf08_rf09_hash_tokens.md`.

---

## RF-01 — Registro de usuarios

**Veredicto: ⚠️ Cumple parcialmente (~80%)** — el flujo completo de registro y activación funciona; faltan CAPTCHA, confirmación de contraseña y algunas validaciones de formato.

### Qué SÍ cumple

- El endpoint `POST /usuarios/` (`usuarios_routers.py:114-121`) recibe todos los campos que pide el RF (tipo y número de identificación, nombres, apellidos, fecha de nacimiento, género, correo, contraseña, teléfono, dirección) y ejecuta `CrearUsuarioUseCase`.
- **Unicidad de correo y de número de identificación**: hay constraints únicos en la base de datos, y si alguno ya existe, el sistema responde con `409 Conflict` y un mensaje específico (`usuario_repository.py:112-115`).
- **Política de contraseña** (mínimo 8 caracteres, mayúscula, número, carácter especial): implementada con una expresión regular tanto en el dominio (`domain/value_objects/contrasena.py`) como en el DTO de entrada.
- **Hash bcrypt**: la contraseña nunca se guarda en texto plano, se cifra con bcrypt antes de persistir (`contrasena.py:62`).
- **Estado inicial "Pendiente de activación"** y **rol por defecto (Productor) asignado automáticamente**: el usuario no puede elegir su rol porque el campo directamente no existe en el formulario de registro — es estructuralmente imposible enviarlo.
- **Token de activación con validez de 24 horas**, generado de forma aleatoria y segura (`secrets.token_urlsafe`).
- **Envío del correo de activación** después de confirmar la transacción en base de datos (como pide el patrón del proyecto), con reintento automático hasta 3 veces si el SMTP falla.
- **Endpoint de activación por token**, que distingue correctamente token inexistente (400), token expirado (410, con mensaje que incluye la fecha) y cuenta ya activada (422).
- **Reenvío de token de activación** si el original expiró.
- **Validación de mayoría de edad (18 años)**: si el usuario declara ser menor, el registro se rechaza con `403 Forbidden`, tal como pide el RF.
- El formato del correo se valida tanto en el dominio como con un `CHECK` en la base de datos.

### Qué NO cumple / gaps

- **No hay CAPTCHA en absoluto.** El RF lo pide explícitamente como requisito no funcional de seguridad ("Implementar CAPTCHA — Google reCAPTCHA v2 o v3") y también como flujo alterno con `HTTP 400`. Hoy no existe ninguna referencia a CAPTCHA/reCAPTCHA en todo el código ni en las variables de entorno.
- **Falta el campo `confirmar_contraseña`** en el formulario de registro. El RF pide que el usuario escriba la contraseña dos veces para evitar errores de tipeo, pero el DTO de registro solo tiene el campo de contraseña (a diferencia de cambio y restablecimiento de contraseña, que sí piden confirmación).
- **`numero_identificacion` no valida que sea solo numérico.** El RF especifica que la identificación debe ser numérica; hoy el campo acepta cualquier texto, tanto en el formulario como en la base de datos.
- **El reintento de envío de correo es síncrono, no asíncrono.** El RF pide que, si el SMTP falla, el sistema reintente "de forma asíncrona" para no bloquear al usuario. En la implementación actual, el reintento (hasta 3 veces, con pausas de 5 segundos entre intentos) ocurre dentro del mismo request HTTP — si el correo falla, el usuario que se está registrando puede quedar esperando hasta ~15 segundos antes de recibir respuesta.
- **El registro y la activación de cuenta no generan evento de auditoría.** El RF-10 exige que "registro de nuevo usuario" sea un evento auditable, pero ni `CrearUsuarioUseCase` ni `ActivarCuentaUseCase` escriben en la tabla de eventos — son de los pocos flujos del módulo que no dejan rastro.

---

## RF-02 — Autenticación de usuarios

**Veredicto: ⚠️ Cumple parcialmente (~85%)** — el flujo de login es robusto y con buena cobertura de seguridad; el detalle más visible es que el token dura 24h en vez de las 8h que pide el RF.

### Qué SÍ cumple

- Login con correo y contraseña, genera un JWT firmado (HS256).
- **Timeout de inactividad de 30 minutos**: si un usuario no hace ninguna petición en 30 minutos, su sesión se cierra automáticamente en el siguiente intento y debe volver a autenticarse. Esto está realmente implementado (contrario a lo que suele ser un gap típico en proyectos de este tipo).
- **Revocación activa de tokens (blacklist)**: existe una tabla de tokens donde se marca cuándo un token fue "usado"/invalidado, y se verifica en cada request.
- **Sesión única por usuario**: al iniciar sesión en un dispositivo nuevo, la sesión anterior se invalida automáticamente (reforzado con un índice único en base de datos que impide dos sesiones activas simultáneas para la misma cuenta).
- **Bloqueo tras 5 intentos fallidos consecutivos, por 15 minutos**, con desbloqueo automático transcurrido ese tiempo, y respuesta `423 Locked` como pide el RF.
- **Validación de estado de cuenta antes de dejar entrar**: cuentas pendientes de activación, inactivas o eliminadas no pueden iniciar sesión, y cada caso responde con el código HTTP correcto (`401`, `403`).
- **Registro de auditoría** de login exitoso, login fallido y cierre de sesión, incluyendo IP y navegador.
- Logout explícito que invalida la sesión y el token de inmediato.

### Qué NO cumple / gaps

- **El token JWT dura 24 horas por defecto, no 8 horas como pide el RF.** La duración se lee de una variable de entorno (`JWT_EXPIRE_HOURS`) que además **no está declarada en `.env.example`**, así que en cualquier ambiente nuevo el sistema corre silenciosamente con el default de 24h salvo que alguien la agregue a mano.
- **No existe el estado `SUSPENDIDO`** que menciona el RF-02 como uno de los estados que impiden el login. El catálogo real de estados es: Pendiente, Activo, Inactivo, Bloqueado, Eliminado — se usa `Eliminado` donde el RF esperaría `Suspendido`. En la práctica el efecto de seguridad es el mismo (la cuenta no puede loguearse), pero el nombre del estado no coincide con la ficha.
- **No hay refresh tokens.** Hoy existe un único JWT de acceso de vida larga; no hay un token de refresco separado y de menor duración. Ya existe una propuesta documentada (`anotaciones/modulo_1/plan_access_refresh_tokens.md`) para resolver esto, pero está marcada explícitamente como "propuesta, no implementada".

---

## RF-03 — Gestión de roles

**Veredicto: ✅ Cumple (~95%)** — implementación completa y más robusta de lo esperado.

> **Corrección a `CLAUDE.md`:** el documento de arquitectura sugiere que los roles son un catálogo fijo (Administrador/Productor/Veterinario/Ingeniero/Contador, IDs 1-5) sin gestión dinámica. Esto **ya no es así**: existe un CRUD completo y en uso real — la tabla de roles en base de datos ya tiene 8 filas, 3 de ellas (Supervisor, Gestor de Granja, Revisor Fiscal) claramente creadas después del catálogo semilla original, lo que confirma que el endpoint de creación se usa en producción/desarrollo.

### Qué SÍ cumple

- CRUD completo: crear, listar, ver detalle, editar y eliminar roles, todos con control de acceso RBAC en el router.
- Crear un rol usa un stored procedure en base de datos que crea el rol y sus permisos iniciales de forma atómica.
- **Nombre de rol único**, validado tanto en la aplicación como con un constraint de base de datos.
- **Todo rol debe tener al menos un permiso**: validado en tres capas distintas (al crear, al crear vía el stored procedure, y al intentar retirar el último permiso de un rol que ya existe — este último bloqueado por un trigger de base de datos).
- **El rol Administrador está protegido**: no se puede eliminar ni cambiarle el nombre, reforzado tanto en la aplicación como con triggers de base de datos (doble capa de seguridad).
- **No se puede eliminar un rol que tiene usuarios asignados**, también con doble capa (aplicación + trigger).
- Cada operación (crear, editar, eliminar rol) queda registrada en el historial de auditoría.

### Qué NO cumple / gaps

- **No hay control de concurrencia optimista al editar un rol.** Si dos administradores editan el mismo rol al mismo tiempo, no hay ningún aviso — el último que guarda gana, sin el mecanismo de "412 Precondition Failed" que sí existe para editar usuarios.
- **No hay invalidación explícita de sesión cuando se modifican los permisos de un rol.** En la práctica esto casi no importa porque cada request vuelve a consultar los permisos en vivo (ver RF-04), pero formalmente no hay un mecanismo de "forzar relogin" ante cambios de rol.

---

## RF-04 — Gestión de permisos

**Veredicto: ✅ Cumple, con una salvedad importante (~90%)**

> **Corrección a `CLAUDE.md`:** al igual que con los roles, sí existe una API administrativa completa para asignar y retirar permisos — no es solo edición manual en base de datos como sugiere el documento de arquitectura.

### Qué SÍ cumple

- Endpoints para asignar y retirar permisos de un rol (`rol + recurso + acción`), y para consultar el catálogo de recursos y acciones disponibles.
- **No se permiten permisos duplicados** (misma combinación rol+recurso+acción), validado en aplicación y en base de datos.
- Se valida que el recurso y la acción existan antes de crear el permiso.
- Los permisos `admin_*` están protegidos por triggers: solo pueden asignarse al rol Administrador y no pueden eliminarse.
- **Validación en cada request sin caché**: `require_permission` (el mecanismo central de RBAC, en `src/shared/rbac.py`) consulta la tabla de permisos en cada petición HTTP, sin ningún tipo de caché — así que un cambio en los permisos de un rol se refleja de inmediato en el siguiente request de cualquier usuario con ese rol, tal como pide el RF ("sin requerir cierre de sesión").

### Qué NO cumple / gaps

- **Salvedad importante — reasignar el rol de un usuario específico SÍ requiere relogin, aunque cambiar los permisos de un rol NO.** El rol del usuario (`id_rol`) queda grabado dentro del JWT en el momento del login y nunca se vuelve a consultar contra la base de datos en peticiones posteriores. Esto significa:
  - Si un admin agrega o quita un permiso a un rol → se aplica de inmediato a todos los usuarios de ese rol, sin relogin. **Esto sí cumple el RF.**
  - Si un admin cambia el rol *de un usuario puntual* (por ejemplo, de Productor a Veterinario) → ese usuario sigue operando con los permisos de su rol anterior hasta que su token expire (hasta 24h, ver RF-02) o cierre sesión manualmente. **Esto no cumple la parte del RF que exige aplicar los cambios "sin requerir cierre de sesión" para este caso específico.**

---

## RF-05 — Edición de datos de usuario

**Veredicto: ⚠️ Cumple parcialmente (~85%)** — funcionalmente muy completo, con un problema de arquitectura (no de negocio) en cómo se implementa el control de acceso.

### Qué SÍ cumple

- Un mismo endpoint (`PATCH /usuarios/{id}`) atiende tanto la autoedición del usuario como la edición por parte de un administrador.
- **Restricción de campos críticos**: si un usuario sin privilegios de administrador intenta enviar `estado_usuario` o `rol_usuario`, la operación se rechaza con `403`.
- **Reverificación de correo**: si se cambia el correo electrónico, la cuenta pasa automáticamente a estado "Pendiente" y se genera y envía un nuevo token de verificación — exactamente como pide el RF. Esto además está reforzado por un trigger de base de datos independiente.
- **Concurrencia optimista implementada**: si dos personas editan al mismo usuario al mismo tiempo, la segunda edición es rechazada con `412 Precondition Failed`. La implementación usa una columna `version` (número entero que se incrementa automáticamente en cada cambio) en vez del patrón de `fecha_actualizacion` documentado en `CLAUDE.md`, pero cumple exactamente la misma función.
- **Un administrador no puede cambiarse a sí mismo el rol ni el estado** (evita que el sistema se quede sin administradores por accidente).
- Validación de formato de nombres/apellidos (solo letras, espacios y caracteres del español como ñ y tildes).
- Invalidación de sesión cuando corresponde (cambio de estado a uno que la invalida, o cambio de correo).
- Auditoría de cada edición, con los valores anteriores y nuevos.
- El campo `dirección`, que el RF no lista como editable pero que el diagrama de análisis sí incluye, está implementado como editable — esto ya estaba documentado como pendiente de confirmación en `CLAUDE.md` y se mantiene así.

### Qué NO cumple / gaps

- **El router de este endpoint no tiene control de acceso RBAC** (`require_permission`). Toda la lógica de "¿quién puede editar qué?" vive dentro del use case, que además hardcodea el número de rol de Administrador directamente en el código — esto va en contra de una regla explícita de `CLAUDE.md`: *"Autorización por RBAC en el router, nunca con `id_rol` quemado en el use case"*. Funcionalmente el resultado es correcto hoy, pero no sigue el patrón de seguridad del resto del proyecto, lo que lo hace más frágil ante futuros cambios.
- El endpoint es un `PATCH`, pero el DTO exige siempre `nombre`, `apellidos` y `version` — no es una edición parcial real de esos tres campos específicos.

---

## RF-06 — Gestión de cuentas de usuario

**Veredicto: ⚠️ Cumple parcialmente (~75%)** — el flujo "oficial" es muy completo, pero existe una segunda vía menos segura para lograr lo mismo.

### Qué SÍ cumple

- Endpoint dedicado (`POST /usuarios/{id}/gestionar`) para que un administrador active, desactive, bloquee o elimine (lógicamente) una cuenta.
- **Eliminación siempre lógica, nunca física**: no existe ningún `DELETE` físico de usuarios en todo el módulo.
- **Validación de transiciones de estado permitidas**, con doble capa (aplicación + trigger de base de datos) — por ejemplo, no se puede "revivir" una cuenta eliminada.
- **Protección del último administrador activo**: si la acción dejaría al sistema sin ningún administrador activo, se rechaza.
- **Campo `motivo_accion` obligatorio** para desactivar o eliminar una cuenta.
- **Invalidación de todas las sesiones activas** al cambiar a un estado que las invalida (Inactivo, Bloqueado, Eliminado), reforzado también por un trigger de base de datos.
- Auditoría doble: en una tabla dedicada a gestión de cuentas y también en el log genérico de eventos.

### Qué NO cumple / gaps

- **El use case hardcodea el rol de Administrador en el código** (`ROL_ADMINISTRADOR = 1`) para validar quién puede ejecutar la acción, en vez de dejar esa validación exclusivamente al RBAC del router — es redundante con el `require_permission` que el router ya tiene, y contradice la misma regla de `CLAUDE.md` mencionada en RF-05.
- **Existe una segunda vía para cambiar el estado de una cuenta** (el mismo endpoint de edición de perfil, `PATCH /usuarios/{id}`, del RF-05) que:
  - No tiene control de acceso RBAC en el router.
  - No exige el campo `motivo_accion`.
  - No aplica la protección de "último administrador activo" a nivel de aplicación (solo evita que un admin se desactive a sí mismo).
  - No queda registrada en la tabla dedicada de gestión de cuentas, solo en el log genérico — dificultando reconstruir el historial completo de cambios de estado de una cuenta desde un solo lugar.
  - Esto significa que, en la práctica, hay dos caminos con distinto nivel de rigor para lograr el mismo resultado de negocio.
- Hay un detalle técnico de manejo de errores: si un trigger de base de datos rechaza una operación (por ejemplo, intentar tocar el estado de un administrador protegido), ese error no siempre se traduce a un mensaje de error limpio del sistema — en algunos casos podría llegar al cliente como un error genérico `500` en vez de un `403`/`422` con mensaje claro.

---

## RF-07 — Cambio de contraseña (usuario autenticado)

**Veredicto: ✅ Cumple (~100%)** — no se detectaron carencias relevantes frente al RF.

### Qué SÍ cumple

- Requiere contraseña actual + nueva + confirmación, y valida que las tres condiciones se cumplan.
- Solo el propio usuario puede cambiar su contraseña (no se puede cambiar la de un tercero por esta vía).
- **No se puede reutilizar la contraseña actual** (validado por un trigger de base de datos).
- Invalida todas las sesiones activas tras el cambio, obligando a re-loguearse en todos los dispositivos.
- Bloqueo tras 5 intentos fallidos, por 30 minutos, con respuesta `423 Locked`.
- Auditoría del evento y notificación al usuario tras el cambio.

### Qué NO cumple / gaps

Ninguno de fondo. Único matiz: la regla de "no reutilizar contraseña" vive en un trigger de base de datos, no en código Python — funciona, pero su alcance exacto (cuántas contraseñas históricas compara) no es visible solo leyendo el repositorio de código.

---

## RF-08 — Recuperación de contraseña (usuario olvidó su clave)

**Veredicto: ⚠️ Cumple parcialmente (~70%)** — el flujo funciona y respeta el anti-enumeración, pero tiene un gap de seguridad real: el token no se guarda como hash.

### Qué SÍ cumple

- El sistema **siempre responde con el mismo mensaje genérico**, exista o no el correo — cumpliendo la protección contra enumeración de usuarios que pide el RF.
- **Rate limiting de 3 solicitudes por hora por IP**, implementado y verificado contra el historial de eventos.
- Genera un token de recuperación aleatorio y seguro, y envía el correo correspondiente.

### Qué NO cumple / gaps

- **El token de recuperación se guarda y se compara en texto plano, no como hash.** El RF pide explícitamente: *"Los tokens deben almacenarse de forma segura (hash)"*. Hoy el token viaja y se guarda tal cual en la columna correspondiente de la base de datos, y se busca comparando texto exacto. Esto es una carencia de seguridad real: si alguien llegara a leer esa tabla, podría usar los tokens de recuperación directamente sin necesidad de "romper" ningún hash.
- **Discrepancia entre lo documentado y lo real en el código de error de rate limiting**: la documentación de la API (Swagger) indica que al exceder el límite se devuelve `429 Too Many Requests`, pero el código realmente devuelve `422`. No es un problema de negocio grave, pero sí una inconsistencia que puede confundir a quien integra el frontend.
- La "vigencia de 15 minutos" del token no se valida en este mismo flujo, sino en el de restablecimiento (RF-09) — funciona igual para el usuario final, pero la responsabilidad de "hasta cuándo es válido" queda repartida entre dos use cases distintos.

---

## RF-09 — Restablecimiento de contraseña (con token)

**Veredicto: ⚠️ Cumple parcialmente (~75%)** — mismo problema de fondo que RF-08: el token no está hasheado.

### Qué SÍ cumple

- Valida correctamente que el token exista, no haya expirado (ventana de 15 minutos) y no se haya usado antes.
- **Uso único garantizado**: una vez usado el token, queda invalidado y no puede reutilizarse.
- Invalida todas las sesiones activas del usuario tras restablecer la contraseña.
- No permite establecer la misma contraseña anterior (mismo trigger de base de datos que RF-07).
- Auditoría del evento.

### Qué NO cumple / gaps

- **Mismo gap de seguridad que RF-08: el token se guarda y compara en texto plano**, no como hash.
- **No hay un contador de intentos fallidos propio de este flujo.** El RF pide bloquear tras 5 intentos fallidos consecutivos en el restablecimiento; en la implementación actual, el bloqueo por `423` en este endpoint solo se dispara si la cuenta ya estaba bloqueada por otro motivo (login o cambio de contraseña) — no hay una lógica que cuente "cuántas veces falló al restablecer" de forma independiente.

---

## RF-10 — Historial de acceso y auditoría

**Veredicto: ✅ Cumple (~100%)** — existe consulta protegida, inmutabilidad real, verificación de integridad y archivado automático con retención mínima de 12 meses.

### Qué SÍ cumple

- **Sí existe un endpoint para consultar el historial** (`GET /auditoria/`), con filtros por usuario, tipo de evento, rango de fechas, y paginación con tope de 50 registros, restringido por RBAC.
- **Los registros son verdaderamente inmutables**: hay triggers en base de datos que bloquean cualquier `UPDATE` o `DELETE` sobre la tabla de eventos, **incluso para el usuario administrador de la base de datos**. Esto se verificó directamente contra la base de datos, no solo leyendo el código.
- **Hash de integridad SHA-256**: cada evento se guarda con un hash calculado sobre su contenido, y ese hash se recalcula y verifica cada vez que se consulta el historial, para detectar manipulación.
- **Categorías funcionales corregidas**: los eventos se clasifican como `AUTENTICACION`, `MODIFICACION` o `CONSULTA` según su tipo. El endpoint también permite filtrar por categoría sin modificar eventos históricos inmutables.
- **El registro de usuario y la activación de cuenta generan eventos de auditoría** (tipos 1 y 2).
- Se auditan correctamente: login exitoso/fallido, cierre de sesión, cambio de contraseña, solicitud y confirmación de recuperación, actualización de perfil, cambio de estado de cuenta, creación/edición/eliminación de roles, asignación/revocación de permisos, y hasta las propias consultas de auditoría, de listado de usuarios y de perfiles.
- **Retención y archivado automático de 12 meses**: una tarea diaria copia en lotes los eventos vencidos a `modulo1.eventos_archivados`, conserva el hash y los originales inmutables, evita concurrencia entre réplicas mediante advisory lock y genera alertas internas por log ante fallos. La tabla y sus índices se crean mediante Alembic. Ver [`rf10_retencion_auditoria_12_meses.md`](./rf10_retencion_auditoria_12_meses.md).

### Qué NO cumple / gaps

Ninguno detectado dentro del alcance de RF-10.

**Nota de arquitectura:** `audit_sdk`, la librería externa mencionada en `CLAUDE.md`, continúa importada pero no activada. La auditoría real del módulo 1 usa su mecanismo propio (`modulo1.eventos` + SHA-256); esto no afecta el cumplimiento del RF.

---

## RF-11 — Visualización de usuarios del sistema (listado paginado)

**Veredicto: ✅ Cumple (~95%)** — el endpoint legacy sin protección fue retirado (PR #13) y el sobre-permisionamiento RBAC fue corregido (issue #17), ambos hallazgos críticos que tenía esta auditoría en su versión original (2026-08-05). Los gaps restantes se cerraron en la misma corrección.

### Qué SÍ cumple

- Endpoint de listado para administradores con filtros combinables (nombre, correo, estado, rol, y ahora también `estado_cuenta` por nombre) usando lógica "Y" entre ellos, tal como pide el RF.
- **Límite máximo de 50 registros por página**, validado en dos capas.
- Solo expone los campos permitidos (nombre, correo, rol, estado, última modificación) — nada de contraseñas, tokens ni datos sensibles.
- Cada consulta queda registrada en auditoría.
- **RBAC exclusivo de Administrador**: corregido en el issue #17 (2026-08-17) — se revocaron los permisos `prod_leer_usuario`, `vet_leer_usuario`, `ing_leer_usuario`, `cont_leer_usuario` que otorgaban acceso a roles no administrativos. Verificado en vivo: un token de Veterinario recibe `403 ACCESO_DENEGADO`. Ver [`pr17_rf11_rf12_paso0_gap_rbac_y_refresco.md`](./pr17_rf11_rf12_paso0_gap_rbac_y_refresco.md).
- **Ordena por `fecha_registro` descendente**, agregado en el mismo fix.
- **Mecanismo de refresco**: cada item expone `ultima_modificacion` (máximo entre `fecha_actualizacion` del usuario y `fecha_cambio_estado` de su cuenta) y el endpoint acepta `actualizado_desde` para polling incremental — cumple la disyunción "tiempo real o refresco manual" del RF sin necesitar WebSocket/SSE (infraestructura que el proyecto no tiene en ningún módulo).
- Resultado vacío (por filtros o por `actualizado_desde`) incluye un `mensaje` informativo, no solo `items: []`.
- **Endpoint legacy `GET /usuarios/` retirado** (PR #13, 2026-08-15) — ya no existe, responde `405`.

### Qué NO cumple / gaps

- **410 (eliminación concurrente) y 500 (fuga de datos) no están implementados, por diseño**: no existe hard-delete de usuarios en el código (el "borrado" es un cambio de estado a `Eliminado`, ya detectable por el mecanismo de refresco), y el response schema es Pydantic con campos fijos, sin ningún path de serialización dinámica que pueda filtrar datos sensibles. Ver el razonamiento completo en `pr17_rf11_rf12_paso0_gap_rbac_y_refresco.md`.

---

## RF-12 — Visualización de detalles del usuario (admin ve la ficha de cualquier usuario)

**Veredicto: ⚠️ Cumple parcialmente (~90%)** — el código está completo y correcto; el gap de acceso más amplio de lo debido ya se corrigió, queda pendiente sembrar el permiso especial de identificación completa.

### Qué SÍ cumple

- Endpoint de detalle con RBAC.
- **Enmascaramiento del número de identificación por defecto** (primeros 4 dígitos + asteriscos), tal como pide el RF.
- Mecanismo para mostrar el número completo si el usuario tiene el permiso especial correspondiente.
- **Auditoría obligatoria de cada acceso**, sin excepción — se registra quién consultó a quién y cuándo.
- **Acceso ahora restringido a Administrador**: `GET /usuarios/{id}/detalle` comparte `require_permission(1, 2)` con el listado de RF-11, así que la corrección aplicada en el issue #17 (revocar `*_leer_usuario` de Productor/Veterinario/Ingeniero de Campo/Contador) también resuelve este gap — verificado en vivo, un token de Veterinario recibe `403`. Ver [`pr17_rf11_rf12_paso0_gap_rbac_y_refresco.md`](./pr17_rf11_rf12_paso0_gap_rbac_y_refresco.md).

### Qué NO cumple / gaps

- **Falta sembrar el permiso especial en base de datos.** El código que decide "¿este admin puede ver la identificación completa?" está listo y correcto, pero hoy **no existe ninguna fila en la tabla de permisos** que otorgue esa capacidad especial a ningún rol — ni siquiera al Administrador. En la práctica, esto significa que **actualmente nadie puede ver el número de identificación completo**, siempre se muestra enmascarado. Esto es exactamente el tipo de gap que `CLAUDE.md` pide prevenir en su "Paso 0" (verificar que los permisos necesarios existan en base de datos antes de dar por implementado un caso de uso) — aquí ese paso quedó pendiente. No se corrigió en el issue #17 por estar fuera de su alcance (era sobre RBAC de lectura general y refresco, no sobre el permiso especial de identificación).

---

## RF-13 — Visualización de perfil propio

**Veredicto: ✅ Cumple (~100%)** — sin gaps detectados.

### Qué SÍ cumple

- Endpoint dedicado (`GET /usuarios/me`) que obtiene la identidad exclusivamente del token de sesión — no acepta ningún identificador externo, así que es imposible que un usuario consulte el perfil de otro por esta vía, tal como exige el RF.
- Devuelve exactamente los campos que pide el RF (nombre, apellido, correo, tipo y número de identificación, fecha de nacimiento, fecha de registro, rol, estado de cuenta), sin datos sensibles.
- Mismo enmascaramiento del número de identificación que RF-12.
- Auditoría de cada acceso.

### Qué NO cumple / gaps

Ninguno.

---

## RF-14 — Notificar a los usuarios

**Veredicto: ✅ Cumple (~100%)** — los eventos relevantes pasan por el servicio centralizado y el usuario dispone de una bandeja interna autenticada.

### Qué SÍ cumple

- Existe un servicio de notificaciones centralizado (no solo envíos de correo sueltos), con dos canales: **correo electrónico** e **interno**. El canal interno persiste la bandeja y además intenta entregar un push mediante Firebase.
- **Estados de envío** (en cola, enviado, fallido), tal como pide el RF.
- **Política anti-spam de 5 minutos**: no se envía más de una notificación del mismo tipo, al mismo usuario, por el mismo canal, dentro de esa ventana — exactamente como especifica el RF.
- **Reglas por estado de cuenta**: los usuarios inactivos no reciben ninguna notificación; los bloqueados solo reciben las de seguridad (login fallido, cambio de estado de cuenta) — igual que pide el RF.
- Conectado a los flujos de registro, activación, login, cambio de contraseña, recuperación de contraseña, edición de perfil y gestión de cuenta, siempre después de confirmar los cambios en base de datos.
- El correo de registro conserva el enlace de activación, pero el token crudo nunca se guarda en `notificaciones.mensaje`.
- `GET /notificaciones` ofrece paginación, contador de no leídas y filtro `solo_no_leidas`; devuelve únicamente el canal interno del usuario autenticado.
- `PATCH /notificaciones/{id_notificacion}/leida` marca una notificación propia de forma idempotente y responde `404` para registros ajenos o no internos.
- El índice parcial `ix_notificaciones_bandeja_usuario` soporta el orden descendente de la bandeja sin cambiar el esquema funcional existente.

### Qué NO cumple / gaps

Ninguno detectado dentro del alcance de RF-14.

---

## Hallazgos transversales (afectan a varios RFs)

Estos son problemas que no son exclusivos de un solo requerimiento — vale la pena atenderlos juntos porque una sola corrección resuelve el gap en más de un RF a la vez.

1. **Autorización mezclada entre router y use case.** `CLAUDE.md` establece una regla clara: la autorización RBAC va siempre en el router (`require_permission`), y el use case nunca debe verificar roles ni hardcodear IDs de rol. Hoy esa regla se rompe en dos lugares: `gestionar_cuenta_use_case.py` y `editar_perfil_use_case.py` hardcodean `ROL_ADMINISTRADOR = 1` dentro del use case, y el router de edición de perfil ni siquiera tiene `require_permission` declarado. *(Afecta RF-05 y RF-06.)*

2. **Tokens de un solo uso guardados en texto plano.** Los tokens de activación de cuenta y de recuperación de contraseña se guardan y comparan sin hash — si alguien accediera a esa tabla, podría usarlos directamente. *(Afecta RF-01, RF-08, RF-09.)*

3. **Cambiar el rol de un usuario no se aplica hasta que vuelve a loguearse.** El rol viaja fijo dentro del token desde el momento del login. *(Afecta RF-04 y RF-06.)*

4. **[RESUELTO]** ~~Endpoint legacy sin protección que expone todos los usuarios sin enmascarar.~~ `GET /usuarios/` fue retirado en el PR #13 (2026-08-15) — responde `405`. El listado sobrevive únicamente como `GET /usuarios/admin`, con RBAC. Adicionalmente, el issue #17 (2026-08-17) corrigió un sobre-permisionamiento del permiso `require_permission(1, 2)` que compartían ese endpoint y `GET /usuarios/{id}/detalle`: estaba concedido a Productor/Veterinario/Ingeniero de Campo/Contador además de Administrador. *(Afectaba RF-11 y RF-12.)*

5. **Duración del JWT sin documentar.** El sistema corre con 24 horas de vigencia por defecto porque la variable que la controla no está en `.env.example`, cuando el RF pide 8 horas. *(Afecta RF-02.)*

6. **Errores de triggers de base de datos sin traducir a errores de dominio en algunos repositorios.** Si un trigger de protección (por ejemplo, sobre el último administrador) rechaza una operación, el error podría llegar al cliente como un `500` genérico en vez de un mensaje claro con el código HTTP correcto. *(Afecta principalmente RF-06.)*

7. **`CLAUDE.md` desactualizado en dos puntos concretos:** (a) sugiere que la gestión de roles y permisos "probablemente no está implementada" — en realidad es un CRUD completo y robusto (RF-03/RF-04); (b) dice que `audit_sdk` se inicializa en `main.py` vía `AuditContextMiddleware` — en realidad ese middleware se importa pero nunca se registra, y la auditoría real corre por un mecanismo propio del módulo (RF-10). Vale la pena actualizar `CLAUDE.md` para que no induzca a error en el futuro.

---

## Si se agrega la medida de seguridad de CAPTCHA

El CAPTCHA solo aparece mencionado explícitamente en **un** requerimiento: RF-01 (registro), tanto en su lista de requisitos no funcionales de seguridad como en su flujo alterno de "Fallo en la validación de seguridad (CAPTCHA)" con respuesta `400`. Ningún otro RF de los 14 (ni login, ni recuperación de contraseña, ni ningún otro flujo) lo menciona en el texto entregado.

**Qué cambiaría si se implementa:**

- **Nuevo campo en el formulario de registro**: el DTO de entrada (`UsuarioCreateDTO`) necesitaría un campo adicional, por ejemplo `captcha_token`, que el frontend obtendría del widget de Google reCAPTCHA y enviaría junto con el resto de los datos.
- **Nueva validación en el use case de registro**: `CrearUsuarioUseCase` necesitaría verificar ese token contra la API de Google reCAPTCHA antes de continuar con el resto de las validaciones. Como es una llamada a un servicio externo, encajaría como un adaptador nuevo en `infrastructure/adapters/`, siguiendo el mismo patrón que ya usa el proyecto para dependencias externas (ver el patrón de "adaptador stub" documentado en `CLAUDE.md`).
- **Nuevo error de dominio**: un `ValidationError` con código de negocio propio (por ejemplo `CAPTCHA_INVALIDO`), que se traduciría al `HTTP 400` que pide el RF.
- **Nueva variable de entorno**: algo como `RECAPTCHA_SECRET_KEY`, que habría que sumar a `.env.example`.
- **Alcance del cambio**: esto solo movería el estado de **RF-01** — no tocaría el login (RF-02), ni la recuperación/restablecimiento de contraseña (RF-08/RF-09), ni ningún otro requerimiento, porque el texto entregado no pide CAPTCHA en esos flujos. Es un cambio acotado y no afecta ninguna de las otras piezas evaluadas en este documento.
