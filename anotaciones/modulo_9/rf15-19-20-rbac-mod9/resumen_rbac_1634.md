# Resumen — Ajuste de RBAC RF-15/19/20 (issue #1634)

Fecha: 2026-08-22
Rama: `feature/rf15-19-20-rbac-mod9`

## Problema

El RBAC dinámico de módulo 9 concedía permisos más amplios que el texto literal de los RF
(hallazgo transversal #5 de `estado_M09.md`). Como los routers de M09 solo verifican
`require_permission(id_recurso, id_accion)` y el mapeo rol→permiso vive en `modulo1.permisos`,
esto es un ajuste de datos + documentación, sin cambios en `src/`.

## Desviaciones y decisión del equipo de análisis

| RF | Recurso (id) | Desviación | Decisión |
|----|-------------|-----------|----------|
| RF-15 | especies (8) | Veterinario (rol 3) con **U** (`vet_actualizar_especie`, id_permiso=48) | **Revocar** — es escritura y contradice los actores del RF |
| RF-19 | fincas (9) | Vet + Ing. de Campo con **R** | **Mantener** — decisión de diseño RBAC dinámico (solo lectura, operativamente defendible) |
| RF-20 | infraestructuras (10) | Vet + Ing. de Campo con **R** | **Mantener** — igual que RF-19 |

## Cambio aplicado en DB

Solo una fila revocada (soft-delete vía `es_activo`):

```sql
UPDATE modulo1.permisos
SET es_activo = false
WHERE id_recurso = 8 AND id_accion = 3 AND id_rol = 3;  -- id_permiso = 48
```

Aplicado en `sgpmp` (dev, vía MCP postgres) y en `pruebas` (vía `TEST_DATABASE_URL`, ya que
el MCP no alcanza esa base). No versionado por migraciones, igual que el resto de la RBAC de
M09. Las `R` de Vet/Ing sobre fincas(9) e infraestructuras(10) **no se tocaron**.

## Prueba de integración (guardián de regresión)

`tests/integration/test_rbac_mod9_1634.py` — 3 casos que verifican la **compuerta RBAC**
(`require_permission`), lo único que cambió el issue:

1. `test_veterinario_no_edita_especie` — vet `PATCH /configuracion/especies/1` → `403 ACCESO_DENEGADO`.
2. `test_ingeniero_campo_conserva_edicion_especie` — ing `PATCH` → no 401/403 (no se revocó de más).
3. `test_veterinario_conserva_lectura_fincas` — vet `GET /configuracion/fincas` → no 401/403 (R mantenida).

La base `pruebas` solo tiene esquema `modulo1`, así que las pruebas asertan la decisión de
permisos (403 vs. no-403), no la query de negocio de modulo9. Requieren el `UPDATE` aplicado
en `pruebas`. Fixture local monta solo los routers de config (no toca el conftest compartido).

Ejecución:

```bash
export TEST_DATABASE_URL="postgresql://USUARIO:CONTRASENA@localhost:5432/pruebas"
.venv/bin/python -m pytest tests/integration/test_rbac_mod9_1634.py -m integration -q
```

## Verificación (ejecutada 2026-08-22)

- `SELECT ... WHERE id_recurso=8 AND id_accion=3 AND id_rol=3;` → `es_activo = false` (dev y pruebas).
- Las `R` de Vet/Ing en recursos 9 y 10 siguen `es_activo = true` (dev y pruebas).
- `pytest tests/integration/test_rbac_mod9_1634.py` → **3 passed**.
- `pytest tests/integration` → **30 passed** (sin regresiones).

## Docs actualizadas

- `estado_M09.md` — RF-15, RF-19, RF-20 y hallazgo transversal #5 marcados como resueltos.
- `inconsistencias_permisos_m09.md` — inconsistencia 1 marcada como revocada.
