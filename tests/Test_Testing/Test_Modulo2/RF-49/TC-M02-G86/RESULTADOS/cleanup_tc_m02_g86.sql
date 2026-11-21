-- ==============================================================================
-- SCRIPT DE LIMPIEZA MANUAL / CONTINGENCIA: TC-M02-G86 (RF-49)
-- Entorno: TEST (158.69.200.27:5448/sgpmp_test)
-- Operación: DML estricto (DELETE de datos temporales). Sin DDL ni cambios estructurales.
-- ==============================================================================

BEGIN;

-- 1. Eliminar registros de auditoría asociados a la asociación temporal de prueba
DELETE FROM modulo2.auditorias_asociaciones_sensor_activo
WHERE id_asociacion_activo_sensor IN (
    SELECT id_asociacion_activo_sensor 
    FROM modulo2.asociaciones_activos_sensores
    WHERE id_sensor = 22 AND id_activo_biologico IN (108, 109)
);

-- 2. Eliminar asociación temporal creada vía API durante el setup de TC-M02-149
DELETE FROM modulo2.asociaciones_activos_sensores
WHERE id_sensor = 22 AND id_activo_biologico IN (108, 109);

-- 3. Verificación de limpieza (solo SELECT)
SELECT COUNT(*) AS asociaciones_remanentes
FROM modulo2.asociaciones_activos_sensores
WHERE id_sensor = 22 AND id_activo_biologico IN (108, 109);

COMMIT;
