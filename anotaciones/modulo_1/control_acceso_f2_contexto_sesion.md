# Control de acceso por BD — F2 (contexto de sesión) y correcciones de F1

**Rama:** `feature/control-acceso-f2-contexto-sesion`
**Base técnica:** `anotaciones/plan_control_acceso_bd_rls.md`,
`anotaciones/IMPLEMENTACION_control_acceso_bd_rls.md`
**Estado de F1 al iniciar:** DBA (SamuelPR21) reportó F1 completada. Verificado
en vivo contra `sgpmp_dev` (vía MCP): existen `sgpmp_owner`/`sgpmp_app` y RLS
con políticas está activo en `modulo1` (migración `8d80fb56a30b`) y `modulo9`
(migración `5243bbbb28de`).

---

## 1. Hallazgo central: los documentos describen un F2 que ya no aplica

`anotaciones/plan_control_acceso_bd_rls.md` sección 7.2 y los dos documentos
de `Downloads/` (`Plan_Estrategico_Seguridad_BD.md`,
`IMPLEMENTACION_control_acceso_bd_rls.md`) especifican que F2 debe hacer:

```sql
SET LOCAL app.usuario_id = '42';
SET LOCAL app.id_rol     = '3';
```

**Eso no es lo que el F1 realmente desplegado consume.** Verificado
consultando `pg_proc`/`pg_get_functiondef` contra `sgpmp_dev`: las políticas
de `modulo1`/`modulo9` llaman `app_ctx.current_user_id()` y
`app_ctx.current_role()`, funciones `STABLE` que leen:

```sql
current_setting('app.current_user_id', true)::bigint
current_setting('app.current_role', true)  -- nombre del rol en TEXTO, no id_rol
```

Implementar F2 tal como está redactado en los documentos habría dejado el RLS
ciego (nunca lee la variable correcta), sin que ningún test superficial lo
detectara — las queries simplemente devolverían 0 filas, indistinguible de
"deny-by-default funcionando bien". Se implementó contra el contrato real,
verificado en vivo, no contra el documento. La convención de nombres
(`anotaciones/convencion_nomenclatura_bd.md`, sección nueva "Variables de
sesión (GUC) para RLS") queda actualizada para que este desface no se repita.

## 2. Qué se implementó (F2)

- **Punto único de contexto**: `get_current_user`
  (`src/identity_access/infrastructure/dependencies.py`) setea, una vez por
  request, después del último `commit()` de la propia dependencia:
  - `app.current_user_id` (bigint) — identidad, leída por `modulo1.fn_id_usuario_actual()`.
  - `app.current_role` (texto, nombre del rol) — requirió añadir
    `Roles.nombre_rol` al `JOIN` que ya arma la fila de `get_current_user`
    (antes solo traía `id_rol`).
  - `app.usuario_id` (entero, legado) — sigue alimentando el trigger
    `modulo2.trg_auditar_activo_biologico`, ajeno a esta rama.
  - Los tres vía `set_config(nombre, valor, true)` — equivalente parametrizado
    de `SET LOCAL`; se prefiere sobre `SET LOCAL app.x = :v` porque Postgres
    no permite bind params dentro de `SET LOCAL` para un valor de texto
    arbitrario (el nombre del rol).
- **Retirados** 5 de los 6 `SET LOCAL app.usuario_id` dispersos en
  `biological_assets` (evento_activo_repository, registrar_transferencia_use_case,
  activo_biologico_repository x3) — se recorrió el grafo de llamadas de cada
  uno antes de tocarlo, no por analogía.
- **Mantenido intacto** el de `historico_estado_repository.py:33`: también lo
  usa `RevertirRetirosVencidosUseCase` (tarea diaria RF-76 en `main.py`), que
  corre sin pasar por `get_current_user`. Borrarlo habría roto en silencio el
  trigger de auditoría de ese job nocturno.
- **Identidad interina de sistema** (`main.py`, función
  `_declarar_identidad_sistema`) para las tareas de fondo que sí tocan
  `modulo1`/`modulo9` ya con RLS activo: el archivado diario de auditoría
  (RF-10) y el poller de exportaciones de auditoría (RF-10) se declaran
  `app.current_role = 'Administrador'` al abrir su `SessionLocal()`. Es una
  respuesta mínima e interina a la Decisión D1 del plan (identidad de
  procesos de fondo), que sigue sin resolver por equipo + DBA — no crea
  usuario de servicio ni toca `modulo1.usuarios`.
- **Test nuevo**
  (`tests/integration/test_control_acceso_f2_contexto_sesion_no_fuga.py`):
  prueba contra una conexión real que `set_config(..., true)` no sobrevive ni
  al `COMMIT` ni al `ROLLBACK` de esa misma conexión — la garantía de la que
  depende todo el diseño frente al pool de `src/shared/database.py`.

## 3. Bugs de F1 corregidos (migración `b53fe19f276e`)

Ninguno era visible hasta ahora porque nada llamaba `set_config` todavía.
Los cinco se verificaron con SQL real contra `sgpmp_dev` (dentro de una
transacción con `ROLLBACK`, sin dejar cambios):

| # | Objeto | Problema | Consecuencia sin el fix |
|---|---|---|---|
| 0 | `sgpmp_app` sin `GRANT USAGE ON SCHEMA app_ctx` | Los triggers `modulo1.fn_prevenir_autocambio_rol()` y `modulo9.fn_proteger_activo_especie()` llaman `app_ctx.*` sin `SECURITY DEFINER`; PL/pgSQL resuelve el nombre con los privilegios de quien ejecuta el `UPDATE` | Cualquier `UPDATE` sobre `modulo1.usuarios` (RF-05/RF-13) o `modulo9.especies` falla con `permission denied for schema app_ctx`, para cualquier rol incluido Administrador |
| 1 | `pol_especies_update` (modulo9) | No incluye `'Veterinario'`, pero `modulo1.permisos` sí le da el permiso `U` sobre `especies` | Veterinario deja de poder editar especies; el `UPDATE` afecta 0 filas sin error explicado |
| 2 | `modulo1.eventos_archivados` | RLS activo, solo política `SELECT` | El `INSERT` del archivado diario (RF-10) queda bloqueado; el job deja de archivar en silencio |
| 3 | `modulo1.cola_exportaciones_auditoria` | Sin política de `UPDATE` | El poller de exportaciones no puede marcar la fila `EN_PROCESO`/`COMPLETADO` |
| 4 | `modulo1.ejecuciones_exportaciones_auditoria` | Sin política de `INSERT` | El mismo poller no puede insertar el resultado de la ejecución |

Los ítems 2-4 se resuelven en conjunto con la identidad interina de sistema
del punto anterior (las políticas nuevas exigen rol `Administrador`, igual
que las ya existentes sobre las mismas tablas).

**Pendiente de autorización de SamuelPR21** en el PR antes de mergear a
`dev` — corrige migraciones de su autoría, y toda migración con DDL lo
requiere (regla no negociable del repo).

### 3.1 Reubicación de las funciones de contexto (migración `731fb3997631`)

Directriz de SamuelPR21 en el PR #469: no mantener un schema dedicado
(`app_ctx`) para las funciones de contexto; pertenecen a identidad y acceso.

| Antes | Después |
|---|---|
| `app_ctx.current_user_id()` | `modulo1.fn_id_usuario_actual()` |
| `app_ctx.current_role()` | `modulo1.fn_rol_actual()` |

- `ALTER FUNCTION ... SET SCHEMA` + `RENAME`, no `CREATE`/`DROP`: las
  políticas guardan la función por OID, así que ninguna `pol_*` se recrea.
- El prefijo `fn_` sigue la convención; además `current_role` suelto es la
  palabra reservada de SQL (devuelve el rol de Postgres, `sgpmp_app`).
- Se recrean los dos triggers PL/pgSQL que nombran las funciones en texto
  (`fn_prevenir_autocambio_rol`, `fn_proteger_activo_especie`), con el
  mismo cuerpo.
- `DROP SCHEMA app_ctx` sin `CASCADE`. El `GRANT USAGE` de `b53fe19f276e`
  deja de hacer falta: `sgpmp_app` ya tiene `USAGE` sobre `modulo1`.
- Orden acordado con el DBA: `d7c4e9a1b2f6 → b53fe19f276e → 731fb3997631 →`
  su F3 (`315eaa6c5dc1`) rebasada encima.

## 4. Qué se dejó documentado y no se tocó en esta rama

- **`correo_recuperacion_background_adapter.py` /
  `notificacion_sesion_background_adapter.py`**: el camino principal (INSERT
  en `modulo1.notificaciones`) no necesita identidad (`WITH CHECK (true)`).
  Solo `_alertar_administradores_fallo_smtp` (rama best-effort, ya con su
  propio log de fallo) quedaría sin destinatarios bajo RLS sin identidad —
  baja frecuencia, se documenta, no se parchea.
- **`mqtt_http_adapter.py`**: lee `modulo1.credenciales_servicio`, que la
  propia migración de F1 deja intencionalmente deny-all. Bajo RLS pasa a
  advertir siempre "token desincronizado" en logs — ruido, no ruptura
  funcional (MQTT sigue funcionando).
- **Rediseño general de las políticas hardcodeadas por rol** (leer
  `modulo1.permisos` dinámicamente en vez de listar nombres de rol en cada
  `CREATE POLICY`, como recomienda la sección 7.3 del análisis): se corrigió
  el caso puntual que rompía algo real (Veterinario/especies), no el patrón
  completo — es un rediseño de políticas ya escritas por el DBA, para F4/F5.
- **`docker-compose.yml` / `Dockerfile.postgres`**: no se modifican. Ese
  Postgres (Dokploy) no crea `sgpmp_app`/`sgpmp_owner` en ningún
  init-script — solo instala `pg_cron`. Cambiar el compose de producción
  requiere coordinar con **chebaztian**; se preparó únicamente el lado código
  (`.env.example`, `alembic/env.py` leen `ALEMBIC_DATABASE_URL` si existe,
  con fallback a `DATABASE_URL`).

## 5. Verificación realizada

- Migración `b53fe19f276e` (upgrade completo + downgrade + upgrade de nuevo)
  ejecutada dentro de una transacción contra `sgpmp_dev`, con `ROLLBACK` al
  final — no queda nada persistido. Incluyó un `UPDATE` real como Veterinario
  sobre `modulo9.especies`, un `INSERT` real en `modulo1.eventos_archivados`,
  un `UPDATE` real en `modulo1.cola_exportaciones_auditoria`, un `INSERT`
  real en `modulo1.ejecuciones_exportaciones_auditoria` y un `UPDATE` real
  sobre `modulo1.usuarios` — los cinco fallaban antes del fix con
  `permission denied` o 0 filas afectadas, y pasan después.
- No se pudo correr la suite de `pytest` autenticada como `sgpmp_app`: no hay
  credenciales de ese rol disponibles en este entorno (la única vía de
  acceso a `sgpmp_dev` en esta sesión es el MCP de Postgres, con rol `dba`).
  Se documenta la limitación en vez de simular una corrida que no se hizo.
- `python -m py_compile` sobre todos los archivos `.py` tocados: sin errores
  de sintaxis.
- Migración `731fb3997631` en un Postgres 17 desechable construido desde cero
  con `alembic upgrade` (no toca ninguna base compartida). En cada estado
  (`b53fe19f276e`, tras upgrade, tras downgrade, tras re-upgrade) se corrió
  como `sgpmp_app` con la identidad declarada vía `set_config`: autocambio de
  rol bloqueado (RF-05), Veterinario no puede desactivar especie y
  Administrador sí (RF-15), y `pol_usuarios_select` limita al Veterinario a su
  fila. Los OID de las funciones se conservan tras el upgrade y el downgrade.
  En una base nueva, `sgpmp_app` hay que crearlo antes de `alembic upgrade`:
  ninguna migración crea ese rol.
- El downgrade completo hasta antes de F1 falla en `8d80fb56a30b`, también
  sin las migraciones de esta rama: el downgrade de `5243bbbb28de` no borra
  `pol_config_globales_insert`/`_update`, que dependen de `current_role()`.
  Las migraciones de esta rama no lo introducen ni lo corrigen.

## 6. Pendiente / a confirmar

- **Decisión D1 definitiva** (identidad de procesos de fondo: usuario de
  servicio dedicado vs. rol con `BYPASSRLS`) — equipo + DBA. La solución de
  esta rama es interina.
- **Cambio de `docker-compose.yml`** para bootstrapear `sgpmp_app`/`sgpmp_owner`
  en el Postgres de Dokploy — revisar con chebaztian.
- **Autorización de SamuelPR21**: `b53fe19f276e` aprobada en comentario del
  PR #469 (2026-10-01); `731fb3997631` pendiente de su revisión. Al mergear a
  `dev`, avisarle para que rebase su F3 (`315eaa6c5dc1`).
- Ver `anotaciones/f3_impacto_usuarios_fincas_por_schema.md` para el impacto
  de F3 (ya implementada) sobre las políticas RLS de F1/F4/F5.
