# DEV-30 — RF-57: permisos de descarte y transiciones de alertas

Fecha: 2026-10-21. Responsable: Leandro Estiven Ramirez.
Historia #3692. Subtareas #3775, #3776 y #3777.
Rama: `fix/dev30-alertas-permisos-transiciones`.
Base: `origin/dev`, `6113a388`. Commit y push de esta rama autorizados por el
usuario después de la reverificación de la base oficial; el hash se informa
en la entrega de publicación.

## 1. Diagnóstico

El endpoint real es `PATCH /iot/alertas/{id_alerta}/estado`.

| Componente | Hallazgo confirmado | Corrección |
|---|---|---|
| Router operativo | Solo exigía U sobre recurso 32; bastaba para descartar | Comprobación adicional con `tiene_permiso_sobre` antes del caso de uso |
| DTO | CERRADA no estaba entre las solicitudes reconocidas; producía 400 | Admitir la solicitud para que el dominio responda 422 |
| Entidad | VENCIDA permitía pasar a EN_ATENCION | VENCIDA terminal, sin transiciones salientes |
| Caso de uso manual | Permitía solicitar VENCIDA | Rechazo explícito con `TRANSICION_INVALIDA` antes de mutar |
| Dominio y PostgreSQL | La entidad permitía reabrir VENCIDA, pero el trigger de PostgreSQL ya lo rechazaba | Alinear el dominio sin modificar el trigger |

Antes: autenticación → U/32 → DTO → transición → actualización e historial.
Ahora: autenticación → U/32 → permiso D específico si se solicita DESCARTADA →
validación manual → transición de dominio → actualización e historial.

Las transiciones inválidas ejecutan rollback y conservan el registro de rechazo
RF-63 mediante el mecanismo existente, en otra transacción. No se alteró el
manejador global de errores ni se crearon códigos nuevos.

## 2. Implementación y archivos

| Archivo | Responsabilidad y cambio | Tarea |
|---|---|---|
| `src/telemetry/infrastructure/routers/alerta_router.py` | Exige además D sobre el recurso por nombre `alertas`, según el contrato documentado de DB-08. Mantiene autenticación, cuenta activa, U/32 y ámbito operativo. Devuelve 403 ACCESO_DENEGADO antes de consultar/modificar la alerta si falta el permiso. | #3775 |
| `src/telemetry/infrastructure/dto/actualizar_estado_alerta_dto.py` | Reconoce CERRADA como solicitud y conserva validaciones de estructura, tipos y estados desconocidos. No incorpora CERRADA al enum ni a PostgreSQL. | #3776 |
| `src/telemetry/domain/entities/alerta.py` | Elimina VENCIDA → EN_ATENCION. Conserva ACTIVA/EN_ATENCION → VENCIDA para el procesamiento interno por SLA. | #3776 |
| `src/telemetry/application/use_cases/alertas/actualizar_estado_alerta_use_case.py` | Impide el destino VENCIDA en el caso de uso manual con 422 TRANSICION_INVALIDA. Reutiliza rollback y auditoría de rechazo. El caso de uso compartido también protege la actualización manual de alertas técnicas. | #3776 |
| `tests/telemetry/test_dev30_permisos_transiciones_alertas.py` | Pruebas de dominio, DTO y HTTP con repositorios y datos de permisos explícitos en memoria. No equivalen a integración JWT/PostgreSQL. | #3777 |
| `tests/integration/test_dev30_alertas_permisos_transiciones.py` | HTTP con JWT, RBAC, repositorios, triggers, rollback y consulta de filas reales en PostgreSQL exclusivo. Omite expresamente los escenarios que necesitan DB-08 si falta su recurso. | #3777 |
| `anotaciones/modulo_3/dev30_rf57_permisos_transiciones_alertas.md` | Diagnóstico, evidencia, dependencia y propuesta de PR. | #3692 |

Los seis archivos Python llevan la tabla de seguimiento exigida por el usuario,
con fecha del cambio y el resultado real de `git config user.name`: `Leandro`.

No se modificaron RBAC compartido, permisos desplegados, migraciones, triggers,
catálogos, frontend ni el procesamiento automático de DEV-31. No se abordó la
duplicación previa del historial entre caso de uso y trigger, correspondiente a DEV-49.

## 3. DB-08: dependencia comprobada y contrato pendiente de integración

El documento `DEV-Reparto_Tareas_RFC012-016_y_Gaps.md`, sección de DB-08,
define descarte mediante acción **D sobre `alertas`**, solo Administrador y
Veterinario, y exige resolver el recurso por nombre, no por id fijo.
La acción D corresponde al identificador 4 en las convenciones existentes.

Se reconstruyó una base PostgreSQL 18 exclusiva desde las migraciones de esta
rama hasta `e5a3c9b17d42`. Su catálogo contiene:

| id_recurso | nombre_recurso |
|---|---|
| 32 | alertas_operativas |
| 36 | alertas_tecnicas_iot |

**No existe `alertas` en esa reconstrucción.** No se encontró una migración DB-08
en la cadena actual. La ausencia de una migración no demuestra que el DML de
permisos no se haya aplicado directamente en desarrollo.

### Reverificación de la base oficial — 2026-10-21, 14:56 UTC

**La conexión oficial sí funciona.** La verificación inicial consultó
incorrectamente `127.0.0.1:5447`; ese destino local no era el servidor oficial.
Se revisó el perfil de conexión de pgAdmin y se conectó al destino real:

| Dato | Valor verificado |
|---|---|
| Host y puerto publicados | `158.69.200.27:5447` |
| Base real (`current_database()`) | `sgpmp_dev`, con la segunda `p` |
| Usuario PostgreSQL | `member_dev` |
| Modo de transacción | `transaction_read_only = on` |
| Evidencia local, sin contraseña | `.pytest_cache/dev30_bd_oficial_readonly.json` |

La `.env` apunta a la base local `integrador:5432`; ese servicio también está
activo, pero no es la base oficial. No se cambió la configuración local ni se
guardaron credenciales en el repositorio.

La consulta directa al catálogo **oficial** confirmó los mismos recursos de la
tabla anterior: `alertas_operativas` (32) y `alertas_tecnicas_iot` (36).
El catálogo `modulo1.acciones` confirma D = 4. Se consultaron las definiciones
actuales de los triggers: `trg_rf57_03_validar_transicion` está activo y su función
rechaza salidas de VENCIDA con P0005; esto coincide con el cambio de la entidad.
No se ejecutaron operaciones de cambio de estado para comprobarlo en DEV.

La matriz de permisos **no pudo verificarse**:

- `member_dev` tiene SELECT sobre `modulo1.permisos`, pero su política RLS
  necesita `modulo1.fn_id_rol_actual()` y el usuario no tiene EXECUTE sobre esa
  función. La consulta termina con SQLSTATE **42501**:
  `permission denied for function fn_id_rol_actual`.
- Se identificó la vista autorizada `modulo1.vw_permisos_roles` y se intentó la
  misma comprobación mediante ella. Aunque tiene SELECT concedido, falla por la
  misma función. No se desactivó RLS ni se alteraron roles o privilegios.
- La lectura de `public.alembic_version` también está denegada; no se utilizó
  como sustituto de revisar los permisos reales.

Por tanto, **no se afirma que DB-08 no esté aplicado**. La conclusión comprobada
es que falta poder leer su matriz efectiva y resolver el nombre del recurso:
el contrato documentado dice `alertas`, pero el catálogo real usa
`alertas_operativas`. Puede haber DML manual aplicado sobre este último.
No se ejecutaron escrituras, GRANT, migraciones ni pruebas con persistencia
en la base oficial.

El router aplica el nombre del contrato documentado y **rechaza el descarte si
ese permiso/recurso falta**. No usa U como sustituto, no busca nombres de rol y
no incorpora un fallback hacia `alertas_operativas`.

### Información mínima para cerrar la dependencia con BD

Mensaje técnico listo para revisión, no enviado:

> DB-08 / DEV-30 (#3692, #3775): se confirmó la conexión oficial a
> 158.69.200.27:5447/sgpmp_dev. Los recursos reales son alertas_operativas (32) y
> alertas_tecnicas_iot (36). La lectura de permisos, directa o mediante
> vw_permisos_roles, falla con 42501 porque member_dev no puede ejecutar
> fn_id_rol_actual, requerida por RLS. Se necesita una consulta de la matriz
> efectiva por un usuario autorizado, o un mecanismo de lectura autorizado que
> permita verificarla. Confirmar si DB-08 ya asignó D/alertas_operativas solo a
> Administrador y Veterinario, y que Productor mantiene U sin D. Si ya está
> aplicado, basta adaptar el nombre real en router/pruebas y verificarlo en
> PostgreSQL aislado; no solicitar otra migración ni duplicar recursos. Si falta
> algún permiso, identificar primero la diferencia efectiva antes de pedir DML.
> El control actual permanece cerrado por defecto hasta resolver ese contrato.

Consulta de diagnóstico para ejecutar con un usuario autorizado, sin modificar datos:

```sql
BEGIN TRANSACTION READ ONLY;
SELECT nombre_rol, recurso, codigo_accion, es_activo
FROM modulo1.vw_permisos_roles
WHERE recurso IN ('alertas_operativas', 'alertas_tecnicas_iot')
  AND codigo_accion IN ('U', 'D')
ORDER BY nombre_rol, recurso, codigo_accion;
ROLLBACK;
```

Las pruebas de integración preparan permisos de forma explícita y reversible
solo cuando existe el recurso acordado. No crean un recurso ficticio ni asignan
permisos a Veterinario para aparentar que DB-08 está disponible.

## 4. Verificación

Entorno: Python 3.13.13 en Windows; PostgreSQL 18 desechable en
`127.0.0.1:55438/sgpmp_dev30_test`. Los commits de casos de uso se aíslan mediante
la transacción exterior/savepoints de `tests/integration/conftest.py`.
Al finalizar se detuvo y retiró exclusivamente esa instancia temporal,
verificando previamente su ruta dentro de TEMP. Los reportes locales se conservaron.

Se ejecutó `alembic upgrade head` exclusivamente en esa base. El primer intento
reveló el prerrequisito de infraestructura `sgpmp_app`; se prepararon los roles
técnicos `sgpmp_app` y `sgpmp_owner` solo en la instancia desechable y la cadena
completa terminó correctamente, sin modificar las migraciones del producto.

### Comandos

Desde la raíz del repositorio, con `.venv/Scripts/python.exe`:

```powershell
# Regresión ejecutable en Windows; los tres módulos excluidos importan fcntl.
& .venv/Scripts/python.exe -m pytest --confcutdir=tests/telemetry tests/telemetry `
  --ignore=tests/telemetry/test_dev06_token_servicio_broker.py `
  --ignore=tests/telemetry/test_dev11_eventos_buffer.py `
  --ignore=tests/telemetry/test_inc_m09_77_g137_observaciones_vision.py `
  -q --tb=short --junitxml=.pytest_cache/dev30_telemetry_disponible.xml

# Casos adicionales de fallo de auditoría, incorporados después de esa ejecución.
& .venv/Scripts/python.exe -m pytest --confcutdir=tests/telemetry `
  tests/telemetry/test_dev30_permisos_transiciones_alertas.py `
  -k fallo_de_auditoria -q --junitxml=.pytest_cache/dev30_auditoria_fallo.xml

# Solo base exclusiva: nunca apuntar TEST_DATABASE_URL a sgpmp_dev.
$env:DATABASE_URL = 'postgresql+psycopg2://postgres@127.0.0.1:55438/sgpmp_dev30_test'
$env:TEST_DATABASE_URL = $env:DATABASE_URL
& .venv/Scripts/python.exe -m pytest --confcutdir=tests/integration `
  tests/integration/test_dev30_alertas_permisos_transiciones.py `
  tests/integration/test_dev04_sqlstate.py `
  -q -rs --tb=short --junitxml=.pytest_cache/dev30_postgresql_final.xml

& .venv/Scripts/python.exe -m bandit `
  src/telemetry/infrastructure/routers/alerta_router.py `
  src/telemetry/infrastructure/dto/actualizar_estado_alerta_dto.py `
  src/telemetry/domain/entities/alerta.py `
  src/telemetry/application/use_cases/alertas/actualizar_estado_alerta_use_case.py `
  -ll -ii -f txt -o .pytest_cache/dev30_bandit.txt
git diff --check
```

### Resultados finales

| Ejecución | Resultado | Evidencia |
|---|---|---|
| Telemetría disponible, incluyendo 28 casos iniciales DEV-30 | 221 aprobadas, 0 fallidas | `dev30_telemetry_disponible.xml`; consola: `221 passed` |
| Dos casos adicionales DEV-30 de fallo de auditoría | 2 aprobadas, 28 deseleccionadas | `dev30_auditoria_fallo.xml`; consola: `2 passed, 28 deselected` |
| DEV-30 PostgreSQL, incluidos JWT, autorización negativa, transiciones, auditoría persistida y rollback real | 10 aprobadas, 6 omitidas por DB-08 | `dev30_postgresql_final.xml` |
| Regresión DEV-04 SQLSTATE en PostgreSQL | 8 aprobadas, 0 fallidas | Mismo XML anterior; ejecución conjunta: `18 passed, 6 skipped` |
| Bandit en los cuatro archivos de aplicación modificados | Sin hallazgos; 472 líneas analizadas | `.pytest_cache/dev30_bandit.txt` |
| Compilación Python de los seis archivos creados/editados | Correcta | `python -m py_compile` terminó con código 0; los cambios posteriores de pruebas también se ejecutaron |
| Revisión de espacios del diff | Correcta | `git diff --check`, sin salida ni errores |

Los XML están en `.pytest_cache/`, fuera del contenido versionado. **Total de
pruebas distintas aprobadas: 241; fallidas en las ejecuciones finales: 0;
omitidas explícitamente por DB-08: 6.** Las 28 deseleccionadas de la ejecución
adicional ya están entre las 221, no se cuentan otra vez. Los ensayos iniciales
de 23, 51 y 10 pruebas tampoco se suman. Los errores de colección de los tres
módulos dependientes de Linux se informan por separado; no se ocultan bajo el
conteo de fallidas finales ni se presentan como aprobados.

DEV-30 aporta 30 casos de dominio/HTTP con dobles y 16 escenarios PostgreSQL
(10 ejecutados y 6 pendientes). Se verificó que los rechazos de transición
persisten `TRANSICION_ALERTA_RECHAZADA` con resultado RECHAZADO y el estado
solicitado, sin alterar la alerta ni su historial. También se indujo un fallo
real de escritura del historial y se comprobó el rollback del cambio de estado.

La advertencia de deprecación Starlette/httpx se observó en las ejecuciones;
no produjo fallos y no se cambiaron dependencias del producto para resolverla.

### Límites de cobertura

- La ejecución general inicial de pytest no llegó a ejecutar pruebas por el
  import de `fcntl` en `tests/conftest.py`, dependencia preexistente de M02 en Linux.
- Al limitar la búsqueda de conftest a telemetría, tres módulos aún importan
  `main.py` y vuelven a cargar esa dependencia. La ejecución completa de M03
  terminó con tres errores de colección. No se cambiaron esas pruebas ni M02;
  la regresión disponible las excluye explícitamente. Falta ejecutar esos módulos
  y la suite general en Linux. No se contabilizan como pruebas aprobadas.
- Se ejecuta FastAPI con el router y handlers reales, no el arranque global de
  `main.py`. Las pruebas PostgreSQL validan JWT y permisos reales en la base
  exclusiva; no demuestran un despliegue remoto ni una ejecución con el rol
  PostgreSQL de aplicación sujeto a RLS. Se conserva el alcance existente.
- Los seis escenarios de DB-08 omitidos cubren los tres descartes autorizados
  (Administrador, Veterinario, rol personalizado), descarte desde VENCIDA,
  D inactivo y D sin U. Los dobles de pruebas unitarias cubren la decisión de
  autorización; no reemplazan estas verificaciones con datos reales.
- Semgrep y Bearer del pipeline no se ejecutaron localmente.
- No se implementó el programador SLA de DEV-31; se preservó la transición
  interna legítima a VENCIDA y se probó que el estado resultante es terminal.

## 5. Estado de las tareas y pendientes de cierre

| Tarea | Estado | Pendiente real |
|---|---|---|
| #3775 | Implementación preparada; integración parcial | Leer la matriz oficial sin el bloqueo RLS/EXECUTE; confirmar si DB-08 ya está aplicado y el nombre real del recurso; adaptar y verificar el descarte autorizado |
| #3776 | Implementada | Validación de QA en el entorno desplegado |
| #3777 | Pruebas implementadas; ejecución parcial | Ejecutar los seis casos DB-08 sin omisiones y completar la regresión dependiente de Linux |
| #3692 | No cerrada integralmente | Integración DB-08 y reevaluación de QA |

No hay migraciones nuevas de DEV-30. Los archivos AGENTS.md y los documentos de
pendientes previos ya estaban sin seguimiento al iniciar esta tarea y no forman
parte del cambio. El commit se limita a los siete archivos de DEV-30; la
publicación autorizada corresponde únicamente a esta rama, sin crear PR remoto.

## 6. Propuesta de PR

### Título

`fix(telemetry): restringir descarte y validar transiciones RF-57 (DEV-30)`

### Descripción

```markdown
## Descripción

Corrige el flujo manual de estados de alertas de RF-57. El descarte exige
además el permiso D del recurso documentado por DB-08, consultado desde el
router mediante tiene_permiso_sobre, y mantiene el permiso general U.
CERRADA y VENCIDA manuales responden 422 TRANSICION_INVALIDA; VENCIDA queda
como estado terminal y se conserva el vencimiento interno por SLA.

## Cambios realizados

- Comprobación del permiso específico de descarte sin ids ni nombres de rol.
- CERRADA alcanza la validación de transición, conservando los 400 estructurales.
- Rechazo de VENCIDA manual antes de cualquier modificación.
- Conservación de rollback, ámbito de alertas y auditoría de rechazos.
- Pruebas de dominio/HTTP y PostgreSQL con fixtures explícitas y reversibles.

## Validación

- 241 pruebas distintas aprobadas: 223 de telemetría/dominio/HTTP y 18 de
  integración PostgreSQL, incluyendo la regresión DEV-04 SQLSTATE.
- 6 escenarios PostgreSQL omitidos porque falta el recurso DB-08.
- Bandit sin hallazgos y git diff --check correcto.
- Tres módulos de regresión no se pudieron importar en Windows por fcntl;
  pendiente ejecutarlos en Linux. No se modificaron esas pruebas.
- Detalle de comandos y evidencia en
  anotaciones/modulo_3/dev30_rf57_permisos_transiciones_alertas.md.

## Dependencias y pendientes

La conexión oficial a 158.69.200.27:5447/sgpmp_dev quedó confirmada en solo
lectura. Su catálogo usa alertas_operativas, mientras la documentación dice
alertas. No se puede concluir que DB-08 esté ausente: member_dev no puede leer
su matriz porque RLS requiere fn_id_rol_actual, sin EXECUTE concedido (42501),
tanto en permisos como en vw_permisos_roles. Pendiente verificar el permiso
efectivo y adaptar el nombre real; no solicitar migraciones innecesarias.
Pendiente también regresión completa en Linux por fcntl y reevaluación de QA.

Refs: #3692, #3775, #3776, #3777.
```

La propuesta no utiliza `Closes` porque no se ha demostrado el cierre integral.
