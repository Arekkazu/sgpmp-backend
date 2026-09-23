# INC-M02-93-G93 [RF-50][TC-M02-157] — Identidad M06 para consumo de RF-50

**Issue:** [#391](https://github.com/Arekkazu/sgpmp-backend/issues/391)
**Precedente directo:** `anotaciones/modulo_2/inc_m02_90_g92_identidad_m04.md`
(INC-M02-90-G92, identidad equivalente para M04).

## Qué reportó QA

TC-M02-157 exige ejecutar la consulta de `datos-consolidados` usando
específicamente a **M06** como consumidor autenticado con scope de
valoración/NIC-41. El endpoint autentica usuarios humanos vía JWT y autoriza
por rol (RBAC), pero no existía ninguna identidad que representara a M06 —
el escenario oficial no podía ejecutarse sin sustituir la precondición.

## Decisión

**Misma decisión que INC-M02-90-G92 (M04), por la misma razón**: M06 es un
módulo interno de la propia plataforma, no un tercero externo (a diferencia
de AgroFusion, que sí tiene su propio mecanismo M2M dedicado en
`src/shared/agrofusion_auth.py`). Se reutiliza RBAC con un rol técnico
dedicado en vez de construir un segundo mecanismo M2M — la misma
justificación que ya se documentó para M04 aplica aquí sin cambios.

**No se resuelve la parte de "scope por tipo_dato"** que también pide RF-50
para M06 (valoración/NIC-41 específicamente) — esa granularidad no existe
hoy en el modelo RBAC de este proyecto (permiso por (recurso, acción), no
por endpoint ni por parámetro de query), tal como quedó documentado
explícitamente como límite conocido en INC-M02-90-G92. Se aborda en el
siguiente PR de esta cadena (INC-M02-92-G93 / #390), que sí extiende el
modelo con recursos RBAC granulares por `tipo_dato`.

## Qué se creó (aplicado en `sgpmp` y `pruebas`)

```sql
DO $$
DECLARE
  v_id_rol INT;
  v_id_usuario INT;
BEGIN
  IF NOT EXISTS (SELECT 1 FROM modulo1.roles WHERE nombre_rol = 'Integración M06') THEN
    INSERT INTO modulo1.roles (nombre_rol, descripcion, es_protegido)
    VALUES (
      'Integración M06',
      'Identidad tecnica de solo lectura para que el modulo 6 (valoracion / NIC-41) consuma los endpoints analiticos de M02 (RF-50 datos-consolidados). Creado para INC-M02-93-G93.',
      false
    )
    RETURNING id_rol INTO v_id_rol;

    INSERT INTO modulo1.permisos (nombre, descripcion, id_recurso, id_accion, id_rol, es_activo)
    VALUES (
      'm06_leer_activo_biologico',
      'Lectura de datos consolidados de activos biologicos para consumo del modulo 6 / valoracion NIC-41 (RF-50).',
      29, 2, v_id_rol, true
    );

    -- Contraseña aleatoria: nunca se hardcodea un secreto en un script versionado.
    INSERT INTO modulo1.usuarios (nombre, apellidos, correo_electronico, contrasena_cifrada, id_rol)
    VALUES (
      'Integración', 'Módulo Seis', 'integracion.m06.test@pecuaria.co',
      crypt(gen_random_uuid()::text || gen_random_uuid()::text, gen_salt('bf', 12)), v_id_rol
    )
    RETURNING id_usuario INTO v_id_usuario;

    INSERT INTO modulo1.cuentas_usuarios (id_usuario, id_estado_cuenta, tiene_correo_verificado)
    VALUES (v_id_usuario, 2, true);
  END IF;
END $$;
```

Aplicado con `IF NOT EXISTS` (idempotente) contra `sgpmp` vía MCP de postgres
y contra `pruebas` vía `psql` (esta es DML de identidad, no DDL de esquema —
sigue el mismo patrón que INC-M02-90-G92, sin migración de Alembic, ya que no
cambia ninguna tabla).

| Campo | `sgpmp` (dev) | `pruebas` |
|---|---|---|
| `id_rol` | 13 | 189 |
| Correo | `integracion.m06.test@pecuaria.co` | igual |
| Permiso | `m06_leer_activo_biologico` — recurso `activos_biologicos` (29), acción `R` (2) | igual |

El `id_rol` difiere entre bases (autoincremental) — el código nunca lo
hardcodea, así que no importa.

**Contraseña:** aleatoria, nunca escrita en texto plano en ningún archivo,
commit, PR ni comentario (ver nota de seguridad en INC-M02-90-G92, que
documenta el incidente que motivó esta práctica). Quien necesite autenticarse
como esta identidad rota la contraseña vía un canal seguro directo a la base.

## Verificación

No se reconstruye login/JWT/HTTP end-to-end (ya cubierto por las pruebas de
`identity_access`) — se verifica el hecho nuevo directamente contra la base:
el rol existe, no es protegido, tiene el permiso `(29, 2)` activo, y el
usuario técnico tiene cuenta activa y correo verificado (sin esto el login
falla por `RF-02`, aunque el usuario exista).

```
TEST_DATABASE_URL=postgresql://postgres:dev@localhost:5432/pruebas \
  python -m pytest tests/integration/test_inc_m02_93_g93_identidad_m06.py -v
```

## Pendiente — no aplicable desde este entorno

El mismo bloque SQL debe ejecutarse contra el ambiente de **TEST** real que
usa QA (no alcanzable desde este entorno de desarrollo), igual que quedó
pendiente para M04 en INC-M02-90-G92.

## Relación con otros issues de esta cadena

- INC-M02-94-G93 (#392, PR previo de esta cadena): la validación de
  suficiencia de métricas PESO quedó deliberadamente **desacoplada** de esta
  identidad — es válida para cualquier consumidor, no solo M06.
- INC-M02-92-G93 (#390, siguiente PR de esta cadena): extiende RBAC con
  recursos granulares por `tipo_dato` y le asigna a este rol un scope
  limitado (solo métricas, no eventos/fases/estado) — realista para un
  módulo de valoración financiera y, de paso, la precondición que pide QA
  para reproducir el 403 por scope faltante.
