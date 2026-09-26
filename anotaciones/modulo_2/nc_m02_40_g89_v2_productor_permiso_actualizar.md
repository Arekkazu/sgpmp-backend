# NC-M02-40-G89 v2.0 (issue #352) — PATCH sigue en 403 para Productor

**RF:** RF-49 (CU11) — ciclo de vida de asociaciones sensor-activo
**Endpoint:** `PATCH /activos-biologicos/{id_activo}/sensores/{id_asociacion}`

## Contexto

El issue reporta que ninguna de las 3 transiciones formales (`ACTIVA→INACTIVA`,
`INACTIVA→ACTIVA`, rechazo hacia `SUPERADA`) es ejecutable en TEST, probando con
Administrador e Ingeniero de Campo.

## Causa raíz

A la fecha de esta re-evaluación (2026-09-17), Administrador (`id_rol=1`) e
Ingeniero de Campo (`id_rol=4`) **ya tienen** la acción `U` (`id_accion=3`)
sobre el recurso 30 (`asociacion_sensor_activo`) — se agregó el 2026-09-12 al
resolver INC-M02-65-G89 (ver `inc_m02_65_g89_patch_ciclo_vida_asociacion_sensor.md`).
Verificado en vivo contra `sgpmp` y `pruebas`: ambas bases tienen las filas
348/465 (admin) y 349/466 (ingeniero).

El gap que seguía vivo — y es el que realmente bloquea el CU11 hoy — es
**Productor** (`id_rol=2`): tiene `C` (agregada el mismo día, INC-M02-62-G87 /
issue #212, 14 minutos después del fix de arriba) y `R`, pero nunca se le dio
`U`. El propio doc de INC-M02-65-G89 dejó esto anotado y explícitamente sin
decidir ("Nota para #212 ... no se decidió en este PR para no invadir el
alcance de #212"). Productor es el actor principal de RF-49 ("Toma decisiones
sobre qué sensores monitorean qué animales... en su finca"), así que puede
crear una asociación vía `POST` pero no puede desactivarla/reactivarla vía
`PATCH` — asimetría de CRUD sobre el mismo recurso que gestiona.

No es un bug de código: `require_permission_m02`/`tiene_permiso`
(`src/shared/rbac.py`) consultan exactamente `(id_rol, id_recurso=30,
id_accion=3, es_activo=true)`, correcto. Es un gap de dato RBAC (Paso 0),
mismo patrón que INC-M02-65-G89 e INC-M02-62-G87.

## Fix

```sql
INSERT INTO modulo1.permisos (id_rol, id_recurso, id_accion, nombre, es_activo, fecha_creacion)
VALUES (2, 30, 3, 'prod_actualizar_asociacion_sensor_activo', true, now());
```

Aplicado en `sgpmp` (id_permiso=357) y `pruebas` (id_permiso=535).

**Pendiente fuera de este repo:** el ambiente TEST de QA es una base distinta
a `sgpmp`/`pruebas` (no accesible desde este checkout) — el mismo INSERT debe
aplicarse ahí para que la re-evaluación de QA vea el fix.

## Estado final de permisos sobre recurso 30 (`asociacion_sensor_activo`)

| id_rol | rol | C | R | U |
|---|---|---|---|---|
| 1 | Administrador | ✅ | ✅ | ✅ |
| 2 | Productor | ✅ | ✅ | ✅ (este fix) |
| 3 | Veterinario | ❌ | ✅ | ❌ (solo consulta, por diseño — actor "de Consulta") |
| 4 | Ingeniero de Campo | ✅ | ✅ | ✅ |
