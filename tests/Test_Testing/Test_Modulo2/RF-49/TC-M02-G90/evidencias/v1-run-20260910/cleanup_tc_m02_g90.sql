-- ==============================================================================
-- SCRIPT DE LIMPIEZA / CONTINGENCIA: TC-M02-G90 (RF-49)
-- Estrategia A: Append-only conforme a RF-49 Restricción 8 (UPDATE de estado).
-- Desactiva asociaciones de prueba creadas durante TC-M02-G90.
-- ==============================================================================

BEGIN;

-- 1. Desactivar asociación creada en TC-M02-221 (Sensor 3 + Activo 1)
UPDATE modulo2.asociaciones_activos_sensores
SET estado_asociacion = 'INACTIVA',
    fecha_fin = GREATEST(clock_timestamp(), fecha_inicio + INTERVAL '1 second'),
    motivo = 'Cleanup tecnico de pruebas TC-M02-G90'
WHERE id_activo_biologico = 1
  AND id_sensor = 3
  AND estado_asociacion = 'ACTIVA'
  AND fecha_fin IS NULL;

-- 2. Desactivar asociación creada en TC-M02-220 (Sensor 3 + Activo 19)
UPDATE modulo2.asociaciones_activos_sensores
SET estado_asociacion = 'INACTIVA',
    fecha_fin = GREATEST(clock_timestamp(), fecha_inicio + INTERVAL '1 second'),
    motivo = 'Cleanup tecnico de pruebas TC-M02-G90'
WHERE id_activo_biologico = 19
  AND id_sensor = 3
  AND estado_asociacion = 'ACTIVA'
  AND fecha_fin IS NULL;

-- 3. Verificación de limpieza acotada a los activos de la prueba
SELECT COUNT(*) AS asociaciones_activas_remanentes
FROM modulo2.asociaciones_activos_sensores
WHERE id_activo_biologico IN (1, 19)
  AND id_sensor = 3
  AND estado_asociacion = 'ACTIVA'
  AND fecha_fin IS NULL;

COMMIT;
