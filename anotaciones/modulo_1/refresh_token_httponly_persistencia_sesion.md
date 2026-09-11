# Refresh token httpOnly — persistir sesión tras recarga (issue #9 frontend)

## Requisito

El JWT de acceso vive solo en memoria en el frontend (R-12/PR #7, correcto
contra XSS). Sin un mecanismo de refresco, cualquier recarga de página (F5,
pestaña nueva) pierde la sesión y fuerza un login nuevo aunque el access token
original todavía fuera válido. Diseño completo: `anotaciones/modulo_1/gaps_bd_refresh_tokens.md`
y `anotaciones/modulo_1/plan_access_refresh_tokens.md` (propuesta original,
5-ago-2026 — este cambio la implementa, con los ajustes documentados abajo).

## Decisiones que se apartan del diseño original

- **El access token se queda en 8h** (`JWT_EXPIRE_HOURS`, sin tocar). El
  documento original proponía acortarlo a 15 min, pero eso choca con RF-02
  (vigencia de 8h exigida explícitamente, con test dedicado
  `tests/shared/test_jwt_config.py`). El refresh token resuelve la
  persistencia tras recarga y evita el relogin al expirar las 8h — no cambia
  la ventana de exposición del access token en memoria.
- **IDs de evento 23/24** en vez de 20/21 (ya tomados por SSO desde el
  5-ago). Ver `gaps_bd_refresh_tokens.md`.
- **Sin `id_sesion` en el access token**: solo el refresh token lo necesita.
- Se eliminó el `CORSMiddleware` muerto de `src/shared/middlewares.py`
  (`allow_origins=["*"]` + `allow_credentials=True`, nunca registrado — el
  CORS real activo siempre fue el de `main.py`).

## Implementación

**Paso 0 (DB)**: ver `gaps_bd_refresh_tokens.md` — enum `refresco`, columnas
`tokens.hash_valor`/`tokens.id_sesion`/`sesiones.id_token_refresco`, FKs,
índices únicos parciales, catálogo de eventos 23/24. Aplicado en `sgpmp` (dev)
y en `pruebas` (integración) — ambas bases locales.

**Dominio**: `Token`/`Sesion` ganan los campos nuevos. `SesionRepository`
(puerto + impl) gana `buscar_token_por_hash`, `buscar_sesion_por_id`,
`crear_token_refresco`, `vincular_token_a_sesion`, `rotar_tokens`;
`invalidar_sesion`/`invalidar_todas_sesiones` ahora también revocan el
refresh token asociado (firma sin cambios, cubre los 7 call sites existentes
gratis). `CuentaRepository` gana `obtener_por_id` (gap real, no existía).

**`emitir_sesion`** (`sesion_comun.py`) gana `emitir_refresco: bool = True`:
mintea el refresh token para login normal y SSO; el camino M2M
(`EmitirTokenAgroFusionUseCase`) pasa `False` — no hay navegador ni cookie
posible en una llamada server-to-server.

**`RefreshTokenUseCase`** (nuevo): resuelve el token por hash SHA-256, valida
reuso (revoca la sesión completa — señal de robo), expiración, estado de
sesión e inactividad (30 min, mismo campo que `get_current_user`, sin
actualizarlo — un refresh no cuenta como actividad real), y rota ambos
tokens en el happy path.

**Router** (`sesiones_routers.py`): `POST /sesiones/` y `POST /sesiones/sso`
setean la cookie `refresh_token` (`HttpOnly`, `SameSite=Strict`, `Secure` en
producción, `path=/`); `DELETE /sesiones/` la borra; `POST /sesiones/refresh`
(nuevo, sin RBAC, sin `get_current_user`) la canjea por un access token
nuevo. El refresh token nunca entra al JSON de respuesta.

**`verify_token`** ahora distingue `ExpiredSignatureError` (`TOKEN_EXPIRADO`)
de `JWTError` genérico (`TOKEN_INVALIDO`) — necesario para que el frontend
sepa cuándo vale la pena refrescar en silencio vs forzar logout duro.

## Verificación

`pytest tests/` (48 tests, incluye `test_refresh_token.py` nuevo: cookie
ausente del JSON, rotación, reuso post-rotación mata la sesión completa,
expiración, logout borra la cookie) — todos verdes contra la base `pruebas`.
Curls manuales documentados en `identity_access_curls.md`.

## Pendiente / fuera de alcance

Frontend (`sgpmp-frontend`, rama separada): `withCredentials`, bootstrap con
refresh silencioso en `AuthContext`, retry automático en el interceptor de
axios ante `401 TOKEN_EXPIRADO`. Ver commits de esa rama.
