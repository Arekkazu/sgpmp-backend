# CU04 — Gaps BD y RBAC (RF-38, RF-44)

## Fecha de análisis
2026-06-28

## Tablas verificadas

### modulo2.historicos_estados_activos
Estado: **EXISTE** — no se requieren DDL adicionales.

Columnas confirmadas:
- id_historico_estado_activo (integer, PK)
- id_activo_biologico (integer, NOT NULL, FK → activos_biologicos)
- id_estado_nuevo (integer, NOT NULL, FK → estados_activos_biologicos)
- id_estado_anterior (integer, NOT NULL, FK → estados_activos_biologicos)
- fecha_cambio (timestamp with time zone, NOT NULL)
- motivo_cambio (text, nullable)
- modulo_origen (varchar, NOT NULL)
- id_usuario (integer, NOT NULL, FK → modulo1.usuarios)

CHECKs relevantes:
- `chk_historico_estado_cambio_real`: id_estado_nuevo != id_estado_anterior
- `chk_historico_modulo_origen_valido`: modulo_origen IN ('MANUAL', 'RF-38', 'RF-45', 'modulo1'..'modulo9')

**Decisión de diseño (actualizada — RF-44 centralización + hallazgo transversal #2)**: el
cambio de estado se centraliza en `aplicar_cambio_estado`, y cada flujo graba su origen real:
`MANUAL` (RF-44), `RF-38` (cierre de ciclo) y `RF-45` (baja). Para ello la migración
`f19e0ca62445` amplía el CHECK `chk_historico_modulo_origen_valido` para aceptar esos tres
literales; se conservan `modulo1`..`modulo9` porque otros módulos (p. ej. supplies/modulo5,
RF-76) escriben su identificador en la misma tabla y por compatibilidad con filas históricas.

### modulo2.asociaciones_activos_sensores
Estado: **EXISTE** — no se requieren DDL adicionales.

Campo `fecha_fin` es NOT NULL con CHECK `fecha_inicio < fecha_fin`.
Un sensor es "activo" cuando `fecha_fin > NOW()`.

### modulo2.estados_activos_biologicos
Catálogo confirmado: 6 estados (id 1-6: ACTIVO, INACTIVO, EN_TRATAMIENTO, AISLADO, CERRADO, BAJA).

## RBAC — Permisos insertados

```sql
-- RF-44 (E=5 sobre recurso 29): Veterinario no tenía Ejecutar
INSERT INTO modulo1.permisos (id_rol, id_recurso, id_accion, nombre, es_activo)
VALUES (3, 29, 5, 'vet_ejecutar_activo_biologico', true);  -- id_permiso: 177

-- RF-38 (D=4 sobre recurso 29): ningún rol tenía Desactivar
INSERT INTO modulo1.permisos (id_rol, id_recurso, id_accion, nombre, es_activo) VALUES
(1, 29, 4, 'admin_desactivar_activo_biologico', true),   -- id_permiso: 178
(2, 29, 4, 'prod_desactivar_activo_biologico', true),    -- id_permiso: 179
(3, 29, 4, 'vet_desactivar_activo_biologico', true);     -- id_permiso: 180
```

Estado posterior: Ingenieros (id_rol=4) NO tienen D=4 — el RF-38 no los lista como actores.
