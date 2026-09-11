# Plan: SSO de `identity_access` con AgroFusion

> **Estado: propuesta / planeación. Nada de esto está implementado ni aplicado a la DB todavía.** Este documento traduce el análisis de los proyectos de referencia de AgroFusion (`anotaciones/AgroFusion_documentacion-main/`) en un diseño concreto sobre el código real de `src/identity_access/`, para discusión con el equipo antes de implementar.

## Contexto

sgpmp necesita poder operar de dos formas sin que una rompa la otra:

1. **Standalone** (como hoy): login propio con correo+contraseña, JWT HS256, sesiones en `modulo1.sesiones`/`modulo1.tokens`. Esto **no cambia**.
2. **Como módulo dentro de AgroFusion**: un usuario que ya inició sesión en AgroFusion debe poder entrar a sgpmp sin volver a loguearse, y AgroFusion debe poder gestionar/sincronizar usuarios y roles de sgpmp desde su panel central.

Para diseñar esto se analizaron dos proyectos de referencia (código fuente completo, no solo documentación) más el dump de esquema de AgroFusion:

- `anotaciones/AgroFusion_documentacion-main/agrofusion-backendauth-main/` — el **proveedor de identidad central** de AgroFusion (login, sesiones, emisión de tokens).
- `anotaciones/AgroFusion_documentacion-main/agrofusion-backendint-main/` — el **backend de integración/Hub** de AgroFusion (confirma, desde el lado consumidor, cómo se llama a proyectos externos).
- `anotaciones/AgroFusion_documentacion-main/01_BDAgrofusion.sql` — dump de esquema (sin datos) de las ~75 tablas de la plataforma.

### Arquitectura actual de sgpmp (para contexto)

- JWT HS256 (`src/shared/jwt.py`), payload mínimo: `{sub: id_usuario, jti: id_token, rol: id_rol, exp, iat}`. Sin `iss`/`aud`/`email`.
- Diseño híbrido con estado: cada JWT tiene una fila en `modulo1.tokens` (blacklist por `fecha_uso`, columna `id_token` = el propio `jti`) y una fila en `modulo1.sesiones` (única sesión activa por cuenta — índice único parcial; expira por 30 min de inactividad, chequeado en `get_current_user`).
- `LoginUseCase.execute()` (`application/use_cases/sesiones/login_use_case.py:61`) ya centraliza todo el flujo post-verificación de credenciales: invalida sesión previa, crea `Token` + `Sesion`, llama `create_token()`, registra evento de auditoría (tipo 3 = login exitoso), hace `commit()`. Devuelve `(jwt_str, fecha_expiracion, sesion_previa_cerrada, id_usuario)`.
- `Usuario` (entidad de dominio, `domain/entities/usuario.py`) y su tabla `modulo1.usuarios` **exigen** `tipo_identificacion`, `numero_identificacion` (único, `NOT NULL`), `nombre`, `apellidos`, `fecha_nacimiento`, `genero` — todos `NOT NULL` en DB (confirmado en `infrastructure/models/usuarios_model.py:47-52`). Esto es relevante para el diseño de auto-provisión (ver más abajo).
- `Cuenta.id_estado_cuenta` es FK a la tabla catálogo `modulo1.estados_cuentas` (no un `ENUM` de Postgres) — agregar un estado nuevo es un `INSERT`, no un `ALTER TYPE`.
- No existe **ningún** rastro de SSO/OAuth/OIDC en `src/` hoy. `.env.example` tiene variables muertas y nunca leídas por el código: `GOOGLE_CLIENT_ID/SECRET`, `MICROSOFT_CLIENT_ID/SECRET`, `EXTERNAL_USERS_API_URL` — vestigios de una idea de SSO anterior que no es la de AgroFusion; se proponen reemplazarlas (sección de variables de entorno).

### Arquitectura de AgroFusion (hallazgos)

AgroFusion son en realidad **tres backends separados** que comparten una base de datos central (confirmado en el README de `agrofusion-backendauth-main` y en `07_InformacionAgroFusion.docx`): `backendauth` (identidad, puerto 8000), `backendaudit` (9000) y `backendint` (Hub de integración, 9001). Existen **dos mecanismos de integración completamente distintos** para un proyecto externo como sgpmp, y ambos se usan en producción según el código de referencia:

#### Mecanismo A — Handoff de login interactivo (RS256, un solo uso)

`POST /auth/sso-token` en `backendauth` (`app/services/sso_service.py`): requiere que el usuario ya tenga una sesión válida en AgroFusion, valida el permiso `"001"` y que el `project_code` destino exista y esté activo en `af_external_projects`. Emite:

```python
payload = {
    "iss": "agrofusion-auth", "aud": project_code,        # ej. "SGPMP"
    "sub": str(user.user_id), "email": user.email,
    "iat": int(now.timestamp()), "exp": int((now + timedelta(minutes=2)).timestamp()),
}
sso_token = jwt.encode(payload, settings.sso_private_key, algorithm="RS256")
```

Puntos clave:
- **RS256 (asimétrico)**, no HS256. sgpmp solo necesita la **clave pública** para verificar, nunca un secreto compartido.
- **TTL de 2 minutos** — es un token de intercambio de un solo uso, no una sesión. Debe canjearse de inmediato.
- El payload es mínimo: solo `sub` (id de usuario en AgroFusion) y `email`. **No incluye rol, nombre, apellidos, ni ningún dato adicional.**
- No existe JWKS ni endpoint de introspección en `backendauth` — la clave pública (`app/keys/sso_public.pem`) se distribuye fuera de banda al equipo consumidor. Confirmado por grep exhaustivo: cero código de `.well-known`, JWKS o introspección en ese repo.
- `backendint`, al decodificar sus *propios* JWT HS256, declara `jwt_issuer` en config pero **nunca valida `iss` ni `aud`** al decodificar (`app/core/security.py::decode_access_token` solo chequea `exp`). Se documenta esto como **antipatrón a no copiar** — sgpmp sí debe validar `iss`/`aud`/`exp` explícitamente.

Flujo de usuario esperado: usuario logueado en AgroFusion → clic en "abrir módulo sgpmp" → frontend de AgroFusion pide el `sso-token` a `backendauth` → redirige al frontend de sgpmp con el token → frontend de sgpmp lo envía de inmediato al backend de sgpmp para canjearlo por una sesión propia.

#### Mecanismo B — Sincronización servidor-a-servidor (push, vía plantillas REST configurables)

AgroFusion registra cada proyecto externo en `af_external_projects` y configura, vía `af_external_url` + `af_external_endpoint` + `af_external_request` (URLs/métodos/plantillas de body y respuesta guardadas en DB, no en código), hasta 7 operaciones que el Hub puede invocar contra el proyecto externo: `GET_ROLES`, `GET_TYPE_DOCUMENT`, `GET_USER`, `CREATE_USER`, `ACTIVATE_ACCOUNT`, `GET_AUTHORIZATION`, `CHANGE_USER_STATUS`, `UPDATE_USER`.

El flujo que sí está implementado y funcionando en `backendint` (`app/services/checks_service.py::_request_external_service_token`) es `GET_AUTHORIZATION`:

```json
POST <url_configurada_para_sgpmp>
{ "client_id": "agrofusion", "client_secret": "super-secret-agrofusion-2026-usco", "email": "usuario@ejemplo.com" }
```

y espera de vuelta un JSON donde el campo mapeado como `access_token` (según `response_template.fields_expected`) contenga un token que `backendint` reenvía como `Authorization: Bearer <token>` en llamadas posteriores.

Comentario explícito encontrado en el schema (`af_external_project_roles`): *"Cada proyecto gestiona sus propios roles en su BD. AgroFusion SSO solo los sincroniza para asignación, NO los crea ni edita."* → **sgpmp sigue siendo el dueño de su propio RBAC** (`modulo1.roles`/`modulo1.permisos`); AgroFusion solo lee/cachea para su UI de administración. Esto es compatible 1:1 con la regla de CLAUDE.md de que el RBAC vive en `modulo1.permisos`, consultado dinámicamente.

### Hallazgo que cambia el diseño de auto-provisión

El payload del Mecanismo A trae **solo `sub` y `email`**. Pero `modulo1.usuarios` exige `NOT NULL` en `tipo_identificacion`, `numero_identificacion` (único), `nombre`, `apellidos` y `fecha_nacimiento`. **No es posible crear un `Usuario` válido solo con esos dos datos** — inventar un número de identificación legal para cumplir el `NOT NULL`/`UNIQUE` sería inaceptable (es el documento de identidad real de la persona, referenciado por control de acceso y, potencialmente, por trazabilidad legal agropecuaria).

Por eso la auto-provisión aprobada se diseña en **dos niveles**, no como una sola operación:

1. **Camino primario — Mecanismo B (`CREATE_USER`)**: cuando un administrador de AgroFusion asigna el módulo sgpmp a un usuario, el Hub llama a `CREATE_USER` con el payload completo (AgroFusion, como plataforma de identidad corporativa, ya tiene estos datos del empleado/productor). sgpmp crea el `Usuario`+`Cuenta` **completos y activos**, con el rol resuelto explícitamente en la llamada. Este es el 90% del caso feliz.
2. **Camino de respaldo — Mecanismo A sin sincronización previa**: si el handoff interactivo llega y el correo no existe todavía en sgpmp (la sincronización no corrió o falló), sgpmp **sí** crea automáticamente un registro — pero mínimo e incompleto, en un nuevo estado de cuenta `PENDIENTE_DATOS`, y el login SSO devuelve una señal explícita para que el frontend redirija a un formulario de "completar tu perfil" (documento de identidad, fecha de nacimiento, género) antes de dejar usar el resto del sistema. Esto cumple la intención de "no bloquear el acceso" sin fabricar un número de identificación falso.

---

## Diseño propuesto — Mecanismo A: login SSO interactivo

### Nuevas piezas (siguiendo el flujo Router → UseCase → Port ← Repository de CLAUDE.md)

- **Value object** `domain/value_objects/identidad_federada.py` → `IdentidadFederada(frozen=True)`: `sub_externo: str`, `email: Email`, `emisor: str`.
- **Puerto** `domain/repositories/sso_provider_port.py` → `SsoProviderPort(ABC)` con `verificar(token: str) -> IdentidadFederada`. Sigue exactamente el patrón ya documentado en CLAUDE.md de "adaptador stub para dependencias cruzadas" (mismo espíritu que `CicloDependencyPort`): el dominio declara qué necesita de un proveedor de identidad externo, sin saber que es AgroFusion ni que es RS256.
- **Adaptador** `infrastructure/adapters/agrofusion_sso_adapter.py` → `AgroFusionSsoAdapter(SsoProviderPort)`. Implementación real con `python-jose`:

  ```python
  from jose import jwt, JWTError
  payload = jwt.decode(
      token, _AGROFUSION_PUBLIC_KEY, algorithms=["RS256"],
      audience=_AGROFUSION_PROJECT_CODE, issuer=_AGROFUSION_ISSUER,
  )
  ```
  A diferencia de `backendint`, aquí **sí** se pasan `audience`/`issuer` a `jwt.decode` para que `python-jose` los valide — no basta con que estén en el payload. Cualquier `JWTError` (firma inválida, `aud`/`iss` incorrectos, expirado — recordar TTL de 2 min) se traduce a `AuthenticationError(code="SSO_TOKEN_INVALIDO")`.
- **Puerto adicional** en `domain/repositories/usuario_repository.py`: confirmar que ya existe `obtener_por_correo(Email)` (usado por `LoginUseCase` — sí existe) y agregar `crear_minimo_sso(email: Email, id_rol: int) -> Usuario` para el camino de respaldo (ver abajo), ya que `registrar_nuevo` exige todos los campos personales.
- **Use case** `application/use_cases/sesiones/sso_login_use_case.py` → `SsoLoginUseCase`:

  1. `identidad = self.sso_provider.verificar(sso_token)` — si falla, `AuthenticationError` (401), no se toca la DB.
  2. `usuario = self.usuarios_repo.obtener_por_correo(identidad.email)`.
  3. **Si no existe**: crear `Usuario` mínimo (`crear_minimo_sso`) con `id_rol = ROL_EXTERNO_AGROFUSION` (ver Paso 0) y `Cuenta` en estado `PENDIENTE_DATOS` (nuevo estado, ver Paso 0) — **activa para efectos de login** (no bloquea sesión) pero marcada para que el frontend fuerce completar perfil. Registrar evento `PROVISION_SSO_MINIMA`.
  4. **Si existe**: reutilizar las mismas verificaciones de estado de `LoginUseCase` (bloqueada / inactiva / eliminada) — **extraer esas ramas a un método compartido** (p. ej. `_verificar_estado_cuenta(cuenta)` en un mixin o función de módulo) para no duplicar la máquina de estados entre `LoginUseCase` y `SsoLoginUseCase`. Nota: si la cuenta está `PENDIENTE` (activación por correo normal, no `PENDIENTE_DATOS`), el login SSO la activa directamente — AgroFusion ya verificó la identidad, no tiene sentido pedirle que confirme un correo que ya está confirmado en la plataforma central.
  5. **Cola idéntica al login normal**: invalidar sesión previa activa (política de sesión única, sin cambios), `crear_token_acceso`, `create_token(...)`, `crear_sesion(...)`, `registrar_acceso`, evento `LOGIN_SSO_EXITOSO`, `commit()`.
  6. Devuelve la misma tupla que `LoginUseCase.execute` **más** un flag `perfil_incompleto: bool`, para que el router pueda decorar la respuesta.
- **Router**: nuevo endpoint público en `sesiones_routers.py`:

  ```python
  @router.post("/sso", response_model=LoginResponse, responses={401: {"model": ErrorResponse}, 503: {"model": ErrorResponse}})
  def iniciar_sesion_sso(dto: SsoLoginDTO, request: Request, db: Session = Depends(get_db)):
      if not settings.agrofusion_sso_habilitado:
          raise ServiceUnavailableError(code="SSO_NO_CONFIGURADO", message="Integración con AgroFusion no disponible en este despliegue.")
      ...
  ```
  Sin `require_permission` — la confianza la da la firma RS256 verificada dentro del use case, no un rol de sgpmp (el usuario todavía no tiene sesión en sgpmp en este punto). Reutiliza `LoginResponse`; si `perfil_incompleto` es `True`, se agrega un campo opcional al schema (`perfil_incompleto: bool = False`) para que el frontend redirija.
- **DTO** `infrastructure/dto/usuario_dto.py` → `SsoLoginDTO(BaseDTO)`: `{ sso_token: str }`.

### Caso borde documentado explícitamente

Si el correo ya existe como cuenta local con contraseña propia (usuario que se registró directo en sgpmp antes de que su empresa adoptara AgroFusion), el login SSO **reutiliza esa misma cuenta** — no se crea una segunda fila ni se pisa la contraseña existente. A partir de ahí el usuario puede seguir entrando por cualquiera de los dos caminos (correo+contraseña o SSO).

---

## Diseño propuesto — Mecanismo B: sincronización servidor-a-servidor

Este es el que hace que la auto-provisión sea real (con todos los datos) en vez de mínima. Autenticación **máquina-a-máquina**, no de usuario — no pasa por `require_permission`/RBAC de rol, porque quien llama no es un `Usuario` de sgpmp con un `id_rol`, es el Hub de AgroFusion.

- **Dependencia nueva** (no confundir con `require_permission`): `verify_agrofusion_client` en `src/shared/agrofusion_auth.py`, que compara `client_id`/`client_secret` del body contra `AGROFUSION_HUB_CLIENT_ID`/`AGROFUSION_HUB_CLIENT_SECRET` con `secrets.compare_digest` (nunca `==`).
- **Router nuevo** `infrastructure/routers/agrofusion_integration_router.py`, montado bajo un prefijo propio (ej. `/integraciones/agrofusion`) para dejar claro que es un contrato M2M distinto del resto de la API:
  - `GET /roles` → `GET_ROLES`. Solo lectura de `modulo1.roles` (id, nombre, prefijo). Usa el `RolRepository` ya existente.
  - `POST /token` → `GET_AUTHORIZATION`. Body `{client_id, client_secret, email}`; si el usuario existe, emite un JWT local normal (mismo `create_token`) sin necesidad de contraseña ni del handoff RS256, y responde `{"access_token": "...", "expires_in": ...}` — el nombre de campo `access_token` es intencional para calzar con `response_template.fields_expected` de `backendint`.
  - `POST /usuarios` → `CREATE_USER`. Body con todos los campos que `Usuario.registrar_nuevo` necesita (`email`, `nombre`, `apellidos`, `tipo_identificacion`, `numero_identificacion`, `fecha_nacimiento`, `genero`, `rol_codigo`). Resuelve `rol_codigo` (ej. `"prod"`, `"vet"`) contra `modulo1.roles.nombre`/prefijo — si no viene o no matchea, usa el rol por defecto igual que el registro normal (`ROL_PRODUCTOR`). Crea `Usuario`+`Cuenta` en estado `ACTIVO` directamente (sin flujo de activación por correo — AgroFusion ya validó la identidad), sin contraseña utilizable (ver más abajo).
  - `GET /usuarios/{email}` → `GET_USER`. Devuelve existencia + estado + rol actual.
  - `PATCH /usuarios/{email}/estado` → `CHANGE_USER_STATUS`. Permite a un admin de AgroFusion desactivar remotamente la cuenta sgpmp de alguien que salió de la organización.
  - `ACTIVATE_ACCOUNT`, `UPDATE_USER`, `GET_TYPE_DOCUMENT` — **no implementar en la primera iteración**; sgpmp no tiene concepto de "tipo de documento" catalogado más allá del `CHECK` fijo (`CC`/`CE`/`Pasaporte`) y las cuentas creadas vía `CREATE_USER` ya nacen `ACTIVO`. Confirmar con el equipo de AgroFusion si el orquestador exige las 7 plantillas configuradas para habilitar un proyecto o si acepta un subconjunto (pregunta abierta, ver más abajo).

### Contraseña para cuentas provistas por AgroFusion (ambos mecanismos)

Ni `CREATE_USER` ni la provisión mínima de SSO reciben una contraseña en texto plano que cifrar. Se genera un hash bcrypt de un secreto aleatorio de alta entropía (`secrets.token_urlsafe(32)`, nunca persistido en claro ni devuelto) vía `Contrasena.cifrar(...)` — la cuenta queda técnicamente con un hash válido en la columna `NOT NULL` existente, pero es computacionalmente inadquirible por fuerza bruta. No se requiere ninguna migración de esquema para permitir "sin contraseña": se reutiliza la columna tal cual. El login por correo+contraseña seguirá funcionando para esa cuenta el día que el usuario use "olvidé mi contraseña" para fijar una propia — no hace falta bloquearlo explícitamente.

---

## Paso 0 — Gaps de BD propuestos (pendientes de aplicar y documentar en vivo vía MCP postgres antes de codear)

```sql
-- 1. Nuevo estado de cuenta para la provisión mínima vía SSO (tabla catálogo, no ENUM — INSERT simple)
INSERT INTO modulo1.estados_cuentas (id_estado_cuenta, nombre)
VALUES (6, 'PENDIENTE_DATOS')
ON CONFLICT DO NOTHING;

-- 2. Rol de mínimo privilegio para usuarios auto-provistos sin sincronización previa
--    (verificar primero el próximo id_rol libre en modulo1.roles; NO asumir que es 6)
INSERT INTO modulo1.roles (id_rol, nombre) VALUES (<siguiente_id>, 'Externo AgroFusion');
-- Sin permisos activos asignados inicialmente en modulo1.permisos — el trigger que
-- bloquea "rol sin permisos" (mencionado en CLAUDE.md para el CRUD de roles) puede
-- requerir al menos un permiso mínimo de lectura de perfil propio; confirmar en vivo.

-- 3. Nuevos tipos de evento de auditoría (modulo1.tipos_eventos es catálogo, no ENUM)
INSERT INTO modulo1.tipos_eventos (id_tipo_evento, nombre, accion) VALUES
  (<siguiente_id>, 'LOGIN_SSO_EXITOSO', 'Inicio de sesión vía handoff SSO de AgroFusion'),
  (<siguiente_id>, 'PROVISION_SSO_MINIMA', 'Cuenta creada automáticamente por SSO sin datos completos'),
  (<siguiente_id>, 'PROVISION_AGROFUSION_SYNC', 'Cuenta creada vía sincronización server-to-server (CREATE_USER)');
```

Notas:
- **RBAC: sin cambios en `modulo1.recursos`/`modulo1.permisos`.** Ninguno de los endpoints nuevos (`/sesiones/sso`, `/integraciones/agrofusion/*`) pasa por `require_permission`: el primero confía en la firma RS256, el segundo en el secreto M2M. Esto es una ventaja de diseño a resaltar, no un descuido — se documenta explícitamente para que quien revise no busque un gap de RBAC que no existe.
- Confirmar en vivo (vía MCP postgres, no asumir) los próximos IDs libres de `modulo1.roles` y `modulo1.tipos_eventos` antes de aplicar, siguiendo la convención ya usada en `anotaciones/modulo_1/` para gaps de BD.
- No se requiere ninguna columna nueva en `modulo1.usuarios` ni `modulo1.cuentas_usuarios` para distinguir "cuenta local" de "cuenta AgroFusion": el estado `PENDIENTE_DATOS` ya es la señal para el caso mínimo, y una cuenta creada vía `CREATE_USER` es indistinguible de una registrada a mano una vez completa — no hace falta trazar el origen más allá de lo que ya registra `modulo1.eventos` (evento `PROVISION_AGROFUSION_SYNC` con el detalle correspondiente).

---

## Variables de entorno nuevas

Reemplazar en `.env.example` el bloque de OAuth Google/Microsoft y `EXTERNAL_USERS_API_URL` (ninguno usado por código real) por:

```env
# SSO con AgroFusion (Mecanismo A — handoff de login interactivo)
# Vacías o ausentes => POST /sesiones/sso responde 503 y sgpmp funciona 100% standalone.
AGROFUSION_SSO_PUBLIC_KEY_PATH=
AGROFUSION_PROJECT_CODE=
AGROFUSION_ISSUER=agrofusion-auth

# Integración con AgroFusion (Mecanismo B — sincronización server-to-server)
AGROFUSION_HUB_CLIENT_ID=
AGROFUSION_HUB_CLIENT_SECRET=
```

`AGROFUSION_SSO_PUBLIC_KEY_PATH` apunta a un archivo `.pem` (la clave pública RSA que entrega el equipo de AgroFusion fuera de banda — no hay JWKS que consultar). **No se debe commitear ese `.pem` al repo** — se distribuye como secreto de despliegue, igual que `SECRET_KEY`.

---

## Consideraciones de seguridad

1. **Distribución de la clave pública RSA fuera de banda**: al no existir JWKS en `backendauth`, el archivo `.pem` debe llegar por un canal seguro (no email plano) y su rotación es manual — documentar el procedimiento de rotación con el equipo de AgroFusion antes de ir a producción.
2. **Validar `iss`/`aud`/`exp` explícitamente** en `jwt.decode(..., audience=..., issuer=...)` — no replicar la laxitud observada en `backendint`, que declara `jwt_issuer` en config pero nunca lo pasa al decode.
3. **TTL de 2 minutos es intencional**: no cachear ni reintentar un `sso_token` vencido; el error debe ser claro (`SSO_TOKEN_INVALIDO`/expirado) para que el frontend vuelva a pedir uno nuevo a AgroFusion, no reintente el mismo.
4. **`secrets.compare_digest`** para el `client_secret` M2M del Mecanismo B, nunca `==` (evita timing attacks).
5. **El secreto M2M es de "plataforma", no por proyecto**: en el código de referencia, `backendint` usa un único `ext_client_id`/`ext_client_secret` para todos sus proyectos externos (no hay uno por proyecto en el modelo). Si se requiere aislar el impacto de una fuga, proponer a AgroFusion un secreto específico para sgpmp — pregunta abierta, ver más abajo.
6. **Rate limiting** en `POST /sesiones/sso` y en `/integraciones/agrofusion/token`: son puntos de entrada sin RBAC previo; aplicar el mismo patrón de límite por IP ya usado en `SolicitarRecuperacionUseCase` (3/hora) como referencia de estilo, ajustando el umbral según el volumen esperado de handoffs.

---

## Cómo esto preserva el modo standalone

Todo lo anterior es **aditivo**: ningún archivo del flujo de login/JWT/RBAC actual (`LoginUseCase`, `get_current_user`, `require_permission`, `verify_token`) se modifica en su comportamiento por defecto. Sin las variables de entorno de AgroFusion configuradas:
- `POST /sesiones/sso` responde `503 SSO_NO_CONFIGURADO` de inmediato, sin tocar la DB.
- `/integraciones/agrofusion/*` puede montarse condicionalmente (`if settings.agrofusion_hub_client_id: app.include_router(...)`) para ni siquiera exponer las rutas en un despliegue standalone.
- El login normal (`POST /sesiones/`) y todo lo demás sigue funcionando exactamente igual.

---

## Prerrequisitos del lado de AgroFusion (fuera del control de este repo)

1. Registrar sgpmp como fila en `af_external_projects` y asignarle un `project_code` (el valor que sgpmp usará como `AGROFUSION_PROJECT_CODE`/`aud`).
2. Entregar la clave pública `sso_public.pem` al equipo de sgpmp por canal seguro.
3. Configurar en `af_external_url`/`af_external_endpoint` las plantillas REST hacia los 5 endpoints implementados por sgpmp (`GET_ROLES`, `GET_AUTHORIZATION`, `CREATE_USER`, `GET_USER`, `CHANGE_USER_STATUS`), incluyendo el `client_id`/`client_secret` que sgpmp validará.
4. Confirmar el formato exacto que el orquestador de AgroFusion espera en la respuesta de `CREATE_USER` (¿solo `200 OK`? ¿algún cuerpo específico?) — no se encontró ese contrato de respuesta documentado en el código de referencia, solo el de solicitud.

---

## Preguntas abiertas para validar con el equipo de AgroFusion

- ¿Es obligatorio configurar las 7 plantillas (`GET_ROLES`...`UPDATE_USER`) para que el orquestador habilite un proyecto externo, o acepta un subconjunto activo?
- ¿Qué valor exacto de `rol_codigo`/nombre de rol espera enviar AgroFusion en `CREATE_USER` — el prefijo de sgpmp (`admin`/`prod`/`vet`/`ing`/`cont`) o un código propio de AgroFusion que sgpmp tendría que mapear?
- ¿El secreto `client_id`/`client_secret` del Mecanismo B será uno global de la plataforma (como en el código de referencia) o uno específico por proyecto externo (recomendado por aislamiento de impacto)?
- ¿Existe o se planea un endpoint de JWKS/introspección en `backendauth` a futuro, para no depender de distribución manual de la clave pública RSA?

---

## Archivos que se crearían/modificarían (cuando se implemente)

**Nuevos:**
- `src/identity_access/domain/value_objects/identidad_federada.py`
- `src/identity_access/domain/repositories/sso_provider_port.py`
- `src/identity_access/infrastructure/adapters/agrofusion_sso_adapter.py`
- `src/identity_access/application/use_cases/sesiones/sso_login_use_case.py`
- `src/identity_access/infrastructure/routers/agrofusion_integration_router.py`
- `src/shared/agrofusion_auth.py` (dependencia `verify_agrofusion_client`)
- `anotaciones/modulo_1/gaps_bd_sso_agrofusion.md` (documentar el DDL una vez aplicado, con los IDs reales confirmados en vivo)
- `anotaciones/curls_m01_sso_agrofusion.md` (curls de los endpoints nuevos, siguiendo el formato de `identity_access_curls.md`)

**Modificados:**
- `src/identity_access/domain/repositories/usuario_repository.py` — método nuevo `crear_minimo_sso`
- `src/identity_access/infrastructure/repositories/usuario_repository.py` — implementación
- `src/identity_access/infrastructure/routers/sesiones_routers.py` — endpoint `POST /sesiones/sso`
- `src/identity_access/infrastructure/dto/usuario_dto.py` — `SsoLoginDTO`
- `src/identity_access/infrastructure/schema/user_schema.py` — `LoginResponse.perfil_incompleto: bool = False`
- `src/identity_access/application/use_cases/sesiones/login_use_case.py` — extraer verificación de estado de cuenta a función compartida con `SsoLoginUseCase`
- `.env.example` — reemplazar bloque OAuth Google/Microsoft + `EXTERNAL_USERS_API_URL` por variables de AgroFusion
- `main.py` — montar `agrofusion_integration_router` condicionalmente
- `CLAUDE.md` — nueva sección breve enlazando a este documento, igual que se hizo para el plan de refresh tokens

---

## Verificación end-to-end propuesta (para cuando se implemente)

```bash
# Mecanismo A — requiere un sso_token RS256 real emitido por backendauth de AgroFusion
# (o, en dev, uno fabricado a mano con la clave privada de prueba) con aud=AGROFUSION_PROJECT_CODE
curl -isv -X POST http://localhost:8000/sesiones/sso \
  -H "Content-Type: application/json" \
  -d '{"sso_token":"<jwt_rs256>"}'
# → 200 con LoginResponse; si el correo no existía, perfil_incompleto=true

# Confirmar que sin las env vars de AgroFusion configuradas, el endpoint no rompe el resto del sistema
unset AGROFUSION_SSO_PUBLIC_KEY_PATH AGROFUSION_PROJECT_CODE
curl -isv -X POST http://localhost:8000/sesiones/sso -d '{"sso_token":"x"}'
# → 503 SSO_NO_CONFIGURADO

# Mecanismo B — simula al Hub de AgroFusion
curl -isv -X POST http://localhost:8000/integraciones/agrofusion/usuarios \
  -H "Content-Type: application/json" \
  -d '{"client_id":"agrofusion","client_secret":"<secreto>","email":"nuevo@ejemplo.com","nombre":"Ana","apellidos":"Pérez","tipo_identificacion":"CC","numero_identificacion":"123456","fecha_nacimiento":"1990-01-01","genero":"F","rol_codigo":"prod"}'
# → 201, cuenta ACTIVO completa

curl -isv -X POST http://localhost:8000/integraciones/agrofusion/token \
  -H "Content-Type: application/json" \
  -d '{"client_id":"agrofusion","client_secret":"<secreto>","email":"nuevo@ejemplo.com"}'
# → 200 {"access_token": "<jwt local>", "expires_in": ...}

# Confirmar que el JWT devuelto funciona exactamente igual que uno de login normal
curl -s http://localhost:8000/sesiones/me/permisos -H "Authorization: Bearer <access_token>" | jq
```
