# INC-M02-61-G52 — Acceso M:N de usuarios a fincas

**RF:** RF-41 (consulta del activo), RF-46 (historial: "el Veterinario puede consultar
el historial de activos de la finca asignada"), RF-25 (alcance por finca)
**Issue:** Arekkazu/SGPMP-FRONT-END-PWA#97
**Migración:** `1b9536d4411c` (`inc_m02_61_g52_usuarios_fincas`)

## Síntoma

Un Administrador consulta el activo 51 → `200`. Un Veterinario con permiso de lectura
activo sobre el recurso consulta el mismo activo segundos después → `404
ACTIVO_NO_ENCONTRADO`, en el detalle y en el historial. Determinístico, no es caché
ni RBAC.

## Causa raíz

`AlcanceFincaAdapter.listar_ids_fincas_permitidas` resolvía las fincas de un rol sin
alcance global con `modulo9.fincas.id_usuario`: **1 finca = 1 dueño**. Un Veterinario
o un Ingeniero de Campo nunca es dueño de la finca que atiende, así que su lista
quedaba vacía y el repositorio filtraba el activo como inexistente.

Tampoco había forma de corregirlo desde la interfaz: `PUT /usuarios/{id}/fincas`
respondía `409 FINCA_YA_ASIGNADA` si la finca ya tenía dueño.

La deuda estaba documentada en `anotaciones/modulo_9/rf25_alcance_finca_multifinca_pendiente.md`.

## Qué cambia

**Base de datos** (sin cambios en tablas existentes):

- `modulo9.usuarios_fincas` (M:N): `id_usuario_finca`, `id_usuario`, `id_finca`,
  `fecha_creacion`, `es_activo`, con `uq_usuario_finca (id_usuario, id_finca)`,
  `idx_usuario_finca_finca` y el trigger genérico `trg_auditoria` (conceder o retirar
  acceso queda en `auditoria.logs_dml`). Las FK son `ON DELETE CASCADE`.
- Migración de datos: una fila por cada `fincas.id_usuario` que apunte a un usuario
  existente. Nadie pierde el acceso que tenía. Los dueños inexistentes (la FK de
  `fincas.id_usuario` es `NOT VALID`) se descartan.
- `modulo9.vw_rf25_contexto_usuario` resuelve la finca activa desde `usuarios_fincas`,
  con las mismas columnas (`CREATE OR REPLACE`, conserva los `GRANT`).

**Decisión sobre `fincas.id_usuario`:** se conserva como **propietario** (lo muestra y
lo fija el CRUD de fincas), pero ya no concede acceso por sí solo. Registrar una finca
con propietario le crea su fila de acceso en la misma transacción
(`SqlAlchemyFincaRepository.guardar`).

**Aplicación:** todo el alcance pasa por `AlcanceFincaAdapter`, que ahora lee
`usuarios_fincas`. Eso corrige de golpe biological_assets, telemetry, configuration,
supplies y prediction. Los tres sitios que comparaban contra el dueño por su cuenta
pasan a usar las fincas permitidas del adaptador:

| Sitio | Antes | Ahora |
|---|---|---|
| `GET /configuracion/fincas` y `/{id_finca}` | `finca.id_usuario == usuario` | `id_finca in fincas_permitidas` |
| `GET /configuracion/sensores/{id}/asociaciones` | dueño de la finca del área | `area.id_finca in fincas_permitidas` |
| `GET /usuarios/{id}/detalle` → `fincas` | `fincas.id_usuario` | `usuarios_fincas` activas |

## Contrato de `PUT /usuarios/{id_usuario}/fincas`

El cuerpo no cambia: `ids_fincas` sigue siendo el conjunto **completo** de fincas del
usuario. Cambia el significado: deja de ser "cambiar el dueño" y pasa a ser "gestionar
accesos".

| | Antes | Ahora |
|---|---|---|
| Finca con otro dueño | `409 FINCA_YA_ASIGNADA` | `200`, se concede el acceso |
| Finca retirada de la lista | `fincas.id_usuario = NULL` | `usuarios_fincas.es_activo = false` |
| `fincas.id_usuario` | lo reescribía | no lo toca |
| Finca inexistente | `404 FINCA_NO_ENCONTRADA` | igual |

`FINCA_YA_ASIGNADA` desaparece del endpoint. El frontend deshabilitaba las fincas con
otro dueño en el modal de usuario; ese bloqueo se retira en el mismo ciclo.

```bash
# Asignar al Veterinario (id 11) la finca 51, que es de otro usuario
curl -X PUT "$API/usuarios/11/fincas" \
  -H "Authorization: Bearer $TOKEN_ADMIN" -H "Content-Type: application/json" \
  -d '{"ids_fincas": [51]}'
# 200 {"message": "Fincas asignadas al usuario 11: [51]."}   (antes: 409 FINCA_YA_ASIGNADA)

# Ahora el Veterinario consulta el activo de esa finca
curl "$API/activos-biologicos/51" -H "Authorization: Bearer $TOKEN_VETERINARIO"
# 200   (antes: 404 ACTIVO_NO_ENCONTRADO)

# Retirarle todas las fincas
curl -X PUT "$API/usuarios/11/fincas" \
  -H "Authorization: Bearer $TOKEN_ADMIN" -H "Content-Type: application/json" \
  -d '{"ids_fincas": []}'
# 200; el propietario de la finca 51 conserva su acceso

# Finca inexistente
curl -X PUT "$API/usuarios/11/fincas" \
  -H "Authorization: Bearer $TOKEN_ADMIN" -H "Content-Type: application/json" \
  -d '{"ids_fincas": [999999]}'
# 404 FINCA_NO_ENCONTRADA
```

## Fuera de alcance

- `modulo9.fn_fincas_del_usuario()` y las políticas RLS: son de la fase siguiente del
  plan de control de acceso por BD, que las consume. El adaptador ya es hoy el único
  punto que responde "qué fincas ve esta persona".
- Retirar `fincas.id_usuario`: requiere cambiar el CRUD de fincas y su pantalla.

## Verificación

- `tests/integration/test_inc_m02_61_g52_usuarios_fincas.py` contra PostgreSQL 17.11
  con `alembic upgrade head` desde cero: asignar a un Veterinario una finca ajena da
  `200` y le concede acceso sin quitárselo al propietario; retirarla lo revoca y
  reasignarla reactiva la misma fila; la vista de contexto y el detalle de usuario la
  reflejan; registrar una finca con propietario le concede acceso. Con el código
  anterior fallan la asignación (409) y la revocación; la del propietario falla si se
  quita la concesión de `guardar`.
- Migración probada con datos previos (dueño real, sin dueño, dueño inexistente),
  `downgrade` y nuevo `upgrade`.
