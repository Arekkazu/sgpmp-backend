-- ==============================================================================
-- SCRIPT DE CONTINGENCIA Y LIMPIEZA MANUAL: TC-M02-G76 (RF-46)
-- Objetivo: Eliminar registros sintéticos generados durante la prueba de límite
-- de paginación (500 vs 501) en caso de interrupción anormal de Pytest.
-- Entorno: TEST (158.69.200.27:5448/sgpmp_test)
-- ==============================================================================

BEGIN;

-- 1. Eliminación de indicadores sintéticos con fecha >= 2030-01-01 para el activo 130
DELETE FROM modulo2.indicadores_zootecnicos
WHERE id_activo_biologico = 130
  AND lower(rango_fecha) >= '2030-01-01'::date;

-- 2. Consulta de verificación (debe retornar 0)
SELECT 
    COUNT(*) AS total_indicadores_remanentes_2030,
    CASE 
        WHEN COUNT(*) = 0 THEN 'EXITO: Limpieza completada sin registros residuales'
        ELSE 'ALERTA: Existen registros remanentes que deben ser revisados'
    END AS estado_limpieza
FROM modulo2.indicadores_zootecnicos
WHERE id_activo_biologico = 130
  AND lower(rango_fecha) >= '2030-01-01'::date;

COMMIT;
