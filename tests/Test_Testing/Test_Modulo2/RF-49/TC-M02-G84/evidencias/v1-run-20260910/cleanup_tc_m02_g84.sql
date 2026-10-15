-- ==============================================================================
-- SCRIPT DE LIMPIEZA MANUAL / CONTINGENCIA: TC-M02-G84 (RF-49)
-- Entorno: TEST (158.69.200.27:5448/sgpmp_test)
-- Caso de Prueba: TC-M02-G84 (Asociación de sensores IoT a activos biológicos)
-- Subcasos: TC-M02-143, TC-M02-144, TC-M02-145, TC-M02-150
-- ==============================================================================

BEGIN;

-- 1. Eliminar auditorías de asociaciones creadas para los sensores de prueba
DELETE FROM modulo2.auditorias_asociaciones_sensor_activo
WHERE id_asociacion_activo_sensor IN (
    SELECT id_asociacion_activo_sensor 
    FROM modulo2.asociaciones_activos_sensores
    WHERE id_sensor IN (22, 23, 24, 6)
      AND id_activo_biologico IN (108, 109, 83, 110)
);

-- 2. Eliminar asociaciones creadas por TC-M02-G84
DELETE FROM modulo2.asociaciones_activos_sensores
WHERE id_sensor IN (22, 23, 24, 6)
  AND id_activo_biologico IN (108, 109, 83, 110);

-- 3. Verificación de limpieza
SELECT COUNT(*) AS asociaciones_remanentes
FROM modulo2.asociaciones_activos_sensores
WHERE id_sensor IN (22, 23, 24, 6)
  AND id_activo_biologico IN (108, 109, 83, 110);

COMMIT;
