-- ==============================================================================
-- SCRIPT DE LIMPIEZA: TC-M02-G89 (RF-49)
-- Estrategia: Transición lógica a INACTIVA (RF-49 R5: no DELETE)
-- Entorno: TEST
-- Subcasos: TC-M02-216, TC-M02-217, TC-M02-218, TC-M02-219
-- ==============================================================================

BEGIN;

-- 1. Desactivar asociaciones de prueba del activo 112 / sensor 30
UPDATE modulo2.asociaciones_activos_sensores
SET estado_asociacion = 'INACTIVA',
    fecha_fin = NOW()
WHERE id_activo_biologico = 112
  AND id_sensor = 30
  AND estado_asociacion = 'ACTIVA'
  AND fecha_fin IS NULL;

-- 2. Verificación post-cleanup (debe retornar 0)
SELECT COUNT(*) AS asociaciones_activas_remanentes
FROM modulo2.asociaciones_activos_sensores
WHERE id_activo_biologico = 112
  AND id_sensor = 30
  AND estado_asociacion = 'ACTIVA'
  AND fecha_fin IS NULL;

COMMIT;
