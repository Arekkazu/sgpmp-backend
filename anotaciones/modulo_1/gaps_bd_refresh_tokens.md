# Gaps de BD — Refresh token httpOnly (Paso 0)

Aplicado en dev (`sgpmp`) y en la base de pruebas de integración (`pruebas`) el
2026-08-17, vía MCP postgres / psql, previo a escribir código. Referencia de
diseño original: `anotaciones/modulo_1/plan_access_refresh_tokens.md`
(5-ago-2026, nunca implementado hasta ahora). No gestionado por migraciones
(igual que el resto de gaps de `modulo1`, ver otros archivos `gaps_bd_*` en
este directorio) — este repo no usa Alembic en la práctica (carpeta `alembic/`
presente pero con 0 revisiones).

Motivación: `AuthContext.tsx` del frontend guarda el JWT solo en memoria
(R-12/PR #7 del frontend) — correcto contra XSS, pero cualquier recarga de
página pierde la sesión. Sin refresh token no hay forma de recuperarla sin
pedir credenciales de nuevo. Ver issue #9 del repo frontend.

## 1. Nuevo valor de enum `refresco`

Aplicado solo (un valor de enum no puede usarse en la misma transacción que lo crea):

```sql
ALTER TYPE modulo1.enum_token_tipo ADD VALUE IF NOT EXISTS 'refresco';
```

Confirmado en vivo tras aplicar: `enum_token_tipo` = `recuperacion`,
`verificacion_correo`, `acceso`, `refresco`.

## 2. Columnas nuevas + FKs + índices

```sql
ALTER TABLE modulo1.tokens
  ADD COLUMN IF NOT EXISTS hash_valor VARCHAR(64),
  ADD COLUMN IF NOT EXISTS id_sesion  INTEGER;

ALTER TABLE modulo1.tokens
  ADD CONSTRAINT fk_tokens_sesion FOREIGN KEY (id_sesion) REFERENCES modulo1.sesiones (id_sesion);

CREATE UNIQUE INDEX uix_tokens_hash_valor ON modulo1.tokens (hash_valor) WHERE hash_valor IS NOT NULL;

ALTER TABLE modulo1.sesiones
  ADD COLUMN IF NOT EXISTS id_token_refresco INTEGER;

ALTER TABLE modulo1.sesiones
  ADD CONSTRAINT fk_token_refresco FOREIGN KEY (id_token_refresco) REFERENCES modulo1.tokens (id_token);

CREATE UNIQUE INDEX uix_sesiones_token_refresco ON modulo1.sesiones (id_token_refresco) WHERE id_token_refresco IS NOT NULL;
```

- `hash_valor VARCHAR(64)`: hash SHA-256 del valor en claro del refresh token
  (nunca se guarda en texto plano) — mismo patrón ya usado en
  `modulo4.versiones_modelos.hash_artefacto_sha256`. Nullable: solo se llena
  para `token_tipo='refresco'`.
- `tokens.id_sesion` y `sesiones.id_token_refresco` se referencian mutuamente
  — ambas nullable, así que el orden de inserción (crear token sin sesión →
  crear sesión referenciando el token → `UPDATE` del token con `id_sesion`)
  no viola FKs. Confirmado en `SqlAlchemySesionRepository` (`crear_token_refresco`
  → `crear_sesion` → `vincular_token_a_sesion`).
- **Sin `id_sesion` en el access token** (simplificación sobre el diseño
  original): solo el refresh token necesita el backlink para resolver la
  sesión a partir del hash. El access token sigue encontrando su sesión vía
  `sesiones.id_token`, como ya hacía antes de este cambio.
- Los modelos ORM (`tokens_model.py`, `sesiones_model.py`) **no declaran
  `relationship`** entre `Tokens` y `Sesiones`: con tres columnas FK cruzadas
  entre ambas tablas (`sesiones.id_token`, `sesiones.id_token_refresco`,
  `tokens.id_sesion`), cualquier `relationship()` sin desambiguar dispara
  `AmbiguousForeignKeysError` al configurar los mappers. Ningún repository
  navega estas relaciones (todo es `db.get()`/query explícito), así que se
  optó por no declararlas — mismo patrón "sin relationships" ya usado en
  varios modelos de `supplies` generados con sqlacodegen.

## 3. Catálogo de eventos de auditoría

Los IDs 20/21 que proponía el diseño original (5-ago) ya estaban tomados por
el trabajo de SSO (`LOGIN_SSO_EXITOSO`, `PROVISION_SSO_MINIMA`) hecho después
de esa fecha; 22 también (`PROVISION_AGROFUSION_SYNC`). Se usan 23/24
(confirmados libres vía MCP postgres antes de insertar). `accion` está
limitado a `VARCHAR(50)` — los textos originales propuestos lo excedían, se
recortaron sin tildes:

```sql
INSERT INTO modulo1.tipos_eventos (id_tipo_evento, nombre, accion) VALUES
  (23, 'REFRESH_TOKEN_ROTADO', 'Renovacion de sesion via refresh token'),
  (24, 'REUSO_TOKEN_REFRESCO_DETECTADO', 'Reuso de refresh token detectado - sesion revocada');
```

## 4. RBAC

Sin cambios — login, refresh y logout no usan `require_permission` (la
confianza la da la cookie/credenciales, no un rol de sgpmp).

## 5. Triggers de BD relevantes (verificados en vivo, sin cambios)

El diseño depende de dos triggers ya existentes. Sus **nombres reales**
difieren de los usados en el documento de diseño original (que citaba el
nombre de la función como si fuera el del trigger):

| Trigger | Tabla | Evento | Función |
|---|---|---|---|
| `trg_token_un_solo_uso` | `modulo1.tokens` | `BEFORE UPDATE OF fecha_uso` | `modulo1.trg_fn_token_un_solo_uso()` |
| `trg_invalidar_sesiones_por_estado` | `modulo1.cuentas_usuarios` | `AFTER UPDATE OF id_estado_cuenta` | `modulo1.trg_fn_invalidar_sesiones_por_estado()` |

Consecuencias de diseño (sin cambios respecto al documento original):
- La rotación (`rotar_tokens`) crea filas nuevas en `tokens` y solo marca
  `fecha_uso` una vez por token — nunca reescribe una fila ya usada (el
  trigger lo rechazaría con `TOKEN_ALREADY_USED`). La detección de reuso
  revoca el par de tokens *vigente* de la sesión, nunca reintenta tocar el
  token viejo presentado.
- Si un admin bloquea/inactiva una cuenta, la DB ya marca
  `sesiones.es_activa = false` automáticamente — `RefreshTokenUseCase`
  hereda esto gratis con solo chequear `sesion.es_activa`.

## 6. Deuda pre-existente encontrada, no corregida (fuera de alcance)

`VITE_API_BASE_URL` del frontend apunta a `.../api` en dev, pero `root_path="/api"`
en `main.py` es cosmético (solo afecta URLs generadas en OpenAPI/docs) — no crea
un prefijo de ruteo real salvo detrás de un proxy inverso de verdad. El usuario
confirmó que no hay tal proxy local hoy y pidió no tocar el `.env` del frontend
como parte de este cambio. La cookie usa `path="/"` precisamente para no
depender de esta capa (funciona igual con o sin el prefijo).
