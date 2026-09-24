# INC-M02-51-G44 — `POST /sesiones/refresh` responde HTTP 500 y la sesión se pierde al recargar

Issue: [backend #404](https://github.com/Arekkazu/sgpmp-backend/issues/404) (hallazgo QA `OBS-G47-03`, detectado durante
la reevaluación de `TC-M02-G47`). No pertenece a RF-40: es el mecanismo de sesiones del Módulo 1 (RF-02).

Ramas:

- backend: `fix/inc-m02-51-g44-refresh-token-http-500` (sale de `fix/m02-fixes`)
- frontend: `fix/inc-m02-51-g44-refresh-500-sin-perder-sesion` (sale de `origin/dev`, rc.30)

## Resumen

El código de refresh es correcto. La causa es que **la base de datos del ambiente TEST no tiene aplicada la migración
`d8e232bc81a3`** (`v5.3.0_sesiones_catalogo_eventos_refresh`), que siembra los tipos de evento 23 y 24 en
`modulo1.tipos_eventos`. Es el mismo defecto que ya se corrigió en DEV como TC-M09-G90
(`anotaciones/modulo_1/tc_m09_g90_refresh_http_500.md`); el arreglo llegó a `dev` en rc.48, pero TEST no lo recibió
porque ese ambiente no tiene migración automática.

## Issues que describen este mismo defecto

| Issue | Repo | Ambiente | Estado | Nota |
|---|---|---|---|---|
| #308 TC-M09-G90 | backend | DEV | cerrado 2026-09-19 | primer reporte, corregido con PR #369 |
| #310 TC-M09-G95/G99 | backend | DEV | cerrado 2026-09-19 | casos bloqueados por el mismo 500 |
| #126 INC-M01-24-088 (TC-M01-088) | frontend | TEST | **abierto** | mismo 500, reportado en el repo equivocado |
| #404 INC-M02-51-G44 (OBS-G47-03) | backend | TEST | **abierto** | este documento |

## Línea de tiempo

| Fecha (UTC) | Evento |
|---|---|
| 2026-09-02 | se retira `migrate-test.yml` ("archivo enviado por error"); desde entonces solo DEV migra por CI |
| 2026-09-14 | #308/#310: refresh responde 500 en DEV |
| 2026-09-15 | frontend #126: mismo 500 en TEST |
| 2026-09-17 | commit `0cd6a7e4`: migración `d8e232bc81a3` que formaliza los tipos 23/24 |
| 2026-09-19 21:27 | PR #369 → `fix/m09`; se cierran #308/#310 |
| 2026-09-20 01:54 | PR #403 `fix/m09` → `dev`; el workflow `migrate-dev` aplica `d8e232bc81a3` en DEV (run 35482583536); release rc.48 |
| 2026-09-20 14:16 | #404: la base de TEST sigue sin el tipo 23 |

## Diagnóstico

Flujo de un refresh válido (`refresh_token_use_case.py`):

1. Busca el token por hash, valida la sesión y la inactividad.
2. Crea el access token y el refresh token nuevos y rota la sesión.
3. Registra la auditoría `tipo_evento=23` (`REFRESH_TOKEN_ROTADO`).
4. `commit()`.

`modulo1.eventos.tipo_evento` tiene una FK hacia `modulo1.tipos_eventos`. Si el catálogo no tiene el id 23, el
`flush()` del paso 3 viola la FK. `SqlAlchemyEventoRepository.registrar` convierte cualquier fallo de persistencia en
`InfrastructureError("AUDITORIA_OBLIGATORIA_FALLIDA")`, porque RF-10 exige cancelar la operación si la auditoría no se
guarda. El caso de uso hace rollback, así que:

- responde 500 y no envía cookie nueva;
- la cookie anterior sigue vigente, por eso reusarla también da 500 (el "reuso" de la tabla del issue no llega a
  detectarse como robo);
- el frontend recibe un error en el refresh, se queda sin access token y manda al usuario a `/login`.

### Qué se descartó

| Hipótesis | Por qué no es la causa |
|---|---|
| Bug en el caso de uso o en el router | 9/9 tests de `test_refresh_token.py` pasan contra `pruebas` en esta rama |
| Categoría de auditoría inválida | el 23 usa la categoría `AUTENTICACION`, igual que el login (tipo 3), que sí funciona en TEST |
| Falta el seed en el repo | los tipos 1-22 vienen del baseline, 23/24 de `d8e232bc81a3` y 25-27 de sus migraciones; ninguno depende de SQL manual |
| Frontend | el refresh al recargar (`AuthContext`) y el deduplicado de refrescos concurrentes (`http.ts`) funcionan; el 500 viene del servidor |

### Estado verificado de las bases

| Base | Tipos 23/24 | Refresh |
|---|---|---|
| `sgpmp` (local) | presentes | funciona (ver "Reproducción local") |
| `pruebas` (local) | presentes | 10/10 tests de integración pasan |
| DEV | aplicados por CI el 2026-09-20 | corregido |
| TEST | ausentes (según el issue) | **500** |

No hay acceso a la base de TEST. El faltante del id 23 lo reporta QA en el issue, y con la migración ya en `dev`
es lo único que explica el comportamiento.

## Reproducción local

El reporte interno fue que la sesión también se pierde al recargar en localhost. Se probó el flujo completo:

| Prueba | Resultado |
|---|---|
| Backend real (`main.py` completo) con `Origin: http://localhost:5173`, sin cookie / cookie inválida | 401 `REFRESH_TOKEN_REQUERIDO` / `REFRESH_TOKEN_INVALIDO`, con cabeceras CORS correctas |
| Escrituras de un refresh sobre `sgpmp` (tokens nuevos, rotación de la sesión 191, evento 23), en un bloque con rollback forzado | aceptadas; nada persistido |
| **Chrome 151**: login real, carga de `/perfil`, F5 (backend real sobre `pruebas`, con rollback) | cookie `refresh_token` guardada (`SameSite=Strict`, `HttpOnly`, `path=/`); refresh 200 en ambas cargas; la sesión se mantiene |
| **Firefox 154**: mismo flujo, por WebDriver BiDi | igual que Chrome: refresh 200 y la sesión se mantiene |
| Chrome con el refresh simulado en 500 (lo que ve QA) | antes del cambio: redirección a `/login`. Después: se queda en la ruta y muestra "No se pudo restaurar tu sesión" |

Con el código actual y una base que tenga el catálogo, **recargar no pierde la sesión** en ninguno de los dos
navegadores. En el historial de `sgpmp` no aparece ninguna recarga fallida posterior al 2026-09-07; antes de esa fecha
hay 20 rotaciones exitosas.

Lo que sí aparece en `sgpmp` son dos comportamientos de RF-02 que, vistos desde la UI, se confunden con este bug:

- **Sesión única por cuenta.** Las sesiones del iPad y del Firefox de escritorio con la misma cuenta se cierran entre
  sí (por ejemplo, la 180 la cerró el login de la 181). Si se recarga el navegador cuya sesión ya fue cerrada, el
  refresh responde 401 y se termina en `/login`.
- **Inactividad de 30 minutos.** Un F5 después de 30 minutos sin peticiones autenticadas responde 401
  `SESION_EXPIRADA_INACTIVIDAD`.

Si la pérdida de sesión en local vuelve a ocurrir, el dato que la identifica es el status y el `error_code` de
`POST /sesiones/refresh` en la pestaña Network.

## Resolución

### 1. Operativa: migrar TEST (resuelve #404 y frontend #126)

La migración ya existe y ya está en `dev`, así que **no hace falta una migración nueva** y no aplica la convención de
nomenclatura (no se crean objetos de BD). Lo que falta es aplicarla en TEST, y eso le toca al DBA (SamuelPR21):

```bash
# con el código de dev (rc.48 o posterior) y DATABASE_URL apuntando a TEST
alembic current      # revisión actual de TEST
alembic heads        # debe devolver una sola head
alembic upgrade head
```

Esto se hace desde `dev`. `fix/m02-fixes` tenía cinco heads sin unificar; la rama de este issue las une (ver punto 4),
pero ese merge solo llega a `dev` cuando se integre `fix/m02-fixes`.

Verificación después de migrar:

```sql
SELECT id_tipo_evento, nombre
FROM modulo1.tipos_eventos
WHERE id_tipo_evento IN (23, 24);
-- 23 REFRESH_TOKEN_ROTADO, 24 REUSO_TOKEN_REFRESCO_DETECTADO
```

Si la migración aborta con `Conflicto en catalogo: ... debe usar id 23/24`, TEST tiene otra fila en ese id (o el
nombre con otro id). En ese caso hay que revisarlo a mano antes de reintentar, no forzarlo.

### 2. Backend: avisar al arrancar si la BD va atrás del código

Es el tercer reporte del mismo defecto (DEV, TEST vía frontend #126, TEST vía #404). Además, en la entrega de rc.47 ya
se habían cerrado cinco issues que no se reproducían porque TEST iba atrasado. Cada vez se descubría tarde, cuando un
usuario perdía la sesión.

`src/shared/migraciones.py` → `verificar_migraciones_aplicadas(engine)`, llamado en el `lifespan` de `main.py` junto a
`verificar_token_configurado()`. Compara las heads de `alembic/versions` (la imagen Docker las incluye) con las de
`alembic_version` y, si difieren, deja un `logger.error` con ambas listas. Es de solo lectura y nunca bloquea el
arranque: si no puede consultar, deja un `warning` y sigue.

Verificado arrancando contra `sgpmp` local, que va atrás de esta rama:

```text
La BD no está en la revisión de Alembic que espera este código (BD: ['5c844a858bde'], código: ['2b747aaae732',
'4f453b6d2b90', '69d26aea234c', '7abae1ee50f6', 'c977eab2eb0d']). ...; ejecuta 'alembic upgrade head' si la BD está
atrasada.
INFO:     Application startup complete.
```

Tests: `tests/shared/test_migraciones.py` (BD atrasada, BD al día, BD inaccesible), con SQLite en memoria y el
comportamiento real de Alembic.

### 3. Frontend: un 5xx en el refresh ya no cierra la sesión

Tras un 5xx la cookie sigue vigente porque el backend hizo rollback, pero el frontend trataba cualquier fallo del
refresh como sesión muerta.

- `http.ts`: `refrescoRechazoLaSesion(error)` es verdadero solo para 401/410. El interceptor cierra la sesión solo en
  ese caso; con 5xx o error de red, rechaza la petición con el error del refresh y conserva la sesión.
- `AuthContext.tsx`: al recargar, un 5xx o error de red en el refresh activa `errorRestaurandoSesion` en vez de
  terminar como "sin sesión". `reintentarRestaurarSesion()` vuelve a intentarlo.
- `App.tsx`: `PrivateRoute` y `AuthedRoute` muestran `SesionNoRestaurada` ("Reintentar" / "Ir al inicio de sesión")
  en lugar de redirigir en silencio. Textos en `auth.json` (`es-CO` y `en-US`).
- Tests: `http.test.ts` (5xx y fallo de red no cierran la sesión; el caso "refresh rechazado" ahora usa un 401 real) y
  `AuthContext.test.tsx` (500 → aviso, 401 → sin aviso). El test del 5xx falla si se revierte `http.ts`.

### 4. Alembic: unificar las cinco heads de `fix/m02-fixes`

`fix/m02-fixes` acumulaba cinco heads, todas descendientes de `c8d4f1a9b7e2` (la head de `dev`): `2b747aaae732`
(M06 identidad, que a su vez viene de `d944f4d8c215`), `4f453b6d2b90` (RF-41), `69d26aea234c` (RF-37), `7abae1ee50f6`
(RF-36) y `c977eab2eb0d` (RF-49). Con varias heads, `validate-migrations.yml` rechaza el PR y `_migrate-template.yml`
se niega a desplegar.

`6af637931784_merge_all_m02_heads.py` es un merge sin operaciones (`upgrade`/`downgrade` vacíos), con el mismo formato
que `c8d4f1a9b7e2_merge_all_m09_heads.py`. No crea objetos de BD, así que la convención de nomenclatura no aplica.
Como es un archivo de migración, el PR necesita el visto bueno del DBA igual que cualquier otro.

Verificación:

- `alembic heads` → una sola head: `6af637931784`.
- `alembic upgrade c8d4f1a9b7e2:head --sql` (offline, sin tocar ninguna base) recorre las seis migraciones de la rama
  y el merge; al final `alembic_version` queda solo con `6af637931784`.
- `origin/dev` no tiene migraciones que falten en la rama, así que al integrar no reaparecen heads.

### 5. Frontend: editar perfil y cambiar contraseña como modal (incluido en el mismo PR)

Reporte aparte, en la misma rama del frontend: en "Mi perfil", los formularios de editar datos y cambiar contraseña
aparecían como paneles al final de la página, debajo de las tarjetas y fuera de la vista. Ahora se abren como modal
superpuesto (`PerfilModal` en `PerfilPage.tsx`), con el mismo patrón que el resto de modales del proyecto: overlay
fijo, `role="dialog"`, `useModalA11y` (foco atrapado y Escape), cierre con la X o haciendo clic fuera, y
`maxHeight: 90vh` con scroll para móvil. Los formularios no cambian.

## Pruebas ejecutadas

| Suite | Resultado |
|---|---|
| Backend `tests/shared/test_migraciones.py` | 3/3 |
| Backend integración refresh (`test_refresh_token.py`, `test_tc_m09_g90_catalogo_refresh.py`) contra `pruebas` | 10/10 |
| Backend suite unitaria completa | 824 pasan, 2 fallan en `test_registrar_transferencia_use_case.py` (ya fallaban en `fix/m02-fixes` sin este cambio) |
| Backend `alembic heads` / upgrade offline `c8d4f1a9b7e2:head` | 1 head / cadena completa |
| Frontend `vitest` completo | 287/287 (incluye 3 tests nuevos de los modales de perfil, que fallan con el código anterior) |
| Frontend `tsc --noEmit` | sin errores |
| Navegador real (Chrome y Firefox) | ver "Reproducción local"; capturas de los modales de perfil en 1280×800 y 390×844 |

## Cómo reprobar (QA, después de migrar TEST)

Con Productor, Veterinario e Ingeniero de Campo:

1. Login → existe la cookie `refresh_token`.
2. `POST /sesiones/refresh` → 200, cookie nueva y `modulo1.eventos` con un evento 23 del usuario.
3. Repetir el paso 2 con la cookie **anterior** → 401 `REFRESH_TOKEN_REUTILIZADO`, sesión revocada y evento 24.
4. Login de nuevo, F5 en una ruta protegida → la sesión se mantiene.
5. Sin cookie → 401 `REFRESH_TOKEN_REQUERIDO`; cookie inventada → 401 `REFRESH_TOKEN_INVALIDO`.

## Riesgos residuales (fuera de alcance, sin evidencia en este issue)

- **Refresh simultáneo desde dos pestañas:** el deduplicado de `http.ts` es por pestaña. Si dos pestañas envían la
  misma cookie a la vez (por ejemplo, al restaurar el navegador), la segunda cuenta como reuso y revoca la sesión. En
  `sgpmp` no hay ningún evento 24, así que no ha ocurrido; solo se atendería si aparece un reporte con
  `REFRESH_TOKEN_REUTILIZADO`.
- **Recarga tras sesión única o inactividad:** termina en `/login` sin explicación (el aviso de "sesión cerrada" solo lo
  deja el interceptor, no la restauración al recargar). Es comportamiento de RF-02; mostrar el motivo sería una mejora
  aparte.
