# PR #50 — Resumen de verificación

Issue #1599 · PR #50 · rama `feature/rf04-rf06-cambio-rol-sin-relogin` (commit único `ccff907`)
Revisión hecha en la rama local `review/pr50-rf04-rf06`, creada desde `origin/dev`.

**Veredicto: el PR es correcto, no rompe nada y cierra el gap de RF-04/06.**
El conflicto de merge quedó resuelto sin perder trabajo previo de `dev`, y los tres riesgos
detectados en la revisión se corrigieron encima (sección 8).

---

## 1. El gap era real, y era peor de lo que decía la issue

La issue describía el síntoma como *"el usuario sigue operando con permisos del rol anterior
hasta que expire el token"*. La conducta real en `dev` es distinta y también incumple el RF:
`editar_perfil_use_case` invalidaba **todas las sesiones** del usuario al reasignarle el rol,
así que el siguiente request con el JWT vigente devolvía `401 TOKEN_REVOCADO`.

Es decir, `dev` no dejaba al usuario con permisos viejos: lo **echaba de la sesión**. Y RF-04
pide literalmente lo contrario — *"los cambios se aplicarán dinámicamente a los usuarios que
posean dicho rol, incluyendo aquellos con sesiones activas, sin requerir cierre de sesión"*.

Comprobado ejecutando la misma prueba end-to-end contra `origin/dev` limpio:

```
AssertionError: {"error_code":"TOKEN_REVOCADO",
                 "message":"El token de sesión ha sido revocado o es inválido."}
assert 401 == 200
```

## 2. El arreglo, y por qué está en el sitio correcto

`get_current_user` (`src/identity_access/infrastructure/dependencies.py`) deja de tomar el rol
del claim `rol` del JWT y consulta `modulo1.usuarios.id_rol` en cada request. En paralelo,
`editar_perfil_use_case` deja de invalidar sesiones cuando lo único que cambia es el rol.

Se verificó por grep sobre `src/` que `dependencies.py:62` era el **único** punto del código que
leía el claim `rol`. Todo lo que decide autorización aguas abajo consume `usuario_actual.id_rol`:

| Consumidor | Ruta |
|---|---|
| `require_permission` (RBAC central) | `src/shared/rbac.py:49` |
| `GET /sesiones/me/permisos` | `sesiones_routers.py:172` |
| Filtro de productor en fincas | `configuration/.../finca_router.py:85,110` |
| Contexto y dashboard por rol | `configuration/.../personalizacion/` (3 use cases) |
| Enmascaramiento de identificación | `consultar_detalle_usuario_use_case.py:148` |

Arreglar el choke point los cubre a todos. `src/shared/agrofusion_auth.py` es un camino M2M
aparte (secreto de plataforma, sin `id_rol`) y no se ve afectado.

## 3. Qué se comprobó que NO rompe

- `usuarios.id_rol` es `NOT NULL`, así que el `scalar()` devolviendo `None` solo significa
  "fila de usuario inexistente". No hay falso 401 por un `id_rol` nulo.
- `RefreshTokenUseCase` ya leía el rol desde base (`refresh_token_use_case.py:137,142`); el
  camino de refresh ya era consistente y sigue siéndolo.
- Retirar la invalidación de sesiones al cambiar de rol respeta RF-06, cuya lista de
  invalidación es solo INACTIVO / BLOQUEADO / ELIMINADO. El rol nunca estuvo en esa lista.
  La invalidación por **cambio de correo** se conserva intacta.
- Las tres guardas de `editar_perfil_use_case.py` siguen en pie: autoedición de rol bloqueada
  (`:138`), el rol debe existir (`:149`), y protección del último usuario activo de un rol
  protegido (`:251`). `rol_modificado` se sigue usando en `:136`, `:194`, `:252`.
- Ninguna prueba unitaria usa `TestClient` ni `dependency_overrides`, así que la query nueva
  solo afecta a integración, donde sí se insertan filas reales de usuario.

## 4. Cambios de base de datos: **ninguno**

Sin DDL, sin DML, sin migración Alembic. El arreglo solo cambia de dónde se lee un dato que ya
existía. Verificado contra `sgpmp` y contra `pruebas`: `usuarios.id_rol NOT NULL`, 9 roles y
permisos poblados para los roles 1-8 en ambas.

## 5. Resolución del conflicto

La rama llegó **26 commits detrás de `dev`**. Tres hunks, los tres resueltos conservando ambos
lados. Nada de `dev` se perdió.

| Archivo | Qué chocaba | Cómo quedó |
|---|---|---|
| `dependencies.py` (imports) | `dev` añadió `establecer_id_token`; el PR añadió `Usuarios` | Los **dos** imports |
| `dependencies.py` (return) | `dev` añadió la llamada de auditoría RF-10; el PR reescribió el `return` | La llamada **y** el return nuevo con `id_rol_vigente` |
| `tests/integration/README.md` | La rama, por vieja, pisaba la línea de RF-01 con la redacción anterior ("script SQL" en vez de "migración Alembic") y perdía el "autorizacion RBAC en router" de RF-05/06 | Se conserva la redacción de `dev` y se añade solo la línea nueva de RF-04/06 |

Auto-merges revisados a mano:

- `estado_M01.md` — solo cambian las secciones de RF-04; las ediciones de `dev` sobre RF-01 y
  RF-12 quedan intactas.
- `editar_perfil_use_case.py` — conserva la validación de identificación de `dev` (`:315`,
  RF-01/RF-12) y aplica el cambio del PR (`:277`, ahora solo `correo_modificado`).

## 6. Resultados de las pruebas

| Suite | `origin/dev` (línea base) | Merge + correcciones |
|---|---|---|
| Unitarias | 119 passed | **121 passed** (+2 del PR) |
| Integración (base `pruebas`) | 73 passed, 7 skipped | **79 passed, 7 skipped** |
| Suite completa | — | **201 passed, 7 skipped** |
| Fallos | 0 | **0** |

Los 7 skips son idénticos en ambas y corresponden a módulo 9 (`test_rf16_*`): la base `pruebas`
no tiene el schema `modulo9`. **Ahí está el origen de los "6 fallos preexistentes de módulo 9"
que menciona la descripción del PR** — allí fallaban contra `pruebas-integrador`; aquí
simplemente se saltan. En ningún caso son regresiones de este cambio.

Regresión específica verificada en verde: `test_rbac_perfil_listado.py`,
`test_rf05_rf06_rbac_perfil_gestion_integration.py`, `test_refresh_token.py` (6 tests) y
`test_sesiones_jwt.py`.

## 7. Prueba end-to-end del comportamiento

El test que traía el PR solo miraba `GET /sesiones/me/permisos`, que es informativo y no pasa
por `require_permission`. Se añadió al repo
(`test_require_permission_pasa_de_403_a_200_con_el_mismo_jwt`) una prueba que ejercita el flujo
completo con **login real** contra un endpoint con RBAC de verdad:

1. Usuario con rol Productor (2), login real vía `POST /sesiones/` con contraseña.
2. `GET /usuarios/admin` con ese JWT → **403**, correcto: recurso 1 / acción 2 solo lo tiene
   el rol Administrador.
3. Un admin hace `PATCH /usuarios/{id}` con `id_rol: 1`.
4. `GET /usuarios/admin` **con el mismo JWT de antes** → **200**.
5. En base, la sesión del login sigue `es_activa = TRUE` y su token con `fecha_uso IS NULL`.

La misma prueba contra `origin/dev` falla en el paso 4 con `401 TOKEN_REVOCADO`. Esa es la
demostración de que el arreglo hace lo que dice.

## 8. Los tres riesgos de la revisión, corregidos

Se resolvieron encima del merge, en la misma rama. Ninguno exigió cambios de base de datos.

### 8.1 La query extra ya no existe

El PR añadía un `SELECT usuarios.id_rol` además del `SELECT cuentas_usuarios` que
`get_current_user` ya hacía. Ambas se fusionaron en una sola consulta con `outerjoin`, que es
gratis porque el bloque de inactividad necesitaba la fila de cuenta de todos modos.

Medido con un listener `before_cursor_execute` de SQLAlchemy sobre un request autenticado real:

| | SELECT por request | dentro de `get_current_user` |
|---|---|---|
| Merge sin corregir | 6 | 3 |
| Corregido | **5** | **2** |

Es decir, el PR ya no añade **ninguna** consulta respecto a `dev`: queda en paridad. El RNF de
RF-04 (<200 ms por validación de permisos) deja de ser una preocupación.

### 8.2 El código de error nuevo se retiró

`USUARIO_SESION_INVALIDO` (401) no figuraba en los flujos alternos del RF y describía un caso
que RF-06 prohíbe (borrado físico de usuarios). Se reutiliza **`TOKEN_REVOCADO`**, que ya
existía y significa lo mismo para el cliente: la sesión no vale. Cero contrato nuevo que
documentar o que el frontend tenga que aprender.

### 8.3 El chequeo de estado de cuenta, en el sitio que dice el RF

RF-04 restringe: *"Los permisos asociados a un rol solo serán efectivos para usuarios que se
encuentren en estado activo dentro del sistema."* Eso no estaba implementado en ninguna parte.

El gate se añadió en **`require_permission` (`src/shared/rbac.py`)**, no en `get_current_user`.
La ubicación importa:

- El RF habla de que los **permisos** no sean efectivos, no de impedir la autenticación.
- Una cuenta `PENDIENTE_DATOS` (alta por SSO de AgroFusion) **tiene** que poder autenticarse
  para completar su perfil por `PATCH /usuarios/me`, endpoint que no pasa por RBAC. Un gate en
  `get_current_user` habría roto ese flujo — era justamente el motivo por el que en la primera
  pasada se descartó tocarlo.
- El estado viaja en `UsuarioActual`, que `get_current_user` ya resuelve, así que el gate
  **no cuesta ninguna consulta adicional**. `UsuarioActual.id_estado_cuenta` tiene default
  `None`, de modo que cualquier construcción manual queda cerrada por omisión (fail closed).

Devuelve `403 CUENTA_NO_ACTIVA`, reutilizando un código que ya existía en `editar_perfil`.

Cubierto por dos pruebas nuevas: una cuenta INACTIVA con rol Administrador recibe 403 en
`GET /usuarios/admin` mientras la misma cuenta ACTIVA recibe 200; y una cuenta
`PENDIENTE_DATOS` sigue pudiendo usar `GET /usuarios/me` pero queda fuera de los endpoints con
RBAC.

### 8.4 Gap adicional encontrado y cerrado

Al revisar el punto anterior apareció un agujero más serio, ya no del PR sino de `dev`.

`login_use_case.py` bloquea la cuenta al agotar los intentos (`cuenta.bloquear()`) y confiaba
en el trigger de base de datos para el resto. Pero `trg_invalidar_sesiones_por_estado` **solo**
hace `UPDATE modulo1.sesiones SET es_activa = FALSE`: no toca `modulo1.tokens.fecha_uso`, que
es exactamente lo único que `get_current_user` comprueba para aceptar un JWT.

El escenario es el del atacante. La víctima tiene su sesión abierta en el móvil; un tercero le
agota los intentos de login desde fuera. Medido sin el arreglo:

```
estado de la cuenta: "Bloqueado"
GET /usuarios/me    → 200 OK  + nombre, correo, identificación, rol...
```

La cuenta figura bloqueada y la sesión sigue operando. Eso incumple el criterio de RF-06
*"El sistema invalida sesiones activas al cambiar el estado a INACTIVO, BLOQUEADO o ELIMINADO"*.

**Arreglo**: `login_use_case` llama `self.sesiones_repo.invalidar_todas_sesiones(...)` antes de
guardar la cuenta — mismo patrón y mismo orden que `gestionar_cuenta_use_case`, que invalida
antes del flush precisamente porque el trigger deja las sesiones inactivas y el método del
repositorio filtra por sesiones activas para poder marcar sus tokens. `LoginUseCase` ya recibía
`sesiones_repo`, así que no cambió ninguna firma ni ningún call-site.

Tras el arreglo, ese `GET /usuarios/me` devuelve **401 TOKEN_REVOCADO** y en base el token queda
con `fecha_uso`, no solo la sesión inactiva.

Se revisaron **todos** los caminos que mutan el estado de una cuenta
(`bloquear`, `cambiar_estado`, `poner_pendiente`, `activar`, `desbloquear`). El único roto era
el del login: `gestionar_cuenta_use_case` y `cambiar_estado_usuario_agrofusion_use_case` ya
invalidaban.

Cubierto por `tests/integration/test_rf06_bloqueo_invalida_sesiones.py`, verificado que falla
sin el arreglo.

## 8.5 El trigger de base de datos, corregido por migración Alembic

Alembic sí está wireado en el repo (13 migraciones y el workflow `migration-db.yml`), así que
esto va como migración y no como DDL suelto: **`e8bb4f321a44`**, sobre el head `f2c84d91a6e7`.

`trg_fn_invalidar_sesiones_por_estado` hacía solo `UPDATE modulo1.sesiones SET es_activa =
FALSE`. Ahora, además, revoca de verdad los tokens:

```sql
IF NEW.id_estado_cuenta IN (3, 4, 5) THEN
    UPDATE modulo1.tokens AS t
    SET fecha_uso = now()
    FROM modulo1.sesiones AS s
    WHERE s.id_cuenta_usuario = NEW.id_cuenta_usuario
      AND (t.id_token = s.id_token OR t.id_token = s.id_token_refresco)
      AND t.fecha_uso IS NULL;
END IF;
```

Tres decisiones de diseño:

- **Acotado a los estados 3/4/5.** Si revocara en *cualquier* cambio de estado, activar una
  cuenta `PENDIENTE_DATOS` echaría de la sesión al usuario que acaba de completar su perfil por
  SSO. Hay un test que fija ese límite.
- **`es_activa` conserva su alcance original** (todo cambio de estado), para no alterar
  conducta existente.
- **Idempotente con la aplicación.** El filtro `fecha_uso IS NULL` hace que, cuando el caso de
  uso ya revocó antes del flush, el trigger no vuelva a marcar nada. Sigue siendo la aplicación
  quien lleva el camino principal —también registra `fecha_finalizacion`, que el trigger no—; el
  trigger es la red para lo que se salte esa vía.

`upgrade` → `downgrade` → `upgrade` verificado contra `sgpmp`, comprobando la definición de la
función en cada paso.

### Estado de las bases

| Base | Cómo quedó |
|---|---|
| `sgpmp` (dev) | `alembic upgrade head` → **`e8bb4f321a44`** |
| `pruebas` (tests) | Mismo DDL, generado en modo offline desde la propia migración (`alembic upgrade f2c84d91a6e7:e8bb4f321a44 --sql`), aplicado **sin** tocar `alembic_version` |

`pruebas` sigue anclada al baseline `f7fe43537842` a propósito: tiene 13 migraciones pendientes
y 5 de ellas tocan `modulo9`, schema que esa base no tiene. Es su estado normal (solo-modulo1).
En CI el workflow `migration-db.yml` sí aplica `alembic upgrade head` a la base de test.

Cubierto por dos pruebas: un cambio de estado por **SQL directo** (sin pasar por ningún caso de
uso) revoca el JWT, y activar una cuenta **no** revoca la sesión del propio usuario.

## 9. Estado del árbol

El merge y las tres correcciones quedaron **resueltos y stageados, sin commit**, en la rama
local `review/pr50-rf04-rf06`. No se pusheó nada y `dev` no se tocó.

Archivos tocados por las correcciones, además de los del PR:

- `src/identity_access/infrastructure/dependencies.py` — consulta fusionada, `TOKEN_REVOCADO`,
  campo `id_estado_cuenta` en `UsuarioActual`.
- `src/shared/rbac.py` — gate de cuenta activa en `require_permission`.
- `src/identity_access/application/use_cases/sesiones/login_use_case.py` — invalidación de
  sesiones al bloquear por intentos fallidos.
- `tests/integration/test_rf04_rf06_cambio_rol_inmediato_integration.py` — 3 pruebas añadidas.
- `tests/integration/test_rf06_bloqueo_invalida_sesiones.py` — nuevo, 3 pruebas de los gaps
  8.4 y 8.5.
- `alembic/versions/e8bb4f321a44_rf06_trigger_revoca_tokens_al_inactivar_.py` — nueva migración.

Para inspeccionarlo:

```
git status
git diff --cached
```

Para completar el merge cuando se decida:

```
git commit        # usa el mensaje de merge por defecto
```

Para descartarlo:

```
git merge --abort
```

---

## 10. Hallazgo abierto (preexistente, fuera del alcance de este PR)

### 10.1 Fuerza bruta contra un rol protegido revienta el login

`trg_proteger_estado_cuenta_admin` impide cambiar el estado de una cuenta con rol protegido, así
que al quinto intento fallido contra un Administrador el `UPDATE` lanza `PROTECTED_ADMIN` y la
excepción de psycopg2 sale del endpoint sin traducir.

**Verificado que es preexistente**: ocurre igual con y sin los cambios de esta rama. Que un
administrador no pueda quedar bloqueado por fuerza bruta parece deliberado (evita un DoS
trivial contra el admin), pero el login debería contemplarlo en vez de propagar el error de
base de datos.
