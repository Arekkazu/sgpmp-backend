-- ==============================================================================
-- SCRIPT DE LIMPIEZA / CONTINGENCIA: TC-M02-G88 (RF-49)
-- Estrategia A: Append-only conforme a RF-49 Restriccion 8 (UPDATE de estado).
-- Desactiva asociaciones de prueba sin eliminar historial ni auditorias.
-- ==============================================================================

BEGIN;

-- 1. Desactivar asociaciones de prueba creadas durante la suite con precedencia explicita
UPDATE modulo2.asociaciones_activos_sensores
SET estado_asociacion = 'INACTIVA',
    fecha_fin = NOW(),
    motivo = 'Cleanup tecnico de pruebas TC-M02-G88'
WHERE (
    (id_sensor = 1 AND id_activo_biologico IN (20, 53))
    OR (id_sensor IN (2, 3) AND id_activo_biologico = 19)
)
  AND estado_asociacion = 'ACTIVA'
  AND fecha_fin IS NULL;

-- 2. Verificacion de limpieza (debe retornar 0 asociaciones activas remanentes)
SELECT COUNT(*) AS asociaciones_activas_remanentes
FROM modulo2.asociaciones_activos_sensores
WHERE (
    (id_sensor = 1 AND id_activo_biologico IN (20, 53))
    OR (id_sensor IN (2, 3) AND id_activo_biologico = 19)
)
  AND estado_asociacion = 'ACTIVA'
  AND fecha_fin IS NULL;

COMMIT;
