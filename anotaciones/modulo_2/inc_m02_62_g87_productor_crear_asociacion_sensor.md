# INC-M02-62-G87 — Productor no podía asociar sensores a sus propios activos

**RF:** RF-49 (CU11) — Asociar sensor IoT al activo biológico
**Endpoint:** `POST /activos-biologicos/{id_activo}/sensores`

## Causa raíz (confirmada, gap de datos RBAC, no de código)

El RF-49 define al Productor Agropecuario como el actor principal que "solicita
la asociación de sensores a sus activos biológicos y toma decisiones sobre qué
sensores monitorean qué animales o lotes en su finca". El rol Productor
(`id_rol=2`) solo tenía la acción `R` (leer, `id_accion=2`) sobre el recurso
`asociacion_sensor_activo` (`id_recurso=30`) en `modulo1.permisos` — nunca `C`
(crear, `id_accion=1`), que es lo que exige `require_permission(30, 1)` en el
router (`activo_biologico_router.py`, endpoint `asociar_sensor_iot`).

Confirmado contra la base real antes de tocar nada:

```sql
SELECT p.nombre, r.nombre_rol, a.codigo FROM modulo1.permisos p
JOIN modulo1.roles r ON r.id_rol = p.id_rol
JOIN modulo1.acciones a ON a.id_accion = p.id_accion
WHERE p.id_recurso = 30;
-- Productor: solo prod_leer_asociacion_sensor_activo (R). Sin fila de C.
```

## Fix — solo datos, sin cambio de código de aplicación

Insertado en `sgpmp` (dev) y `pruebas` (test), mismo patrón "Paso 0" usado en
toda esta cadena de issues:

```sql
INSERT INTO modulo1.permisos (nombre, descripcion, id_recurso, id_accion, id_rol, es_activo)
VALUES (
    'prod_crear_asociacion_sensor_activo',
    'Permite al Productor asociar sensores IoT a sus propios activos biologicos (RF-49/CU11).',
    30, 1, 2, true
);
```

Nombre del permiso sigue la convención `{rol}_{accion}_{recurso_singular}` ya
usada en el resto del proyecto (`prod_crear_asociacion_sensor_activo`, igual
patrón que `admin_crear_asociacion_sensor_activo` / `ing_crear_asociacion_sensor_activo`
ya existentes para Administrador e Ingeniero de Campo).

## Advertencia explícita — alcance por finca sigue sin validarse aquí

**Este fix NO cierra ningún riesgo de alcance por finca.** El router
(`asociar_sensor_iot`) llama `use_case.execute(id_activo, dto, usuario_actual)`
sin pasar ninguna lista de fincas permitidas, y `AsociarSensorActivoUseCase`
resuelve el activo con `obtener_por_id(id_activo)` sin filtro de alcance —
exactamente el mismo patrón de gap que INC-M02-71-G48 (#221, esta misma cadena)
ya identificó y documentó como sistémico en casi todos los use cases de
escritura de este módulo, incluyendo explícitamente `asociar_sensor_activo`.

Antes de este fix, esto era irrelevante porque el Productor no podía llegar
siquiera al use case (403 en el RBAC). **Después de este fix, el Productor SÍ
puede crear una asociación sensor-activo sobre un activo de CUALQUIER finca**,
no solo la suya — el RF-49 exige lo contrario ("sus propios activos
biológicos"). Esto no se corrige en este ticket porque:

1. El alcance de INC-M02-62-G87 según el propio reporte de QA es puntualmente
   el permiso RBAC faltante, no el alcance por finca.
2. El fix sistémico de alcance por finca en escritura ya está identificado
   como trabajo de auditoría separado (ver
   `anotaciones/modulo_2/inc_m02_71_g48_alcance_finca_crecimiento.md`), y
   mezclarlo aquí duplicaría ese esfuerzo en vez de resolverlo una sola vez
   para los ~10 use cases afectados.

**Se deja como hallazgo explícito para dicha auditoría, no como gap oculto.**

## Pruebas

`tests/integration/test_rbac_inc_m02_62_g87.py` (nuevo, requiere
`TEST_DATABASE_URL` apuntando a `pruebas`): verifica que el Productor ya no
recibe 401/403 al llamar el endpoint (RBAC pasa; el use case falla aguas abajo
por `id_activo`/`sensor_id` inexistentes, resultado irrelevante para esta
prueba), y que el Veterinario —que nunca tuvo `C` sobre este recurso— sigue en
403 como control negativo. Suite de integración completa: 164 passed, 7
fallos preexistentes sin relación (ya caracterizados en
`inc_m02_72_g80_compatibilidad_tipo_infraestructura.md`, RBAC de
`/configuracion/tipos-area` y dos casos de M01).

Suite unitaria de `tests/biological_assets/`: 102 passed, sin regresiones (no
se tocó código de aplicación).
