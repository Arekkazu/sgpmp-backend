# Bloqueo Técnico por RBAC — Caso TC-M02-G89 (RF-49 CU11)

**Fecha de Identificación:** 2026-09-19  
**Módulo:** 2 — Activos Biológicos  
**Requisito Funcional:** RF-49 (CU11 — Ciclo de Vida de Asociaciones IoT)  
**Subcasos Bloqueados:** TC-M02-216, TC-M02-218, TC-M02-219  
**Subcaso Operativo:** TC-M02-217 (Superación automática vía `POST`)  

---

## 1. Causa Raíz del Bloqueo
El endpoint `PATCH /activos-biologicos/{id_activo}/sensores/{id_asociacion}` implementado en el backend está protegido por:
```python
dependencies=[Depends(require_permission_m02(_RECURSO_SENSOR, 3, rf_origen='RF49'))]
```
Donde:
- `_RECURSO_SENSOR = 30` (`asociacion_sensor_activo`)
- Acción `3` = `U` (Actualizar / UPDATE)

En la base de datos `sgpmp_test`, la tabla `modulo1.permisos` **NO CONTIENE** la tupla de permiso con `id_accion = 3` sobre `id_recurso = 30` para ningún rol:
- Permisos actuales en `id_recurso = 30`:
  `[(1, 30, 1), (1, 30, 2), (4, 30, 1), (4, 30, 2), (2, 30, 2), (3, 30, 2), (2, 30, 1)]`
- La migración `1d7d6069da52` (PR #286) otorgó únicamente `(id_rol=2, id_recurso=30, id_accion=1)` (Crear para Productor), pero omitió la acción `3` (Actualizar) tanto para Administrador (`id_rol=1`) como para Productor (`id_rol=2`).

Como consecuencia, toda solicitud `PATCH` realizada por el Administrador (o Productor) es rechazada con:
```json
HTTP 403 Forbidden
{
  "error_code": "ACCESO_DENEGADO",
  "message": "Acceso denegado. Su rol no tiene permisos para realizar esta operación."
}
```

---

## 2. Solución Requerida
El equipo de Backend / DBA debe aplicar una migración Alembic que inserte los permisos requeridos:
```sql
INSERT INTO modulo1.permisos (nombre, descripcion, id_rol, id_recurso, id_accion, es_activo)
VALUES 
  ('admin_actualizar_asociacion_sensor', 'Permite al Administrador cambiar estado de asociaciones sensor-activo', 1, 30, 3, TRUE),
  ('prod_actualizar_asociacion_sensor', 'Permite al Productor cambiar estado de asociaciones sensor-activo', 2, 30, 3, TRUE)
ON CONFLICT (id_rol, id_recurso, id_accion) DO UPDATE SET es_activo = TRUE;
```

---

## 3. Estado de la Suite
El caso **TC-M02-G89** se declara **BLOQUEADO** (Veredicto consolidado: **Rechazado**). No es ejecutable limpiamente en V3 hasta que se aplique la migración anterior.
