-- ====================================================================
-- Script de Verificación de Integridad y Contingencia: TC-M02-G30 (RF-36)
-- Entorno: TEST (Base de Datos: sgpmp_test)
-- Objetivo: Confirmar con SELECT que no existen registros residuales ni
--           alteraciones tras la ejecución de los subcasos TC-M02-194 y TC-M02-195.
-- ====================================================================

-- 1. Confirmar que el activo inexistente 99999 nunca fue creado en la base de datos
SELECT COUNT(*) AS total_activos_99999
FROM modulo2.activos_biologicos
WHERE id_activo_biologico = 99999;

-- 2. Confirmar que no se persistió ningún evento con la descripción del intento de prueba TC-M02-195
SELECT COUNT(*) AS total_eventos_tc_m02_195
FROM modulo2.eventos_activos
WHERE descripcion LIKE '%TC-M02-195%';

-- 3. Confirmar que no quedaron asociaciones sensor-activo remanentes vinculadas a la prueba
SELECT COUNT(*) AS total_asociaciones_remanentes
FROM modulo2.asociaciones_activos_sensores
WHERE motivo LIKE '%TC-M02-G30%' OR motivo LIKE '%TC-M02-195%';

-- ====================================================================
-- SECCIÓN DE CONTINGENCIA (SOLO DML - COMENTADA)
-- NOTA: Dado que las pruebas son de rechazo estricto (404 y 400), los SELECT
-- anteriores deben retornar 0. En caso de alguna anomalía no prevista,
-- descomentar y ejecutar manualmente:
--
-- DELETE FROM modulo2.eventos_crecimeinto
-- WHERE id_evento IN (
--     SELECT id_eventos FROM modulo2.eventos_activos WHERE descripcion LIKE '%TC-M02-195%'
-- );
-- DELETE FROM modulo2.eventos_activos
-- WHERE descripcion LIKE '%TC-M02-195%';
-- ====================================================================
