# TC-M09-G94 (#309) — GET /configuracion/interfaz/contexto respondió 401

## Qué se verificó

`GET /configuracion/interfaz/contexto` (`src/configuration/infrastructure/routers/contexto_interfaz_router.py`)
usa el mismo mecanismo de autenticación que el resto de la API: `get_current_user`
(`src/identity_access/infrastructure/dependencies.py`) valida el JWT y comprueba
que la fila del token en `modulo1.tokens` siga vigente (`fecha_uso IS NULL`).
El endpoint no tiene ninguna condición propia sobre el token — RBAC via
`require_permission(22, 2)` es lo único adicional, y ese solo produce 403, nunca 401.

Un access token deja de ser válido (`fecha_uso` se marca) exclusivamente cuando:

- se rota vía `POST /sesiones/refresh` (el token anterior se invalida al emitir el nuevo par), o
- se cierra sesión, o
- se detecta reuso de un refresh token ya rotado (revocación completa de la sesión).

## Por qué el 401 es la respuesta correcta, no un defecto

El caso #309 describe: login exitoso → `/dashboard` carga bien → una llamada directa a
`/configuracion/interfaz/contexto` "con el Bearer de la sesión autenticada" responde 401.
No hay ninguna mención de haber llamado `/sesiones/refresh` entre medio.

El diseño de este backend (documentado en `CLAUDE.md`, sección de autenticación) es que el
access token vive **solo en memoria** en el frontend (nunca `localStorage`), así que cualquier
recarga de página / nueva navegación completa pierde el token en memoria y el `AuthContext`
del frontend (`sgpmp-frontend/src/shared/auth/AuthContext.tsx`, efecto en la línea ~119)
dispara automáticamente un refresh silencioso contra la cookie `httpOnly` para recuperar la
sesión — lo cual **rota** el access token existente.

Si el caso de prueba captura el Bearer del login y lo reutiliza directamente vía `cy.request()`
tras una navegación de página completa (p.ej. `cy.visit('/dashboard')` seguido de otro
`cy.visit`/recarga antes de la llamada a contexto), ese refresh silencioso ya rotó el token en
segundo plano y el Bearer capturado quedó revocado — exactamente el mismo mecanismo que ya
corrigió `#1827` (backend PR #65) para llamadas concurrentes de refresh, aplicado aquí a un
cliente que retiene un token viejo en vez de leer el nuevo.

Se agregó una prueba de regresión (`tests/integration/test_refresh_token.py::test_access_token_anterior_a_un_refresh_queda_revocado`)
que reproduce exactamente esto: login → refresh exitoso → reutilizar el access token
**anterior** al refresh contra un endpoint protegido → se confirma `401 TOKEN_REVOCADO`
(no 500, no 200 con datos obsoletos). Esto es el comportamiento de seguridad esperado
(evita que un token robado/viejo siga sirviendo tras una rotación).

## Qué no es esto

No es el mismo root cause que #308 (ese era un 500 no controlado en el refresh por un catálogo
`modulo1.tipos_eventos` incompleto — ya corregido en la rama `fix/sesiones-tc-m09-g90-refresh-http-500`,
PR #369, retargeteado a `fix/m09`). Aquí el refresh en sí funciona; el 401 es el resultado
correcto de usar un token que ya fue rotado.

## Recomendación para QA

Si la colección/Cypress captura el Bearer del login y lo reutiliza en pasos posteriores sin
pasar por el flujo real de la SPA (que sí actualiza el token en memoria al refrescar), conviene
releer el token vigente antes de la llamada a `/configuracion/interfaz/contexto`, o ejecutar el
flujo end-to-end por la UI en vez de mezclar `cy.request()` directo con navegación de página
completa entre pasos.
