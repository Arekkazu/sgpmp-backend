# Implementación — Control de acceso a nivel de base de datos

**Base técnica:** `anotaciones/plan_control_acceso_bd_rls.md`
**Objetivo:** que el aislamiento por finca lo garantice PostgreSQL, no el olvido de quien escribe el repositorio.
**Estado:** nada ejecutado. Este documento dice **quién hace qué, en qué orden y para qué.**

---

## Reparto

| Frente | Responsable | Qué le toca |
|---|---|---|
| **BD** | DBA | Roles de clúster, grants, funciones PL/pgSQL, políticas RLS, índices, migración de datos |
| **Desarrollo** | Backend | Variables de entorno, contexto de sesión, adaptadores, casos de uso, modelos ORM, pruebas |
| **Frontend** | Frontend | Solo F3: cambio de contrato de `PUT /usuarios/{id}/fincas` |
| **Análisis** | Análisis | Decisiones D2 y D3 |

**Toda migración con DDL necesita autorización del DBA comentada en el PR antes del merge.**

---

## Orden

```
F1 roles de BD  →  F2 contexto de sesión  →  F3 usuarios_fincas  →  F4 piloto RLS  →  F5 rollout  →  F6 CI
     (obligatoria)        (obligatoria)          (obligatoria)        (decide si se sigue)
```

F1, F2 y F3 se hacen de todos modos: arreglan huecos reales aunque nunca se llegue a RLS.
**F4 no se puede empezar sin F1.** Un superusuario ignora RLS: las políticas serían decoración.

---

## F1 — Dejar de conectarse como superusuario

| Quién | Tarea | Para qué sirve |
|---|---|---|
| BD | `CREATE ROLE sgpmp_owner NOLOGIN` (dueño de objetos) y `CREATE ROLE sgpmp_app LOGIN` (API). `sgpmp_app`: NOSUPERUSER, NOBYPASSRLS, NOCREATEROLE | Separar quién *es dueño* de quién *consulta*. Sin esta separación las políticas de RLS no aplican: el dueño de una tabla se salta las suyas |
| BD | `REASSIGN OWNED` de los objetos de negocio a `sgpmp_owner` | Que `sgpmp_app` quede como un usuario común y corriente frente a las tablas, sujeto a las reglas |
| BD | Grants a `sgpmp_app` **esquema por esquema** (`modulo1`..`modulo9`, `auditoria`). **`public` queda fuera** | Que la conexión de la API llegue solo a lo del dominio. `public` tiene 18 tablas de otra aplicación que hoy son alcanzables |
| BD | Resolver `modulo8.consultas_auditoria_externas`: o se le escribe política o se le quita el RLS | Hoy tiene RLS activo y cero políticas, lo que en PostgreSQL es *deny-all*. En cuanto dejemos de ser superusuario esa tabla se vuelve invisible sin avisar |
| BD | Mismos roles y grants en la base `pruebas` | Que las pruebas corran en las mismas condiciones que producción, no en una versión más permisiva |
| Desarrollo | `DATABASE_URL` → `sgpmp_app`. Nueva `ALEMBIC_DATABASE_URL` → `sgpmp_owner`, leída en `alembic/env.py` | La API deja de tener privilegios de administrador; las migraciones siguen pudiendo crear objetos |
| Desarrollo | Actualizar `.env.example`, variables del CI y `scripts/provisionar_pruebas.sh` | Que nadie levante un entorno nuevo apuntando otra vez a `postgres` |
| Desarrollo | Correr la suite completa conectada como `sgpmp_app` | Detectar los grants faltantes ahora, en local, y no en despliegue |

**Valor por sí solo:** hoy una credencial filtrada o una inyección SQL entrega el clúster entero. Después de F1, entrega una conexión limitada a las tablas del dominio.
**Listo cuando:** la suite pasa en verde como `sgpmp_app`.
**Reversión:** volver `DATABASE_URL` a `postgres`. Inmediata.

---

## F2 — Contexto de sesión

Solo desarrollo. La BD no toca nada.

| Quién | Tarea | Para qué sirve |
|---|---|---|
| Desarrollo | En `get_current_user` (`src/identity_access/infrastructure/dependencies.py`): `SET LOCAL app.usuario_id` y `SET LOCAL app.id_rol` | Que cada transacción sepa **quién la está ejecutando**. Es el dato que van a leer las políticas de RLS en F4, y el único punto donde se declara |
| Desarrollo | Borrar los 6 `SET LOCAL` dispersos en repositorios de `biological_assets` y `supplies` | El mismo dato ya se pone a mano en 6 sitios para los triggers de auditoría. Pasa a ponerse una vez por request, en un solo lugar |
| Desarrollo | Prueba: el contexto existe dentro del request y **no** sobrevive al siguiente | El pool reutiliza conexiones. Si el contexto se filtrara entre requests, un usuario vería los datos del anterior |

**Valor por sí solo:** menos código y un invariante en un único sitio, con o sin RLS.
**Listo cuando:** los triggers de auditoría de `modulo2` siguen recibiendo su `app.usuario_id` sin que los repositorios lo pongan.

---

## F3 — `usuarios_fincas`

| Quién | Tarea | Para qué sirve |
|---|---|---|
| BD | Migración Alembic: tabla `modulo9.usuarios_fincas` (M:N) + `uq_usuario_finca` + `idx_usuario_finca_usuario` + `idx_usuario_finca_finca` | Hoy el modelo es **1 finca = 1 dueño**, y por eso Veterinario e Ingeniero de Campo ven listados vacíos de fincas que les toca operar. Esta tabla permite que varias personas tengan acceso a una misma finca |
| BD | `CREATE FUNCTION modulo9.fn_fincas_del_usuario(int) ... STABLE SECURITY DEFINER` | Un único objeto que responde "¿qué fincas ve esta persona?". Todas las políticas de F4/F5 lo van a usar, así que cambiar el modelo después toca un solo sitio y no decenas de políticas |
| BD | Migrar los datos desde `modulo9.fincas.id_usuario` (10 filas, 4 propietarios) | Que nadie pierda el acceso que ya tenía al cambiar de modelo |
| BD | Actualizar la vista `modulo9.vw_rf25_contexto_usuario` | La vista resuelve hoy la finca activa desde el modelo viejo; si no se actualiza, devuelve datos incoherentes |
| Desarrollo | Modelo ORM de la tabla nueva (`sqlacodegen`) | Mapear la tabla siguiendo la práctica del repo, sin escribirla a mano |
| Desarrollo | `src/shared/alcance_finca_adapter.py` lee de `usuarios_fincas`, no de `fincas.id_usuario` | Es el punto por el que hoy pasa todo el alcance por finca de la aplicación. Cambiarlo aquí arregla los 7 repositorios de golpe |
| Desarrollo | `asignar_fincas_usuario_use_case.py` pasa de `UPDATE` 1:1 a alta/baja M:N | Poder asignar una finca a varias personas, que es justo lo que pide M02 RF-46 |
| Desarrollo | DTO, schema y curls de `PUT /usuarios/{id}/fincas` | El endpoint deja de ser "cambiar el dueño" y pasa a ser "gestionar accesos" |
| Frontend | Consumir el contrato nuevo | Hoy el endpoint responde 409 si la finca ya tiene dueño; deja de hacerlo. Sin este ajuste el frontend rompe al desplegar |

**Valor por sí solo:** **corrige M02 RF-46, que hoy está incumplido** — existan políticas RLS o no.
**Listo cuando:** un Veterinario asignado a una finca ajena ve los activos de esa finca.

---

## F4 — Piloto de RLS

Dos tablas: `modulo9.infraestructuras` (finca directa) y `modulo2.activos_biologicos` (finca por cadena). Una barata y una cara, para saber a qué nos enfrentamos antes de tocar 187 tablas.

| Quién | Tarea | Para qué sirve |
|---|---|---|
| BD | `ANALYZE` primero | 64 tablas nunca se han analizado y las estadísticas mienten. Medir rendimiento sin esto no dice nada |
| BD | Índices: `fincas.id_usuario` (hoy no tiene ninguno), `infraestructuras.id_finca`, `activos_biologicos.id_infraestructura` | Toda columna que aparezca en una política se consulta en cada query. Sin índice, cada listado se vuelve un recorrido completo de la tabla |
| BD | `CREATE FUNCTION modulo1.fn_alcance_global(int) ... STABLE SECURITY DEFINER` | Responde "¿este rol ve todo?" leyendo `modulo1.permisos` — la misma regla que ya usa la aplicación. Así la regla sigue siendo **dato editable**, no algo quemado en DDL |
| BD | `ENABLE` + **`FORCE ROW LEVEL SECURITY`** y una política por tabla | Es la red de seguridad: aunque un repositorio olvide filtrar, la base devuelve solo las filas que corresponden |
| BD | `EXPLAIN (ANALYZE, BUFFERS)` de los listados más pesados, **con y sin** política | Es el dato que decide si las cadenas de 3 saltos de F5 se resuelven con función auxiliar o desnormalizando `id_finca`. Se decide con la medición, no con una estimación |
| Desarrollo | Dar identidad a las 7 tareas de fondo de `main.py` (ver D1) | Corren sin usuario autenticado. Bajo RLS verían cero filas y los batch nocturnos dejarían de funcionar |
| Desarrollo | Resolver la ingesta por `X-Gateway-Id` (ver D4) | El gateway tampoco tiene usuario, y lo que escribe pertenece a la finca del dispositivo, no a una persona |
| Desarrollo | Prueba de aislamiento: dos usuarios, dos fincas, mismo rol, ninguno ve lo del otro **ni con SQL crudo** | Es la demostración de que la tercera capa realmente existe y no depende de que la aplicación se porte bien |

**Listo cuando:** la prueba de aislamiento pasa y la latencia medida cabe en los 200 ms de RF-04.
**Reversión:** `DROP POLICY` + `DISABLE ROW LEVEL SECURITY`. Sin pérdida de datos.

---

## F5 — Rollout

| Quién | Tarea | Para qué sirve |
|---|---|---|
| Desarrollo + BD | Clasificar las 187 tablas: catálogo (sin RLS) / auditoría (solo lectura) / propia del usuario / finca directa / finca por cadena | Sin clasificación previa se escriben políticas a ojo. Ojo: muchas tablas tienen `id_usuario` como *"quién lo registró"*, no *"de quién es"* — confundirlos deja fuera al dueño legítimo |
| BD | **Una migración Alembic por módulo**, nunca una sola para todo. Orden: `modulo9`, `modulo2`, `modulo3`, `modulo4`, `modulo5`, `modulo6`, `modulo8` | Que un módulo con problemas se pueda revertir sin tumbar los demás |

**Listo cuando:** toda tabla tiene patrón asignado, incluido "sin RLS, y por qué".

---

## F6 — Pruebas negativas en CI

| Quién | Tarea | Para qué sirve |
|---|---|---|
| Desarrollo | Una prueba de integración por patrón que **falle si la política se cae** | Una política borrada por accidente no rompe nada visible: la aplicación sigue respondiendo, solo que de más. Sin esta prueba el hueco vuelve en silencio |
| Desarrollo | Chequeo que detecte tablas de negocio nuevas sin patrón asignado | Que el módulo que se escriba dentro de seis meses no quede fuera del esquema sin que nadie se entere |

**Listo cuando:** quitar una política rompe el CI.

---

## Decisiones a cerrar antes de empezar

| # | Decisión | Quién | Bloquea | Qué pasa si no se decide |
|---|---|---|---|---|
| D1 | Identidad de las 7 tareas de fondo: usuario de servicio en `modulo1.usuarios` *(recomendado)* vs. rol `sgpmp_batch` con `BYPASSRLS` | Equipo + DBA | F1 | Los batch nocturnos dejan de ver datos al activar RLS |
| D2 | `fincas.id_usuario` tras F3: ¿se conserva como "propietario" o se retira? | Análisis | F3 | No se puede escribir la migración de datos |
| D3 | M01 no define en ningún RF la relación usuario↔finca que M02 y M09 dan por hecha | Análisis | F3 | Se implementa una regla de negocio sin requerimiento que la respalde |
| D4 | Cómo resuelve su finca la ingesta por `X-Gateway-Id` | Equipo | F4 | La telemetría deja de entrar al activar las políticas |

**Además, sin bloquear:** el rol `Externo AgroFusion` tiene 6 usuarios activos y 0 permisos — reciben 403 en todo endpoint protegido.

---

## Cuatro reglas que invalidan el trabajo si se rompen

| Regla | Por qué |
|---|---|
| **Ninguna política mientras la app se conecte como `postgres`** | El superusuario ignora RLS por completo. Serían políticas decorativas: seguridad de mentira, peor que ninguna |
| **`FORCE ROW LEVEL SECURITY` siempre** | Sin él, el dueño de la tabla se salta sus propias políticas |
| **Las funciones de alcance van `STABLE`** | Si quedan `VOLATILE` se evalúan una vez **por fila** en vez de una vez por consulta. Es la diferencia entre imperceptible e inaceptable |
| **Las pruebas se conectan como `sgpmp_app`** | Si corren como superusuario pasan en verde con producción abierta — es el peor modo de fallo del plan |

Y dos cosas que **no** se tocan: el RBAC se queda como está (los 337 permisos siguen siendo datos en `modulo1.permisos`, no `GRANT`s) y **no se crea un rol de PostgreSQL por cada rol del sistema** — son 2 fijos, aunque mañana existan 50 roles de negocio.
