-- ==============================================================================
-- SCRIPT DE LIMPIEZA / CONTINGENCIA: TC-M02-G89 (RF-49)
-- Estrategia A: Append-only conforme a RF-49 Restricción 8 (UPDATE de estado).
-- Desactiva asociaciones de prueba sin eliminar historial ni auditorías.
-- ==============================================================================

BEGIN;

-- 1. Desactivar asociaciones de prueba creadas durante TC-M02-G89
UPDATE modulo2.asociaciones_activos_sensores
SET estado_asociacion = 'INACTIVA',
    fecha_fin = GREATEST(clock_timestamp(), fecha_inicio + INTERVAL '1 second'),
    motivo = 'Cleanup tecnico de pruebas TC-M02-G89'
WHERE id_activo_biologico = 19
  AND id_sensor = 2
  AND estado_asociacion = 'ACTIVA'
  AND fecha_fin IS NULL;

-- 2. Verificación de limpieza (debe retornar 0 asociaciones activas remanentes)
SELECT COUNT(*) AS asociaciones_activas_remanentes
FROM modulo2.asociaciones_activos_sensores
WHERE id_activo_biologico = 19
  AND id_sensor = 2
  AND estado_asociacion = 'ACTIVA'
  AND fecha_fin IS NULL;

COMMIT;
