# CU07 — Gaps BD y RBAC: RF-41

Fecha de análisis: 2026-06-29

---

## Gap BD: ninguno

La tabla `modulo2.eventos_sanitarios` ya contiene todos los campos requeridos por RF-41:

```sql
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_schema = 'modulo2' AND table_name = 'eventos_sanitarios'
ORDER BY ordinal_position;
-- id_evento, diagnostico, medicamento, dosis, unidad_dosis, frecuencia, tipo (enum), duracion, observaciones
```

Los CHECK constraints por tipo también existen (`check_tratamiento`, `check_vacunacion`, `check_diagnostico`, `check_control`). No se aplicó ningún DDL.

El enum PG `enum_evento_sanitario_tipo` contiene: `VACUNACION`, `TRATAMIENTO`, `DIAGNOSTICO`, `CONTROL_PREVENTIVO`. Mapeado como `String(30)` en el ORM conforme al patrón del proyecto.

---

## Gap RBAC: ninguno

El recurso 29 (`activos_biologicos`) ya tiene acción C para los roles requeridos por RF-41:

| id_permiso | rol              | accion |
|------------|------------------|--------|
| 163        | Administrador    | C      |
| 165        | Productor        | C      |
| 176        | Veterinario      | C      |
| 167        | Ingeniero de Campo | C    |

No se insertaron nuevas filas en `modulo1.permisos`.

---

## Limitación conocida: restricción Veterinario-solo para DIAGNOSTICO

El CU07 establece: "El Veterinario es el único actor autorizado para registrar diagnósticos; el Productor puede registrar únicamente observaciones de salud no diagnósticas."

Esta restricción **no está implementada** en la versión actual porque no puede expresarse en el RBAC de un único endpoint sin hardcodear el id de rol en el use case (violación de CLAUDE.md).

**Deuda técnica**: para implementarla correctamente crear:
1. Recurso 30 `evento_sanitario_diagnostico` en `modulo1.recursos`
2. Permisos C sobre recurso 30 solo para Administrador (id_rol=1) y Veterinario (id_rol=3)
3. Endpoint separado `POST /{id}/eventos/sanitario/diagnostico` con `require_permission(30, 1)`

Por ahora el endpoint único acepta DIAGNOSTICO de cualquier rol con permiso C sobre recurso 29.
