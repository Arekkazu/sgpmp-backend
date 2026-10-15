-- ==============================================================================
-- SCRIPT DE LIMPIEZA MANUAL / CONTINGENCIA: TC-M02-G85 (RF-49)
-- Entorno: TEST (158.69.200.27:5448/sgpmp_test)
-- Casos: TC-M02-146, TC-M02-147, TC-M02-148
-- ==============================================================================

BEGIN;

-- 1. Eliminar auditorías de asociaciones accidentales si hubiese existido inserción
DELETE FROM modulo2.auditorias_asociaciones_sensor_activo
WHERE id_asociacion_activo_sensor IN (
    SELECT id_asociacion_activo_sensor 
    FROM modulo2.asociaciones_activos_sensores
    WHERE (id_sensor = 1 AND id_activo_biologico = 10)
       OR (id_sensor = 8 AND id_activo_biologico = 108)
       OR (id_sensor = 1 AND id_activo_biologico = 279)
);

-- 2. Eliminar posibles asociaciones creadas por error en TC-M02-G85
DELETE FROM modulo2.asociaciones_activos_sensores
WHERE (id_sensor = 1 AND id_activo_biologico = 10)
   OR (id_sensor = 8 AND id_activo_biologico = 108)
   OR (id_sensor = 1 AND id_activo_biologico = 279);

-- 3. Verificación de integridad
SELECT COUNT(*) AS asociaciones_remanentes
FROM modulo2.asociaciones_activos_sensores
WHERE (id_sensor = 1 AND id_activo_biologico = 10)
   OR (id_sensor = 8 AND id_activo_biologico = 108)
   OR (id_sensor = 1 AND id_activo_biologico = 279);

COMMIT;
