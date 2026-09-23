# INC-M02-92-G93 [RF-50][TC-M02-155] — Scope por `tipo_dato`

**Issue:** [#390](https://github.com/Arekkazu/sgpmp-backend/issues/390)
**Depende de:** INC-M02-93-G93 (#391, PR previo de esta cadena — identidad M06).

## Qué pedía QA

TC-M02-155 exige construir un escenario:

```
módulo autenticado = Sí
scope general válido = Sí
scope para el tipo_dato solicitado = No
→ verificar HTTP 403
```

El modelo RBAC de este proyecto autoriza por `(recurso, acción)` a nivel de
**endpoint completo** — no existía forma de dar acceso a `datos-consolidados`
en general pero negarlo para un `tipo_dato` específico (`eventos`, `fases`,
`estado`, `metricas`). Esto ya se había documentado como límite conocido en
`inc_m02_90_g92_identidad_m04.md`: "acotar esto a endpoints específicos
requeriría rediseñar el modelo RBAC completo — fuera de alcance de este
issue puntual". Este PR sí aborda esa granularidad, pero acotada a una sola
dimensión (`tipo_dato` de este endpoint), no un rediseño general de RBAC.

## Decisión: 4 recursos RBAC nuevos, uno por `tipo_dato`

Se agregan 4 filas a `modulo1.recursos` (una por valor de `tipo_dato` del DTO,
excepto `todos`, que exige tenerlos los cuatro):

- `datos_consolidados_eventos`
- `datos_consolidados_fases`
- `datos_consolidados_estado`
- `datos_consolidados_metricas`

El router, después de construir el DTO (ya conoce el `tipo_dato` solicitado),
verifica con `tiene_permiso()` — la misma función que usa `require_permission`
en todo el proyecto — que el rol del usuario tenga el recurso granular
correspondiente, **además** del permiso base sobre `activos_biologicos` (29)
que ya exige el endpoint. Si falta, `403 SCOPE_TIPO_DATO_NO_AUTORIZADO` con
el mensaje textual del flujo alterno de RF-50 ("Acceso denegado: El módulo
solicitante no tiene autorización para consumir datos de tipo [TIPO_DATO]").

Se optó por **reusar el mecanismo RBAC existente** (`modulo1.recursos` +
`modulo1.permisos` + `tiene_permiso`) en vez de construir un sistema de
scopes paralelo (tabla de "consumidores de módulo" con credenciales propias)
— exactamente la misma filosofía de las dos identidades técnicas ya creadas
(M04, M06): resolver con datos/configuración lo que no requiere código nuevo.

**Compatibilidad retroactiva:** todos los roles que ya tenían acceso al
endpoint (Administrador, Productor, Veterinario, Ingeniero de Campo,
Integración M04) reciben los 4 scopes granulares — su comportamiento no
cambia. Solo **Integración M06** recibe deliberadamente un scope parcial
(solo `metricas`, coherente con su propósito de valoración/NIC-41) — esto
también es, de paso, la precondición real que pedía QA para reproducir el
403 (antes no había ningún consumidor real con ese scope incompleto para
probarlo sin fabricar datos artificiales).

## Por qué se resuelve el `id_recurso` por nombre, no por número

**Hallazgo durante la implementación:** al aplicar el mismo DDL a `sgpmp` y
`pruebas`, los 4 recursos nuevos terminaron con IDs distintos en cada base
(`60-63` en `sgpmp`, inicialmente `58-61` en `pruebas`) porque el máximo
`id_recurso` preexistente ya era distinto entre ambas — division ambiental
no causada por este cambio, preexistente (`pruebas` no tenía todos los
recursos que sí tiene `sgpmp`, ej. algunos de M05).

Intentar forzar el mismo id numérico en ambas bases chocó con un trigger
real de protección: `trg_proteger_permisos_admin_update` /
`..._delete` hacen que cualquier permiso ya creado para el rol
**Administrador** sea inmutable e indeleble (protección legítima e
intencional del sistema, no un bug). Una vez insertado, el permiso
`admin_leer_dc_eventos` en `pruebas` quedó fijo apuntando al `id_recurso`
que le tocó, sin forma de corregirlo después sin desactivar triggers de
seguridad — algo que no se justifica para arreglar un error de seeding.

**Conclusión de diseño:** el código resuelve `id_recurso` consultando
`modulo1.recursos` por `nombre_recurso` (`datos_consolidados_<tipo>`) en
cada request, en vez de hardcodear el número como hace el resto del router
(`_RECURSO = 29`). Es un patrón distinto al resto del archivo a propósito:
`activos_biologicos` (29) se sembró de forma idéntica en todas las bases
desde el origen del proyecto; un recurso nuevo creado hoy no tiene esa
garantía. Este PR no vuelve a alinear los IDs de `sgpmp` y `pruebas` (no era
necesario una vez resuelto por nombre, y forzarlo habría requerido tocar
triggers de protección de permisos de Administrador sin necesidad real).

## Qué se creó (aplicado en `sgpmp` y `pruebas`)

| `nombre_recurso` | `id_recurso` en `sgpmp` | `id_recurso` en `pruebas` |
|---|---|---|
| `datos_consolidados_eventos` | 60 | 58 |
| `datos_consolidados_fases` | 61 | 59 |
| `datos_consolidados_estado` | 62 | 60 |
| `datos_consolidados_metricas` | 63 | 61 |

(Los números difieren entre bases — ver explicación arriba; el código nunca
los usa directamente.)

Permisos otorgados (acción `R`=2) en ambas bases:

- Administrador, Productor, Veterinario, Ingeniero de Campo, Integración M04:
  los 4 scopes (preserva el acceso previo).
- Integración M06: solo `datos_consolidados_metricas`.

DML aplicado directamente vía MCP de postgres (`sgpmp`) y `psql` (`pruebas`),
sin migración de Alembic — mismo criterio que INC-M02-93-G93 (datos de
catálogo/RBAC, no cambio de esquema).

## Qué cambia en código

- `activo_biologico_router.py`: `_id_recurso_datos_consolidados()` (lookup
  por nombre) + `_verificar_scope_tipo_dato()` (aplicado en
  `consultar_datos_consolidados`, después de construir el DTO).
- Sin cambios al DTO, al use case ni al contrato de respuesta — es una capa
  de autorización adicional, no de datos.

## Qué NO se hizo

No se audita a RF-52 el rechazo por scope de `tipo_dato` (a diferencia del
rechazo por `(recurso, acción)` base, que sí audita `require_permission_m02`
vía `RegistrarAccesoNoAutorizadoUseCase`). Cablear esa auditoría requiere
`Request` en la firma del handler y reconstruir el mismo flujo de auditoría
manualmente — se dejó fuera de este PR para no expandir el alcance del issue
puntual; la bitácora RF-52 de M02 ya tiene gaps de cobertura documentados de
forma transversal (ver `estado_M02.md`, hallazgo #6).

## Verificación

```
TEST_DATABASE_URL=postgresql://postgres:dev@localhost:5432/pruebas \
  python -m pytest tests/biological_assets/test_inc_m02_92_g93_rf50_scope_tipo_dato.py \
                    tests/integration/test_inc_m02_92_g93_rf50_scope_m06_e2e.py \
                    tests/biological_assets/ tests/integration/ -q
```
10 tests nuevos (5 unitarios + 5 de integración contra Postgres real,
incluyendo la verificación de que M06 obtiene 403 en `eventos`/`fases`/
`estado` y 200 en `metricas`) en verde. Los 14 fallos que aparecen en la
suite amplia son preexistentes en la base sin este cambio (confirmado
reproduciéndolos también en `fix/m02-fixes` sin este PR aplicado) — no
relacionados.
