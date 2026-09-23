# INC-M02-92-G93 — Scope por `tipo_dato` en datos-consolidados (issue #390)

**RF:** RF-50 — Disponibilidad de datos para módulos analíticos
**CU:** CU12 / **Caso QA:** TC-M02-155 / **Grupo:** TC-M02-G93
**Endpoint:** `GET /activos-biologicos/{id_activo}/datos-consolidados`

---

## Reporte de QA (resumen)

TC-M02-155 exige una identidad de módulo consumidor autenticada, con
credencial válida pero **sin scope para el `tipo_dato` solicitado**. El
mecanismo vigente solo evaluaba `require_permission_m02(29, 2)` — un permiso
único sobre el endpoint completo, sin granularidad por `tipo_dato` — así que
QA no tenía forma de construir esa precondición sin fabricar un 403 por otra
vía (rol sin permiso general), lo que habría sido un falso positivo. Caso
`BLOCKED`.

---

## Paso 0 — Contraste contra el RF y el esquema real

RF-50 (texto completo compartido por el usuario, no solo el resumen de
`cu12_gaps_bd_rf50_rf51.md`) especifica:

- Precondición: *"El sistema debe contar con usuarios autenticados con
  permisos de acceso a datos (RF-02, RF-04)"* — es decir, RF-50 mismo ata el
  mecanismo de autorización de módulos consumidores al RBAC de usuario
  existente (RF-02/RF-04), no a un esquema M2M nuevo. Esto confirma la
  decisión ya tomada en INC-M02-90-G92 (identidad técnica vía rol + RBAC, no
  un segundo mecanismo de autenticación).
- Flujo alterno #4: *"El módulo que realiza la petición no cuenta con los
  permisos o el scope necesario para el tipo_dato solicitado → HTTP 403 →
  'Acceso denegado: El módulo solicitante no tiene autorización para
  consumir datos de tipo [TIPO_DATO].'"* — mensaje literal reproducido tal
  cual en el nuevo `AuthorizationError`.
- Auditoría: debe registrar "Módulo solicitante" — confirmó el hallazgo ya
  documentado en `estado_M02.md` (RF-50): `EventoAuditoria.modulo_consumidor`
  existe en el modelo pero ningún use case lo sobre-escribía nunca (quedaba
  siempre en el default `'modulo2'`).

### Consultas ejecutadas (MCP `postgres`, `sgpmp_dev`)

```sql
SELECT id_recurso, nombre_recurso FROM modulo1.recursos ORDER BY id_recurso DESC LIMIT 10;
SELECT id_rol, nombre_rol FROM modulo1.roles ORDER BY id_rol;
SELECT id_accion, codigo, descripcion FROM modulo1.acciones ORDER BY id_accion;
SELECT p.id_permiso, p.nombre, p.id_rol, r.nombre_rol, p.id_accion, p.es_activo
FROM modulo1.permisos p JOIN modulo1.roles r ON r.id_rol = p.id_rol
WHERE p.id_recurso = 29 ORDER BY p.id_accion, p.id_rol;
SELECT id_usuario, correo_electronico, id_rol FROM modulo1.usuarios
WHERE correo_electronico ILIKE '%integracion%' OR correo_electronico ILIKE '%test@pecuaria%';
SELECT conname, contype, pg_get_constraintdef(oid) FROM pg_constraint WHERE conrelid = 'modulo1.permisos'::regclass;
SELECT tgname, pg_get_triggerdef(oid) FROM pg_trigger WHERE tgrelid='modulo1.permisos'::regclass AND NOT tgisinternal;
SELECT proname, prosrc FROM pg_proc WHERE proname LIKE 'trg_fn_proteger_permisos_admin%' AND pronamespace='modulo1'::regnamespace;
```

### Gaps detectados

1. **Sin granularidad por `tipo_dato` en RBAC** (el gap que reporta QA). El
   único gate era `(recurso=29, accion=R)` a nivel de endpoint completo.
2. **`modulo_consumidor` inútil para auditoría.** Confirmado: el campo existe
   en `modulo2.bitacora_auditoria_m02` y en la entidad `EventoAuditoria`, pero
   ningún use case lo asignaba — quedaba siempre en `'modulo2'`.
3. **La identidad técnica M04 que INC-M02-90-G92 documenta como creada NO
   existe en `sgpmp_dev`.** `modulo1.roles` va de 1 a 11 y 14 — ningún rol
   `'Integración M04'`. Ese incidente dejó el bloque SQL como "Pendiente — no
   aplicable desde este entorno"; nunca se ejecutó contra esta base. Sin esa
   identidad, QA tampoco podía reejecutar TC-M02-155 aunque el código ya
   tuviera scopes.
4. **Los permisos `admin_*` son inmutables a nivel de trigger** una vez
   insertados (`trg_fn_proteger_permisos_admin_delete` /
   `..._update`, sin excepción para cascadas de FK). Esto obliga a que el
   seed de los permisos de scope para Administrador use
   `ON CONFLICT ... DO NOTHING` (nunca `DO UPDATE`) y a que el `downgrade()`
   de la migración sea un no-op documentado — mismo patrón ya usado en
   `f2c84d91a6e7` (RF-12).
5. **`fk_recurso_rol` (permisos → roles) tiene `ON DELETE CASCADE`** desde
   `c4a19e7d2b63` (RF-03), pero `usuarios.id_rol` sigue en `NO ACTION` — al
   revertir una identidad de rol hay que borrar primero sus usuarios/cuentas,
   nunca el rol directo.

## Decisión

Scopes granulares sobre el RBAC existente, no un mecanismo M2M nuevo (RF-50
mismo lo pide así — ver arriba). Se agregan 4 recursos nuevos en
`modulo1.recursos`, uno por `tipo_dato` (`eventos`, `fases`, `estado`,
`metricas`), cada uno con permiso de acción R. `tipo_dato=todos` exige los 4
scopes de forma estricta (RF-50: *"los datos requeridos por el módulo
consumidor deben existir; en caso contrario, se debe rechazar la
solicitud"*) — no se devuelve un subconjunto parcial en silencio cuando falta
alguno.

**Asunción documentada** (no especificada literalmente por el RF): el
comportamiento de `tipo_dato=todos` ante scopes parciales. Se optó por
rechazo estricto por ser el más simple, predecible y verificable por QA, y
por alinearse con el lenguaje de "completitud mínima → rechazar" del propio
RF-50. Si el criterio real del negocio es devolver un subconjunto parcial con
advertencia, es un cambio acotado a `_verificar_scope_tipo_dato` en el router.

## SQL aplicado

Migración Alembic `d944f4d8c215` (`v5.5.0_inc_m02_92_scope_tipo_dato_datos_consolidados`,
`down_revision=1147428cd8fb`) — ver el archivo para el DDL/DML completo:

1. Inserta los 4 recursos nuevos (`datos_analiticos_eventos/fases/estado/metricas`).
2. Otorga los 4 scopes a los 4 roles humanos que hoy ya leen el endpoint
   completo (Administrador, Productor, Veterinario, Ingeniero de Campo) — sin
   esto, activar el scope los habría dejado con 403 en un endpoint que hoy
   funciona para ellos.
3. Reaplica el bloque de INC-M02-90-G92 (rol `'Integración M04'` + usuario
   técnico `integracion.m04.test@pecuaria.co`, contraseña aleatoria nunca
   escrita en el repositorio) — idempotente, no lo toca si ya existe.
4. Otorga a `'Integración M04'` scope en 3 de los 4 `tipo_dato` (eventos,
   fases, estado) — **`metricas` queda deliberadamente sin scope**, como
   fixture real para que QA reejecute TC-M02-155 sin fabricar nada:
   módulo autenticado = sí, scope general (recurso 29/R) = sí, scope del
   `tipo_dato` solicitado (`metricas`) = no → HTTP 403
   `SCOPE_TIPO_DATO_NO_AUTORIZADO`.

**No se ejecutó** contra `sgpmp_dev` desde este entorno: la credencial de
sesión (`member_dev`) es de solo lectura (confirmado: `SELECT` sobre
`information_schema.role_table_grants` para `modulo1.permisos` devuelve cero
filas, y `alembic current`/`upgrade` fallan con `permission denied for table
alembic_version`). Queda pendiente de aplicación y aprobación formal del DBA
antes de mergear, como toda migración de este repositorio.

## RBAC — recursos nuevos y sus IDs

Los IDs (`59`–`62`) asumen que esta migración corre inmediatamente después de
`1147428cd8fb` (head actual al momento de escribir esto) sin que otra
migración concurrente inserte un recurso antes — `modulo1.recursos.id_recurso`
es una secuencia, así que el orden real depende del orden de aplicación de la
cadena de Alembic. Si otra migración con recurso nuevo se mergea primero,
los IDs hardcodeados en `activo_biologico_router.py`
(`_RECURSO_DATOS_EVENTOS` etc.) deben reverificarse contra la BD real antes
de desplegar — mismo riesgo ya implícito en todos los `_RECURSO*` existentes
de este router.

| id_recurso (esperado) | nombre_recurso | accion |
|---|---|---|
| 59 | `datos_analiticos_eventos` | R (2) |
| 60 | `datos_analiticos_fases` | R (2) |
| 61 | `datos_analiticos_estado` | R (2) |
| 62 | `datos_analiticos_metricas` | R (2) |

## Código

- `src/biological_assets/infrastructure/routers/activo_biologico_router.py`:
  constantes de recurso + `_verificar_scope_tipo_dato()` (evalúa el/los scope(s)
  requeridos vía `tiene_permiso()`, audita el rechazo en RF-52 igual que
  `require_permission_m02`, y lanza `AuthorizationError` con el mensaje
  literal del flujo alterno #4 de RF-50). Se invoca en el endpoint justo
  después de validar el DTO (ya conoce `tipo_dato` normalizado) y antes de
  construir el use case.
- `src/biological_assets/application/use_cases/gestion/consultar_datos_consolidados_use_case.py`:
  nuevo parámetro opcional `rol_repo: RolRepository | None`, usado en
  `_resolver_modulo_consumidor()` para derivar el `modulo_consumidor` real de
  la auditoría a partir del nombre del rol autenticado (patrón `'Integración
  M0<n>'` → `'modulo<n>'`; cualquier otro rol conserva el default histórico
  `'modulo2'`). Mismo patrón que ya usa `ConsultarBitacoraUseCase` para leer
  el nombre del rol vía el puerto `RolRepository`, no SQL directo.

## Fuera de alcance

- **Aislamiento del rate limit por módulo** (no por usuario) — sigue
  bloqueado por la ausencia de un securityScheme M2M propio; INC-M02-96-G94
  ya lo documentó como pendiente. La identidad M04 que esta migración por fin
  siembra desbloquea la *precondición* para hacerlo, pero cambiar la clave
  del limitador compartido (`id_usuario` → identidad de módulo) es una
  decisión de diseño de `src/shared/rate_limit.py`, usado por otros módulos —
  no se toca aquí.
- **Identidades para M03, M06 y M08** (los otros 3 consumidores que lista el
  RF). Solo M04 tenía un incidente previo (INC-M02-90-G92) pidiéndola
  explícitamente; sembrar las otras tres sin un caso de uso concreto que las
  necesite sería agregar datos de prueba sin consumidor real. Mismo patrón
  (rol `'Integración M0<n>'` + scopes) aplica cuando se necesiten.
- **RBAC más amplio que los actores que lista el RF** (Hallazgo transversal
  #5 de `estado_M02.md`): RF-50 solo lista "Sistema (módulos M03, M04, M06,
  M08)" como actor, pero el endpoint sigue siendo accesible para los 4 roles
  humanos vía el mismo recurso 29 que protege el resto de `activos-biologicos`.
  No se restringe aquí — es un problema de granularidad del catálogo RBAC más
  amplio que este ticket puntual, ya documentado como hallazgo sistémico.
