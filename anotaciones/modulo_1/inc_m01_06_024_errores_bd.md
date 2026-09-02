# INC-M01-06-024 — reintentos de conexión y traducción de fallos de BD

Fecha: 2026-09-02 · Rama: `fix/inc-m01-06-024-reintentos-bd`

## Qué pasaba

`get_db()` no reintentaba la conexión a PostgreSQL ni traducía el fallo a un error
controlado. Ante una caída de BD propagaba el `OperationalError` crudo de SQLAlchemy,
Starlette lo convertía en `500 Internal Server Error` en **texto plano** — sin
`error_code`, sin `timestamp`, con una forma distinta a la del resto de la API — y
`POST /sesiones/` daba a entender que el fallo era de la aplicación.

RF-02 exige agotar 3 reintentos internos y responder `503 Service Unavailable` con un
mensaje claro.

## Qué se hizo

### 1. Reintentos y traducción en `get_db` (`src/shared/database.py`)

`get_db` toma la conexión al inicio del request y reintenta **3 veces** con pausa de
0.5 s. Si la BD sigue sin responder, lanza `ServiceUnavailableError` →
**503 `BD_NO_DISPONIBLE`**.

La pausa es corta a propósito: el frontend aborta a los 15 s
(`sgpmp-frontend/src/shared/api/http.ts`), así que el presupuesto total de reintentos
(~1 s medido) tiene que caber muy por debajo de ese límite. Reutiliza el idiom que ya
existía en `src/shared/email.py` (`_MAX_RETRIES = 3` → `ServiceUnavailableError`).

También se añadió el `rollback()` que faltaba en el `except`: sin él, una excepción a
mitad de request dejaba la transacción abierta y la sesión podía volver al pool
contaminada.

### 2. Reconexión automática

El engine pasa a `create_engine(DATABASE_URL, pool_pre_ping=True, pool_recycle=1800)`.
Antes estaba pelado, con `pool_recycle=-1`: una conexión que el proxy mataba por
inactividad reventaba el primer request que la sacara del pool. `pool_pre_ping` **es**
la reconexión — no hace falta un bucle propio a nivel de engine.

Curiosidad: `tests/integration/conftest.py` ya usaba `pool_pre_ping=True`. El test
estaba mejor configurado que producción.

### 3. Red de seguridad global (`src/shared/error_handlers.py`)

Los reintentos cubren el fallo **al tomar** la conexión. Perderla **a mitad** del
request seguía saliendo como texto plano, igual que los ~35 `flush()/commit()` sin
`try/except`, los 208 `commit()` que viven en use cases y todas las lecturas (ningún
repositorio envuelve sus queries de lectura). Se registran cuatro handlers nuevos:

| Excepción | Respuesta |
|---|---|
| `OperationalError`, `InterfaceError` | 503 `BD_NO_DISPONIBLE` |
| `SQLAlchemyError` (resto) | 500 `ERROR_INTERNO` |
| `Exception` (cualquier otra) | 500 `ERROR_INTERNO` |

El detalle de la excepción va **solo al log**, junto con el `X-Request-ID`. El cliente
nunca ve cadenas de conexión, credenciales ni tracebacks.

## Cambios en los códigos de error — para frontend

Los 289 códigos de negocio existentes **no cambian**. Solo se tocaron los que emitía el
traductor de BD (`src/shared/db_error_translator.py`), que eran crípticos o mentían
sobre de quién era la culpa:

| Caso | Antes | Ahora |
|---|---|---|
| Violación de unicidad | 409 `UNICIDAD` · "El recurso ya existe" | 409 `RECURSO_DUPLICADO` · "Ya existe un registro con esos datos." |
| Violación de check | 400 `VAL_ENTRADA` | 400 `VALOR_NO_PERMITIDO` |
| FK: el registro está referenciado | **500** `INFRAESTRUC` | **409** `REFERENCIA_EN_USO` |
| FK: el referenciado no existe | **500** `INFRAESTRUC` | **400** `REFERENCIA_INVALIDA` |
| Dato fuera de rango | 400 `VAL_ENTRADA` | 400 `VALOR_FUERA_DE_RANGO` |
| Fallo de conectividad | **500** `INFRAESTRUC` | **503** `BD_NO_DISPONIBLE` |
| Resto | 500 `INFRAESTRUC` | 500 `ERROR_INTERNO` |

Las dos violaciones de FK dejan de ser 500: en ambos casos el origen es el dato que
mandó el cliente, no un fallo del servidor.

### Fin de la fuga de nombres de constraint

El traductor pasaba `field=<nombre crudo del constraint>`, así que el frontend recibía
`{"field": "uq_usuario_correo"}` y `describeField` lo renderizaba al usuario como
**"Uq usuario correo"**. Pasaba en **109 de 127** call-sites (los que no declaran un
mensaje amigable).

Ahora un helper deriva el nombre de columna real: prefiere el `column_name` que da
PostgreSQL y, si no está, limpia el constraint quitando el prefijo de tipo
(`uq_`, `uk_`, `fk_`, `ck_`, `chk_`, `pk_`, `idx_`, `ix_`) y el de tabla. Así
`uq_usuario_correo` sobre la tabla `usuario` sale como `field: "correo"`.

**El frontend no necesita ningún cambio.** `resolveMessage` ya prioriza `data.message`,
así que los mensajes nuevos en español llegan tal cual, y el shape de la respuesta
(`error_code`, `message`, `fields`, `timestamp`) es exactamente el mismo de siempre.

Se comprobó ejecutando `mapToApiError` del frontend contra cada respuesta nueva. Esto es
lo que termina viendo el usuario:

| HTTP | `error_code` | Texto mostrado | `field` |
|---|---|---|---|
| 503 | `BD_NO_DISPONIBLE` | El servicio no está disponible temporalmente. Intenta de nuevo en unos momentos. | — |
| 409 | `RECURSO_DUPLICADO` | Ya existe un registro con esos datos. | `correo` |
| 409 | `RECURSO_DUPLICADO` | El correo ya está registrado. *(mensaje del repositorio)* | `correo` |
| 400 | `REFERENCIA_INVALIDA` | El registro relacionado que indicaste no existe. | `id_especie` |
| 409 | `REFERENCIA_EN_USO` | No se puede eliminar: otros registros dependen de este. | — |
| 500 | `ERROR_INTERNO` | Ocurrió un error interno. Intenta de nuevo; si el problema persiste, contacta al equipo de soporte. | — |

El `error_code` no se muestra nunca: solo alimenta las ramas de decisión que ya existen
(`TOKEN_EXPIRADO` para el refresh en `http.ts`, `CUENTA_PENDIENTE` en `LoginPage`).

Nota: el correlativo de la petición viaja en la cabecera `X-Request-ID` y `mapToApiError`
no lee cabeceras. Si en algún momento quieren mostrarlo en los errores 500, ahí está.

## Efecto colateral corregido

Dos bucles de reintento de módulo 5 (`registrar_suministro_directo_use_case.py` y
`registrar_correccion_suministro_use_case.py`) reintentaban ante `InfrastructureError`.
Como los fallos de conectividad ahora salen como `ServiceUnavailableError`, habrían
dejado de reintentarse. Ambos pasan a capturar `_ERRORES_REINTENTABLES`
(`InfrastructureError` + `ServiceUnavailableError`).

De paso ganan algo: una violación de FK es determinística y antes se reintentaba 3
veces en vano; ahora falla de inmediato.

## Pruebas

Tres archivos nuevos en `tests/shared/`, 38 casos:

- `test_database_reintentos.py` — cubre el incidente: reintenta 2 veces y conecta a la
  tercera; agota los 3 y lanza 503 `BD_NO_DISPONIBLE`; `InterfaceError` también se
  reintenta; el mensaje no expone la cadena de conexión.
- `test_db_error_translator.py` — una prueba por rama del mapeo. La que importa:
  `uq_usuario_correo` sobre la tabla `usuario` sale como `field="correo"` y **nunca**
  contiene `uq_`.
- `test_error_handlers_globales.py` — los cuatro handlers emiten el mismo cuerpo y no
  filtran el detalle de la excepción al cliente.

`pytest.ini` gana `testpaths = tests`. Sin eso, `pytest` a secas recolecta los repos de
AgroFusion vendorizados bajo `anotaciones/` y aborta con `ModuleNotFoundError` antes de
correr un solo test. Nota: hay que invocar `python -m pytest`, no `pytest` a secas — es
`python -m` quien pone la raíz del repo en `sys.path` para que los tests importen `src`.

También se borró `tests/schemas.py`, copia byte-a-byte de `src/shared/schemas.py` que no
importaba nadie.

## Verificación hecha

| Comprobación | Resultado |
|---|---|
| Suite unitaria | 197 pasan (eran 159 + 38 nuevos), 0.9 s |
| BD inalcanzable → `POST` | 503 `BD_NO_DISPONIBLE`, 3 intentos en el log, **1.05 s** de latencia |
| Ciclo `docker stop` → `docker start` de la BD | 200 de nuevo **sin reiniciar la app** |
| Integración (base `pruebas`) | 89 pasan, 10 fallan — **idénticos** a los del baseline sin estos cambios |

Los 10 fallos de integración son preexistentes: la base local `pruebas` está varada en
el baseline `f7fe43537842`. Se verificó con `git stash` que el conteo es exactamente el
mismo antes y después del cambio.

## Fuera de alcance

Se evaluaron y se descartaron para no mezclar despliegue con el arreglo del incidente:

- Gate de pruebas en el `Dockerfile` (correr la suite al construir la imagen).
- `healthcheck` del backend en `docker-compose.yml`.
- `/health` consultando la BD y devolviendo 503 cuando no responde.

Si se retoman, ojo con dos detalles ya comprobados: `.dockerignore` excluye `tests/` y
tapa `.env.example` (que `test_jwt_config.py` lee), y sus reglas `__pycache__/` /
`.pytest_cache/` solo aplican en la raíz, así que se cuelan `.pyc` con rutas del host
dentro de la imagen. Sobre el `healthcheck`: se verificó que en Docker Compose normal un
contenedor `unhealthy` **no** se reinicia (`RestartCount: 0` tras 481 fallos seguidos
con `restart: unless-stopped`); eso solo ocurre en modo Swarm.
