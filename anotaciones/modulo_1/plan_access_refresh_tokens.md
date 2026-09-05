# Plan: Access Token + Refresh Token para `identity_access`

> **Estado: propuesta / planeación. Nada de esto está implementado ni aplicado a la DB todavía.** Este documento registra el análisis de seguridad realizado sobre el mecanismo de autenticación actual y la propuesta de rediseño, para discusión con el equipo antes de implementar.

## Contexto

Hoy `POST /sesiones/` emite un único JWT de acceso con vigencia de **24h** (`JWT_EXPIRE_HOURS`, con default hardcodeado — ni siquiera está en `.env.example`), devuelto **solo en el body JSON** (`LoginResponse.token`). No existe `Set-Cookie`/`HttpOnly`/`SameSite` en ningún lugar del código (confirmado por grep exhaustivo sobre `src/`). Esto obliga al frontend a guardar el JWT en algo legible por JS (`localStorage`/`sessionStorage`/memoria) — si el frontend (una PWA de Ionic + React) sufre un XSS, ese token es robable y sirve hasta por 24h.

**No existe ningún mecanismo de refresh token** — ni tabla, ni endpoint, ni valor en `enum_token_tipo` (solo `recuperacion`, `verificacion_correo`, `acceso`). Al expirar o revocarse el JWT, el usuario debe re-loguearse con correo+contraseña desde cero.

Lo que sí está bien hecho hoy y no se toca: bloqueo de cuenta tras 5 intentos fallidos (15 min), política de sesión única (índice único parcial `uix_sesiones_activa_por_cuenta`), blacklist de tokens respaldada en DB (`tokens.fecha_uso`) verificada en cada request vía `get_current_user`, y logout que revoca el token de inmediato en servidor.

### Decisión propuesta

Separar dos tokens:
- **Access token**: JWT de vida corta (minutos), sigue viajando en el body JSON como hoy. El frontend lo guarda solo en memoria (nunca `localStorage`) — decisión de frontend, no de este documento.
- **Refresh token**: valor opaco de alta entropía (no JWT), entregado **exclusivamente vía cookie `HttpOnly; Secure; SameSite=Strict`**, invisible para JS incluso con XSS. Vive más tiempo (días). Un endpoint nuevo (`POST /sesiones/refresh`) lo cambia por un access token nuevo sin pedir credenciales, con **rotación** (cada uso invalida el refresh token usado y emite uno nuevo) y **detección de reuso** (presentar un refresh token ya rotado es señal de robo → se revoca toda la sesión).

Contexto de cliente: el frontend es una PWA Ionic + React — corre en motor de navegador, no es app nativa con Keychain/Keystore, así que las cookies `HttpOnly` funcionan de forma nativa y son la opción correcta. **Nota de riesgo a futuro** (no se diseña nada especial para esto hoy): si el frontend se empaqueta más adelante con Capacitor para tiendas de apps, las cookies cross-origin dentro del WebView pueden volverse poco confiables por ITP (Safari/WKWebView) — es un puente a cruzar si/cuando ocurra.

El patrón de offline planeado por frontend ("cachear lecturas + encolar escrituras para sincronizar al reconectar") es compatible sin cambios adicionales de backend: cualquier request real (lectura fresca o replay de una escritura encolada) requiere red de todos modos, momento en el cual se puede pedir un access token fresco vía `/sesiones/refresh` (la cookie viaja sola, la envía el navegador).

Esto cambia el contrato hoy documentado en `CLAUDE.md` ("dónde y cómo el frontend almacena el token... es decisión exclusiva del equipo de frontend y no afecta el contrato del backend") — el backend pasaría a gestionar directamente el transporte del refresh token. Ver la propuesta de párrafo de reemplazo al final de este documento.

### Dos hallazgos de DB verificados en vivo (vía MCP postgres) que determinan el diseño

1. **Trigger `trg_fn_token_un_solo_uso`** (`BEFORE UPDATE OF fecha_uso ON modulo1.tokens`) — rechaza con `RAISE EXCEPTION 'TOKEN_ALREADY_USED'` cualquier intento de tocar `fecha_uso` en una fila donde `OLD.fecha_uso IS NOT NULL`. **Consecuencia de diseño: la rotación debe crear filas nuevas en `tokens`, nunca reescribir la fila vieja.** Si se detecta reuso, la revocación debe operar sobre el par de tokens *vigente* de la sesión, nunca reintentar tocar el token viejo presentado (la DB lo bloquearía con excepción).
2. **`trg_fn_invalidar_sesiones_por_estado`** (`AFTER UPDATE OF id_estado_cuenta ON modulo1.cuentas_usuarios`) — si un admin bloquea/inactiva la cuenta, la DB ya marca `sesiones.es_activa = false` automáticamente. El use case de refresh hereda esto gratis con solo chequear `sesion.es_activa`.

`enum_token_tipo` actual confirmado en vivo: `recuperacion` (1), `verificacion_correo` (2), `acceso` (3) — sin valor de refresco.

---

## Paso 0 — Gaps de BD propuestos (pendientes de aplicar)

**Llamada A (`execute_sql`, sola — un valor de enum no puede usarse en la misma transacción que lo crea):**
```sql
ALTER TYPE modulo1.enum_token_tipo ADD VALUE IF NOT EXISTS 'refresco';
```

**Llamada B (`execute_sql`, separada, todo junto en una transacción):**
```sql
-- Hash del refresh token (nunca se guarda en texto plano) + backlink inverso a la sesión
ALTER TABLE modulo1.tokens
  ADD COLUMN IF NOT EXISTS hash_valor VARCHAR(64),
  ADD COLUMN IF NOT EXISTS id_sesion  INTEGER;

ALTER TABLE modulo1.tokens
  ADD CONSTRAINT fk_tokens_sesion FOREIGN KEY (id_sesion) REFERENCES modulo1.sesiones (id_sesion);

CREATE UNIQUE INDEX uix_tokens_hash_valor ON modulo1.tokens (hash_valor) WHERE hash_valor IS NOT NULL;
CREATE INDEX ix_tokens_id_sesion ON modulo1.tokens (id_sesion) WHERE id_sesion IS NOT NULL;

-- Segundo token por sesión (hoy sesiones.id_token es 1:1 UNIQUE; ahora hacen falta dos)
ALTER TABLE modulo1.sesiones
  ADD COLUMN IF NOT EXISTS id_token_refresco INTEGER;

ALTER TABLE modulo1.sesiones
  ADD CONSTRAINT fk_token_refresco FOREIGN KEY (id_token_refresco) REFERENCES modulo1.tokens (id_token);

CREATE UNIQUE INDEX uix_sesiones_token_refresco ON modulo1.sesiones (id_token_refresco) WHERE id_token_refresco IS NOT NULL;

-- Catálogo de eventos nuevos (modulo1.eventos.tipo_evento -> tipos_eventos)
INSERT INTO modulo1.tipos_eventos (id_tipo_evento, nombre, accion) VALUES
  (20, 'REFRESH_TOKEN_ROTADO', 'Renovación de sesión vía refresh token'),
  (21, 'REUSO_TOKEN_REFRESCO_DETECTADO', 'Reuso de refresh token detectado (posible robo) — sesión revocada');
```

Notas:
- `hash_valor VARCHAR(64)` sigue el patrón ya usado en el proyecto (`modulo4.versiones_modelos.hash_artefacto_sha256`, `modulo4.despliegues_ota.hash_modelo_sha256` — confirmado que existe ese precedente). Nullable: solo se llenaría para `token_tipo='refresco'`.
- `tokens.id_sesion` y `sesiones.id_token_refresco` se referenciarían mutuamente — ambas nullable, así que el orden de inserción (crear token sin sesión → crear sesión referenciando el token → UPDATE del token con `id_sesion`) no viola FKs.
- Las 126 sesiones y 141 tokens existentes (conteo al momento del análisis) quedarían con estas columnas en `NULL` — no hay refresh token histórico que reconstruir, esas sesiones simplemente no serían "refrescables" bajo el modelo viejo.
- `ALTER TYPE ... ADD VALUE` es prácticamente irreversible — confirmar entorno (dev vs. algo compartido) antes de aplicar.
- RBAC: sin cambios — ni login, ni refresh, ni logout usarían `require_permission`; no hay gaps en `modulo1.permisos`.

---

## Variables de entorno propuestas

Reemplazar `JWT_EXPIRE_HOURS` por dos variables (y de paso corregir dos inconsistencias documentales preexistentes: `CLAUDE.md` dice `JWT_SECRET` pero el código usa `SECRET_KEY`; `JWT_EXPIRE_HOURS` nunca estuvo en `.env.example` pese a ser leída por el código):

```env
# JWT — access token (vida corta, JWT firmado, viaja en el body)
JWT_ACCESS_EXPIRE_MINUTES=15

# Refresh token (vida larga, opaco, viaja solo por cookie HttpOnly)
JWT_REFRESH_EXPIRE_DAYS=7

# Opcional — solo si frontend y backend viven en subdominios distintos del mismo dominio raíz en producción
COOKIE_DOMAIN=
```

**Riesgo operativo a comunicar:** es un rename, no aditivo. Si el `.env` de un entorno desplegado no se actualiza, el código caería a los defaults (15 min / 7 días) sin crashear — pero el valor efectivo no sería el que ops cree haber configurado hasta que actualice el nombre de la variable.

En `src/shared/jwt.py`: `create_token`/`token_expiration()` cambiarían su `timedelta` de `hours=_EXPIRE_HOURS` a `minutes=_ACCESS_EXPIRE_MINUTES` (misma firma de función, no rompe a `LoginUseCase`). Se agregaría `refresh_token_expiration() -> datetime` nueva (`timedelta(days=_REFRESH_EXPIRE_DAYS)`).

---

## Diseño del flujo propuesto

### 1. Timeout de inactividad (30 min) — se quedaría en `get_current_user` Y se duplicaría en el refresh

- `get_current_user` seguiría siendo el único punto que observa actividad *real* de negocio — no se movería de ahí.
- Pero un refresh token robado usado contra una cuenta abandonada nunca pasa por `get_current_user`, así que `RefreshTokenUseCase` repetiría el mismo chequeo (mismo campo `cuentas_usuarios.ultimo_acceso`, misma ventana de 30 min como constante local, siguiendo el estilo ya existente de constantes por archivo tipo `MAX_INTENTOS`).
- **Un refresh exitoso NO actualizaría `ultimo_acceso`** — solo lo haría una llamada real de negocio vía `get_current_user`. Si el refresh también lo tocara, un timer puramente mecánico del frontend anularía el control de inactividad.

### 2. `POST /sesiones/refresh` (nuevo) — rotación y detección de robo

Nuevo `RefreshTokenUseCase.execute(refresh_token_raw, ip, user_agent) -> (jwt_acceso, exp_acceso, refresh_raw_nuevo, exp_refresco)`:

1. `hash_valor = sha256(refresh_token_raw).hexdigest()` → buscar en `tokens` por hash. No existe → 401 `REFRESH_TOKEN_INVALIDO`.
2. Resolver `sesion` (por `token.id_sesion`) y `cuenta` (por `sesion.id_cuenta_usuario`).
3. **Reuso/robo**: si `token.esta_usado()` → si la sesión sigue activa, invalidarla completa (mata el par de tokens *vigente*, nunca el token viejo presentado — el trigger lo bloquearía), registrar evento tipo 21, commit, **401 `REFRESH_TOKEN_REUTILIZADO`**.
4. **Expirado**: si `ahora > token.fecha_expiracion` → cerrar sesión si seguía activa (limpieza, no es robo), commit, **410 `REFRESH_TOKEN_EXPIRADO`**.
5. **Sesión inválida** (defensivo, ej. trigger de bloqueo de cuenta ya la mató): `sesion is None or not sesion.es_activa` → **401 `SESION_INVALIDA`**.
6. **Inactividad** (ver punto 1): si excede 30 min → invalidar sesión, commit, **401 `SESION_EXPIRADA_INACTIVIDAD`**.
7. **Happy path**: generar nuevo token de acceso (`crear_token_acceso(token_expiration(), id_sesion=...)` + `create_token(...)`) y nuevo refresh (`secrets.token_urlsafe(32)` + su hash → `crear_token_refresco(refresh_token_expiration(), hash, id_sesion=...)`); `rotar_tokens(sesion, ...)` marcaría ambos tokens viejos como usados, actualizaría los punteros de la sesión y extendería `fecha_finalizacion` en una sola operación; registrar evento tipo 20 exitoso; commit.

`secrets.token_urlsafe(32)` y `hashlib.sha256(...).hexdigest()` ya son los patrones usados en `solicitar_recuperacion_use_case.py` y `evento_repository.py` respectivamente — no serían elecciones nuevas para el proyecto.

**Nota de borde aceptada:** si una sesión ya murió por otra vía (logout, nuevo login, cambio de contraseña) y luego se repite ese refresh token ya muerto, la rama de "reuso" también dispararía aunque no sea un robo real — el estado final es idéntico (sesión ya muerta), el único costo es un evento de auditoría etiquetado como reuso que en realidad fue benigno. Aceptado como trade-off, no amerita una columna adicional de "sucesor" solo para distinguir ese caso.

### 3. Cambios propuestos en endpoints existentes

**Cookie compartida** (constante en el router): `NOMBRE_COOKIE_REFRESH = "refresh_token"`, `httponly=True`, `secure=(os.getenv("ENV") == "production")` (mismo patrón que ya usa `main.py` para CORS — hardcodear `True` rompería pruebas por HTTP en dev), `samesite="strict"`, **`path="/"`**, `max_age` según `refresh_token_expiration()`.

> **Por qué `path="/"` y no `path="/sesiones"`:** confirmado en `main.py:275` que `root_path="/api"` — en producción el proxy externo expone `/api/sesiones/...` pero la app enruta internamente `/sesiones/...`. El `Set-Cookie` que emite la app usa el path *interno*; el navegador evalúa el matching contra la URL *externa* (`/api/sesiones/refresh`). Con `path="/sesiones"` la cookie no calzaría y se perdería silenciosamente **solo en producción** (funcionaría en dev, donde no hay prefijo). `path="/"` evita el problema — la cookie sigue siendo `HttpOnly` e invisible a JS, el costo es que viajaría en cada request (igual que ya hace el header `Authorization`).

- **`POST /sesiones/` (login)**: el router ganaría `response: Response`. `LoginUseCase.execute` extendería su tupla de retorno agregando al final `(refresh_raw, exp_refresco)` (sin reordenar lo existente). Internamente también mintearía el refresh token y llamaría `crear_sesion(..., id_token_refresco=...)`. El router haría `response.set_cookie(...)`; el body JSON (`LoginResponse`) seguiría devolviendo solo `token`/`tipo`/`expira_en`/`message` — **el refresh token nunca entraría al JSON**.
- **`DELETE /sesiones/` (logout)**: `LogoutUseCase` no cambiaría (su única llamada, `invalidar_sesion`, ya blacklistearía el refresco gracias al cambio de implementación del repository). Solo el router cambiaría: ganaría `response: Response` y llamaría `response.delete_cookie(NOMBRE_COOKIE_REFRESH, path="/")` tras el logout — **el `path` debe ser idéntico al de `set_cookie`**, o el navegador no reconoce la cookie y no la borra.
- **`POST /sesiones/refresh` (nuevo)**: sin RBAC, sin `Depends(get_current_user)` (ese es justo el punto — reemplaza la necesidad de credenciales). Leería `refresh_token: Optional[str] = Cookie(None)`; si falta → 401 `REFRESH_TOKEN_REQUERIDO`. Reutilizaría `LoginResponse` como schema de salida (misma forma exacta) — no crearía un schema redundante.

### 4. Fix propuesto de `verify_token` (distinguir expirado de inválido)

`ExpiredSignatureError` es subclase de `JWTError` en `python-jose` (confirmado en el venv del proyecto) — el `except` específico debe ir antes del genérico:

```python
from jose import ExpiredSignatureError, JWTError, jwt

def verify_token(token: str) -> dict:
    try:
        return jwt.decode(token, _SECRET_KEY, algorithms=[_ALGORITHM])
    except ExpiredSignatureError:
        raise AuthenticationError(code="TOKEN_EXPIRADO", message="El token de acceso ha expirado.")
    except JWTError:
        raise AuthenticationError(code="TOKEN_INVALIDO", message="El token es inválido o está mal formado.")
```

Esto es lo que le permitiría al frontend distinguir "llama a `/refresh` en silencio" de "fuerza logout duro".

### Tabla de códigos de error (contrato propuesto para frontend)

| Código | HTTP | Origen | Acción esperada del frontend |
|---|---|---|---|
| `TOKEN_EXPIRADO` | 401 | `verify_token` (nuevo) | Llamar `/sesiones/refresh` en silencio y reintentar |
| `TOKEN_INVALIDO` | 401 | `verify_token` | Logout duro |
| `TOKEN_REVOCADO` | 401 | `get_current_user` (sin cambios) | Logout duro |
| `SESION_EXPIRADA_INACTIVIDAD` | 401 | `get_current_user` y `RefreshTokenUseCase` | Logout duro |
| `REFRESH_TOKEN_REQUERIDO` | 401 | router `/refresh` (nuevo) | Logout duro (no hay cookie) |
| `REFRESH_TOKEN_INVALIDO` | 401 | `RefreshTokenUseCase` (nuevo) | Logout duro |
| `REFRESH_TOKEN_REUTILIZADO` | 401 | `RefreshTokenUseCase` (nuevo) | Logout duro + aviso de actividad sospechosa |
| `REFRESH_TOKEN_EXPIRADO` | 410 | `RefreshTokenUseCase` (nuevo) | Logout duro, ir a login |
| `SESION_INVALIDA` | 401 | `RefreshTokenUseCase` (nuevo, defensivo) | Logout duro |

---

## Archivos que se crearían/modificarían (cuando se implemente)

**Nuevos:**
- `anotaciones/modulo_1/gaps_bd_refresh_tokens.md` (documentar el DDL una vez aplicado)
- `src/identity_access/application/use_cases/sesiones/refresh_token_use_case.py`

**Modificados:**
- `src/identity_access/infrastructure/models/enums_models.py` — `EnumTokenTipo.REFRESCO = 'refresco'`
- `src/identity_access/infrastructure/models/tokens_model.py` — columnas `hash_valor`, `id_sesion`
- `src/identity_access/infrastructure/models/sesiones_model.py` — columna `id_token_refresco`
- `src/identity_access/domain/entities/token.py` — campos `hash_valor`, `id_sesion` (`Optional`, default `None`)
- `src/identity_access/domain/entities/sesion.py` — campo `id_token_refresco: Optional[int] = None`
- `src/identity_access/domain/repositories/sesion_repository.py` — métodos nuevos: `buscar_token_por_hash`, `buscar_sesion_por_id`, `crear_token_refresco`, `vincular_tokens_a_sesion`, `rotar_tokens`; modificar firma de `crear_token_acceso` (+`id_sesion` opcional) y `crear_sesion` (+`id_token_refresco` requerido)
- `src/identity_access/domain/repositories/cuenta_repository.py` — método nuevo `obtener_por_id(id_cuenta_usuario)`
- `src/identity_access/infrastructure/repositories/sesion_repository.py` — implementación de todo lo anterior; `invalidar_sesion`/`invalidar_todas_sesiones` también marcarían `fecha_uso` en el token de refresco asociado (firma no cambia — los 5 llamadores existentes, `login_use_case`, `logout_use_case`, `editar_perfil_use_case`, `restablecer_contrasena_use_case`, `cambiar_contrasena_use_case`, `gestionar_cuenta_use_case`, no necesitarían tocarse)
- `src/identity_access/infrastructure/repositories/cuenta_repository.py` — implementación de `obtener_por_id`
- `src/identity_access/application/use_cases/sesiones/login_use_case.py` — mintearía también el refresh token; tupla de retorno extendida
- `src/identity_access/infrastructure/dependencies.py` — la rama de expiración por inactividad usaría `SqlAlchemySesionRepository(db).invalidar_sesion(...)` en vez de mutar el ORM inline
- `src/shared/jwt.py` — nuevas env vars, `refresh_token_expiration()`, fix de `verify_token`
- `src/identity_access/infrastructure/routers/sesiones_routers.py` — cookie en login/logout, endpoint `/refresh` nuevo
- `.env.example` — bloque `# JWT` actualizado
- `CLAUDE.md` — sección de env vars (`SECRET_KEY` en vez de `JWT_SECRET`, nuevas vars) + párrafo "Autenticación frontend → backend" (ver propuesta abajo)
- `anotaciones/modulo_1/identity_access_curls.md` — se extendería con los curls de refresh

**Limpieza opcional fuera de alcance** (solo mencionar, no ejecutar): `src/shared/middlewares.py::setup_middlewares` define un `CORSMiddleware` con `allow_origins=["*"] + allow_credentials=True`, pero es código muerto — nada lo invoca; el CORS real activo es el de `main.py`. Se podría eliminar como limpieza aparte, sin relación con este cambio.

### Párrafo de reemplazo propuesto para CLAUDE.md

```
**Autenticación frontend → backend**
El backend usa dos tokens con transporte distinto (diseño completo y contrato
exacto en `anotaciones/modulo_1/plan_access_refresh_tokens.md`):
- **Access token** (JWT, vida corta — `JWT_ACCESS_EXPIRE_MINUTES`): viaja en el
  body JSON de `POST /sesiones/` y `POST /sesiones/refresh`; el frontend lo
  envía en `Authorization: Bearer <token>`. Dónde lo guarda en memoria (nunca
  `localStorage`/`IndexedDB`) es decisión del equipo de frontend.
- **Refresh token** (opaco, vida larga — `JWT_REFRESH_EXPIRE_DAYS`): gestionado
  exclusivamente por el backend vía cookie `HttpOnly; Secure; SameSite=Strict`,
  invisible para JS. El frontend nunca la lee ni la transporta manualmente.
  Esta parte del mecanismo sí es contrato de backend, no decisión de frontend.

Ante un `401 TOKEN_EXPIRADO`, el frontend debe llamar `POST /sesiones/refresh`
(sin body) para obtener un access token nuevo antes de reintentar la request
original.
```

---

## Verificación end-to-end propuesta (para cuando se implemente)

Se agregaría como nueva sección en `anotaciones/modulo_1/identity_access_curls.md`. Usa cookie jar (`-c`/`-b`) porque `curl` no persiste cookies solo.

```bash
# 1. Login — guarda la cookie de refresco en jar.txt
curl -isv -c jar.txt -X POST http://localhost:8000/sesiones/ \
  -H "Content-Type: application/json" \
  -d '{"correo_electronico":"usuario@ejemplo.com","contrasena":"Contrasena1!"}' | grep -i "set-cookie\|token"
# → confirmar Set-Cookie presente y que el JSON NO contiene el refresh token

# 2. Guardar copia del jar ANTES de rotar (para el paso de reuso más abajo)
cp jar.txt jar_viejo.txt

# 3. Forzar expiración del access token sin esperar 15 min (dev, vía MCP postgres):
#    UPDATE modulo1.tokens SET fecha_expiracion = now() - interval '1 minute' WHERE id_token = <jti del JWT>;
curl -s http://localhost:8000/sesiones/me/permisos -H "Authorization: Bearer <ACCESS_TOKEN>" | jq
# → 401 TOKEN_EXPIRADO

# 4. Refresh — usa la cookie del jar, sin Authorization header
curl -isv -b jar.txt -c jar.txt -X POST http://localhost:8000/sesiones/refresh | grep -i "set-cookie\|token"
# → nuevo access token en el body; Set-Cookie con valor DISTINTO al original

# 5. Confirmar que el nuevo access token funciona
curl -s http://localhost:8000/sesiones/me/permisos -H "Authorization: Bearer <NUEVO_ACCESS_TOKEN>" | jq

# 6. Detección de robo — reusar el refresh token VIEJO (jar_viejo.txt, ya rotado en el paso 4)
curl -isv -b jar_viejo.txt -X POST http://localhost:8000/sesiones/refresh
# → 401 REFRESH_TOKEN_REUTILIZADO

# 7. Confirmar que TODA la sesión murió
curl -s http://localhost:8000/sesiones/me/permisos -H "Authorization: Bearer <NUEVO_ACCESS_TOKEN>" | jq
# → 401 TOKEN_REVOCADO
curl -isv -b jar.txt -X POST http://localhost:8000/sesiones/refresh
# → 401 (sesión ya muerta)

# 8. Logout — confirmar limpieza de cookie
curl -isv -c jar2.txt -X POST http://localhost:8000/sesiones/ -H "Content-Type: application/json" -d '{...}'
curl -isv -b jar2.txt -c jar2.txt -X DELETE http://localhost:8000/sesiones/ -H "Authorization: Bearer <ACCESS_TOKEN>" | grep -i set-cookie
# → Set-Cookie: refresh_token=; Max-Age=0
curl -isv -b jar2.txt -X POST http://localhost:8000/sesiones/refresh
# → 401
```

**Verificación adicional recomendada** (por el gotcha de `path` + `root_path="/api"`): repetir el flujo contra un despliegue real detrás del proxy inverso (no solo `uvicorn` local), confirmando con `curl -v` que el `Set-Cookie` efectivamente vuelve en requests a `/api/sesiones/refresh`.
