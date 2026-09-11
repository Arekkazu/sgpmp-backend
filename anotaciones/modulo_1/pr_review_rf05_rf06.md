# Revisión — PR #16 "RF-05/06: unificar autorización de perfil y gestión de cuenta"

Rama: `feature/rf05-rf06-unified-rbac-account-profile` (GitHub PR #16, título
interno "#8 RF-05/06") → `dev`. Revisión hecha el 2026-08-15 sobre
`review/pr16-rf05-rf06`, una rama local = PR branch + merge de `dev` + un
commit de corrección.

## Resumen

El PR separa correctamente la edición de perfil propio (`PATCH /usuarios/me`,
solo autenticación) de la edición administrativa (`PATCH /usuarios/{id}`,
RBAC) y de la gestión de estado de cuenta (`POST /usuarios/{id}/gestionar`,
única vía para activar/inactivar/bloquear/eliminar). Generaliza la protección
de "último administrador" a "último usuario activo de un rol protegido"
(`roles.es_protegido`) en vez de un `id_rol == 1` fijo. Esa parte del diseño
es correcta y sigue el patrón RBAC de `CLAUDE.md`.

Pero la rama **no estaba lista para mergear tal cual**: estaba desactualizada
por 8 commits y escondía dos problemas reales que no se habrían notado sin
comparar contra el estado de la base de datos y el código previo. Ambos se
corrigieron como parte de esta revisión (ver commits en
`review/pr16-rf05-rf06`, sin aplicar todavía a la rama remota del PR ni a
`dev` — pendiente de tu confirmación para el push).

## Hallazgos

### 1. Rama desactualizada (resuelto — merge local)
Partía de `714d32f` (8 commits detrás de `dev`). GitHub marcaba
`mergeable: CONFLICTING`. Único conflicto real:
`src/identity_access/infrastructure/routers/usuarios_routers.py`, mecánico
(RF-11 quitó el `GET /usuarios/` legacy sin auth; esta rama no lo sabía).
Un segundo conflicto apareció al mergear `dev` actualizado, en
`editar_perfil_use_case.py` (RF-01/08/09 cambió a hashear el token de
verificación de correo antes de guardarlo). Resueltos ambos conservando el
contenido de `dev` donde corresponde (endpoint legacy eliminado, token
hasheado) más el refactor completo del PR.

### 2. Regresión: finalización de perfil SSO eliminada (resuelto — restaurado)
El refactor de `EditarPerfilDTO`/`EditarPerfilAdminDTO`/`EditarPerfilUseCase`
quitó por completo `tipo_identificacion`, `numero_identificacion`,
`fecha_nacimiento`, `genero` y el auto-activado de cuentas `PENDIENTE_DATOS`
— funcionalidad ya implementada y verificada end-to-end en la feature SSO
AgroFusion, sin ningún test que la cubriera. Se restauró en
`review/pr16-rf05-rf06` (commit `fix(rf05): restaurar finalización de perfil
SSO...`), preservando el resto del refactor del PR (los campos de estado y
las transiciones siguen viviendo exclusivamente en `gestionar_cuenta_use_case.py`,
como el PR pretendía).

### 3. Escalada de privilegios (resuelto — permisos revocados en dev y `pruebas`)
Ver detalle completo en `pr16_rf05_rf06_paso0_gap_rbac.md`. Resumen: el nuevo
`require_permission(1, 3)` en el endpoint admin coincidía con un permiso que
la base de datos ya concedía también a Productor, Veterinario, Ingeniero de
Campo y Contador. Confirmado en vivo (antes del fix): un Productor podía
promover a cualquier usuario a Administrador vía `PATCH /usuarios/{id}`.
Corregido revocando esos 4 permisos vía la API de roles (con registro de
auditoría), en `sgpmp` (dev) y en la base local `pruebas`.

### 4. Hallazgo adicional, fuera de alcance de este PR (solo reportado, no corregido)
Al verificar en vivo la finalización parcial de un perfil SSO (completar solo
2 de los 6 campos requeridos, escenario realista si el frontend envía
actualizaciones progresivas), `PATCH /usuarios/me` responde `500` sin
capturar: `UsuarioResponse` (`src/identity_access/infrastructure/schema/user_schema.py`)
declara `tipo_identificacion`, `numero_identificacion` y `genero` como
obligatorios, pero la entidad `Usuario` permite los tres en `None` mientras la
cuenta está `PENDIENTE_DATOS`. Esto es preexistente a este PR (viene de la
feature SSO, PR #10) y no lo introduce ni lo agrava el PR #16 — se deja
documentado aquí porque es la misma ruta de código que este PR toca, pero no
se corrigió por no ser parte del encargo de esta revisión.

## Tests

- Unit: `pytest tests/identity_access/ tests/shared/` → **18 passed**.
- Integración (`TEST_DATABASE_URL` → `postgresql://postgres:dev@localhost:5432/pruebas`):
  `pytest tests/ -m integration` → **10 passed** (incluye los 3 tests nuevos
  del PR: separación `/me` vs `/{id}` con RBAC, y protección del último
  usuario activo de un rol protegido).

## Verificación en vivo (además de la suite de tests)

Todo contra `pruebas`, usando los fixtures existentes de
`tests/integration/conftest.py` (transacción por test, revertida al salir —
no deja residuos):

- Escalada de privilegios: reproducida (200 antes del fix) y cerrada (403
  `ACCESO_DENEGADO` después, para Productor/Veterinario/Ingeniero de
  Campo/Contador).
- SSO: completar los 6 campos sobre una cuenta `PENDIENTE_DATOS` → cuenta pasa
  a `ACTIVO` automáticamente. Un usuario no-admin fuera de `PENDIENTE_DATOS`
  que intenta enviar campos de identificación recibe `403
  SIN_PERMISO_CAMPOS_IDENTIFICACION`.
- **Superado por RF-04/06:** el cambio de rol conserva la sesión y el rol
  vigente se consulta en base de datos en cada request. Ver
  `rf04_rf06_cambio_rol_sin_relogin.md`.
- Concurrencia optimista: versión desincronizada → `412`.
- Correo duplicado → `409`.
- Cambio de correo propio → cuenta pasa a `PENDIENTE`, se dispara el envío de
  verificación (interceptado con `monkeypatch`, no se envió correo real).
- `POST /usuarios/{id}/gestionar`: motivo obligatorio en acciones críticas
  (`400 MOTIVO_REQUERIDO`), transición inválida (`422 TRANSICION_INVALIDA`),
  `inactivar` invalida la sesión activa del usuario afectado.

## Pendiente de decisión (no ejecutado en esta revisión)

- **Push**: los 3 commits de `review/pr16-rf05-rf06` (merge de `dev` + fix
  SSO) no se subieron a `feature/rf05-rf06-unified-rbac-account-profile` ni
  se abrió PR/comentario hacia el autor. Falta decidir si se sube tal cual,
  se le pide al autor (Leandro) que lo incorpore, o se abre un PR aparte.
- **Hallazgo #4** (`UsuarioResponse` con campos SSO obligatorios): sin
  corregir, documentado para que se priorice por separado.
- **`docs/curls`**: se agregó un ejemplo de finalización de perfil SSO a
  `identity_access_curls.md` para que quede documentado junto con el resto de
  `PATCH /usuarios/me`.
