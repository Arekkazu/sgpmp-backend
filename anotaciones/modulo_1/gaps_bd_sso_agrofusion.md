# Gaps de BD — SSO con AgroFusion (Paso 0)

Aplicado en dev el 2026-08-08, vía MCP postgres, previo a escribir código. Referencia de diseño: `anotaciones/modulo_1/plan_sso_agrofusion.md`. No gestionado por migraciones (igual que el resto de gaps de `modulo1`, ver otros archivos `gaps_bd_*` en este directorio).

## 1. Columnas nullable en `modulo1.usuarios`

El payload RS256 del handoff SSO de AgroFusion (Mecanismo A) solo trae `sub` + `email`. `tipo_identificacion`, `numero_identificacion`, `nombre`, `apellidos`, `fecha_nacimiento` y `genero` eran `NOT NULL`, lo cual hacía imposible crear un `Usuario` mínimo sin inventar datos de identidad. Se optó por hacerlas nullable (decisión explícita: no fabricar un número de identificación o género falsos).

```sql
ALTER TABLE modulo1.usuarios
  ALTER COLUMN tipo_identificacion DROP NOT NULL,
  ALTER COLUMN numero_identificacion DROP NOT NULL,
  ALTER COLUMN nombre DROP NOT NULL,
  ALTER COLUMN apellidos DROP NOT NULL,
  ALTER COLUMN fecha_nacimiento DROP NOT NULL,
  ALTER COLUMN genero DROP NOT NULL;
```

Verificado que esto es seguro sin más cambios:
- Los `CHECK` existentes (`chk_usuario_tipo_identificacion`, `chk_usuario_nombre_validos`, `chk_usuario_apellidos_validos`) pasan automáticamente cuando el valor es `NULL` (semántica estándar de Postgres: un `CHECK` solo rechaza cuando la expresión evalúa a `FALSE`, no a `NULL`).
- `uq_usuario_numero_identificacion` (UNIQUE) permite múltiples filas con `NULL` en Postgres (los `NULL` no se consideran iguales entre sí para unicidad) — varias cuentas SSO mínimas pueden coexistir sin choque.

Confirmado en vivo tras aplicar: las 6 columnas quedaron `is_nullable = YES`.

## 2. Nuevo estado de cuenta `PENDIENTE_DATOS`

```sql
INSERT INTO modulo1.estados_cuentas (id_estado_cuenta, nombre)
VALUES (6, 'Pendiente Datos');
```

Resultado confirmado: `id_estado_cuenta=6, nombre='Pendiente Datos'`. Corresponde a `Cuenta.ESTADO_PENDIENTE_DATOS` en `domain/entities/cuenta.py` (código).

## 3. Rol "Externo AgroFusion"

Insertado con **SQL directo**, no vía la API de roles (`POST /roles` usa el stored procedure `sp_crear_rol`, que exige al menos un permiso inicial — ver `domain/repositories/rol_repository.py:35-49` — y la decisión de producto fue que este rol nazca con cero permisos).

```sql
INSERT INTO modulo1.roles (nombre_rol, descripcion, es_protegido)
VALUES ('Externo AgroFusion', 'Cuenta auto-provista vía SSO sin sincronización previa de datos completos', false);
```

Resultado confirmado: **`id_rol = 9`**. Sin filas en `modulo1.permisos` para este rol — verificado que el trigger `trg_fn_validar_permiso_minimo_rol` solo protege contra `DELETE`/`UPDATE` del último permiso activo de un rol existente, no bloquea `INSERT` de un rol nuevo con cero permisos.

Efecto: un usuario con este rol puede autenticarse (login/SSO no pasan por `require_permission`) y acceder a las rutas de perfil propio (tampoco pasan por `require_permission`), pero cualquier otro endpoint RBAC-protegido le devuelve `403` hasta que complete su perfil (pasa a un rol real) o un administrador se lo reasigne.

## 4. Nuevos tipos de evento de auditoría

```sql
INSERT INTO modulo1.tipos_eventos (nombre, accion) VALUES
  ('LOGIN_SSO_EXITOSO', 'Login SSO vía handoff AgroFusion'),
  ('PROVISION_SSO_MINIMA', 'Provisión mínima SSO sin datos completos'),
  ('PROVISION_AGROFUSION_SYNC', 'Provisión usuario vía sync AgroFusion');
```

Nota: la columna `accion` es `varchar(50)`; los textos originales del plan de diseño excedían ese límite y se acortaron.

Resultado confirmado: **`id_tipo_evento = 20, 21, 22`** respectivamente.

Gap operativo encontrado de paso: la secuencia `modulo1.tipos_evento_id_tipo_evento_seq` estaba desincronizada del `MAX(id_tipo_evento)` real de la tabla (`last_value=17` cuando el máximo real era `19` — indica que algunas filas del seed original se insertaron con ID explícito sin pasar por la secuencia). Se corrigió con `setval(..., (SELECT MAX(id_tipo_evento) FROM modulo1.tipos_eventos))` antes de insertar. No se tocó ninguna fila existente.

## 5. Sin cambios en RBAC (`modulo1.recursos` / `modulo1.permisos`)

Ninguno de los endpoints nuevos de este feature (`POST /sesiones/sso`, `/integraciones/agrofusion/*`) usa `require_permission`:
- El primero confía en la verificación de firma RS256 (el usuario aún no tiene sesión sgpmp en ese punto).
- El segundo confía en el secreto compartido `AGROFUSION_HUB_CLIENT_ID`/`SECRET` (quien llama es el Hub de AgroFusion, no un `Usuario` de sgpmp con `id_rol`).

Esto es una decisión de diseño documentada, no un gap pendiente — no buscar un permiso RBAC faltante para estas rutas.

## 6. Trigger de transición de estados (descubierto en verificación end-to-end)

No estaba documentado en el plan original: `modulo1.cuentas_usuarios` tiene un trigger `trg_validar_transicion_estado` (`BEFORE UPDATE OF id_estado_cuenta`) que mantiene su **propia** lista blanca de transiciones válidas en PL/pgSQL, independiente del diccionario `TRANSICIONES_VALIDAS` de la aplicación. Antes de este fix, cualquier `UPDATE` que llevara una cuenta a/desde `Pendiente Datos` (6) fallaba con `INVALID_TRANSITION` (detectado en vivo al probar el flujo SSO real).

Se corrigió agregando `Pendiente Datos → (Activo, Eliminado)` a la lista blanca del trigger:

```sql
CREATE OR REPLACE FUNCTION modulo1.trg_fn_validar_transicion_estado()
 RETURNS trigger LANGUAGE plpgsql AS $function$
DECLARE
    v_estado_origen  VARCHAR(55);
    v_estado_destino VARCHAR(55);
BEGIN
    IF NEW.id_estado_cuenta = OLD.id_estado_cuenta THEN RETURN NEW; END IF;
    SELECT nombre INTO v_estado_origen FROM modulo1.estados_cuentas WHERE id_estado_cuenta = OLD.id_estado_cuenta;
    SELECT nombre INTO v_estado_destino FROM modulo1.estados_cuentas WHERE id_estado_cuenta = NEW.id_estado_cuenta;
    IF v_estado_origen = 'Eliminado' THEN
        RAISE EXCEPTION 'INVALID_TRANSITION: Una cuenta Eliminada no puede cambiar a %.', v_estado_destino USING ERRCODE = 'P0003';
    END IF;
    IF NOT (
        (v_estado_origen = 'Pendiente' AND v_estado_destino IN ('Activo', 'Eliminado'))
        OR (v_estado_origen = 'Activo'    AND v_estado_destino IN ('Pendiente', 'Inactivo', 'Bloqueado', 'Eliminado'))
        OR (v_estado_origen = 'Inactivo'  AND v_estado_destino IN ('Activo', 'Eliminado'))
        OR (v_estado_origen = 'Bloqueado' AND v_estado_destino IN ('Activo', 'Inactivo', 'Eliminado'))
        OR (v_estado_origen = 'Pendiente Datos' AND v_estado_destino IN ('Activo', 'Eliminado'))  -- añadido
    ) THEN
        RAISE EXCEPTION 'INVALID_TRANSITION: Transición no permitida (% → %).', v_estado_origen, v_estado_destino USING ERRCODE = 'P0003';
    END IF;
    NEW.fecha_cambio_estado := now();
    RETURN NEW;
END;
$function$;
```

**No se agregó** `Pendiente → Pendiente Datos` a la lista blanca: en vez de crear la cuenta como `Pendiente` y luego transicionarla (lo que hubiera requerido esa entrada extra), `SsoLoginUseCase` crea la cuenta **directo** en `Pendiente Datos` vía `INSERT` (el trigger solo se dispara en `UPDATE`, no en `INSERT`). Esto requirió que `CuentaRepository.crear()` aceptara un `id_estado_cuenta` inicial opcional (antes hardcodeaba `ESTADO_PENDIENTE`); ver commit de código. `crear_usuario_agrofusion_use_case.py` (Mecanismo B) sigue usando el camino `Pendiente → Activo` sin cambios, porque esa transición ya estaba en la lista blanca original.

## Datos de prueba dejados en dev tras la verificación end-to-end (2026-08-08)

Dos usuarios de prueba quedaron en la base de datos dev tras validar el flujo real (login SSO minimal-provisioning + completar perfil + Mecanismo B `CREATE_USER`/`GET_AUTHORIZATION`/`CHANGE_USER_STATUS`): `sso.nuevo@ejemplo.com` (id_usuario=34) y `m2m.nuevo@ejemplo.com` (id_usuario=35, quedó en estado `Inactivo` tras probar `CHANGE_USER_STATUS`). No se eliminaron porque `modulo1.eventos` es inmutable (triggers bloquean `DELETE` incluso para `postgres`) y esas filas referencian `id_usuario` por FK — no es posible borrar el usuario sin antes poder borrar sus eventos, lo cual el propio diseño de auditoría impide intencionalmente. Quedan identificables por su correo de prueba.

## IDs reales para referencia rápida (código)

| Concepto | Valor |
|---|---|
| `Cuenta.ESTADO_PENDIENTE_DATOS` | `6` |
| Rol "Externo AgroFusion" (`id_rol`) | `9` |
| `LOGIN_SSO_EXITOSO` (`id_tipo_evento`) | `20` |
| `PROVISION_SSO_MINIMA` (`id_tipo_evento`) | `21` |
| `PROVISION_AGROFUSION_SYNC` (`id_tipo_evento`) | `22` |
