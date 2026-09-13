# INC-M02-90-G92 — Definir identidad M04 para consumo de endpoints analíticos en TEST

> **Nota de seguridad:** una versión anterior de este documento (y del PR/comentario de
> issue asociados) incluyó la contraseña de la identidad de prueba en texto plano en
> un repositorio público. Se rotó de inmediato al detectarlo — esa contraseña ya no es
> válida — y se removió de aquí. La contraseña vigente nunca se escribe en git.

**RF:** RF-50/RF-51 — Endpoints analíticos (`datos-consolidados`, `indicadores`)
**Naturaleza:** no es un defecto funcional del producto (así lo indica el propio reporte de QA).
El bloqueo era de datos: no existía ninguna identidad con la que el módulo 4 (o QA
simulándolo) pudiera autenticarse contra estos endpoints en un ambiente de pruebas.

## Decisión

No se construyó ningún mecanismo de autenticación nuevo. El backend ya resuelve
"otro sistema que necesita autenticarse sin ser un usuario humano" con dos
patrones existentes:

1. **M2M con credenciales dedicadas** (`src/shared/agrofusion_auth.py` +
   `emitir_token_agrofusion_use_case.py`): pensado para el Hub externo AgroFusion,
   con su propio contrato y rol `Externo AgroFusion` (`id_rol=9`).
2. **Usuario técnico con rol dedicado + permisos RBAC de solo lectura**: patrón ya
   usado para necesidades equivalentes de este mismo módulo (`Gestor de Granja`
   `id_rol=7`, `Revisor Fiscal` `id_rol=8`, ambos de RF-81, con usuarios
   `*.test@pecuaria.co`).

M04 es un módulo interno de la propia plataforma (no un tercero externo como
AgroFusion), así que se optó por el patrón (2): reutilizar RBAC en vez de construir
un segundo mecanismo M2M. Construir uno nuevo para este caso habría sido resolver
con código un problema que es puramente de datos.

## Qué se creó (aplicado en `sgpmp`, dev)

```sql
-- Rol dedicado
INSERT INTO modulo1.roles (nombre_rol, descripcion, es_protegido)
VALUES ('Integración M04', '...', false);
-- id_rol = 12

-- Permiso: solo lectura (accion=2) sobre el recurso de activos biológicos (id_recurso=29),
-- el mismo recurso que protege tanto /indicadores como /datos-consolidados.
INSERT INTO modulo1.permisos (nombre, descripcion, id_recurso, id_accion, id_rol, es_activo)
VALUES ('m04_leer_activo_biologico', '...', 29, 2, 12, true);

-- Usuario técnico. La contraseña se genera aleatoriamente y nunca se escribe
-- en texto plano en ningún archivo, commit, PR ni comentario -- quien necesite
-- autenticarse como esta identidad la rota por un canal seguro (ver nota abajo).
INSERT INTO modulo1.usuarios (nombre, apellidos, correo_electronico, contrasena_cifrada, id_rol)
VALUES (
    'Integración', 'Módulo Cuatro', 'integracion.m04.test@pecuaria.co',
    crypt(gen_random_uuid()::text || gen_random_uuid()::text, gen_salt('bf', 12)), 12
);

-- Cuenta activa y verificada (sin esto el login falla: verificar_estado_cuenta
-- espera una fila en cuentas_usuarios, un INSERT de usuario solo no basta)
INSERT INTO modulo1.cuentas_usuarios (id_usuario, id_estado_cuenta, tiene_correo_verificado)
VALUES (<id_usuario nuevo>, 2, true);
```

**Identidad M04 (ambiente de pruebas únicamente, nunca usar en producción):**

| Campo | Valor |
|---|---|
| Correo | `integracion.m04.test@pecuaria.co` |
| Contraseña | rotada por un administrador vía canal seguro — nunca se escribe en el repositorio (este es público) |
| Rol | `Integración M04` (`id_rol=12` en `sgpmp`) |
| Permiso | `m04_leer_activo_biologico` — recurso `activos_biologicos` (29), acción `R` (2) |

Para obtener acceso, un administrador con acceso directo a la base `sgpmp` rota la
contraseña de este usuario (`UPDATE modulo1.usuarios SET contrasena_cifrada = crypt(...)`)
y la comunica por un canal seguro (nunca por git, PR o comentario de issue).
Login: `POST /sesiones/` con esas credenciales devuelve un `token` (JWT, 8h) que se
usa como `Authorization: Bearer <token>` contra cualquier endpoint de este módulo.

**Nota sobre alcance de la RBAC de este proyecto:** el permiso es por
(recurso, acción), no por endpoint individual — así funciona toda la RBAC del
sistema, no es una limitación introducida aquí. Esto significa que la identidad
M04 también puede leer `GET /activos-biologicos/` y `GET /activos-biologicos/{id}`
(mismo recurso/acción), no solo los dos endpoints analíticos. Acotar esto a
endpoints específicos requeriría rediseñar el modelo RBAC completo — fuera de
alcance de este issue puntual. Verificado con prueba de humo end-to-end (login +
lectura de `/indicadores` y `/datos-consolidados` + rechazo 403 en escritura)
antes de eliminarla; no se deja como test permanente porque no cubre lógica de
aplicación nueva, solo datos semilla.

## Pendiente — no aplicable desde este entorno

Este mismo bloque SQL (idempotente, con guarda `NOT EXISTS`) debe ejecutarse
también contra la base del ambiente de **TEST** real que usa QA. No se aplicó
aquí porque esa base no es alcanzable desde este entorno de desarrollo; quien
tenga acceso a `TEST_DATABASE_URL` de ese ambiente debe correrlo:

```sql
DO $$
DECLARE
  v_id_rol INT;
  v_id_usuario INT;
BEGIN
  IF NOT EXISTS (SELECT 1 FROM modulo1.roles WHERE nombre_rol = 'Integración M04') THEN
    INSERT INTO modulo1.roles (nombre_rol, descripcion, es_protegido)
    VALUES (
      'Integración M04',
      'Identidad tecnica de solo lectura para que el modulo 4 (analitica/prediccion) consuma los endpoints analiticos de M02 (RF-50 datos-consolidados, RF-51 indicadores). Creado para INC-M02-90-G92.',
      false
    )
    RETURNING id_rol INTO v_id_rol;

    INSERT INTO modulo1.permisos (nombre, descripcion, id_recurso, id_accion, id_rol, es_activo)
    VALUES (
      'm04_leer_activo_biologico',
      'Lectura de indicadores y datos consolidados de activos biologicos para consumo del modulo 4 (RF-50/RF-51).',
      29, 2, v_id_rol, true
    );

    -- Contraseña aleatoria: nunca se hardcodea un secreto en un script versionado.
    -- Quien aplique este bloque rota la contraseña real después, por canal seguro.
    INSERT INTO modulo1.usuarios (nombre, apellidos, correo_electronico, contrasena_cifrada, id_rol)
    VALUES (
      'Integración', 'Módulo Cuatro', 'integracion.m04.test@pecuaria.co',
      crypt(gen_random_uuid()::text || gen_random_uuid()::text, gen_salt('bf', 12)), v_id_rol
    )
    RETURNING id_usuario INTO v_id_usuario;

    INSERT INTO modulo1.cuentas_usuarios (id_usuario, id_estado_cuenta, tiene_correo_verificado)
    VALUES (v_id_usuario, 2, true);
  END IF;
END $$;
```

Requiere la extensión `pgcrypto` (ya está presente en `sgpmp`; verificar en el
ambiente destino con `SELECT * FROM pg_extension WHERE extname='pgcrypto'`) y que
`id_estado_cuenta=2` siga significando "activa" en ese ambiente (es el mismo valor
usado hoy por los usuarios de prueba `gestor.granja.test@pecuaria.co` e
`id_estado_cuenta` análogos).

## Relación con otros issues de esta cadena

`INC-M02-96-G94` (rate limiting de `datos-consolidados`, PR previo de esta misma
cadena) dejó pendiente el aislamiento del límite por-módulo en vez de por-usuario,
bloqueado exactamente por la falta de esta identidad. Con `id_rol=12` /
`m04_leer_activo_biologico` ya existente, ese aislamiento por-módulo queda
desbloqueado como trabajo futuro (no se retoma en este PR — cambiar la clave del
limitador de `id_usuario` a `id_rol`/`id_usuario` de M04 es una decisión de diseño
del rate limiter compartido, usado por otros módulos, y excede el alcance de esta
identidad puntual).
