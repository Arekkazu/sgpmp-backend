# Plan — Administrador con alcance global sobre las fincas

Fecha: 2026-10-10 · Estado: **implementado** (rama `feature/admin-alcance-global`) · Requiere: autorización del DBA para la migración `f68851f9a433`

> **Decisión (2026-10-10):** el Administrador es global para **leer y escribir**, como dice
> RF-19/M01 ("hace de todo y ve de todo"). Se implementa la **opción A**. El punto 3 de
> riesgos queda cerrado: global también para escribir.

## Qué se hizo

| Capa | Archivo | Cambio |
|---|---|---|
| BD | `alembic/versions/f68851f9a433_administrador_alcance_global_fincas.py` | `CREATE OR REPLACE FUNCTION modulo9.fn_fincas_del_usuario`: si el rol de `p_usuario_id` es el protegido (`roles.es_protegido`), devuelve todas las fincas; si no, la misma consulta de siempre sobre `usuarios_fincas`. Ninguna política cambia. El `downgrade` restaura el cuerpo anterior. No se crean objetos nuevos (convención `fn_` intacta). |
| App | `src/shared/alcance_finca_adapter.py` | `es_global(id_rol)` reutiliza `modulo1.fn_rol_protegido(id_rol)`; `listar_ids_fincas_permitidas` devuelve `None` para ese rol. Los 12 consumidores ya manejaban `None`. |
| App | puerto, `finca_router.py`, `finca_repository.py` (dominio e infraestructura), `alcance_activo_m02_adapter.py` | Solo docstrings y comentarios que decían "ningún rol es global". |

Sin cambios: políticas RLS, routers, use cases y frontend. El vínculo automático del creador
al registrar una finca se conserva; ya no es necesario para RLS, pero no estorba.

## Verificación

- **Migración:** `upgrade` → `downgrade` → `upgrade` sobre un Postgres 17 limpio construido con
  `alembic upgrade head`, y `upgrade` sobre `sgpmp_dev` local (head `f68851f9a433`).
- **Unitarias** (biological_assets, telemetry, prediction, configuration, shared): 1152 pasan.
  El único fallo, `test_ingreso_fecha_futura_lanza_validation_error`, falla igual sin este cambio.
- **Integración** (toda `tests/integration`, con `TEST_ROL_APP=sgpmp_app`, es decir, requests
  sujetos a RLS), comparando la misma BD con y sin el cambio:
  - **0 fallos nuevos.** Con el cambio fallan 16 pruebas; sin él, 19. Las 16 son de entorno
    (BD desechable sin datos ni dueños reales; por ejemplo, la vista `vw_rf48` es de `postgres`).
  - `test_administrador_ve_y_edita_lo_de_cualquier_finca` (nueva, RLS como `sgpmp_app`) falla sin
    la migración y pasa con ella.
  - `test_los_demas_roles_siguen_limitados_a_sus_fincas` (nueva) pasa en ambos casos.
  - `test_veterinario_asignado_a_finca_ajena_accede_a_ella` pasaba **solo** con el cambio. Un
    Administrador sin vínculo no podía asignar una finca ajena a otro usuario
    (`PUT /usuarios/{id}/fincas`) porque RLS le ocultaba la finca. Este cambio también lo corrige.
- **Datos reales de `sgpmp_dev`**, como `sgpmp_app` y en una transacción revertida (15 fincas y
  28 activos en total): el Administrador (vinculado a 1 finca) ve 15/15 fincas y 28/28 activos.
  Los otros 10 roles ven exactamente sus fincas vinculadas, igual que antes.

## Pruebas tocadas

- `tests/shared/test_alcance_finca.py`: el Administrador es global; un rol no protegido no lo es.
- `tests/configuration/test_inc_m09_g82_acceso_finca.py`: el fake responde la consulta de rol;
  `test_permiso_de_gestion_no_concede_alcance_global` se mantiene (un permiso de gestión no
  vuelve global a un rol no protegido); nueva prueba del Administrador.
- `tests/integration/test_inc_m09_g82_acceso_finca_integration.py`:
  `test_administrador_solo_consulta_sus_fincas` → `test_administrador_consulta_todas_las_fincas`.
- `tests/integration/test_control_acceso_f4_aislamiento.py`: el fixture acepta el rol; 2 pruebas nuevas.

## Problema

RF-19 y todo M01 tratan al Administrador como "Administrador del sistema" (rol global).
Hoy, por decisión del DBA en el PR #485 (F4, ver `anotaciones/f4_rls_desarrollo.md`, fila
"Alcance global": *"Ningún rol lo tiene, ni el Administrador … `fn_alcance_global` no se
crea"*), el Administrador solo ve los datos operativos de las fincas en las que tiene una
fila activa en `modulo9.usuarios_fincas`.

Efecto visible: un admin no vinculado ve listas vacías, recibe 404, o `200 null` (caso
`identidad_visuales`). Puede crear y editar fincas (`pol_fincas_insert/update` revisan
`fn_rol_actual() = 'Administrador'`), pero no puede leer una finca que no tenga vinculada.
Como en Postgres un `UPDATE` también exige pasar la política SELECT, en la práctica
tampoco puede editarla.

Cambiar esto **revierte una decisión explícita del DBA**, así que no es solo un cambio técnico.

## Inventario (BD local `sgpmp_dev`, head `5c2e8a1f7d39`)

### Dónde vive el filtro por finca en la BD

Solo `modulo1`, `modulo2` y `modulo9` tienen RLS (los módulos 3–8 no tienen políticas, salvo
1 tabla en `modulo8`). Todo el filtro por finca pasa por una sola cadena de funciones helper:

```
fn_fincas_del_usuario(uid)            ← lee usuarios_fincas (ÚNICO punto que decide)
 └─ fn_infraestructuras_del_usuario   ← áreas de esas fincas
     ├─ fn_dispositivos_del_usuario
     │   └─ fn_sensores_del_usuario
     └─ modulo2.fn_activos_del_usuario
```

| Esquema | Políticas que filtran por helper | Heredan por `EXISTS` sobre una tabla padre con RLS |
|---|---|---|
| modulo9 | 35 (fincas 8, infraestructuras 15, dispositivos 10, sensores 2) | — |
| modulo2 | 31 (activos 20, infraestructuras 8, sensores 3) | 14 (eventos_* y auditoría de asociaciones) |

No hay políticas que lean `usuarios_fincas` directamente: todas llaman a los helpers.
**Si se cambia `fn_fincas_del_usuario`, se corrigen las ~80 políticas de una vez.**

`modulo1` (usuarios, roles, permisos, eventos) **ya es global para el admin**: usa
`fn_tiene_permiso(recurso, acción)`. No se toca.

Otros objetos que leen `usuarios_fincas` (no son compuertas de acceso; solo muestran datos):
- `vw_rf19_fincas_productor_resumen` y `vw_rf20_fincas_activas_selector`: agregan los
  productores de cada finca, filtrados por `nombre_rol`.
- `vw_rf25_contexto_usuario`: "finca activa" del usuario. Un admin sin vínculo seguirá
  sin finca activa ahí, porque la vista no usa el helper (es aceptable; ver riesgos).
- Trigger `fn_asignar_finca_usuario_servicio`: vincula al usuario de servicio a cada finca nueva.

### Dónde vive el filtro por finca en la app

`src/shared/alcance_finca_adapter.py` (`AlcanceFincaAdapter`) es el único punto:
- `es_global()` → siempre `False`
- `listar_ids_fincas_permitidas()` → nunca devuelve `None`

Lo usan 12 archivos (routers de configuración, activos, telemetría, y adaptadores de M04/M05).
**Todos ya manejan `None` = "sin restricción"**: el contrato se conservó a propósito
(ver el docstring del puerto). Basta con cambiar el adaptador; no hay que tocar a los consumidores.

### Datos

`sgpmp_dev`: 6 usuarios Administrador, todos vinculados al menos a una finca hoy. El
usuario de servicio `servicio.sistema@sgpmp.local` **también tiene rol Administrador**
(`src/shared/database.py:70`) y ya ve todas las fincas por filas explícitas.

## Opciones

### A. Excepción del admin en `fn_fincas_del_usuario` + adaptador de la app (recomendada)

**BD — 1 migración Alembic, 1 `CREATE OR REPLACE FUNCTION`:**

```sql
CREATE OR REPLACE FUNCTION modulo9.fn_fincas_del_usuario(p_usuario_id bigint)
RETURNS TABLE(id_finca integer) LANGUAGE sql STABLE SECURITY DEFINER
SET search_path TO 'pg_catalog', 'modulo9', 'modulo1' AS $$
    SELECT f.id_finca FROM modulo9.fincas f
    WHERE EXISTS (SELECT 1 FROM modulo1.usuarios u JOIN modulo1.roles r ON r.id_rol = u.id_rol
                  WHERE u.id_usuario = p_usuario_id AND r.es_protegido)
    UNION
    SELECT uf.id_finca FROM modulo9.usuarios_fincas uf
    WHERE uf.id_usuario = p_usuario_id AND uf.es_activo IS TRUE;
$$;
```

- Decide por el rol del `p_usuario_id` (no por `app.current_role`): así el helper responde
  igual sin importar quién lo invoque.
- Usa `roles.es_protegido` (hoy solo lo tiene Administrador; no se puede renombrar ni borrar
  por los triggers de M01) en vez del nombre quemado. Alternativa equivalente:
  `r.nombre_rol = 'Administrador'`, como ya hacen `pol_fincas_insert/update`.
- `downgrade`: restaurar el cuerpo actual (una sola consulta a `usuarios_fincas`).

**App — 1 archivo:** `AlcanceFincaAdapter.es_global(id_rol)` devuelve `True` para el rol
protegido, y `listar_ids_fincas_permitidas` devuelve `None` en ese caso. Se puede leer
`roles.es_protegido` por `id_rol`, igual que la BD, para no quemar ningún id.

**Tests que fijan la regla actual y hay que invertir:**
- `tests/shared/test_alcance_finca.py::test_ningun_rol_es_global_ni_el_administrador`
- `tests/shared/test_alcance_finca.py::test_administrador_lista_solo_sus_fincas`
- `tests/configuration/test_inc_m09_g82_acceso_finca.py::test_permiso_de_gestion_no_concede_alcance_global`
- `tests/integration/test_inc_m09_g82_acceso_finca_integration.py::test_administrador_solo_consulta_sus_fincas`
- Prueba nueva en `tests/integration/test_control_acceso_f4_aislamiento.py`: admin sin vínculo,
  conectado como `sgpmp_app`, ve una finca ajena y sus activos; un Productor sigue sin verla.

**Tamaño:** 1 migración pequeña + 1 archivo de app + ~5 tests. Sin cambios en políticas,
routers ni frontend.

### A2. Igual que A, pero decidido por permiso RBAC en vez de por rol

Crear un recurso `alcance_global_fincas` (acción R) en `modulo1.recursos`/`permisos` y que
el helper y el adaptador consulten si el rol de `p_usuario_id` tiene ese permiso.
- A favor: es dinámico, como manda la regla RBAC del CLAUDE.md. Mañana se podría dar alcance
  global a "Supervisor" sin migrar.
- En contra: más DML (recurso + permiso, con el drift de `id_recurso` entre `sgpmp` y
  `pruebas`; resolver por nombre), y `fn_tiene_permiso` hoy mira el rol de la sesión, no el
  de un `p_usuario_id`, así que hace falta una variante.

### B. Agregar `OR fn_rol_actual() = 'Administrador'` política por política

~66 políticas en 2 esquemas, con riesgo de olvidar alguna (F5 ya borró una política por
accidente, ver PR #547). Mismo resultado que A con 30 veces más superficie. **Descartada.**

### C. `BYPASSRLS`

Todos los usuarios entran por el mismo login `sgpmp_app`; no se puede dar solo al admin.
**Descartada.**

### D. Sin tocar esquema: vincular automáticamente a los admins con todas las fincas

Un trigger en `fincas` (como el del usuario de servicio) más un backfill, y otro trigger
cuando un usuario pasa a ser Administrador.
- A favor: cero cambios en políticas y en la app; es solo una extensión del patrón D1 del DBA.
- En contra: llena `usuarios_fincas` de filas que significan "todo"; hay que mantener la
  sincronía en 3 eventos (alta de finca, alta de admin, cambio de rol) y retirarlas al degradar
  el rol; el admin quedaría como "usuario de la finca" en la pantalla de accesos de cada finca.
  Sigue siendo una migración (triggers), así que también pasa por el DBA.

## Riesgos y puntos a decidir

1. **Revierte la decisión del DBA (PR #485).** Hay que presentarla así, con RF-19/M01 como
   respaldo. Sin su OK no se mergea (migración ⇒ autorización de SamuelPR21).
2. **El usuario de servicio tiene rol Administrador.** Con A pasa a ser global por rol.
   En la práctica no cambia nada (ya ve todas las fincas por filas explícitas), pero contradice
   el espíritu de D1 ("filas explícitas"). Si el DBA lo pide, se excluye por correo dentro
   del helper.
3. **Escritura:** con A, el admin también pasa los `WITH CHECK` de M02/M09 en fincas
   ajenas (crear activos, eventos, dispositivos). Eso es coherente con "Administrador del
   sistema", pero hay que confirmarlo con Análisis: ¿global solo para leer, o también para
   escribir? Si es solo lectura, A no sirve tal cual: habría que tocar solo las políticas
   SELECT (se parece a B, pero en ~30 políticas).
4. **Volumen:** el admin listará todas las fincas y todos sus activos. Los endpoints ya paginan
   en su mayoría; revisar los que no (selector de fincas, monitoreo).
5. **RF-25 contexto (`vw_rf25_contexto_usuario`):** un admin sin vínculo seguirá sin "finca
   activa". Si el frontend depende de eso para habilitar pantallas, hay que revisarlo aparte.
6. **Bases:** aplicar en `sgpmp` (dev), `pruebas` y TEST mediante Alembic.

## Recomendación

**Opción A** (o A2, si Análisis quiere que el alcance global sea configurable por permiso).
Antes de codear hace falta cerrar el punto 3 (lectura vs. escritura) con Análisis y
tener el visto bueno del DBA para revertir la decisión de F4.
