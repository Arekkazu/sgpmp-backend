BEGIN;
UPDATE modulo2.asociaciones_activos_sensores
SET estado_asociacion = 'INACTIVA', fecha_fin = NOW(),
    motivo = 'Cleanup tecnico de pruebas TC-M02-G91'
WHERE id_activo_biologico = 19 AND id_sensor = 2
  AND estado_asociacion = 'ACTIVA' AND fecha_fin IS NULL;
SELECT COUNT(*) AS asociaciones_activas_remanentes
FROM modulo2.asociaciones_activos_sensores
WHERE id_activo_biologico = 19 AND id_sensor = 2
  AND estado_asociacion = 'ACTIVA' AND fecha_fin IS NULL;
COMMIT;
