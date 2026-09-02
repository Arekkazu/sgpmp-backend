# Bug #1827 — Invalidación intermitente de sesión (401) al navegar tras login

**Reportado por:** Santiago García Cuevas (QA), ambiente TEST (Dockploy).
**Evidencia:** `BLOQUEADO-BUG-SESION-401-RF04-RF06-RF10-RF11-RF12` (trazas
Playwright RF-03/RF-06/RF-10, todas con 401 en `refresh`/`me`/`permisos` a los
pocos segundos de un login exitoso, pantalla en blanco).

## Diagnóstico

Login exitoso, pero casi de inmediato el backend responde 401 en `refresh` y en
llamadas autenticadas (`me`, `permisos`). Intermitente: la misma ruta a veces
carga bien y a veces no. QA ya sospechaba una condición de carrera.

### Causa raíz — frontend

`AuthProvider` (`sgpmp-frontend/src/shared/auth/AuthContext.tsx`) intenta un
refresh silencioso (`POST /sesiones/refresh`) en **todo** mount sin token en
memoria — incluida `/login`, antes de que el usuario envíe el formulario. Si el
navegador todavía conserva una cookie `refresh_token` vigente de una sesión
anterior de la misma cuenta (pestaña previa, corrida de prueba anterior con el
mismo usuario `adminplaywright@gmail.com`), ese refresh silencioso compite sin
ninguna coordinación contra el login explícito que el usuario está enviando en
paralelo.

El backend solo permite **una sesión activa por cuenta** (login invalida
cualquier sesión previa activa — `sesion_comun.py::emitir_sesion`). Cuando el
refresh silencioso y el login corren casi al mismo tiempo:

- Si el login "gana" la carrera en el backend, el refresh silencioso —que
  usaba el token viejo— cae limpio en 401 `REFRESH_TOKEN_REUTILIZADO`, sin
  tocar la sesión nueva. No hay síntoma visible.
- Si el refresh silencioso llega primero y rota el token de la sesión vieja,
  el login que llega después la encuentra activa, la invalida y crea una
  sesión completamente nueva. Cuál de las dos respuestas HTTP el navegador
  termina aplicando último (y por lo tanto qué JWT/cookie quedan en memoria)
  depende de la latencia relativa de cada request, no del orden de commit en
  la base. Si el navegador aplica la respuesta del refresh silencioso
  *después* de la del login, el frontend queda con un JWT y una cookie que el
  backend ya invalidó — la siguiente petición autenticada (`me`, `permisos`)
  cae en 401 y el interceptor limpia la sesión (pantalla en blanco).

Ninguna página pública (`/login`, `/registro`, `/activar`, etc.) lee
`token`/`isBootstrapping` del contexto — el restauro de sesión ahí no cumplía
ningún propósito, solo abría esta ventana de carrera. Se corrigió restringiendo
el refresh silencioso a rutas protegidas (que es el único caso real: recargar
—F5— una pantalla ya autenticada). Fix + test en
`sgpmp-frontend` (PR referenciado en el issue del bug).

### Gap de concurrencia — backend (defensa en profundidad)

Al revisar `RefreshTokenUseCase`/`SqlAlchemySesionRepository` para este bug se
encontró que `buscar_token_por_hash` (usado para detectar reuso/rotar) era un
`SELECT` plano, sin `SELECT ... FOR UPDATE` — el único punto de escritura
concurrente del módulo sin ningún lock, a diferencia de todo el resto del
código (`exportacion_auditoria_repository.py`, `acumulado_ciclo_repository.py`,
`transferencia_repository.py`, `evento_repository.py`, todos usan
`with_for_update()`/lock advisory para esta misma clase de problema).

Sin lock, dos llamadas realmente concurrentes a `/sesiones/refresh` con el
mismo refresh token (dos pestañas, doble clic, un reintento) podían leer ambas
`fecha_uso IS NULL` antes de que cualquiera confirmara — la perdedora termina
en una condición de carrera cruda contra el trigger `trg_token_un_solo_uso` en
vez de un 401 limpio. Se agregó `.with_for_update()` en
`sesion_repository.py::buscar_token_por_hash`: la segunda llamada ahora espera
a que la primera confirme y relee `fecha_uso` ya actualizado, así que toma
determinísticamente la rama de "reuso detectado" en vez de competir contra el
trigger. No es la causa raíz de este ticket específico (el escenario real fue
refresh-vs-login, no refresh-vs-refresh), pero es el mismo tipo de ventana y
quedaba sin cubrir en este módulo.

## Verificación

- `tests/integration/test_refresh_token.py` (6/6, incluye rotación y
  detección de reuso) pasa igual tras agregar el lock.
- `sgpmp-frontend`: `AuthContext.test.tsx` (nuevo) confirma que el bootstrap
  no llama `refreshAccessToken()` en `/login` y sí lo hace en una ruta
  protegida; `http.test.ts` (mutex de refresh) sigue en verde.

## Fuera de alcance

No se tocó el flag `secure`/`samesite` de la cookie de refresco
(`os.getenv("ENV") == "production"` en `sesiones_routers.py`), que ya se
identificó en su momento como un patrón poco confiable en Dokploy y se
corrigió para CORS (`ALLOWED_ORIGINS`, PR #30) pero no para esta cookie. No
hay evidencia de que sea la causa de este bug (el patrón de fallos —
intermitente, justo tras login— no encaja con un `Secure`/`SameSite`
mal seteado, que fallaría el 100% de las veces), pero conviene revisarlo por
separado.
