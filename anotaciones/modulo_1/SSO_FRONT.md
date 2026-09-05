# SSO con AgroFusion — Qué debe implementar el frontend

**Audiencia:** equipo de frontend de sgpmp.
**Estado del backend:** implementado y probado end-to-end en `feature/sso-login`. Ver `resumen_sso_agrofusion.md` (resumen de diseño), `plan_sso_agrofusion.md` (diseño completo), `curls_m01_sso_agrofusion.md` (contratos exactos de cada endpoint) y `prueba_local_sso_agrofusion.md` (prueba real ejecutada).

Este documento es descriptivo: explica qué vistas construir, qué debe hacer cada una, en qué orden, y qué datos entran/salen de cada endpoint. No incluye CSS ni código — solo la lógica de flujo y una descripción de cómo debería sentirse/verse cada pantalla.

---

## 1. Resumen

AgroFusion ofrece dos mecanismos de integración con sgpmp. **El frontend solo construye interfaz para uno de ellos:**

- **Mecanismo A — login SSO interactivo.** Un usuario ya logueado en AgroFusion hace clic en "abrir sgpmp" y entra sin volver a escribir contraseña. **Esto sí requiere vistas nuevas en el frontend** — es el contenido de las secciones 2 a 4.
- **Mecanismo B — sincronización servidor-a-servidor.** El Hub de AgroFusion llama directamente al backend de sgpmp (sin pasar por el frontend) para crear usuarios, consultar roles, emitir tokens, etc. **El frontend no implementa nada para esto.** Su único efecto observable para el frontend: algunos usuarios llegan a sgpmp con la cuenta ya completa y activa (porque un admin de AgroFusion los sincronizó de antemano). Esos usuarios, al hacer login SSO, **nunca verán la pantalla de "completar perfil"** de la sección 4 — entran directo. Es información de contexto, no una vista a construir.

El resto del documento cubre solo el Mecanismo A.

---

## 2. Vista 1 — Botón "Continuar con AgroFusion" en el login existente

**No es un formulario nuevo.** Es un elemento adicional en la pantalla de login que ya existe (la de correo + contraseña).

### Qué debe hacer

Al hacer clic, el usuario es redirigido a la pantalla de login de AgroFusion (fuera de sgpmp). Ahí el usuario se autentica (si no lo estaba ya) y AgroFusion, tras verificar que tiene permiso para abrir el módulo sgpmp, lo redirige de vuelta al frontend de sgpmp con un token de intercambio en la URL (ver Vista 2).

**Importante:** la URL exacta a la que debe apuntar este botón no está definida en el backend de sgpmp — depende de cómo AgroFusion exponga su propio login/selector de proyectos. Es un dato pendiente de coordinar con el equipo de AgroFusion (ver sección 6).

### Cómo debería verse

Tratamiento típico de un botón de SSO secundario: se ubica debajo del formulario de correo/contraseña existente, separado por un divisor visual (ej. una línea con la palabra "o" en medio). Debe usar el mismo lenguaje visual que el resto de la pantalla de login (mismos radios de borde, tipografía, espaciados) — no es una superficie para experimentar con un estilo distinto. Si se dispone del logo/branding de AgroFusion, puede incluirse como ícono junto al texto del botón (ej. "Continuar con AgroFusion"), siguiendo el patrón visual habitual de botones "Continuar con Google/Microsoft/etc.".

---

## 3. Vista 2 — Ruta de callback (canje del token)

El frontend necesita una **ruta dedicada** (ej. `/sso/callback`) que sea la que AgroFusion use para redirigir de vuelta al usuario, con el token de intercambio como parámetro de la URL.

### Qué debe hacer

1. Al montar la vista, leer el token del query param de la URL. **Confirmado contra el código real del frontend de AgroFusion (`Dashboard.tsx`): el nombre del query param es `token`, no `sso_token`** — la URL de redirección real tiene la forma `?token=<jwt_rs256>`.
2. Inmediatamente, sin esperar ninguna acción del usuario, hacer:

   ```
   POST /sesiones/sso
   Content-Type: application/json

   { "sso_token": "<token leído de la URL>" }
   ```

3. **El token expira en 2 minutos y es de un solo uso** — por eso el canje debe dispararse automáticamente al llegar a esta vista, sin pantallas intermedias ni pasos manuales.

### Respuesta 200 — éxito

```json
{
  "token": "<jwt de sgpmp>",
  "tipo": "Bearer",
  "expira_en": 86400,
  "message": "Sesión SSO iniciada exitosamente.",
  "perfil_incompleto": false
}
```

- Guardar `token` exactamente igual que se hace hoy tras un login normal (mismo mecanismo de almacenamiento e inyección en `Authorization: Bearer <token>` que ya usa el frontend — esto no cambia).
- Luego decidir a dónde navegar:
  - `perfil_incompleto: false` → ir directo al dashboard/home normal, como cualquier login exitoso.
  - `perfil_incompleto: true` → ir a la Vista 3 (sección 4), sin dejar navegar a otra parte todavía.

### Errores posibles

| HTTP | `code` | Qué significa | Qué mostrar/hacer |
|---|---|---|---|
| 503 | `SSO_NO_CONFIGURADO` | El backend de este ambiente no tiene SSO habilitado | Mensaje genérico de error, ofrecer volver al login normal (no es un error recuperable por el usuario) |
| 500 | `AGROFUSION_CLAVE_PUBLICA_NO_DISPONIBLE` | Falla de configuración del servidor | Mensaje genérico de error, ofrecer volver al login normal |
| 401 | `SSO_TOKEN_INVALIDO` | Firma inválida, token expirado (los 2 minutos), o `aud`/`iss` incorrectos | "El enlace expiró o no es válido. Vuelve a intentar desde AgroFusion." + botón para regresar a la Vista 1 |
| 423 | `CUENTA_BLOQUEADA` | La cuenta existe pero está bloqueada temporalmente (intentos fallidos de login normal) | Mensaje explicando el bloqueo temporal, igual al que ya se muestra en login normal para este mismo código |
| 403 | `CUENTA_DESHABILITADA` | La cuenta existe pero está inactiva/eliminada | Mensaje de cuenta deshabilitada, sugerir contactar a un administrador |

No hay ningún caso en el que el usuario deba reintentar el mismo token — si falla, siempre implica volver a la Vista 1 para obtener un token nuevo desde AgroFusion.

### Cómo debería verse

Pantalla transitoria y minimalista: sin header, sin sidebar, sin navegación visible — el usuario no debe percibirla como una página a la que pueda "quedarse" o volver. Un indicador de carga (spinner) centrado con un texto de estado breve, por ejemplo "Verificando tu sesión con AgroFusion…". Si hay error, reemplazar el spinner por el mensaje correspondiente de la tabla de arriba, manteniendo el mismo layout centrado y minimalista (no reintroducir navegación completa solo para mostrar el error).

---

## 4. Vista 3 — Completar perfil (solo cuando `perfil_incompleto: true`)

Ocurre quien usa el Mecanismo A **sin sincronización previa desde AgroFusion**: sgpmp crea una cuenta mínima con nombre, apellidos, tipo/número de identificación, fecha de nacimiento y género todos vacíos, en un estado especial (`Pendiente Datos`) que impide operar el resto del sistema hasta completarlos.

### Antes de mostrar el formulario

`LoginResponse` (la respuesta de la Vista 2) **no trae `id_usuario` ni `version`**, y ambos son necesarios para el siguiente paso. Justo después del login SSO, con el token ya guardado, llamar:

```
GET /usuarios/me
Authorization: Bearer <token>
```

y usar el `id_usuario` y el `version` de la respuesta para armar la llamada de completar perfil.

### El formulario

Reutiliza el endpoint que ya existe para editar perfil — **no es un endpoint nuevo**:

```
PATCH /usuarios/{id_usuario}
Authorization: Bearer <token>
Content-Type: application/json

{
  "nombre": "...",
  "apellidos": "...",
  "tipo_identificacion": "...",
  "numero_identificacion": "...",
  "fecha_nacimiento": "YYYY-MM-DD",
  "genero": "...",
  "version": <version obtenido de GET /usuarios/me>
}
```

Campos a mostrar y sus restricciones:

| Campo | Tipo de control | Notas |
|---|---|---|
| `nombre` | texto | obligatorio |
| `apellidos` | texto | obligatorio |
| `tipo_identificacion` | select cerrado | únicamente `CC`, `CE`, `Pasaporte` (valores exactos, sensibles a mayúsculas) |
| `numero_identificacion` | texto | debe ser único en el sistema — ver error 409 abajo |
| `fecha_nacimiento` | selector de fecha | formato `YYYY-MM-DD` |
| `genero` | select cerrado | valores permitidos: `M`, `F`, `X`, `T` — el backend no define las etiquetas visibles de cada código; el frontend decide qué texto mostrar por cada opción |

Estos 4 campos de identificación **solo se pueden enviar mientras la cuenta está en este estado especial** — una vez completados, la cuenta pasa automáticamente a estado activo y ya no podrán volver a editarse desde este mismo formulario (un intento de reenviarlos después da 403, ver tabla de errores).

### Comportamiento esperado

- Al enviar exitosamente, la cuenta queda activa automáticamente — no hay un paso adicional de confirmación. Navegar directo al dashboard/home normal.
- Esta vista debe ser **bloqueante**: mientras `perfil_incompleto` sea `true`, el usuario no debe poder navegar al resto del sistema. Se recomienda tratarla como un paso de onboarding de una sola pantalla, sin opción de "cancelar" o "más tarde" (si el usuario no quiere completarlo ahora, la salida válida es cerrar sesión, no aplazarlo).

### Errores posibles

| HTTP | `code` | Qué significa | Qué mostrar/hacer |
|---|---|---|---|
| 403 | `SIN_PERMISO_CAMPOS_IDENTIFICACION` | Se intentaron enviar los campos de identificación fuera de este estado (no debería ocurrir si la UI respeta el flujo, pero puede pasar si el usuario reabre esta vista tarde) | Redirigir al dashboard normal — la cuenta ya está completa |
| 412 | `CONFLICTO_CONCURRENCIA` | El `version` enviado ya no coincide (otra sesión modificó el registro) | Volver a pedir `GET /usuarios/me` y reintentar con el `version` actualizado |
| 409 | `UNICIDAD` | El número de identificación ya pertenece a otra cuenta | Error de campo sobre `numero_identificacion`, pedir corregirlo |

### Algo a tener en cuenta para el equipo de producto

El rol con el que nace esta cuenta (`Externo AgroFusion`) no tiene ningún permiso asignado por defecto. Completar el perfil activa la cuenta, pero **no cambia su rol** — el usuario puede seguir viendo errores 403 en funciones protegidas del sistema hasta que un administrador le asigne un rol distinto. Vale la pena considerar un mensaje o aviso post-onboarding indicando esto (a criterio de frontend/producto; el backend no impone ningún texto ni pantalla específica para este caso).

### Cómo debería verse

A diferencia de la Vista 2, esta sí es una pantalla con la que el usuario interactúa activamente, así que debe sentirse como parte normal del sistema: mismos componentes de formulario (inputs, selects, selector de fecha) que ya usa el formulario de registro o de edición de perfil existente, para mantener consistencia visual — no es el lugar para introducir un estilo nuevo. Un texto explicativo breve arriba del formulario ayuda a que el usuario entienda por qué se le pide esto (ej. "Estás ingresando por primera vez desde AgroFusion. Completa estos datos para continuar."). Al tratarse de un paso obligatorio de una sola pantalla, conviene que ocupe el espacio principal sin distracciones de navegación alrededor (similar en espíritu a la Vista 2, pero con el formulario como contenido central en vez de un spinner).

---

## 5. Convivencia con las vistas de auth existentes

Nada de esto cambia el comportamiento de las vistas que ya existen — son aditivas:

- **Login normal** (correo + contraseña), **registro**, **activación de cuenta por correo**, **recuperar/restablecer contraseña**: siguen funcionando exactamente igual, sin ningún ajuste necesario.
- Si un correo ya tenía cuenta local con contraseña propia (el usuario se registró directo en sgpmp antes de usar AgroFusion), el login SSO reutiliza esa misma cuenta automáticamente — no hay pantalla especial para este caso, es transparente para el usuario, que a partir de ahí puede seguir entrando por cualquiera de los dos caminos indistintamente.
- El manejo de sesión después de un login exitoso (almacenamiento del token, inyección en cada request, expiración) es idéntico entre login normal y login SSO — ambos devuelven el mismo `LoginResponse` y el mismo tipo de JWT.

---

## 6. Pendiente de coordinar con AgroFusion (fuera del control de este repo)

- **URL de login de AgroFusion** a la que debe apuntar el botón de la Vista 1 — no está definida en sgpmp, la entrega el equipo de AgroFusion.
- ~~Nombre exacto del query param~~ — **confirmado**: `token` (ver Vista 2). Verificado leyendo el código real de `agrofusion-frontendweb-main/src/pages/Dashboard.tsx` y probando el flujo completo contra una instancia real de AgroFusion levantada en Docker (`anotaciones/AgroFusion_documentacion-main/docker/`).

## 7. Verificación realizada

El flujo completo (Vista 2 + Vista 3) se probó de punta a punta contra una instancia real de AgroFusion (no un JWT fabricado a mano): login real → `sso-token` RS256 real → `POST /sesiones/sso` (`perfil_incompleto: true`) → `GET /usuarios/me` (con `id_usuario`/`version`) → `PATCH /usuarios/{id}` → cuenta transicionada a `Activo`. Detalles del entorno de prueba y el paso a paso en `anotaciones/AgroFusion_documentacion-main/docker/README.md`.

Esa prueba encontró y corrigió un bug real en sgpmp: `GET /usuarios/me` respondía `500` para una cuenta recién aprovisionada por SSO (campos personales `NULL`) y no exponía `id_usuario`/`version`. Ya está corregido en `ConsultarPerfilUseCase`/`ConsultarDetalleUsuarioUseCase`/`UsuarioDetalleResponse` — el flujo descrito en la Vista 3 de este documento ya refleja el comportamiento corregido.
