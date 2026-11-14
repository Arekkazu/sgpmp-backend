-- =============================================================================
-- SCRIPT DE AUDITORÍA Y FUTURA LIMPIEZA: TC-M02-G87 (RF-49 CU11)
-- Ubicación: evidencias/v3-run-20260919/audit_cleanup_tc_m02_g87.sql
-- Fecha: 2026-09-19
-- 
-- ADVERTENCIA DE SEGURIDAD QA:
-- Este script es de carcter DOCUMENTAL Y DE AUDITORÍA.
-- NO EJECUTAR DIRECTAMENTE contra la base de datos sin autorización previa del DBA.
-- La desactivación normal vía API (PATCH /activos-biologicos/{id}/sensores/{asoc_id})
-- quedó bloqueada con HTTP 403 debido al gap RBAC de UPDATE (acción 3, recurso 30).
-- =============================================================================

-- 1. CONSULTA DE AUDITORÍA: Identificación de asociaciones huérfanas creadas por TC-M02-G87
SELECT 
    id_asociacion_activo_sensor,
    id_activo_biologico,
    id_sensor,
    estado_asociacion,
    motivo,
    fecha_inicio,
    fecha_fin
FROM modulo2.asociaciones_activos_sensores
WHERE id_asociacion_activo_sensor IN (66, 67, 68, 71)
ORDER BY id_asociacion_activo_sensor;

-- 2. SENTENCIA DE LIMPIEZA DEFENSIVA (SOFT-DELETE / DESACTIVACIÓN LÓGICA APPEND-ONLY):
-- Cuando el equipo de infraestructura/DBA autorice la limpieza manual, ejecutar:
/*
UPDATE modulo2.asociaciones_activos_sensores
SET 
    estado_asociacion = 'INACTIVA',
    fecha_fin = CURRENT_TIMESTAMP,
    motivo = motivo || ' | [CLEANUP MANUAL AUDITORIA V3 TC-M02-G87]'
WHERE id_asociacion_activo_sensor IN (66, 67, 68, 71)
  AND estado_asociacion = 'ACTIVA';
*/

-- 3. VERIFICACIÓN POST-LIMPIEZA:
/*
SELECT id_asociacion_activo_sensor, id_sensor, estado_asociacion, fecha_fin
FROM modulo2.asociaciones_activos_sensores
WHERE id_asociacion_activo_sensor IN (66, 67, 68, 71);
*/
