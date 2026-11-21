-- ==============================================================================
-- ARCHIVO: cleanup_seed_tc_m03_g164.sql
-- MÓDULO: Módulo 3 (Telemetría IoT) - RF-62 / TC-M03-G164
-- OBJETIVO: Limpieza determinista de registros de seed identificados con marcador
--           metadatos->>'seed_id' = 'TC_M03_G164_SEED' en modulo3.telemetrias.
-- AVISO NORMATIVO:
-- ROLLBACK POR DEFECTO. COMMIT SOLO CON VARIABLE EXPLÍCITA \set confirmar_commit 1.
-- ==============================================================================

\set ON_ERROR_STOP on

BEGIN;

DO $$
DECLARE
    v_conteo_calidad INTEGER;
    v_conteo_telemetrias INTEGER;
BEGIN
    -- 1. Contar filas marcadas en ambas tablas
    SELECT count(*) INTO v_conteo_calidad
    FROM modulo3.telemetria_calidad
    WHERE id_telemetria IN (
        SELECT id_telemetria 
        FROM modulo3.telemetrias 
        WHERE metadatos->>'seed_id' = 'TC_M03_G164_SEED'
    );

    SELECT count(*) INTO v_conteo_telemetrias
    FROM modulo3.telemetrias
    WHERE metadatos->>'seed_id' = 'TC_M03_G164_SEED';

    RAISE NOTICE 'Registros de seed detectados para limpieza: % en telemetria_calidad, % en telemetrias.', v_conteo_calidad, v_conteo_telemetrias;

    -- 2. Abortar si el conteo de telemetrías marcadas es 0
    IF v_conteo_telemetrias = 0 THEN
        RAISE EXCEPTION 'Limpieza abortada: No existen registros marcados con seed_id = TC_M03_G164_SEED.';
    END IF;

    -- 3. Desactivar referencias circulares/recursivas de id_evaluacion_superada (F-HG8)
    UPDATE modulo3.telemetria_calidad
    SET id_evaluacion_superada = NULL
    WHERE id_telemetria IN (
        SELECT id_telemetria 
        FROM modulo3.telemetrias 
        WHERE metadatos->>'seed_id' = 'TC_M03_G164_SEED'
    ) OR parametros_aplicados->>'seed_id' = 'TC_M03_G164_SEED';

    -- 4. Eliminar en la tabla hija (telemetria_calidad)
    DELETE FROM modulo3.telemetria_calidad
    WHERE id_telemetria IN (
        SELECT id_telemetria 
        FROM modulo3.telemetrias 
        WHERE metadatos->>'seed_id' = 'TC_M03_G164_SEED'
    ) OR parametros_aplicados->>'seed_id' = 'TC_M03_G164_SEED';

    -- 5. Eliminar en la tabla padre (telemetrias)
    DELETE FROM modulo3.telemetrias
    WHERE metadatos->>'seed_id' = 'TC_M03_G164_SEED';

    RAISE NOTICE 'Limpieza ejecutada exitosamente: % evaluaciones y % telemetrias eliminadas.', v_conteo_calidad, v_conteo_telemetrias;
END $$;

-- Sanity check post-cleanup: debe retornar 0 filas para ambos marcadores
SELECT count(*) AS residual_telemetrias 
FROM modulo3.telemetrias 
WHERE metadatos->>'seed_id' = 'TC_M03_G164_SEED';

SELECT count(*) AS residual_calidad 
FROM modulo3.telemetria_calidad 
WHERE parametros_aplicados->>'seed_id' = 'TC_M03_G164_SEED';

-- AVISO NORMATIVO SOBRE TRIGGERS (M15):
-- Estado de triggers de inmutabilidad: NO VERIFICADO en el catálogo activo de TEST.
-- En las migraciones de Alembic y esquemas de código no constan triggers de inmutabilidad (DROP/DELETE)
-- sobre modulo3.telemetria_calidad ni modulo3.telemetrias.
-- Para verificar en tiempo de ejecución de base de datos antes de la limpieza, el DBA puede ejecutar:
-- SELECT tgname, relname, tgenabled FROM pg_trigger t JOIN pg_class c ON t.tgrelid = c.oid 
-- WHERE c.relname IN ('telemetria_calidad', 'telemetrias') AND tgname NOT LIKE 'RI_ConstraintTrigger%';

-- Control de transacción: ROLLBACK por defecto. COMMIT solo con \set confirmar_commit 1
\if :{?confirmar_commit}
    COMMIT;
    \echo 'TRANSACCIÓN CONFIRMADA (COMMIT): Limpieza persistida en base de datos.'
\else
    ROLLBACK;
    \echo 'TRANSACCIÓN REVERTIDA (ROLLBACK): No se aplicaron cambios permanentes.'
\endif
