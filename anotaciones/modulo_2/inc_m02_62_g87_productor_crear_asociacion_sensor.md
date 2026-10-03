# INC-M02-37-G87 v2.0 — Productor no podía asociar sensores a sus propios activos

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

## Fix persistente — migración Alembic v5.3.0

La corrección deja de depender de un `INSERT` manual y se versiona en
`1d7d6069da52_v5_3_0_rf49_permiso_productor_.py`. La migración valida los
catálogos esperados y hace un upsert idempotente del permiso:

```sql
INSERT INTO modulo1.permisos (nombre, descripcion, id_rol, id_recurso, id_accion, es_activo)
VALUES (
    'prod_crear_asociacion_sensor_activo',
    'Permite al Productor asociar sensores IoT a activos e infraestructuras de sus propias fincas (RF-49).',
    2, 30, 1, true
)
ON CONFLICT (id_rol, id_recurso, id_accion)
DO UPDATE SET nombre = EXCLUDED.nombre,
              descripcion = EXCLUDED.descripcion,
              es_activo = true;
```

Nombre del permiso sigue la convención `{rol}_{accion}_{recurso_singular}` ya
usada en el resto del proyecto (`prod_crear_asociacion_sensor_activo`, igual
patrón que `admin_crear_asociacion_sensor_activo` / `ing_crear_asociacion_sensor_activo`
ya existentes para Administrador e Ingeniero de Campo).

## Alcance por finca cerrado junto con la habilitación

Conceder `C` hacía alcanzable una vulnerabilidad latente: el POST resolvía el
activo sin filtrar las fincas del usuario. Ahora el router obtiene el alcance
con `AlcanceFincaAdapter` y `AsociarSensorActivoUseCase` lo entrega a
`obtener_por_id`. Un activo ajeno se enmascara como `ACTIVO_NO_ENCONTRADO`
(422), sin revelar su existencia.

El mismo permiso protege el POST de asociación ambiental por infraestructura.
Por eso `AsociarSensorInfraestructuraUseCase` también valida que la
infraestructura objetivo pertenezca al alcance del Productor y responde
`INFRAESTRUCTURA_NO_ENCONTRADA` (422) cuando es ajena. Los roles que ya tenían
CREATE antes de esta corrección conservan su alcance operativo existente.

## Pruebas

`tests/integration/test_rbac_inc_m02_62_g87.py` verifica que el Productor ya no
recibe 401/403 al llamar el endpoint (RBAC pasa; el use case falla aguas abajo
por `id_activo`/`sensor_id` inexistentes, resultado irrelevante para esta
prueba), y que el Veterinario —que nunca tuvo `C` sobre este recurso— sigue en
403 como control negativo. Las pruebas unitarias nuevas cubren el rechazo de
activos e infraestructuras fuera de alcance y preservan el acceso global.
