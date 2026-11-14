-- ==============================================================================
-- SCRIPT DE LIMPIEZA / CONTINGENCIA: TC-M02-G87 (RF-49)
-- Operación: DML puro (DELETE de datos temporales). Sin DDL ni cambios estructurales.
-- ==============================================================================

BEGIN;

-- 1. Eliminar registros de auditoría de asociaciones temporales involucradas en las pruebas
DELETE FROM modulo2.auditorias_asociaciones_sensor_activo
WHERE id_asociacion_activo_sensor IN (
    SELECT id_asociacion_activo_sensor 
    FROM modulo2.asociaciones_activos_sensores
    WHERE (id_sensor = 8 AND id_activo_biologico = 108)
       OR (id_sensor = 17 AND id_activo_biologico = 108)
       OR (id_sensor = 22 AND id_activo_biologico = 108)
);

-- 2. Eliminar posibles asociaciones de prueba de modulo2.asociaciones_activos_sensores
DELETE FROM modulo2.asociaciones_activos_sensores
WHERE (id_sensor = 8 AND id_activo_biologico = 108)
   OR (id_sensor = 17 AND id_activo_biologico = 108)
   OR (id_sensor = 22 AND id_activo_biologico = 108);

-- 3. Verificación de limpieza (solo SELECT)
SELECT COUNT(*) AS asociaciones_remanentes
FROM modulo2.asociaciones_activos_sensores
WHERE (id_sensor = 8 AND id_activo_biologico = 108)
   OR (id_sensor = 17 AND id_activo_biologico = 108)
   OR (id_sensor = 22 AND id_activo_biologico = 108);

COMMIT;
