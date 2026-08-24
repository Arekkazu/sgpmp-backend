# Inconsistencias entre RF-15 y tabla `modulo1.permisos` — M09 Especies

Fecha detectada: 2026-06-13

## Contexto

Al implementar CU01 (Gestionar Catálogo de Especies Productivas) se compararon los
permisos registrados en `modulo1.permisos` para el recurso `especies` (`id_recurso = 8`)
contra lo que establece el documento RF-15.

---

## Inconsistencia 1 — Veterinario tiene permiso U (Actualizar) sobre especies

**Lo que dice la DB:**

| permiso | nombre_permiso | rol | accion |
|---------|---------------|-----|--------|
| 48 | `vet_actualizar_especie` | Veterinario (id_rol=3) | U (id_accion=3) |

**Lo que dice RF-15:**

Solo el **Administrador** y el **Ingeniero de Campo** pueden editar especies.
El Veterinario no aparece como actor del CU01 para ninguna operación de escritura.

**Decisión — RESUELTA (2026-08-22, issue #1634): REVOCADA.** El equipo de análisis confirmó
que el Veterinario **no debe** poder editar especies. Se aplicó:

```sql
UPDATE modulo1.permisos
SET es_activo = false
WHERE id_recurso = 8 AND id_accion = 3 AND id_rol = 3;  -- id_permiso = 48
```

El Veterinario ahora recibe `403` al intentar `PATCH /configuracion/especies/{id}`. Ver
`rf15-19-20-rbac-mod9/resumen_rbac_1634.md`.

---

## Inconsistencia 2 — Faltaba permiso D (Eliminar/Desactivar) para Admin

**Situación original:** No existía ningún registro en `modulo1.permisos` para la acción
`D` (`id_accion=4`) sobre el recurso `especies`.

**Resolución:** Insertado el 2026-06-13 durante la implementación de CU01:

```sql
INSERT INTO modulo1.permisos (nombre, descripcion, id_recurso, id_accion, id_rol, es_activo)
VALUES ('admin_eliminar_especie', 'Desactivar y reactivar especies del catálogo productivo', 8, 4, 1, true);
-- Resultado: id_permiso = 78
```

Este permiso cubre los flujos C (desactivar) y D (reactivar) de RF-15, ambos exclusivos
del Administrador.

---

## Estado final de permisos para recurso `especies` (id_recurso=8)

| id_permiso | nombre | accion | rol |
|------------|--------|--------|-----|
| 34 | admin_crear_especie | C | Administrador |
| 35 | admin_leer_especie | R | Administrador |
| 43 | prod_leer_especie | R | Productor |
| 47 | vet_leer_especie | R | Veterinario |
| 55 | ing_leer_especie | R | Ingeniero de Campo |
| 67 | cont_leer_especie | R | Contador |
| 36 | admin_actualizar_especie | U | Administrador |
| 48 | vet_actualizar_especie | U | Veterinario ❌ revocado (es_activo=false, issue #1634) |
| 56 | ing_actualizar_especie | U | Ingeniero de Campo |
| 78 | admin_eliminar_especie | D | Administrador ✓ insertado en CU01 |
