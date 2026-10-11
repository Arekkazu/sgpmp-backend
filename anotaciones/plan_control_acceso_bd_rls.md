# Control de acceso a nivel de base de datos — análisis y plan (RBAC de aplicación ↔ RLS de PostgreSQL)

**Estado:** propuesta de arquitectura. Ningún DDL de este documento ha sido ejecutado.
**Alcance:** transversal a todos los módulos.
**Fecha del diagnóstico:** 2026-09-16, contra la base `sgpmp` (PostgreSQL 17.11).

---

## 1. Resumen ejecutivo

**El problema.** El sistema tiene dos filtros de acceso y ambos viven en la
aplicación. El primero (¿qué acción sobre qué recurso?) está sólido: 206 de 239
endpoints pasan por `require_permission`. El segundo (¿qué filas?) es opt-in y
está aplicado en 7 de 104 repositorios: el router calcula `ids_fincas_permitidas`
y lo pasa a mano hacia abajo. Si alguien olvida pasarlo, **nada falla** — la
consulta simplemente devuelve todas las filas del sistema.

Por debajo no hay red. Todas las consultas llegan a PostgreSQL con la **misma
identidad**: `postgres`, superusuario, con `rolbypassrls`, y es el **único rol con
login de todo el clúster**.

**El requerimiento existe** y es más exigente que lo implementado. M09 RF-19 y
RF-20 lo dicen como RNF de seguridad: *"El sistema debe garantizar el aislamiento
de datos entre fincas."* M02 RF-46 define una matriz por rol. M01 RF-10 ya sentó
el precedente de exigir cumplimiento *"a nivel de API y Base de Datos"*.

**La recomendación.** Mantener el RBAC donde está y añadir una tercera capa en la
base de datos mediante **Row Level Security gobernada por variables de sesión**
(`SET LOCAL app.usuario_id`), no mediante un mapeo de roles de aplicación a roles
de PostgreSQL. Esto responde la duda de partida: **no se crea ni un solo usuario
de PostgreSQL por usuario ni por rol del sistema**. Se crean exactamente dos
roles de clúster, fijos, que no cambian aunque mañana existan cincuenta roles de
aplicación.

**El costo.** La parte cara no es RLS: es que solo 6 tablas de 187 referencian
`fincas` y el resto llega a ella por cadenas de dos o tres saltos. Y hay un
prerrequisito de modelo sin el cual las políticas congelarían un incumplimiento
(ver §7.6).

**La ventana.** La tabla de negocio más grande tiene ~1.776 filas y los nueve
esquemas suman unas 6.000. El rendimiento **no es hoy un obstáculo** — y
precisamente por eso este es el momento barato para hacerlo.

---

## 2. Qué pide el requerimiento

Todas las citas son literales, con archivo y línea.

### 2.1 Aislamiento por finca (Módulo 9)

`anotaciones/Requerimientos/Especificacion-Requerimientos-Modulo9.md:1168` (RF-19, RNF)
y `:1358` (RF-20, RNF), idéntico en ambos:

> Seguridad: El sistema debe garantizar el aislamiento de datos entre fincas.

`…Modulo9.md:1014` (RF-19, Restricciones):

> Los usuarios con rol Productor solo pueden consultar la información de las
> fincas a las que están asignados.

`…Modulo9.md:1162` (RF-19, Criterios de aceptación):

> Los usuarios con rol Productor solo pueden visualizar las fincas a las que
> están asignados.

`…Modulo9.md:982` (RF-19, Descripción):

> Cada finca representa una unidad organizacional independiente dentro del
> sistema, a la cual se asociarán los usuarios, la infraestructura productiva,
> los dispositivos de monitoreo y los activos biológicos gestionados.

### 2.2 Visibilidad por granja y rol (Módulo 2)

`…Modulo2.md:424-427` (RF-34, Restricciones):

> 3. Visibilidad Limitada por Granja y Rol (RBAC)
> El usuario solo puede consultar la asociación de activos pertenecientes a las
> granjas a las que tiene acceso **según su perfil en M01**.

`…Modulo2.md:3557-3561` (RF-46, Precondiciones) — la matriz explícita:

> 3. El usuario debe tener permisos de consulta sobre el activo según su rol (RF-04):
>    — Productor: puede consultar el historial de sus propios activos.
>    — Veterinario: puede consultar el historial de activos de la finca asignada.
>    — Administrador: puede consultar el historial de todos los activos del sistema.

`…Modulo2.md:3704` (RF-46, Criterios de aceptación):

> El sistema muestra exclusivamente los registros que corresponden al nivel de
> visibilidad del rol del usuario.

### 2.3 Precedente de cumplimiento en la base de datos (Módulo 1)

`…Modulo1.md:1909` (RF-10, Flujo alterno — inmutabilidad):

> El sistema debe tener bloqueados estos métodos a nivel de API y Base de Datos.

Esto **ya está implementado** con triggers que bloquean `UPDATE`/`DELETE` sobre
`modulo1.eventos` incluso para el rol `postgres`. Es decir: el proyecto **ya
acepta** que ciertas garantías vivan en el motor, no solo en la aplicación. Lo
que se propone aquí es la misma idea aplicada a la visibilidad de filas.

### 2.4 Auto-acceso y enmascaramiento (Módulo 1)

`…Modulo1.md:2505` (RF-13, Restricciones):

> El usuario solo puede acceder a su propio perfil.

`…Modulo1.md:2286` (RF-12, Restricciones) — protección **a nivel de columna**,
no de fila:

> mostrarse completo únicamente si el administrador posee el permiso de acción
> 'ver_identificacion_completa' sobre el recurso 'usuario', conforme al modelo
> RBAC definido en RF-04.

### 2.5 La dependencia colgante

M02 RF-34 delega el alcance por granja a *"su perfil en M01"*, y M09 RF-25 toma
`id_finca` como *"la finca activa asociada al usuario"*. Pero **ningún RF del
Módulo 1 define una relación usuario↔finca**: los 14 RF de M01 son RBAC global
(RF-03/RF-04) más una única regla de auto-acceso a nivel de sesión (RF-13). No
hay entradas, salidas ni restricciones que hablen de fincas en todo M01. RF-11
habla explícitamente del *"listado global de usuarios"*.

**Consecuencia:** el alcance por finca se implementó (RF-25) sin un requerimiento
de M01 que lo respaldara, y por eso su regla de negocio —"quién ve todo"— quedó
inferida desde los permisos en vez de declarada. Esto debería corregirse en la
especificación, no solo en el código.

---

## 3. Estado actual de la aplicación

### 3.1 Las tres capas

| Capa | Pregunta que responde | Mecanismo | Cobertura |
|---|---|---|---|
| 1 — RBAC | ¿Puede este rol ejecutar esta acción sobre este recurso? | `require_permission` (`src/shared/rbac.py:39`) contra `modulo1.permisos` | **206 / 239 endpoints** |
| 2 — Alcance | ¿Qué filas puede ver? | `AlcanceFincaPort` / `AlcanceFincaAdapter` (`src/shared/alcance_finca_*.py`) | **7 / 104 repositorios** |
| 3 — Motor | ¿Se puede saltar el filtro por error? | — | **Inexistente** |

Los 33 endpoints sin RBAC no son un descuido: son públicos por diseño
(`contrasena_routers.py`, login/registro en `sesiones_routers.py`,
`/usuarios/me`) o puertas máquina-a-máquina (`agrofusion_integration_router.py`
con credenciales M2M, `version_modelo_router.py:42` con `X-RF71-Internal-Key`,
y la ingesta por `X-Gateway-Id`). `auditoria_routers.py` usa su propia
dependencia `verificar_acceso_auditoria` (`auditoria_routers.py:68`).

### 3.2 Cómo funciona hoy el alcance por finca

`src/shared/alcance_finca_adapter.py:34-46`:

- **Global** si el rol tiene permiso `U` (3) o `D` (4) sobre el recurso `fincas`
  (`id_recurso = 9`) → devuelve `None`, que aguas abajo significa "sin filtro".
- **Restringido** en cualquier otro caso → `SELECT id_finca FROM modulo9.fincas
  WHERE id_usuario = :id_usuario`.

Es una decisión correcta de diseño (la regla es dato, no `id_rol` quemado), pero
el resultado se transporta **como argumento de función** desde el router hasta el
repositorio. No hay nada en la sesión, en el engine ni en el motor que lo
garantice.

Repositorios que sí aplican alcance de finca (7):

- `biological_assets/…/activo_biologico_repository.py:161-202`
- `configuration/…/dispositivo_iot_repository.py:37-103`
- `configuration/…/infraestructura_repository.py:39-98`
- `telemetry/…/alerta_repository.py:139-217`
- `telemetry/…/historial_telemetria_repository.py:152-154`
- `telemetry/…/monitoreo_repository.py:140-165`
- `telemetry/…/vinculacion_lectura_repository.py:48-99`

### 3.3 Ejemplos concretos del hueco

Nueve consultas que hoy no filtran por pertenencia:

| # | Ubicación | Qué devuelve de más |
|---|---|---|
| 1 | `configuration/…/plantilla_repository.py:44-50` | `listar_todas()` devuelve las plantillas de todos los usuarios, aunque el modelo **tiene** `id_usuario` y lo usa al guardar (línea 54) |
| 2 | `supplies/…/medicamento_repository.py:166-186` | `listar()` filtra por activo/fecha/estado, nunca por dueño |
| 3 | `supplies/…/registro_suministro_repository.py:135-140` | el `id_gestion_fases` viene del path sin verificar que la fase sea de una finca del usuario |
| 4 | `biological_assets/…/evento_activo_repository.py:185-192` | `listar_por_activo()` sin gate; la protección vive fuera, en el use case |
| 5 | `configuration/…/sensor_repository.py:48-57` | `listar_por_dispositivo()` sin alcance, aunque el módulo ya lo tiene en `dispositivo_iot_repository.py:103` |
| 6 | `telemetry/…/estado_dispositivo_iot_repository.py:35-41` | `listar_activos()` devuelve el estado de todos los dispositivos IoT del sistema |
| 7 | `telemetry/…/telemetria_repository.py:109-125` | SQL crudo por `id_sensor`, sin join a finca |
| 8 | `configuration/…/identidad_visual_repository.py:41` | filtra por el `id_finca` **que viene del path**, sin comprobar que esa finca sea del usuario |
| 9 | `configuration/…/widget_datos_repository.py:37` | `SELECT * FROM {vista}` con nombre interpolado (mitigado por allowlist), sin ningún filtro de fila |

El patrón se repite: **la protección está donde alguien se acordó de ponerla.**
Ninguno de estos casos es un bug de una persona; es la consecuencia previsible de
que el alcance sea un argumento opcional en vez de una propiedad de la sesión.

### 3.4 El mecanismo que ya existe y nadie ha generalizado

`SET LOCAL app.usuario_id` **ya se usa en este repositorio**, para alimentar
triggers de auditoría:

- `biological_assets/…/activo_biologico_repository.py:97` y `:391`
- `biological_assets/…/evento_activo_repository.py:116`
- `biological_assets/…/historico_estado_repository.py:33`
- `biological_assets/…/registrar_transferencia_use_case.py:252`
- `supplies/…/estado_activo_m02_adapter.py:50`

Y las funciones PL/pgSQL del baseline ya leen `current_setting('app.usuario_id')`
(`alembic/baseline/esquema_baseline.sql:5098` y `:15351`).

Esto importa mucho para la valoración de esfuerzo: **la propuesta de este
documento no inventa un mecanismo nuevo.** Toma uno que ya está en producción y
lo mueve de ad-hoc por repositorio a sistemático por request — eliminando de paso
esas seis llamadas dispersas.

### 3.5 Infraestructura de sesión

`src/shared/database.py`: engine con `pool_pre_ping=True`, `pool_recycle=1800`,
`QueuePool` por defecto. `get_db()` abre la sesión, fuerza el checkout con
reintentos y hace `rollback()`/`close()`. **No hay ningún `event.listen` ni
`execution_options` en todo `src/`**, y `SET ROLE` no se usa en ninguna parte.

`get_current_user` (`src/identity_access/infrastructure/dependencies.py:40-138`)
es el punto de paso natural: ya tiene la sesión abierta y **ya relee el rol
vigente contra la base en cada request**, ignorando a propósito el claim `rol`
del JWT para que una reasignación administrativa aplique sin cerrar sesión
(comentario en `dependencies.py:78-82`). `UsuarioActual` lleva hoy cuatro campos
—`id_usuario`, `id_token`, `id_rol`, `id_estado_cuenta`— y **ningún
identificador de finca o tenant**.

---

## 4. Estado actual de la base de datos

Cada dato viene de una consulta reproducible vía MCP de postgres.

### 4.1 Identidad de conexión

```sql
SELECT current_user, session_user, current_database(), version();
```

| current_user | session_user | base | versión |
|---|---|---|---|
| `postgres` | `postgres` | `sgpmp` | PostgreSQL 17.11 |

`.env` → `DATABASE_URL=postgresql://postgres:***@localhost:5432/sgpmp`.

### 4.2 Roles del clúster

```sql
SELECT rolname, rolsuper, rolcanlogin, rolbypassrls FROM pg_roles ORDER BY rolname;
```

16 filas. **15 son roles predefinidos de PostgreSQL** (`pg_read_all_data`,
`pg_monitor`, …), ninguno con login. El decimosexto:

| rolname | rolsuper | rolcanlogin | rolbypassrls |
|---|---|---|---|
| `postgres` | **true** | **true** | **true** |

**No existe ningún rol de aplicación.** Y con `rolsuper = true`, RLS es inoperante
por definición: un superusuario se salta todas las políticas, y `FORCE ROW LEVEL
SECURITY` tampoco lo detiene.

### 4.3 Row Level Security existente

```sql
SELECT schemaname, tablename, rowsecurity FROM pg_tables WHERE rowsecurity;
SELECT * FROM pg_policies;
```

| esquema | tabla | RLS | políticas |
|---|---|---|---|
| `cron` | `job` | sí | `cron_job_policy` (la crea `pg_cron`) |
| `cron` | `job_run_details` | sí | `cron_job_run_details_policy` (la crea `pg_cron`) |
| `modulo8` | `consultas_auditoria_externas` | **sí** | **ninguna** |

**Cero políticas de negocio.** Y una trampa latente: `modulo8.consultas_auditoria_externas`
tiene RLS habilitado sin ninguna política, lo que en PostgreSQL significa
*deny-all*. Hoy es inocuo porque solo se conecta un superusuario; el día que la
aplicación pase a un rol normal, esa tabla se vuelve invisible sin previo aviso.
Es el primer sitio que hay que revisar en la fase 1.

### 4.4 Grants

```sql
SELECT grantee, table_schema, privilege_type, count(*)
FROM information_schema.role_table_grants GROUP BY 1,2,3;
```

Ningún esquema de negocio tiene grants a `PUBLIC` ni a ningún rol distinto de
`postgres`. Crear `sgpmp_app` implica otorgar privilegios desde cero, esquema por
esquema — lo cual es una oportunidad, no un problema: permite dejar fuera lo que
no corresponde (ver §4.7).

### 4.5 La matriz RBAC, en cifras reales

| Tabla | Filas | Nota |
|---|---|---|
| `modulo1.roles` | **11** | no 5; hay 6 creados después del seed, y el `id_rol` 11 fue eliminado |
| `modulo1.acciones` | 5 | C, R, U, D, E — con `CHECK` de dominio |
| `modulo1.recursos` | **58** | 13 marcados `es_proceso_especial` |
| `modulo1.permisos` | **337** | `UNIQUE (id_rol, id_recurso, id_accion)`, `ON DELETE CASCADE` desde roles |
| `modulo1.usuarios` | 36 | 27 cuentas activas, 7 pendientes, 1 inactiva |

Roles actuales: Administrador (141 permisos), Productor (47), Veterinario (65),
Ingeniero de Campo (44), Contador (25), Supervisor (2), Gestor de Granja (2),
Revisor Fiscal (6), **Externo AgroFusion (0)**, Prueba (4), Integración M04 (1).

> **Hallazgo:** el rol `Externo AgroFusion` (id 9) tiene **6 usuarios activos y
> cero permisos**. Con RBAC puro, esos seis usuarios reciben 403 en todo endpoint
> protegido. Es independiente de este análisis, pero conviene resolverlo.

Esta tabla es la razón de fondo por la que **el RBAC no puede bajar a GRANTs**:
337 combinaciones sobre 58 "recursos" que en su mayoría **no son tablas**. El
comentario de `modulo1.recursos` lo dice textualmente:

> Un recurso puede ser una tabla, vista, módulo, endpoint o proceso especial.

### 4.6 El modelo de pertenencia

`modulo9.fincas` — 10 filas, 7 activas, 4 propietarios distintos, 1 sin dueño:

| columna | tipo | nulable |
|---|---|---|
| `id_finca` | integer | NO |
| `id_usuario` | integer | **SÍ** |

- FK `finca_id_usuario_fkey → modulo1.usuarios(id_usuario)`, declarada **`NOT VALID`**.
- **Sin índice sobre `id_usuario`.** El único índice es la PK.
- **Solo 6 tablas en toda la base referencian `modulo9.fincas`**:
  `modulo3.reglas_alertas`, `modulo4.alertas_patologicas`,
  `modulo8.reportes_regulatorios`, `modulo9.auditorias_fincas`,
  `modulo9.identidad_visuales`, `modulo9.infraestructuras`.
- **`modulo2.activos_biologicos` no tiene `id_finca`.** Llega por
  `id_infraestructura → modulo9.infraestructuras.id_finca`. Ninguna tabla de
  `modulo5` ni `modulo6` tiene `id_finca` tampoco.

La cadena canónica de pertenencia, tal como ya la codifica
`src/supplies/infrastructure/adapters/alcance_activo_m02_adapter.py:22-29`:

```
modulo1.usuarios
   └── modulo9.fincas.id_usuario
          └── modulo9.infraestructuras.id_finca
                 └── modulo2.activos_biologicos.id_infraestructura
                        └── (modulo3, modulo4, modulo5, modulo6 …)
```

Muchas tablas tienen `id_usuario`, pero la mayoría lo usa como **"quién lo hizo"**
(auditoría), no como **"de quién es"**. Distinguir ambos usos tabla por tabla es
parte del trabajo de la fase de rollout, y no se puede automatizar por nombre de
columna.

### 4.7 Volumetría y extensiones

Extensiones: `pg_cron 1.6`, `pgcrypto 1.3`, `plpgsql 1.0`.

| esquema | tablas base | filas aprox. |
|---|---|---|
| `auditoria` | 3 | 12.934 (28 MB — `logs_dml` + `logs_ddl`) |
| `modulo1` | 22 | 2.119 |
| `modulo9` | 46 | 2.055 |
| `modulo4` | 24 | 1.332 |
| `modulo2` | 20 | 209 |
| `modulo5` | 25 | 107 |
| `modulo3` | 17 | 100 |
| `modulo8` | 13 | 62 |
| `modulo7` | 15 | 61 |
| `modulo6` | 18 | 47 |

La tabla de negocio más grande (`modulo9.auditorias_dispositivos_iot`) tiene
~1.776 filas.

> **Aviso metodológico:** `reltuples` está desactualizado —dice 12 usuarios donde
> hay 36, y 259 permisos donde hay 337— y **64 tablas nunca han sido analizadas**
> (18 en `modulo5`, 17 en `modulo9`). Antes de cualquier medición de rendimiento
> hay que correr `ANALYZE`.

> **Hallazgo:** el esquema `public` contiene **18 tablas de una aplicación ajena
> al dominio** (taller de servicio técnico: `clientes`, `ordenes_servicio`,
> `ventas`, `productos`, `cotizaciones`…) más `alembic_version` y
> `_sqlx_migrations`. Un rol de aplicación con grants amplios las alcanzaría.
> Los grants de `sgpmp_app` deben acotarse esquema por esquema.

Otras rarezas encontradas, para registro:

- `modulo1.roles.fecha_creacion` y `fecha_actualizacion` son `time with time
  zone` (solo hora, sin fecha), a diferencia del resto del modelo que usa
  `timestamptz`.
- Typo en el DDL real: `modulo3.historico_transiciones_dispositivos.id_usuairo_responsable`
  (con FK correcta a `modulo1.usuarios`).

---

## 5. La idea de partida, evaluada

El planteamiento original era:

> La persona dice: "Soy Juan y soy un Técnico". El JWT transporta esa afirmación
> de forma segura hacia la API. El backend lee el JWT y traduce: "Técnico =
> `app_autenticado`". La base de datos recibe la orden: "Asume el rol
> `app_autenticado` y filtra por RLS usando el ID de Juan".

**La estructura es correcta.** Separa tres cosas que deben estar separadas: quién
afirma la identidad (el JWT), quién la traduce (el backend) y quién la hace
cumplir (el motor). Ese es exactamente el modelo que se recomienda. Necesita dos
correcciones.

### 5.1 Corrección 1 — "Técnico = `app_autenticado`" no debe ser un mapeo rol-app → rol-PG

Tres razones, en orden de gravedad:

**a) Los roles del sistema son datos CRUD-ables; los de PostgreSQL son DDL.**

RF-03 exige crear, modificar y eliminar roles por API, y está implementado
(`roles_routers.py`, 10 endpoints). La prueba está en la base: hay **11 roles**,
no los 5 del seed. Seis se crearon después (Supervisor, Gestor de Granja, Revisor
Fiscal, Externo AgroFusion, Prueba, Integración M04) y uno se eliminó (falta el
`id_rol` 11).

Espejar eso 1:1 significaría ejecutar `CREATE ROLE` y `DROP ROLE` dentro del
request HTTP de "crear rol". Para eso, la conexión de la aplicación necesitaría
el atributo `CREATEROLE` — es decir, **la aplicación podría fabricarse roles de
base de datos**. Eso es una vía de escalada de privilegios abierta de par en par,
y es estrictamente peor que el problema que se quería resolver.

**b) `modulo1.recursos` no son tablas, así que `GRANT` no puede expresarlos.**

De los 58 recursos, 13 están marcados `es_proceso_especial`: "cierre de ciclo
productivo", "administración del motor batch ICA", "exportación de datos",
"provisión NIC-41". `GRANT` solo sabe hablar de tablas, vistas, columnas,
secuencias y funciones. No existe forma de expresar "este rol puede **ejecutar**
el cierre de ciclo" como un privilegio SQL sin inventar una función por cada
proceso y gestionarle el `EXECUTE` — lo cual multiplica el problema (a).

La matriz de 337 permisos × 58 recursos **no es traducible a GRANTs**, ni total
ni parcialmente sin perder semántica.

**c) RF-03 y RF-04 exigen propagación inmediata sin cerrar sesión.**

> Los cambios realizados en permisos deben reflejarse inmediatamente en las
> sesiones activas del sistema, aplicándose en la siguiente solicitud realizada
> por el usuario.

`…Modulo1.md:809` (RF-04, Restricciones). Ídem `:527` para RF-03.

Con `modulo1.permisos` eso es un `UPDATE` y ya: `require_permission` consulta la
tabla en cada request. Con GRANTs sería **DDL en caliente sobre un clúster en
uso**, tomando locks sobre objetos que otras transacciones están leyendo.

### 5.2 Corrección 2 — la identidad viaja en un GUC, no en el rol de conexión

En lugar de `SET ROLE <rol_del_usuario>`, la transacción declara **quién es** el
usuario:

```sql
SET LOCAL app.usuario_id = '42';
SET LOCAL app.id_rol     = '3';
```

Y las políticas leen `current_setting('app.usuario_id', true)`.

Ventajas concretas sobre `SET ROLE`:

| | `SET ROLE` | `SET LOCAL app.*` |
|---|---|---|
| Roles PG a crear | uno por rol de aplicación, en DDL | **dos, fijos** |
| Crear un rol nuevo en la app | `CREATE ROLE` + `GRANT` en el request | un `INSERT` |
| Fuga entre requests por el pool | sí, si falta `RESET ROLE` | **no**: `SET LOCAL` muere en el `COMMIT`/`ROLLBACK` |
| Granularidad | tabla/columna | **cualquier predicado SQL** |
| Convención en este repo | no se usa en `src/` | **ya en uso en 6 sitios** |

### 5.3 Respuesta directa a la duda de partida

> *"Ya tener muchos usuarios en la BD por cada rol es algo que podría afectar."*

Con el diseño recomendado **se crean cero usuarios de PostgreSQL por usuario o
rol del sistema**. El clúster pasa de 1 rol con login a **2**:

- `sgpmp_owner` — dueño de los objetos, corre Alembic. No usado por la API.
- `sgpmp_app` — la conexión de la aplicación.

Y esos dos no cambian nunca, ni cuando se creen cincuenta roles de negocio. La
identidad del usuario no vive en el catálogo de PostgreSQL: vive en una variable
de la transacción, que dura lo que dura el request.

---

## 6. Opciones evaluadas

| | **A. Espejo de roles PG + GRANTs** | **B. RLS con GUC de sesión** (recomendada) | **C. Híbrido con `SET ROLE` de solo lectura** | **D. Reforzar solo la aplicación** |
|---|---|---|---|---|
| Qué cubre | permisos por tabla | **filas, con cualquier predicado** | lectura/escritura gruesa + filas | el olvido accidental |
| Roles PG a crear | uno por rol de app (hoy 11, creciendo) | **2 fijos** | 3 fijos | 0 |
| Crear rol en la app | DDL en el request, requiere `CREATEROLE` | `INSERT` | `INSERT` | `INSERT` |
| ¿Expresa la matriz de 337 permisos? | **no** (recursos ≠ tablas) | no aplica — el RBAC se queda en la app | no aplica | sí, como hoy |
| Propagación inmediata (RF-03/04) | DDL en caliente | **sí** | sí | sí |
| Protege ante `WHERE` olvidado | no | **sí** | sí | parcialmente (con test) |
| Protege ante SQL crudo / acceso directo | no | **sí** | sí | **no** |
| Riesgo con el pool de conexiones | alto | **bajo** (`SET LOCAL`) | medio (exige `RESET ROLE`) | ninguno |
| Esfuerzo | alto y recurrente | **medio, concentrado** | medio-alto | **bajo** |
| ¿Rompe las tareas de fondo e ingesta? | sí | sí — hay que darles identidad | sí | no |

**A queda descartada** por las tres razones de §5.1: no es que sea cara, es que
no puede expresar el modelo.

**C** añade una capa de `SET ROLE` (por ejemplo, un rol de solo lectura para los
endpoints de consulta) sobre B. Es defensible a futuro, pero el beneficio
marginal sobre B es pequeño y el costo operativo —el `RESET ROLE` en el *checkin*
del pool— es real. Se deja anotada, no se recomienda ahora.

**D es la opción barata y honesta**: hacer que el alcance deje de ser un argumento
opcional. Un único punto de composición de consultas, más una prueba que falle si
un endpoint de listado nuevo no lo aplica. Cubre el fallo realmente observado —el
olvido— por una fracción del costo. **No cubre** SQL crudo, acceso directo a la
base, ni un repositorio que construya su consulta al margen del punto común.

**Recomendación:** B, con una salvedad de secuencia. Las fases 1 a 3 (§11) hay que
hacerlas de todos modos, porque arreglan huecos reales por sí solas y son
prerrequisito tanto de B como de D. La decisión definitiva entre B y D se toma
**después del piloto de la fase 4**, con una medición real en la mano y no con
una estimación.

---

## 7. Diseño recomendado

### 7.1 Los dos roles del clúster

```sql
-- PROPUESTA, no ejecutado.
CREATE ROLE sgpmp_owner NOLOGIN;              -- dueño de los objetos; corre Alembic
CREATE ROLE sgpmp_app   LOGIN PASSWORD '***'; -- la conexión de la API
-- sgpmp_app: NOSUPERUSER, NOCREATEROLE, NOCREATEDB, NOBYPASSRLS (valores por defecto)
```

Tres reglas que no son negociables, porque cualquiera de ellas convierte todas
las políticas en decoración:

1. **`sgpmp_app` no puede ser superusuario.** Un superusuario se salta RLS
   siempre, sin excepción.
2. **`sgpmp_app` no puede tener `BYPASSRLS`.**
3. **`sgpmp_app` no puede ser el dueño de las tablas.** El dueño también se salta
   sus propias políticas, salvo que la tabla declare `FORCE ROW LEVEL SECURITY`.
   Por eso se separan `sgpmp_owner` y `sgpmp_app`, y por eso toda tabla con RLS
   lleva además `FORCE`.

Los grants se otorgan **esquema por esquema**, dejando `public` fuera (§4.7).

### 7.2 El contexto de sesión

```sql
-- PROPUESTA
SET LOCAL app.usuario_id = '42';
SET LOCAL app.id_rol     = '3';
```

Se reutiliza el nombre `app.usuario_id` porque **ya es la convención del
repositorio** (§3.4): los triggers de auditoría de `modulo2` ya lo leen. Añadir
un segundo nombre para lo mismo sería gratuito y confuso.

**Dónde se inyecta:** en `get_current_user`
(`src/identity_access/infrastructure/dependencies.py:40-138`). Es el punto
correcto por cuatro razones:

1. Ya tiene la sesión (`db: Session = Depends(get_db)`).
2. Ya resuelve el `id_rol` **vigente en la base**, no el del JWT
   (`dependencies.py:78-98`), que es justo lo que RF-03/RF-04 exigen.
3. Todo endpoint autenticado pasa por ahí, incluidos los 33 sin RBAC que sí
   tienen usuario.
4. Permite **eliminar** los seis `SET LOCAL` dispersos de §3.4, que pasan a estar
   cubiertos por el del request.

**Por qué `SET LOCAL` y no `SET`:** `SET LOCAL` se revierte solo al `COMMIT` o
`ROLLBACK`. El pool de `src/shared/database.py` devuelve la conexión sin
contexto, sin necesidad de un hook de *checkin* — que hoy no existe (`src/` no
tiene ni un `event.listen`).

**Los endpoints sin usuario** (login, registro, recuperación, ingesta por
`X-Gateway-Id`) no setean el GUC. `current_setting('app.usuario_id', true)`
devuelve `NULL` y las políticas deben tratarlo como **denegar**, salvo donde
explícitamente se decida otra cosa (§9).

### 7.3 La regla de alcance se queda siendo dato

El backend **solo afirma identidad** — lo que legítimamente conoce del JWT. Es la
base de datos la que decide el alcance, consultando la misma regla que hoy usa
`AlcanceFincaAdapter.es_global`:

```sql
-- PROPUESTA
CREATE FUNCTION modulo1.fn_alcance_global(p_id_rol integer)
RETURNS boolean
LANGUAGE sql
STABLE
SECURITY DEFINER
AS $$
    SELECT EXISTS (
        SELECT 1 FROM modulo1.permisos
        WHERE id_rol = p_id_rol
          AND id_recurso = 9          -- fincas
          AND id_accion IN (3, 4)     -- U actualizar, D desactivar
          AND es_activo
    );
$$;
```

`STABLE` es lo que hace esto viable: PostgreSQL evalúa la función **una vez por
sentencia**, no una vez por fila. `SECURITY DEFINER` permite leer
`modulo1.permisos` sin otorgarle a `sgpmp_app` un `SELECT` que podría usar para
otra cosa.

**Por qué no pasar un booleano calculado por el backend:** si la aplicación
enviara `SET LOCAL app.alcance_global = 'true'`, la base estaría confiando en un
juicio del backend, y la tercera capa dejaría de ser independiente. El GUC debe
llevar **hechos de identidad** (quién es, qué rol tiene), nunca **conclusiones de
autorización**.

### 7.4 La función de pertenencia

```sql
-- PROPUESTA
CREATE FUNCTION modulo9.fn_fincas_del_usuario(p_id_usuario integer)
RETURNS SETOF integer
LANGUAGE sql
STABLE
SECURITY DEFINER
AS $$
    SELECT id_finca FROM modulo9.usuarios_fincas WHERE id_usuario = p_id_usuario;
$$;
```

**Todas** las políticas se escriben contra esta función, nunca contra
`modulo9.fincas.id_usuario` directamente. Así, cambiar el modelo de pertenencia
—que es exactamente lo que hay que hacer, §7.6— toca **un solo objeto** en vez de
decenas de políticas.

### 7.5 Las cinco plantillas de política

```sql
-- PROPUESTA — patrón base, idéntico para toda tabla con RLS
ALTER TABLE <esquema>.<tabla> ENABLE ROW LEVEL SECURITY;
ALTER TABLE <esquema>.<tabla> FORCE ROW LEVEL SECURITY;  -- imprescindible
```

**Patrón 1 — propia del usuario.** Preferencias, dashboard, notificaciones, temas,
idioma. Ejemplos: `modulo9.dashboard_layouts`, `modulo9.temas_visuales`,
`modulo9.preferencias_idiomas`, `modulo1.notificaciones`.

```sql
CREATE POLICY pol_dashboard_layout_propio ON modulo9.dashboard_layouts
    FOR ALL
    USING (id_usuario = current_setting('app.usuario_id', true)::int);
```

**Patrón 2 — finca directa.** Las 6 tablas con `id_finca` propio:
`modulo9.infraestructuras`, `modulo9.identidad_visuales`,
`modulo9.auditorias_fincas`, `modulo3.reglas_alertas`,
`modulo4.alertas_patologicas`, `modulo8.reportes_regulatorios`.

```sql
CREATE POLICY pol_infraestructura_por_finca ON modulo9.infraestructuras
    FOR ALL
    USING (
        modulo1.fn_alcance_global(current_setting('app.id_rol', true)::int)
        OR id_finca IN (
            SELECT modulo9.fn_fincas_del_usuario(
                current_setting('app.usuario_id', true)::int)
        )
    );
```

**Patrón 3 — finca indirecta.** La mayoría. Requiere recorrer la cadena de §4.6.
Es el patrón caro y el que hay que medir.

```sql
CREATE POLICY pol_activo_biologico_por_finca ON modulo2.activos_biologicos
    FOR ALL
    USING (
        modulo1.fn_alcance_global(current_setting('app.id_rol', true)::int)
        OR EXISTS (
            SELECT 1 FROM modulo9.infraestructuras i
            WHERE i.id_infraestructura = activos_biologicos.id_infraestructura
              AND i.id_finca IN (
                  SELECT modulo9.fn_fincas_del_usuario(
                      current_setting('app.usuario_id', true)::int))
        )
    );
```

Para tablas a tres o más saltos (`modulo5`, `modulo6`) hay dos salidas, y la
decisión se toma **con el `EXPLAIN` del piloto en la mano**, no antes:

- **Función auxiliar `STABLE`** `fn_activos_del_usuario()` que devuelve el
  conjunto una vez por sentencia. Sin migración de datos, pero materializa una
  lista que puede crecer.
- **Desnormalizar `id_finca`** en la tabla hoja, con trigger de consistencia.
  Rápido de consultar, pero es migración de esquema y un invariante más que
  mantener.

**Patrón 4 — catálogo global.** Especies, patologías, tipos de área, tipos de
dispositivo, variables ambientales, ciclos biológicos, y todo `modulo1`
(usuarios, roles, permisos). **No llevan RLS.** Su protección es RBAC, y ya la
tienen. Ponerles políticas sería puro costo sin beneficio.

**Patrón 5 — auditoría inmutable.** `modulo1.eventos`, `auditoria.logs_*`,
`modulo2.bitacora_auditoria_m02`, `modulo5.auditorias_suministros`. Su invariante
ya está en el motor, con triggers que bloquean `UPDATE`/`DELETE`. Si se les
aplica RLS, debe ser **solo de lectura** (`FOR SELECT`), respetando RF-10 (`…Modulo1.md:1809`):
*"Solo los usuarios con privilegios administrativos pueden consultar el historial
completo de auditoría"*. **No se tocan sus reglas de escritura.**

### 7.6 Prerrequisito: el modelo de pertenencia está incompleto

Hoy: **1 finca = 1 dueño** (`modulo9.fincas.id_usuario`, nullable, FK `NOT VALID`,
sin índice). La consecuencia está documentada desde hace tiempo en
`anotaciones/modulo_9/rf25_alcance_finca_multifinca_pendiente.md`:

> Roles que en la operación real atienden fincas de terceros — **Veterinario,
> Ingeniero de Campo, Supervisor, Gestor de Granja** — no verán fincas que no les
> pertenezcan, aunque les corresponda operarlas. Verán listados vacíos.

Pero M02 RF-46 (`…Modulo2.md:3560`) exige literalmente:

> Veterinario: puede consultar el historial de activos de la finca asignada.

Es decir: **no es solo deuda técnica, es un requerimiento incumplido.** Hoy se
manifiesta como "el veterinario no ve nada"; si se escriben políticas RLS sobre
este modelo, el incumplimiento queda congelado en DDL y corregirlo después cuesta
mucho más.

Por eso `usuarios_fincas` es **fase prerrequisito**, no una mejora posterior:

```sql
-- PROPUESTA
CREATE TABLE modulo9.usuarios_fincas (
    id_usuario_finca integer GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    id_usuario       integer NOT NULL REFERENCES modulo1.usuarios(id_usuario),
    id_finca         integer NOT NULL REFERENCES modulo9.fincas(id_finca),
    fecha_creacion   timestamptz NOT NULL DEFAULT now(),
    es_activo        boolean NOT NULL DEFAULT true,
    CONSTRAINT uq_usuario_finca UNIQUE (id_usuario, id_finca)
);
CREATE INDEX idx_usuario_finca_usuario ON modulo9.usuarios_fincas (id_usuario);
CREATE INDEX idx_usuario_finca_finca   ON modulo9.usuarios_fincas (id_finca);
```

Nombres según `anotaciones/convencion_nomenclatura_bd.md` (tabla en plural,
`uq_`, `idx_`, booleano `es_`, fecha `fecha_`).

Lo que arrastra este cambio:

| Qué | Dónde |
|---|---|
| Resolver fincas desde la tabla nueva | `src/shared/alcance_finca_adapter.py:23-25,43-46` |
| Asignación de fincas a usuario | `asignar_fincas_usuario_use_case.py` (hoy hace `UPDATE` sobre `fincas.id_usuario`) |
| Endpoint `PUT /usuarios/{id}/fincas` | contrato cambia de 1:1 a M:N; hoy responde 409 si la finca ya tiene dueño |
| Vista de contexto | `modulo9.vw_rf25_contexto_usuario` |
| Migración de datos | poblar `usuarios_fincas` desde `fincas.id_usuario` (10 filas, 4 propietarios) |
| Decisión pendiente | si `fincas.id_usuario` se conserva como "propietario" además de la relación de acceso, o se retira |

### 7.7 Convención de nombres

`anotaciones/convencion_nomenclatura_bd.md` **no cubre políticas RLS**. Se
propone extenderlo con una fila:

| Categoría | Tipo | Convención |
|---|---|---|
| Seguridad | Policy | Prefijo `pol_` + tabla en singular + criterio (ej. `pol_activo_biologico_por_finca`). Español, minúsculas, snake_case. Nombre explícito, nunca autogenerado. |

Las funciones auxiliares usan el prefijo `fn_` ya establecido en la convención.
Esta extensión debe acordarse con el equipo antes de la primera migración.

---

## 8. Clasificación de las tablas por patrón

No se hace aquí el inventario de las 187 tablas: eso es trabajo de la fase de
rollout (§11, F5), tabla por tabla, porque **no se puede decidir por el nombre de
la columna**. Muchas tablas tienen `id_usuario` como "quién lo hizo" (auditoría)
y no como "de quién es" — y confundir ambos casos produce políticas que dejan
fuera al dueño legítimo o dentro a quien solo registró un evento.

Lo que sí se fija ahora es **el criterio de clasificación** y su reparto
aproximado, para dimensionar el trabajo.

### 8.1 Criterio de decisión

Para cada tabla, en este orden:

1. ¿Es un catálogo compartido por todo el sistema? → **Patrón 4**, sin RLS.
2. ¿Es un registro de auditoría inmutable? → **Patrón 5**, RLS solo de lectura.
3. ¿Su `id_usuario` significa "de quién es" (no "quién lo registró")? → **Patrón 1**.
4. ¿Tiene `id_finca` propio? → **Patrón 2**.
5. ¿Llega a una finca por FK? → **Patrón 3**, y se anota la cadena exacta.
6. Si no llega a ninguna finca ni a ningún usuario → **caso a resolver**: o es
   catálogo mal clasificado, o le falta el vínculo. Se documenta, no se adivina.

### 8.2 Reparto por módulo

| Módulo | Tablas base | Perfil dominante | Patrón previsible |
|---|---:|---|---|
| `modulo1` (identidad) | 22 | usuarios, roles, permisos, sesiones, eventos | **4** (catálogo/administrativo) y **5** (eventos). RF-13 exige el auto-acceso al perfil, que hoy se resuelve en la aplicación |
| `modulo9` (configuración) | 46 | 4 con `id_finca` propio; 27 con `id_usuario`; catálogos (especies, tipos de área, métricas, ciclos) | mezcla de **1**, **2** y **4**. Es el módulo con más variedad y el mejor candidato a piloto |
| `modulo2` (activos) | 20 | `activos_biologicos` y derivadas; **ninguna con `id_finca`** | **3** casi por completo, cadena `id_infraestructura → id_finca` |
| `modulo3` (telemetría) | 17 | `reglas_alertas` tiene `id_finca`; el resto cuelga de sensores/dispositivos | **2** (una) y **3** (el resto) |
| `modulo4` (predicción) | 24 | `alertas_patologicas` tiene `id_finca`; signos y patologías son catálogo | **2**, **3** y **4** mezclados |
| `modulo5` (suministros) | 25 | ninguna con `id_finca`; llegan vía activo biológico | **3**, la cadena más larga del sistema |
| `modulo6` (NIC-41) | 18 | ninguna con `id_finca` | **3** |
| `modulo7` (integraciones) | 15 | peticiones, mapeadores, solicitudes | mayormente **4** / servicio |
| `modulo8` (reportes) | 13 | `reportes_regulatorios` tiene `id_finca` | **2** y **3**; incluye la tabla con RLS huérfana (§4.3) |
| `auditoria` | 3 | `logs_dml`, `logs_ddl`, `configuracion` | **5** |
| `public` | 18 | **aplicación ajena al dominio** | fuera de alcance; excluir de los grants |

### 8.3 Lo que este reparto implica

- **Patrón 3 domina.** Es el caro: exige recorrer la cadena o desnormalizar. Y es
  donde vive el grueso de `modulo2`, `modulo5` y `modulo6`.
- **`modulo9` es el mejor piloto**: tiene los cuatro patrones interesantes en un
  solo módulo, es donde está `fincas`, y es donde el requerimiento (M09 RF-19) es
  más explícito.
- **`modulo1` no necesita RLS por finca.** Su control es RBAC, y el único
  requisito de fila (RF-13, perfil propio) ya se cumple en la aplicación
  resolviendo el `id_usuario` desde el token. Añadirle políticas complicaría
  login, registro y activación sin ganar nada.

---

## 9. Casos que rompen

Esta sección es el verdadero inventario de riesgo. Cada uno de estos flujos hoy
funciona **porque nada filtra**. Bajo RLS, todos verían cero filas si no se les da
identidad explícita.

### 9.1 Tareas de fondo (7)

`main.py:85-422` lanza siete bucles `asyncio`, todos con `SessionLocal()` y
**ningún usuario autenticado**:

| Tarea | Línea | Qué hace |
|---|---|---|
| `_evaluar_dispositivos_periodicamente` | 85 | RF-60, cada 60 s |
| `_ejecutar_batch_ica_diario` | 116 | RF-74, batch nocturno |
| `_revertir_retiros_vencidos_diariamente` | 163 | RF-76 |
| `_archivar_auditoria_diariamente` | 194 | RF-10 |
| `_procesar_cola_reportes_gastos_periodicamente` | 293 | RF-77 |
| `_procesar_cola_historial_suministros_periodicamente` | 334 | RF-81 |
| `_procesar_cola_exportaciones_auditoria_periodicamente` | 370 | RF-10 |

**Opciones**, a decidir en F1:

- Un usuario de servicio en `modulo1.usuarios` con un rol cuyo alcance sea global
  — consistente con el modelo, auditable, y no requiere excepciones en las
  políticas.
- Una conexión separada con un rol `sgpmp_batch` que tenga `BYPASSRLS` — más
  simple, pero abre un camino sin filtro que hay que vigilar.

Se recomienda la primera: mantiene una sola vía de acceso y deja rastro en la
auditoría de quién hizo qué.

### 9.2 Ingesta por token de dispositivo

- `telemetry/…/telemetria_router.py:81` y `:105` — `X-Gateway-Id`
- `telemetry/…/evento_edge_router.py:44` — `X-Gateway-Id`

No hay usuario. El gateway escribe telemetría que **pertenece a la finca donde
está el dispositivo**, no a una persona. Bajo RLS necesitan o bien una identidad
de servicio, o bien una política propia que resuelva la finca desde el
dispositivo. Esta última es la más correcta semánticamente y merece su propia
decisión de diseño.

### 9.3 Integración M2M de AgroFusion

`agrofusion_integration_router.py:51,67,95,133,161` — cinco endpoints con
credenciales M2M (`src/shared/agrofusion_auth.py`). Recordar además que el rol
`Externo AgroFusion` tiene hoy **cero permisos** (§4.5), lo que hay que resolver
antes de tocar nada más.

También `version_modelo_router.py:42`, con `X-RF71-Internal-Key`.

### 9.4 Flujos sin sesión

Registro, activación por token, recuperación y restablecimiento de contraseña
escriben en `modulo1.usuarios` / `cuentas_usuarios` / `tokens` **sin usuario
autenticado**. Es una de las razones por las que `modulo1` no debería llevar RLS
por finca (§8.3).

### 9.5 Alembic y el baseline

- `alembic/env.py` toma la URL de `DATABASE_URL` sin distinguir owner de app.
  Con dos roles, las migraciones deben correr como `sgpmp_owner` — hace falta
  una variable propia o un `ALEMBIC_DATABASE_URL`.
- Alembic **no autogenera políticas RLS**: van escritas a mano con `op.execute`,
  con su `downgrade` correspondiente.
- `alembic/baseline/esquema_baseline.sql` son ~48.000 líneas de dump cargadas con
  `SET search_path TO public` (`f7fe43537842_…py:73-76`). Reprovisionar una base
  desde cero con roles nuevos exige revisar el dueño de los objetos del dump.
- `env.py` no declara `include_schemas=True`, y `prediction` usa una
  `DeclarativeBase` propia fuera de `target_metadata` — inconsistencia
  preexistente que un `--autogenerate` futuro no detectaría.

### 9.6 Pruebas

- `tests/integration/conftest.py` abre una **transacción exterior** y convierte
  los `commit()` de los casos de uso en savepoints. Un `SET LOCAL` dentro de ese
  esquema aplica al ámbito de la transacción exterior: hay que verificar que el
  contexto se establezca y se limpie por prueba, no por sesión.
- **Las pruebas deben conectarse como `sgpmp_app`**, no como `postgres`. Si
  corren como superusuario, pasarán en verde mientras producción queda
  desprotegida — es el modo de fallo más peligroso de todo este trabajo.
- La base `pruebas` necesita los mismos roles, grants y políticas. Hoy esa base
  se aprovisiona fuera de Alembic (el baseline no la construye desde cero); el
  procedimiento debe actualizarse en la misma fase que cree los roles.

### 9.7 `sqlacodegen`

La práctica del repo es generar modelos ORM desde la base. Los roles, grants y
políticas **no aparecen** en el modelo generado: son estado de la base que solo
vive en las migraciones. Conviene dejarlo escrito para que nadie asuma que el
modelo ORM refleja la seguridad.

### 9.8 La tabla con RLS huérfana

`modulo8.consultas_auditoria_externas` tiene RLS habilitado y **cero políticas**
(§4.3). En cuanto la aplicación deje de conectarse como superusuario, esa tabla
pasa a *deny-all*. Debe resolverse **en la fase 1**, antes que cualquier otra
cosa: o se le escribe política, o se le quita el RLS.

---

## 10. Rendimiento

RF-04 fija el presupuesto (`…Modulo1.md:994`): *"Validación de permisos en
menos de 200 ms"*.

**Hoy no es el problema.** La tabla de negocio más grande tiene ~1.776 filas y los
nueve esquemas suman unas 6.000 (§4.7). Una política con `EXISTS` sobre una
cadena de dos saltos, con la función de alcance marcada `STABLE`, es
imperceptible a esta escala.

Lo que sí hay que hacer, en este orden:

1. **`ANALYZE` primero.** 64 tablas nunca han sido analizadas y `reltuples` miente
   (§4.7). Medir sin estadísticas frescas no sirve de nada.
2. **Índices que faltan.** `modulo9.fincas.id_usuario` **no tiene ninguno** — su
   único índice es la PK. Toda columna que aparezca en una política necesita
   índice: `infraestructuras.id_finca`, `activos_biologicos.id_infraestructura`,
   y los dos de `usuarios_fincas` (§7.6).
3. **`EXPLAIN (ANALYZE, BUFFERS)`** sobre los tres o cuatro listados más pesados
   del piloto, **con y sin** la política activa, y comparar. Ese delta es el dato
   que decide si el patrón 3 se resuelve con función auxiliar o desnormalizando
   `id_finca` (§7.5).
4. **`STABLE`, siempre.** Una función de alcance marcada `VOLATILE` se evalúa
   **una vez por fila**. Es la diferencia entre imperceptible e inaceptable, y es
   el error más fácil de cometer.

Un efecto secundario que conviene anticipar: con RLS, el plan de consulta cambia,
y una consulta que hoy usa un índice puede pasar a un *seq scan* porque el
predicado de la política se aplica antes. Por eso la medición va en el piloto y
no al final.

---

## 11. Plan por fases

Cada fase entrega algo utilizable por sí misma y se puede detener sin dejar el
sistema a medias.

### F0 — Decisión y alineación

**Entregable:** este documento revisado y aprobado por el equipo y por el DBA.
Decisión explícita sobre: extensión de la convención de nombres (§7.7), identidad
de las tareas de fondo (§9.1) y si se sigue hasta F4 o se corta en F3.
**Criterio de salida:** acuerdo escrito.
**Riesgo:** ninguno.

### F1 — Dejar de conectarse como superusuario

**Por qué primero:** sin esto, todo lo demás es decorativo. Y tiene valor propio
aunque no se llegue nunca a RLS: hoy un fallo de inyección SQL o una credencial
filtrada entrega el clúster entero.

**Entregable:**
- `sgpmp_owner` y `sgpmp_app` creados; grants por esquema, **excluyendo `public`**.
- `DATABASE_URL` apuntando a `sgpmp_app`; URL separada para Alembic.
- `modulo8.consultas_auditoria_externas` resuelta (§9.8).
- Mismos roles en la base `pruebas` y en el CI.

**Criterio de salida:** la suite completa pasa conectada como `sgpmp_app`.
**Reversión:** volver `DATABASE_URL` a `postgres`. Inmediata.
**Riesgo:** medio — un grant que falte se manifiesta como error en runtime. Se
mitiga corriendo toda la suite antes de tocar el despliegue.

### F2 — Contexto de sesión sistemático

**Entregable:**
- `SET LOCAL app.usuario_id` y `app.id_rol` en `get_current_user`.
- Eliminación de los seis `SET LOCAL` dispersos (§3.4).
- Prueba que verifique que el contexto está puesto dentro del request y **no**
  sobrevive al siguiente.

**Criterio de salida:** los triggers de auditoría de `modulo2` siguen recibiendo
su `app.usuario_id` sin que los repositorios lo pongan.
**Reversión:** revertir el commit; los `SET LOCAL` originales vuelven.
**Riesgo:** bajo. **Valor inmediato:** menos código y un invariante en un solo
sitio, con o sin RLS.

### F3 — `usuarios_fincas` (prerrequisito de modelo)

**Entregable:** la tabla de §7.6, migración de los datos existentes,
`fn_fincas_del_usuario()`, y la actualización de `AlcanceFincaAdapter`, del
endpoint de asignación y de `vw_rf25_contexto_usuario`.

**Criterio de salida:** un Veterinario asignado a una finca ajena ve sus activos
— es decir, **M02 RF-46 deja de estar incumplido**.
**Reversión:** el adaptador vuelve a leer `fincas.id_usuario`; la tabla queda sin
uso.
**Riesgo:** medio — cambia el contrato de `PUT /usuarios/{id}/fincas`, que hoy
responde 409 cuando la finca ya tiene dueño. Hay que coordinarlo con frontend.
**Valor inmediato:** corrige un incumplimiento real, exista RLS o no.

### F4 — Piloto de RLS

**Alcance:** `modulo9.infraestructuras` (patrón 2) y `modulo2.activos_biologicos`
(patrón 3). Un patrón caro y uno barato, en la cadena donde el requerimiento es
explícito.

**Entregable:** políticas, `FORCE ROW LEVEL SECURITY`, índices, y la medición de
§10 con y sin política.
**Criterio de salida:** dos usuarios de fincas distintas, con el mismo rol, no ven
las filas del otro **ni ejecutando SQL crudo** contra la conexión de la API. Y el
delta de latencia medido cabe en el presupuesto.
**Reversión:** `DROP POLICY` + `DISABLE ROW LEVEL SECURITY`. Sin pérdida de datos.
**Riesgo:** medio-alto. Es aquí donde se descubre lo que este documento no puede
prever.

### F5 — Rollout por patrón

**Entregable:** clasificación de las 187 tablas según §8.1 y aplicación por
módulo, empezando por `modulo9` y `modulo2` (ya piloteados), siguiendo por
`modulo3`, `modulo4`, `modulo5`, `modulo6`, `modulo8`.
**Criterio de salida:** toda tabla del sistema tiene un patrón asignado — incluido
"sin RLS, y por qué".
**Reversión:** por módulo, independiente.
**Riesgo:** alto en volumen, bajo por paso. Una migración Alembic por módulo,
nunca una sola para todo.

### F6 — Pruebas negativas en CI

**Entregable:** una prueba de integración por patrón que **falle si la política se
cae**: dos usuarios, dos fincas, aserción de que cada uno ve solo lo suyo. Más un
chequeo que verifique que ninguna tabla de negocio nueva queda sin patrón
asignado.
**Criterio de salida:** quitar una política rompe el CI.
**Riesgo:** ninguno. Sin esto, las políticas se erosionan en silencio.

---

## 12. Riesgos y decisiones abiertas

| # | Riesgo / decisión | Impacto | Quién decide |
|---|---|---|---|
| 1 | Las pruebas corren como superusuario y pasan en verde mientras producción queda abierta | **Crítico** — es el modo de fallo más peligroso de todo el plan | Equipo, en F1 |
| 2 | Identidad de las 7 tareas de fondo: usuario de servicio vs. rol `BYPASSRLS` | Alto | Equipo + DBA, en F1 |
| 3 | Cómo resuelve su finca la ingesta por `X-Gateway-Id` | Alto | Equipo, en F4 |
| 4 | Patrón 3 a tres saltos: función auxiliar vs. desnormalizar `id_finca` | Medio — se decide **con el `EXPLAIN` del piloto**, no antes | Equipo, en F4 |
| 5 | `fincas.id_usuario` tras F3: ¿se conserva como "propietario" o se retira? | Medio | Análisis + equipo, en F3 |
| 6 | Cambio de contrato en `PUT /usuarios/{id}/fincas` | Medio — requiere coordinación con frontend | Equipo, en F3 |
| 7 | Rol `Externo AgroFusion` con 6 usuarios y 0 permisos | Medio — independiente, pero aflora en F1 | Análisis |
| 8 | Extensión de `convencion_nomenclatura_bd.md` con el prefijo `pol_` | Bajo | Equipo, en F0 |
| 9 | Toda migración con DDL necesita autorización explícita del DBA antes del merge | Bloqueante por proceso | DBA |
| 10 | El esquema `public` con una aplicación ajena: ¿se aísla, se mueve o se documenta? | Bajo para este plan, alto para higiene general | Equipo + DBA |
| 11 | M01 no especifica la relación usuario↔finca que M02 y M09 dan por hecha | Medio — hueco de especificación, no de código | Grupo de análisis |

---

## 13. Qué NO hacer

Esta sección existe para que el documento sirva de barrera, no solo de guía.

1. **No crear un rol de PostgreSQL por cada rol de aplicación.** Los roles son
   datos CRUD-ables (11 hoy y creciendo); los de PostgreSQL son DDL de clúster.
   Espejarlos obliga a darle `CREATEROLE` a la aplicación — una escalada de
   privilegios peor que el problema original. §5.1(a).
2. **No mover `modulo1.permisos` a GRANTs.** 58 recursos que en su mayoría no son
   tablas (módulos, endpoints, procesos especiales) y 337 combinaciones. `GRANT`
   no puede expresarlo, y RF-03/RF-04 exigen propagación inmediata sin cerrar
   sesión. §5.1(b) y (c).
3. **No confiar en un booleano de alcance calculado por el backend.** El GUC lleva
   **hechos de identidad**, nunca **conclusiones de autorización**; si no, la
   tercera capa deja de ser independiente y solo repite lo que dijo la segunda.
   §7.3.
4. **No escribir una sola política mientras `DATABASE_URL` apunte a `postgres`.**
   Un superusuario ignora RLS, y `FORCE ROW LEVEL SECURITY` tampoco lo detiene.
   Sería seguridad de mentira, que es peor que ninguna. §7.1.
5. **No olvidar `FORCE ROW LEVEL SECURITY`.** El dueño de la tabla se salta sus
   propias políticas sin él. §7.1.
6. **No marcar las funciones de alcance como `VOLATILE`.** Se evaluarían una vez
   por fila. §10.
7. **No aplicar RLS a los catálogos ni a `modulo1`.** Su control es RBAC y ya lo
   tienen; añadir políticas solo complicaría login, registro y activación. §8.3.
8. **No hacer una migración única para las 187 tablas.** Una por módulo, cada una
   revertible por separado. §11 F5.
9. **No tocar las reglas de escritura de las tablas de auditoría.** Su
   inmutabilidad ya está en el motor (RF-10) y funciona. §7.5, patrón 5.

---

## Referencias

- `src/shared/rbac.py`, `src/shared/database.py`
- `src/shared/alcance_finca_port.py`, `src/shared/alcance_finca_adapter.py`
- `src/supplies/infrastructure/adapters/alcance_activo_m02_adapter.py`
- `src/identity_access/infrastructure/dependencies.py`
- `main.py` (tareas de fondo), `alembic/env.py`, `tests/integration/conftest.py`
- `anotaciones/modulo_9/rf25_alcance_finca_multifinca_pendiente.md`
- `anotaciones/convencion_nomenclatura_bd.md`
- `anotaciones/Requerimientos/Especificacion-Requerimientos-Modulo{1,2,9}.md`
- `CLAUDE.md` — sección "Control de acceso (RBAC)"
