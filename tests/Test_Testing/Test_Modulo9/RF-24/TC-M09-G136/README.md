# TC-M09-G136 — RF-24 v2.0

Auditoría **best-effort** del rechazo de calibración.

- **Requisito:** RF-24 v2.0
- **Caso de uso:** CU05 — Gestionar Dispositivos IoT, Flujo D
- **Caso:** TC-M09-274
- **Tipo:** Auditoría / control de infraestructura
- **Herramientas:** Pytest + PostgreSQL real + logs del backend
- **Prueba local:** **SÍ**
- **Informe de cada corrida:** `RESULTADOS/<RUN_ID>/TC-M09-G136_resultado.md`

Hay que demostrar que, cuando la aplicación **no puede escribir el historial RF-10**, los
rechazos conservan su error funcional en lugar de degradarse a 500:

```text
REVOKE INSERT modulo1.eventos      (único fallo inducido)
→ valor fuera de rango     -> sigue siendo HTTP 400, nunca 500
→ dispositivo inactivo     -> sigue siendo HTTP 422, nunca 500
en ambos: ninguna calibración creada, la escritura RF-10 falla de verdad
y queda una constancia observable del fallo, una por intento
```

## Esta prueba NO se ejecuta contra TEST, DEV ni MAIN

El fault injection está autorizado **solo** dentro de la base local y efímera
`sgpmp_g136_lab`. El test aborta con **BLOCKED / SAFETY GUARD** antes de cualquier SQL de
setup si la base no es esa, si el DSN o la URL de la API no son locales, o si alguna cadena
referencia `inmero.co`, `sslip.io`, `back-sigab` o `dokploy`.

La base se crea desde cero, se le aplican las migraciones reales del proyecto y se siembra
únicamente el fixture del caso. **No se copia ningún dato de TEST.** El volumen es exclusivo
(`sgpmp_g136_pgdata`): no se reutiliza `sgpmp_pgdata` ni ningún volumen de DEV/TEST.

Hay además guard de carpeta: todo aborta si se ejecuta fuera de `TC-M09-G136`.

## Dos identidades de base de datos

Es lo que vuelve fiable el fault injection. El compose normal del proyecto usa el mismo
`POSTGRES_USER` para crear la BD y para el backend, y eso no sirve aquí: un owner o superusuario
puede conservar privilegios que harían inefectivo el `REVOKE`.

| Identidad | Uso | Requisitos |
|---|---|---|
| `g136_owner` | migraciones, seed, `REVOKE`/`GRANT`, consultas administrativas | owner |
| `g136_app` | `DATABASE_URL` real del backend | LOGIN, **no** superusuario, **no** owner de `modulo1.eventos`, sin herencia de otros roles |

El test verifica las tres condiciones del app role antes de inducir el fallo.

### Por qué `g136_app` lleva `BYPASSRLS`

Las políticas RLS de `modulo1` leen `app.current_user_id`, que la aplicación fija en
`get_current_user`, es decir **después** de autenticar. Un rol sujeto a RLS no vería filas en
`modulo1.usuarios` y no podría ni iniciar sesión. `BYPASSRLS` afecta solo políticas de **fila**,
no privilegios de **tabla**, así que el `REVOKE INSERT` sobre `modulo1.eventos` sigue frenando a
la aplicación — y el RUN lo comprueba empíricamente antes de enviar los POST.

El rol `sgpmp_app` existe como marcador `NOLOGIN` porque una migración del proyecto hace
`GRANT ... TO sgpmp_app` sin condicional. Nadie es miembro suyo, de modo que no presta
privilegios por herencia.

## Preparación del laboratorio

Requiere Docker en marcha. Las contraseñas llegan por variables de proceso y no se versionan.

```powershell
$env:G136_OWNER_PASSWORD="<clave del owner>"
$env:G136_APP_PASSWORD="<clave del app role>"
$env:G136_SECRET_KEY="<secret key del backend local>"

# 1. PostgreSQL aislado, volumen exclusivo, publicado solo en localhost
docker compose -p sgpmp-g136 -f docker-compose.g136.yml up -d --build db

# 2. Roles ANTES de migrar (una migración hace GRANT ... TO sgpmp_app sin condicional)
docker exec -i sgpmp-g136-db psql -U g136_owner -d sgpmp_g136_lab -c "
  CREATE ROLE postgres LOGIN SUPERUSER;
  CREATE ROLE sgpmp_app NOLOGIN;
  CREATE ROLE g136_app LOGIN PASSWORD '<clave>' NOSUPERUSER NOCREATEDB NOCREATEROLE BYPASSRLS INHERIT;"

# 3. Migraciones reales, como owner (desde la raíz del repo)
$env:ALEMBIC_DATABASE_URL="postgresql://g136_owner:<clave>@127.0.0.1:55436/sgpmp_g136_lab"
$env:DATABASE_URL=$env:ALEMBIC_DATABASE_URL
python -m alembic upgrade head

# 4. Privilegios funcionales normales del app role (sin SUPERUSER extra ni ownership)
docker exec -i sgpmp-g136-db psql -U g136_owner -d sgpmp_g136_lab -c "
  DO \$\$ DECLARE s text; BEGIN
    FOR s IN SELECT nspname FROM pg_namespace
             WHERE nspname NOT LIKE 'pg\_%' AND nspname <> 'information_schema' LOOP
      EXECUTE format('GRANT USAGE ON SCHEMA %I TO g136_app', s);
      EXECUTE format('GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA %I TO g136_app', s);
      EXECUTE format('GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA %I TO g136_app', s);
      EXECUTE format('GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA %I TO g136_app', s);
    END LOOP; END \$\$;"

# 5. Backend real (contenedor: no corre nativo en Windows porque importa fcntl)
docker compose -p sgpmp-g136 -f docker-compose.g136.yml up -d --build backend
```

El **seed del fixture está embebido en el test** y es idempotente: no hace falta un `.sql`
aparte. Siembra el Ingeniero (su hash se genera con el value object del propio proyecto, sin
inventar hashes), un dispositivo activo con sensor, un dispositivo inactivo con sensor, el área y
las asociaciones vigentes.

## Ejecución del RUN

```powershell
$env:G136_RUN_ID="run-YYYYMMDD-HHMMSS"
$env:G136_ADMIN_DSN="postgresql://g136_owner:<clave>@127.0.0.1:55436/sgpmp_g136_lab"
$env:G136_API_URL="http://127.0.0.1:18036"
$env:G136_ING_EMAIL="ingeniero.g136@pecuaria.co"
$env:G136_ING_PASSWORD="<clave del ingeniero>"

python -m pytest test_tc_m09_274.py -v --noconftest `
  --junitxml="RESULTADOS/$env:G136_RUN_ID/pytest.xml"
```

`--noconftest` es necesario: el `conftest.py` del repositorio importa `src`, que arrastra `fcntl`
y no es importable en Windows. El test es autónomo y no modifica nada del repositorio.

## Reglas que la automatización hace cumplir

- **PostgreSQL real, sin dobles.** No hay `DbFake`, repositorios fake, SQLite, mock del
  repositorio de eventos ni monkeypatch que lance una excepción artificial. El fallo proviene de
  PostgreSQL negando `INSERT INTO modulo1.eventos`.
- **Token antes del `REVOKE`.** El login escribe auditoría RF-10 y contaminaría el fault
  injection. El control previo es de **lectura**, para no consumir el caso.
- **El `REVOKE` toca solo `modulo1.eventos`.** Se comprueba que durante el fault se conservan
  `INSERT` sobre `modulo9.calibraciones` y `modulo9.auditorias_calibraciones`, y que el `SELECT`
  del fixture sigue funcionando: el único fallo inducido es la escritura RF-10.
- **Se verifica que el `REVOKE` es efectivo antes de los POST.** Si el privilegio sobreviviera por
  ownership, superusuario o herencia, el laboratorio sería inválido y los POST no se enviarían.
- **Valor determinista:** `valor_fuera = max + 0.0001` calculado con `Decimal` sobre el rango
  sembrado, de modo que el caso funciona aunque el seed use otro máximo.
- **Una sola invalidez por variante:** en RANGE solo el valor excede el rango; en INACTIVE el
  valor es válido y lo único inválido es el estado del dispositivo.
- **Mensajes comparados de forma exacta** contra el FA de RF-24 v2.0, construyendo valor,
  categoría y serial reales. Conservar el HTTP correcto con un mensaje que incumple el FA es
  variante rechazada.
- **Constancia observable por intento.** El log se agrupa en eventos de alerta: las múltiples
  líneas de una misma excepción cuentan como **un** evento, y cada uno se correlaciona con su POST
  por el sensor que la constancia nombra. Una sola entrada genérica no vale para ambos intentos.
- **Se comprueba que el evento RF-10 realmente no se escribió**, consultando `modulo1.eventos` en
  la ventana de cada intento. Esa ausencia es parte del fault injection, **no** un defecto.
- **Restauración en `finally`:** no depende de que una assertion pase ni del orden de los tests.
  Devuelve exactamente el privilegio que el snapshot PRE demostró disponible y verifica el
  resultado. Si no se logra, se reporta EJECUCIÓN INVÁLIDA / LABORATORIO NO CERRADO en lugar de
  un PASS.
- **El RUN no se sobrescribe** y el `permission denied` intencional **no** es una incidencia.

## Si se detecta un error QA después de los POST

Se conserva el RUN, se marca como **EJECUCIÓN INVÁLIDA POR ERROR QA**, se restauran los permisos,
se corrige la automatización y se ejecuta con un `RUN_ID` nuevo. No es incidencia de producto. En
este caso ya ocurrió una vez: ver `RESULTADOS/run-20261007-140032/EJECUCION_INVALIDA.md`.

## Cierre del laboratorio

```powershell
docker compose -p sgpmp-g136 -f docker-compose.g136.yml stop   # conserva el volumen
docker compose -p sgpmp-g136 -f docker-compose.g136.yml down -v  # limpieza completa
```

Conviene conservarlo hasta validar el informe; la eliminación es una limpieza separada.

## Artefactos por corrida

```text
RESULTADOS/<RUN_ID>/
├── evidencia.json              git, guard del laboratorio, roles de BD, fixtures,
│                               privilegios antes/durante/después, request/response y
│                               snapshots de cada variante, eventos RF-10, alertas,
│                               restauración, resultado, incidencia y seguridad
├── backend.log                 log del backend durante el fault injection, sanitizado
├── pytest.xml
└── TC-M09-G136_resultado.md    informe del caso
```
