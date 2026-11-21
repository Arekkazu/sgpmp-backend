# TC-M09-G79-v2.0 — RF-24 v2.0

Atomicidad del registro de calibración ante un **fallo real** de escritura de auditoría.

- **Requisito:** RF-24 v2.0
- **Caso de uso:** CU05 — Gestionar Dispositivos IoT, Flujo D
- **Caso:** TC-M09-150-v2.0
- **Tipo:** Integridad / Atomicidad transaccional
- **Herramientas:** Pytest + PostgreSQL real + backend HTTP real
- **Ambiente decisorio:** LOCAL AISLADO (TEST remoto **no aplica** a esta prueba)
- **Informe de cada corrida:** `RESULTADOS/<RUN_ID>/TC-M09-G79_resultado.md`

Cadena que debe demostrarse:

```text
calibración válida -> alcanza la transacción de persistencia
-> falla el INSERT de auditoría por permisos -> rollback
-> HTTP 500 con el mensaje exacto del FA -> ninguna calibración nueva persistida
```

## Esta prueba NO se ejecuta contra TEST ni DEV

Las escrituras SQL (seed, `REVOKE`/`GRANT`) están autorizadas **solo** dentro de la base
efímera `sgpmp_g79_v2` del laboratorio. La regla de solo lectura sobre TEST/DEV sigue vigente.

`helpers_g79_v2.safety_guard()` aborta con **BLOCKED / SAFETY GUARD** antes de cualquier
escritura si la base no es `sgpmp_g79_v2`, si el host del DSN o de la API no es local, o si
alguna cadena referencia `inmero.co`, `sslip.io`, `back-sigab` o `dokploy`. Ante un guard
fallido no se intenta "arreglar" la conexión.

Además hay guard de carpeta: todo aborta si se ejecuta fuera de `TC-M09-G79-v2.0`.

```python
if Path(__file__).resolve().parent.name != "TC-M09-G79-v2.0":
    raise RuntimeError("Directorio no autorizado para TC-M09-G79-v2.0")
```

La carpeta histórica `../TC-M09-G79/` es de **solo lectura**. Su implementación usaba `DbFake`
y repositorios falsos, y declaraba no usar PostgreSQL real, de modo que **no satisface** este
caso: sirve de referencia, nunca como prueba ejecutable de v2.0.

## Dos identidades de base de datos

Es la condición que hace fiable el fault injection:

| Identidad | Uso | Requisitos |
|---|---|---|
| `sgpmp_owner` | migraciones (`ALEMBIC_DATABASE_URL`), seed, `REVOKE`/`GRANT` | dueño de los objetos |
| `sgpmp_app` | `DATABASE_URL` del backend | LOGIN, **no** superusuario, **no** owner |

Si la aplicación operara como owner o superusuario, un `REVOKE INSERT` no la frenaría y la
prueba no probaría nada. El RUN verifica ambas condiciones antes de inducir el fallo.

### Por qué `sgpmp_app` lleva `BYPASSRLS`

Las políticas RLS de `modulo1` leen `app.current_user_id` / `app.current_role`, y la aplicación
las fija en `get_current_user` (`src/identity_access/infrastructure/dependencies.py`), es decir
**después** de autenticar. El login ocurre antes, así que un rol sujeto a RLS ve 0 filas en
`modulo1.usuarios` y nunca logra autenticarse. En los entornos desplegados la API se conecta
con el usuario dueño de los objetos (ver `docker-compose.yml` y `.env.example`), y un owner
elude RLS; `BYPASSRLS` reproduce ese comportamiento sin conceder ownership ni superusuario.

Lo decisivo: `BYPASSRLS` afecta solo políticas de **fila**, no privilegios de **tabla**, así que
el `REVOKE INSERT` sobre las auditorías sigue frenando a la aplicación. El RUN lo comprueba
empíricamente antes del POST objetivo.

## Preparación del laboratorio

Requiere Docker en marcha. Las contraseñas llegan por variables de proceso y no se versionan.

```powershell
$env:G79_OWNER_PASSWORD="<clave del owner del laboratorio>"
$env:G79_APP_PASSWORD="<clave del rol de la aplicacion>"
$env:G79_SECRET_KEY="<secret key del backend local>"

# 1. PostgreSQL real, efímero, publicado solo en localhost
docker compose -p sgpmp-g79-v2 -f docker-compose.g79-v2.yml up -d --build db

# 2. Roles ANTES de migrar: una migracion hace GRANT ... TO sgpmp_app sin condicional
docker exec -i sgpmp-g79-v2-db psql -U sgpmp_owner -d sgpmp_g79_v2 `
  -c "SET g79.app_password='<clave>';" -f - < sql/bootstrap_roles.sql

# 3. Migraciones reales del proyecto, como owner
$env:ALEMBIC_DATABASE_URL="postgresql://sgpmp_owner:<clave>@127.0.0.1:55479/sgpmp_g79_v2"
$env:DATABASE_URL=$env:ALEMBIC_DATABASE_URL
python -m alembic upgrade head     # desde la raiz del repo

# 4. Privilegios funcionales normales del app role (sin SUPERUSER/BYPASSRLS extra ni ownership)
docker exec -i sgpmp-g79-v2-db psql -U sgpmp_owner -d sgpmp_g79_v2 -f - < sql/grant_app_privileges.sql

# 5. Fixture. El hash bcrypt se genera con el value object del propio proyecto
#    (src/identity_access/domain/value_objects/contrasena.py): no se inventan hashes.
docker exec -i sgpmp-g79-v2-db psql -U sgpmp_owner -d sgpmp_g79_v2 -v ing_hash="<hash>" -f - < sql/seed_fixture.sql

# 6. Backend real (contenedor: no puede correr nativo en Windows porque importa fcntl)
docker compose -p sgpmp-g79-v2 -f docker-compose.g79-v2.yml up -d --build backend
```

> Cuidado al editar el compose: la base usa `tmpfs`, así que recrear el contenedor `db`
> descarta migraciones y seed. En postgres:18 el montaje va en `/var/lib/postgresql`, no en
> `.../data`.

## Ejecución del RUN

```powershell
$env:G79_RUN_ID="run-YYYYMMDD-HHMMSS"
$env:G79_ADMIN_DSN="postgresql://sgpmp_owner:<clave>@127.0.0.1:55479/sgpmp_g79_v2"
$env:G79_API_URL="http://127.0.0.1:18079"
$env:G79_ING_EMAIL="ingeniero@pecuaria.co"
$env:G79_ING_PASSWORD="<clave del ingeniero>"

python -m pytest test_tc_m09_150_v2.py -v --noconftest `
  --junitxml="RESULTADOS/$env:G79_RUN_ID/pytest-TC-M09-150-v2.0.xml"
python verificar_cierre.py
```

`--noconftest` es necesario: el `conftest.py` del repositorio importa `src`, que arrastra
`fcntl` y no es importable en Windows. La prueba es autónoma y no modifica nada del repositorio.

## Reglas que la automatización hace cumplir

- **Presupuesto: 1 POST de control positivo y 1 POST objetivo.** Nunca se reintenta un POST. Si
  el objetivo quedara ambiguo, se consulta la base y los logs; no se reenvía.
- **El control positivo es obligatorio antes del fault.** Si falla, no se ejecuta `REVOKE` ni el
  POST objetivo: el resultado es BLOQUEADO / entorno no apto, no un defecto del producto.
- **El `REVOKE` solo toca el `INSERT` de auditoría.** No se revoca el `INSERT` de
  `modulo9.calibraciones`, ni `SELECT`, ni `CONNECT`, ni `USAGE`: eso movería el punto de fallo.
- **Se verifica que el `REVOKE` es efectivo antes del POST.** Si `audit_insert` siguiera en
  `true`, el POST no se envía (app owner, superusuario o privilegio heredado ⇒ laboratorio
  inválido).
- **Se verifica que el fallo ocurrió en la auditoría**, no antes: el log no debe mostrar
  `permission denied for table calibraciones`.
- **El rollback se comprueba por SQL**, comparando conteo **y** filas completas
  (`id_dispositivo_iot`, `id_sensor`, `valor_referencia`, `fecha_calibracion`, `id_usuario`,
  `observaciones`), además de la ausencia de auditoría huérfana.
- **El mensaje se compara de forma exacta** contra el FA de RF-24 v2.0. No se adapta al backend
  ni se reinterpreta después de ver la respuesta.
- **La restauración va en `finally`:** no depende de que una assertion pase ni del orden de los
  tests. Solo devuelve los privilegios que el snapshot PRE demostró disponibles; nunca
  `GRANT ALL`, `SUPERUSER` ni `ALTER OWNER`. Si no se logra, se marca RESTAURACIÓN PENDIENTE en
  lugar de ocultarlo.
- **Nada se borra:** si apareciera una calibración o auditoría inesperada, se conserva como
  evidencia.
- Token del Ingeniero obtenido **antes** del fault, y vive solo en memoria.
- `observaciones` exactas: `QA TC-M09-150-v2.0 CONTROL` y `QA TC-M09-150-v2.0`, sin el `RUN_ID`.

## Cierre del laboratorio

Conviene conservarlo hasta validar el informe. Como la base usa `tmpfs`, **detener el contenedor
descarta los datos en memoria**, así que la inspección debe hacerse antes:

```powershell
docker compose -p sgpmp-g79-v2 -f docker-compose.g79-v2.yml stop   # descarta los datos
docker compose -p sgpmp-g79-v2 -f docker-compose.g79-v2.yml down   # limpieza completa
```

La eliminación es una limpieza separada, no parte del oráculo.

## Artefactos por corrida

```text
RESULTADOS/<RUN_ID>/
├── git_pre.txt                      git_final.txt
├── environment_guard.json           postgres_version.txt   alembic_state.txt
├── db_identity_pre.json             db_role_pre.json       table_owners_pre.json
├── fixture.json                     actor.json
├── control_request.json             control_response.json
├── control_db_calibracion.json      control_db_auditoria_m9.json   control_db_eventos.json
├── count_target_before.json         rows_target_before.json
├── privilegios_pre.json             privilegios_pre_snapshot.txt
├── revoke_output.txt                privilegios_revoke.json
├── target_request.json              target_response.json   backend_fault.log
├── count_target_after.json          rows_target_after.json audit_partial_check.json
├── restore_output.txt               privilegios_post_restore.json
├── pytest-TC-M09-150-v2.0.xml       pytest-TC-M09-150-v2.0.log
├── automation/                      automation_manifest.json  (SHA-256)
├── verificacion-final-readonly.json seguridad-evidencias.json
└── TC-M09-G79_resultado.md
```
