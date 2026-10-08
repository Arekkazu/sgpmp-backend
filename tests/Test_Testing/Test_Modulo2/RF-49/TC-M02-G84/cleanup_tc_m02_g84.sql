-- ==============================================================================
-- SCRIPT DE LIMPIEZA / CONTINGENCIA: TC-M02-G84 (RF-49)
-- Estrategia: Transición lógica de estado (UPDATE a 'INACTIVA')
-- Conforme a RF-49 Restricción 5: No se permite eliminar registros de asociación;
-- solo cambiar su estado. La auditoría se mantiene inmutable por diseño.
-- Entorno: TEST (158.69.200.27:5448/sgpmp_test)
-- Caso de Prueba: TC-M02-G84 (Asociación de sensores IoT a activos biológicos)
-- Subcasos cubiertos: TC-M02-143, TC-M02-144, TC-M02-145, TC-M02-150
-- ==============================================================================

BEGIN;

-- 1. Desactivar asociaciones de prueba creadas durante la suite TC-M02-G84
UPDATE modulo2.asociaciones_activos_sensores
SET estado_asociacion = 'INACTIVA',
    fecha_fin = NOW(),
    motivo = 'Cleanup tecnico de pruebas TC-M02-G84'
WHERE (
    (id_sensor IN (22, 23, 24, 6) AND id_activo_biologico IN (108, 109, 83, 110))
    OR (id_sensor = 23 AND id_infraestructura = 3 AND id_activo_biologico IS NULL)
)
  AND estado_asociacion = 'ACTIVA'
  AND fecha_fin IS NULL;

-- 2. Verificación de limpieza (debe retornar 0 asociaciones activas remanentes)
SELECT COUNT(*) AS asociaciones_activas_remanentes
FROM modulo2.asociaciones_activos_sensores
WHERE (
    (id_sensor IN (22, 23, 24, 6) AND id_activo_biologico IN (108, 109, 83, 110))
    OR (id_sensor = 23 AND id_infraestructura = 3 AND id_activo_biologico IS NULL)
)
  AND estado_asociacion = 'ACTIVA'
  AND fecha_fin IS NULL;

COMMIT;
