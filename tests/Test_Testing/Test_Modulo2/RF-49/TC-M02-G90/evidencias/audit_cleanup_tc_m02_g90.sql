-- =============================================================================
-- SCRIPT DE AUDITORÍA Y FUTURA LIMPIEZA: TC-M02-G90 (RF-49 CU11)
-- Ubicación: evidencias/audit_cleanup_tc_m02_g90.sql
-- Fecha: 2026-09-19
-- 
-- ADVERTENCIA DE SEGURIDAD QA:
-- Este script es de carácter DOCUMENTAL Y DE AUDITORÍA.
-- NO EJECUTAR DIRECTAMENTE contra la base de datos sin autorización previa del DBA.
-- La desactivación normal vía API (PATCH /activos-biologicos/{id}/sensores/{asoc_id})
-- quedó bloqueada con HTTP 403 debido al gap RBAC de UPDATE (acción 3, recurso 30).
-- =============================================================================

-- 1. CONSULTA DE AUDITORÍA: Identificación de asociaciones creadas por preflight y corridas V3 TC-M02-G90
SELECT 
    id_asociacion_activo_sensor,
    id_activo_biologico,
    id_sensor,
    tipo,
    id_infraestructura,
    estado_asociacion,
    motivo,
    fecha_inicio,
    fecha_fin
FROM modulo2.asociaciones_activos_sensores
WHERE id_asociacion_activo_sensor IN (72, 73, 74, 75, 76, 77, 78, 79, 80, 81, 82, 83, 84, 85, 86, 87, 88, 89, 90, 91, 92)
ORDER BY id_asociacion_activo_sensor;

-- 2. SENTENCIA DE LIMPIEZA DEFENSIVA (SOFT-DELETE / DESACTIVACIÓN LÓGICA APPEND-ONLY):
-- Cuando el equipo de infraestructura/DBA autorice la limpieza manual, ejecutar:
/*
UPDATE modulo2.asociaciones_activos_sensores
SET 
    estado_asociacion = 'INACTIVA',
    fecha_fin = CURRENT_TIMESTAMP,
    motivo = motivo || ' | [CLEANUP MANUAL AUDITORIA PREFLIGHT/V3 TC-M02-G90]'
WHERE id_asociacion_activo_sensor IN (72, 73, 74, 75, 76, 77, 78, 79, 80, 81, 82, 83, 84, 85, 86, 87, 88, 89, 90, 91, 92)
  AND estado_asociacion = 'ACTIVA';
*/

-- 3. VERIFICACIÓN POST-LIMPIEZA:
/*
SELECT id_asociacion_activo_sensor, id_sensor, estado_asociacion, fecha_fin
FROM modulo2.asociaciones_activos_sensores
WHERE id_asociacion_activo_sensor IN (72, 73, 74, 75, 76, 77, 78, 79, 80, 81, 82, 83, 84, 85, 86, 87, 88, 89, 90, 91, 92);
*/
