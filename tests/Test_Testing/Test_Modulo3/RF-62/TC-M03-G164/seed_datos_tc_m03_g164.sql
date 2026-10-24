-- ==============================================================================
-- ARCHIVO: seed_datos_tc_m03_g164.sql
-- MÓDULO: Módulo 3 (Telemetría IoT) - RF-62 / TC-M03-G164
-- OBJETIVO: Generar registros de prueba para cubrir precondiciones de calidad
--           (clasificaciones APTO, NO_APTO, APTO_CON_RESERVA, INDETERMINADA y estado SUPERADA)
--           distribuidos en >=3 sensores reales, con >=3 filas SUPERADA reales
--           (id_evaluacion_superada = NULL) y volumen >200 evaluaciones.
-- MARCADOR: metadatos->>'seed_id' = 'TC_M03_G164_SEED' en modulo3.telemetrias
-- AVISO NORMATIVO:
-- NO EJECUTAR SIN AUTORIZACIÓN DEL EQUIPO; CONTRADICE EL PRINCIPIO DE CERO CONTAMINACIÓN.
-- EL MECANISMO PREFERIDO ES EL SANDBOX TRANSACCIONAL CON ROLLBACK AUTOMÁTICO.
-- ==============================================================================

\set ON_ERROR_STOP on

-- Transacción principal
BEGIN;

DO $$
DECLARE
    v_conteo_previo INTEGER;
    v_sensores_arr INTEGER[];
    v_dispositivo_arr INTEGER[];
    v_variables_arr INTEGER[];
    v_base_time TIMESTAMPTZ := date_trunc('second', now()) - interval '30 days';
    v_id_telem INTEGER;
    v_i INTEGER;
    v_sensor_idx INTEGER;
    v_sensor_id INTEGER;
    v_disp_id INTEGER;
    v_var_id INTEGER;
    v_calidad_idx INTEGER;
    v_clasif VARCHAR(20);
    v_indice SMALLINT;
    v_apto_ia BOOLEAN;
    v_apto_nic41 BOOLEAN;
    v_flags JSONB;
BEGIN
    -- 1. Idempotencia real: comprobar si ya existen registros con el marcador
    SELECT count(*) INTO v_conteo_previo
    FROM modulo3.telemetrias
    WHERE metadatos->>'seed_id' = 'TC_M03_G164_SEED';

    IF v_conteo_previo > 0 THEN
        RAISE NOTICE 'Seed TC-M03-G164 ya aplicado previamente (% telemetrias encontradas). Omitiendo inserción.', v_conteo_previo;
        RETURN;
    END IF;

    -- 2. Seleccionar dinámicamente al menos 3 sensores válidos con su dispositivo y variable
    SELECT array_agg(s.id_sensores), array_agg(s.id_dispositivo_iot), array_agg(s.id_variable)
    INTO v_sensores_arr, v_dispositivo_arr, v_variables_arr
    FROM (
        SELECT DISTINCT id_sensores, id_dispositivo_iot, id_variable
        FROM modulo9.sensores
        WHERE id_dispositivo_iot IS NOT NULL AND id_variable IS NOT NULL
        LIMIT 3
    ) s;

    IF array_length(v_sensores_arr, 1) IS NULL OR array_length(v_sensores_arr, 1) < 3 THEN
        RAISE EXCEPTION 'Precondición fallida: Se requieren al menos 3 sensores en modulo9.sensores con dispositivo y variable asociados.';
    END IF;

    -- 3. Insertar evaluaciones específicas para cubrir clasificaciones y estado SUPERADA
    -- 3.1. Tres evaluaciones SUPERADA reales (con motivo y id_evaluacion_superada = NULL)
    FOR v_sensor_idx IN 1..3 LOOP
        v_sensor_id := v_sensores_arr[v_sensor_idx];
        v_disp_id := v_dispositivo_arr[v_sensor_idx];
        v_var_id := v_variables_arr[v_sensor_idx];

        INSERT INTO modulo3.telemetrias (
            id_sensor, id_variable, id_dispositivo_iot, valor_crudo, valor_ajustado,
            timestamp_captura, timestamp_procesamiento, origen, estado_calidad,
            calibrado, metadatos, categoria_variable, unidad_medida
        ) VALUES (
            v_sensor_id, v_var_id, v_disp_id, 25.0000, 25.0000,
            v_base_time + (v_sensor_idx * interval '10 second'), now(),
            'TIEMPO_REAL', 'OPTIMA', true,
            '{"seed_id": "TC_M03_G164_SEED"}'::jsonb, 'AMBIENTAL', '°C'
        ) RETURNING id_telemetria INTO v_id_telem;

        INSERT INTO modulo3.telemetria_calidad (
            id_telemetria, id_sensor, timestamp_evaluacion,
            indice_calidad, clasificacion_calidad, apto_para_ia, apto_para_nic41,
            flags_detectados, parametros_aplicados, parametros_calibracion_aplicados,
            estado_evaluacion, motivo_reevaluacion, id_evaluacion_superada, version_evaluacion
        ) VALUES (
            v_id_telem, v_sensor_id, v_base_time + (v_sensor_idx * interval '10 second'),
            85, 'APTO', true, true,
            '{}'::jsonb,
            '{"k": 3.0, "M": 5, "N": 20, "umbral_drift": 5.0}'::jsonb,
            '{"offset": "0.0000", "ganancia": "1.0000"}'::jsonb,
            'SUPERADA', 'Re-evaluación histórica documentada: ajuste de parámetros zootécnicos', NULL, '1.0'
        );
    END LOOP;

    -- 4. Sembrar >200 evaluaciones distribuidas entre los 3 sensores cubriendo las 4 clasificaciones
    FOR v_i IN 1..210 LOOP
        v_sensor_idx := 1 + (v_i % 3);
        v_sensor_id := v_sensores_arr[v_sensor_idx];
        v_disp_id := v_dispositivo_arr[v_sensor_idx];
        v_var_id := v_variables_arr[v_sensor_idx];

        v_calidad_idx := v_i % 4;
        IF v_calidad_idx = 0 THEN
            v_clasif := 'APTO';
            v_indice := 95;
            v_apto_ia := true;
            v_apto_nic41 := true;
            v_flags := '{}'::jsonb;
        ELSIF v_calidad_idx = 1 THEN
            v_clasif := 'APTO_CON_RESERVA';
            v_indice := 60;
            v_apto_ia := true;
            v_apto_nic41 := false;
            v_flags := '{"outlier_estadistico": {"activo": true}}'::jsonb;
        ELSIF v_calidad_idx = 2 THEN
            v_clasif := 'NO_APTO';
            v_indice := 20;
            v_apto_ia := false;
            v_apto_nic41 := false;
            v_flags := '{"sensor_congelado": {"activo": true, "severidad": "CRITICO"}}'::jsonb;
        ELSE
            v_clasif := 'INDETERMINADA';
            v_indice := NULL;
            v_apto_ia := false;
            v_apto_nic41 := false;
            v_flags := '{"serie_insuficiente": {"activo": true}}'::jsonb;
        END IF;

        INSERT INTO modulo3.telemetrias (
            id_sensor, id_variable, id_dispositivo_iot, valor_crudo, valor_ajustado,
            timestamp_captura, timestamp_procesamiento, origen, estado_calidad,
            calibrado, metadatos, categoria_variable, unidad_medida
        ) VALUES (
            v_sensor_id, v_var_id, v_disp_id, 24.5000 + (v_i * 0.01), 24.5000 + (v_i * 0.01),
            v_base_time + (100 + v_i) * interval '1 second', now(),
            'TIEMPO_REAL', 'OPTIMA', true,
            '{"seed_id": "TC_M03_G164_SEED"}'::jsonb, 'AMBIENTAL', '°C'
        ) RETURNING id_telemetria INTO v_id_telem;

        INSERT INTO modulo3.telemetria_calidad (
            id_telemetria, id_sensor, timestamp_evaluacion,
            indice_calidad, clasificacion_calidad, apto_para_ia, apto_para_nic41,
            flags_detectados, parametros_aplicados, parametros_calibracion_aplicados,
            estado_evaluacion, motivo_reevaluacion, id_evaluacion_superada, version_evaluacion
        ) VALUES (
            v_id_telem, v_sensor_id, v_base_time + (100 + v_i) * interval '1 second',
            v_indice, v_clasif, v_apto_ia, v_apto_nic41,
            v_flags,
            '{"k": 3.0, "M": 5, "N": 20, "umbral_drift": 5.0}'::jsonb,
            '{"offset": "0.0000", "ganancia": "1.0000"}'::jsonb,
            'VIGENTE', NULL, NULL, '1.0'
        );
    END LOOP;

    RAISE NOTICE 'Seed TC-M03-G164 completado exitosamente: 213 registros sembrados en >=3 sensores.';
END $$;

-- Verificación de conteo previo antes de confirmar:
-- SELECT count(*) AS telemetrias_sembradas FROM modulo3.telemetrias WHERE metadatos->>'seed_id' = 'TC_M03_G164_SEED';
-- SELECT count(*) AS calidades_sembradas FROM modulo3.telemetria_calidad WHERE id_telemetria IN (SELECT id_telemetria FROM modulo3.telemetrias WHERE metadatos->>'seed_id' = 'TC_M03_G164_SEED');

-- Control de transacción: ROLLBACK por defecto. COMMIT solo con \set confirmar_commit 1
\if :{?confirmar_commit}
    COMMIT;
    \echo 'TRANSACCIÓN CONFIRMADA (COMMIT): Registros de seed persistidos.'
\else
    ROLLBACK;
    \echo 'TRANSACCIÓN REVERTIDA (ROLLBACK): No se realizaron cambios permanentes en la base de datos.'
\endif
