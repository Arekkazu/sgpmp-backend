-- ==============================================================================
-- ARCHIVO: seed_datos_tc_m03_g164.sql
-- MÓDULO: Módulo 3 (Telemetría IoT) - RF-62 / TC-M03-G164
-- OBJETIVO: Generar registros de prueba deterministas para cubrir precondiciones:
--           Total filas insertadas: 216
--           (200 tc308 + 4 apto + 4 reserva + 2 no_apto + 3 superada + 3 vigente_base)
-- MARCADORES DETERMINISTAS (Zero-Pollution):
--   modulo3.telemetrias: metadatos->>'seed_id' = 'TC_M03_G164_SEED'
--   modulo3.telemetria_calidad: parametros_aplicados->>'seed_id' = 'TC_M03_G164_SEED'
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
    v_base_time TIMESTAMPTZ := date_trunc('second', now()) - interval '30 days';
    v_id_telem INTEGER;
    v_id_eval_base UUID;
    v_i INTEGER;

    -- Sensores deterministas (F-HG9)
    v_s302_id INTEGER;
    v_s302_disp INTEGER;
    v_s302_var INTEGER;

    v_s304_id INTEGER;
    v_s304_disp INTEGER;
    v_s304_var INTEGER;

    v_s308_id INTEGER;
    v_s308_disp INTEGER;
    v_s308_var INTEGER;

    v_s3_id INTEGER;
    v_s3_disp INTEGER;
    v_s3_var INTEGER;

    v_sensores_arr INTEGER[];
    v_dispositivo_arr INTEGER[];
    v_variables_arr INTEGER[];

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

    -- 2. Selección determinista de sensores (F-HG9)
    -- 2.1. Sensor para TC-302 (debe existir id_telemetria = 62)
    SELECT id_sensor, id_dispositivo_iot, id_variable 
    INTO v_s302_id, v_s302_disp, v_s302_var
    FROM modulo3.telemetrias 
    WHERE id_telemetria = 62;

    IF v_s302_id IS NULL THEN
        RAISE EXCEPTION 'Precondición fallida F-HG9: No existe id_telemetria = 62 en modulo3.telemetrias.';
    END IF;

    -- 2.2. Sensor para TC-304 (>= 5 evaluaciones existentes en telemetria_calidad)
    SELECT id_sensor 
    INTO v_s304_id
    FROM modulo3.telemetria_calidad
    GROUP BY id_sensor 
    HAVING COUNT(*) >= 5
    ORDER BY COUNT(*) DESC 
    LIMIT 1;

    IF v_s304_id IS NULL THEN
        RAISE EXCEPTION 'Precondición fallida F-HG9: No existe sensor con >= 5 evaluaciones en modulo3.telemetria_calidad.';
    END IF;

    SELECT id_dispositivo_iot, id_variable 
    INTO v_s304_disp, v_s304_var
    FROM modulo3.telemetrias 
    WHERE id_sensor = v_s304_id 
    LIMIT 1;

    -- 2.3. Sensor para TC-308: se concentra en el sensor principal (v_s304_id) para garantizar volumen >= 200
    v_s308_id := v_s304_id;
    v_s308_disp := v_s304_disp;
    v_s308_var := v_s304_var;

    -- 2.4. Sensor 3 alternativo (para diversidad en SUPERADA / F-5c)
    SELECT id_sensor, id_dispositivo_iot, id_variable 
    INTO v_s3_id, v_s3_disp, v_s3_var
    FROM modulo3.telemetrias 
    WHERE id_sensor NOT IN (v_s302_id, v_s304_id)
    LIMIT 1;

    IF v_s3_id IS NULL THEN
        v_s3_id := v_s302_id;
        v_s3_disp := v_s302_disp;
        v_s3_var := v_s302_var;
    END IF;

    v_sensores_arr := ARRAY[v_s302_id, v_s304_id, v_s3_id];
    v_dispositivo_arr := ARRAY[v_s302_disp, v_s304_disp, v_s3_disp];
    v_variables_arr := ARRAY[v_s302_var, v_s304_var, v_s3_var];

    -- 3. Insertar 3 evaluaciones base VIGENTE y 3 SUPERADA para TC-307 (F-5c / HG-7: 6 filas)
    FOR v_sensor_idx IN 1..3 LOOP
        v_sensor_id := v_sensores_arr[v_sensor_idx];
        v_disp_id := v_dispositivo_arr[v_sensor_idx];
        v_var_id := v_variables_arr[v_sensor_idx];

        -- 3.1. Insertar evaluación base VIGENTE previa del mismo sensor para servir de objetivo FK
        INSERT INTO modulo3.telemetrias (
            id_sensor, id_variable, id_dispositivo_iot, valor_crudo, valor_ajustado,
            timestamp_captura, timestamp_procesamiento, origen, estado_calidad,
            calibrado, metadatos, categoria_variable, unidad_medida
        ) VALUES (
            v_sensor_id, v_var_id, v_disp_id, 24.0000, 24.0000,
            v_base_time + (v_sensor_idx * interval '10 second'), now(),
            'TIEMPO_REAL', 'OPTIMA', true,
            '{"seed_id": "TC_M03_G164_SEED"}'::jsonb, 'AMBIENTAL', '°C'
        ) RETURNING id_telemetria INTO v_id_telem;

        v_id_eval_base := gen_random_uuid();
        INSERT INTO modulo3.telemetria_calidad (
            id_evaluacion, id_telemetria, id_sensor, timestamp_evaluacion,
            indice_calidad, clasificacion_calidad, apto_para_ia, apto_para_nic41,
            flags_detectados, parametros_aplicados, parametros_calibracion_aplicados,
            estado_evaluacion, motivo_reevaluacion, id_evaluacion_superada, version_evaluacion
        ) VALUES (
            v_id_eval_base, v_id_telem, v_sensor_id, v_base_time + (v_sensor_idx * interval '10 second'),
            95, 'APTO', true, true,
            '{}'::jsonb,
            '{"k": 3.0, "M": 5, "N": 20, "umbral_drift": 5.0, "seed_id": "TC_M03_G164_SEED"}'::jsonb,
            '{"offset": "0.0000", "ganancia": "1.0000"}'::jsonb,
            'VIGENTE', NULL, NULL, '1.0'
        );

        -- 3.2. Insertar evaluación SUPERADA (F-5c / HG-7: id_evaluacion_superada apunta a v_id_eval_base del MISMO sensor)
        INSERT INTO modulo3.telemetrias (
            id_sensor, id_variable, id_dispositivo_iot, valor_crudo, valor_ajustado,
            timestamp_captura, timestamp_procesamiento, origen, estado_calidad,
            calibrado, metadatos, categoria_variable, unidad_medida
        ) VALUES (
            v_sensor_id, v_var_id, v_disp_id, 25.0000, 25.0000,
            v_base_time + (v_sensor_idx * interval '10 second') + interval '5 second', now(),
            'TIEMPO_REAL', 'OPTIMA', true,
            '{"seed_id": "TC_M03_G164_SEED"}'::jsonb, 'AMBIENTAL', '°C'
        ) RETURNING id_telemetria INTO v_id_telem;

        INSERT INTO modulo3.telemetria_calidad (
            id_evaluacion, id_telemetria, id_sensor, timestamp_evaluacion,
            indice_calidad, clasificacion_calidad, apto_para_ia, apto_para_nic41,
            flags_detectados, parametros_aplicados, parametros_calibracion_aplicados,
            estado_evaluacion, motivo_reevaluacion, id_evaluacion_superada, version_evaluacion
        ) VALUES (
            gen_random_uuid(), v_id_telem, v_sensor_id, v_base_time + (v_sensor_idx * interval '10 second') + interval '5 second',
            95, 'APTO', true, true,
            '{}'::jsonb,
            '{"k": 3.0, "M": 5, "N": 20, "umbral_drift": 5.0, "seed_id": "TC_M03_G164_SEED"}'::jsonb,
            '{"offset": "0.0000", "ganancia": "1.0000"}'::jsonb,
            'SUPERADA', 'Re-evaluación zootécnica documentada: actualización de parámetros y umbrales', v_id_eval_base, '1.0'
        );
    END LOOP;

    -- 4. Sembrar 10 evaluaciones específicas para TC-305 (4 APTO, 4 APTO_CON_RESERVA, 2 NO_APTO)
    FOR v_i IN 1..10 LOOP
        v_sensor_idx := 1 + (v_i % 2); -- alternar entre sensor 302 y sensor 304
        v_sensor_id := v_sensores_arr[v_sensor_idx];
        v_disp_id := v_dispositivo_arr[v_sensor_idx];
        v_var_id := v_variables_arr[v_sensor_idx];

        IF v_i <= 4 THEN
            v_clasif := 'APTO';
            v_indice := 95;
            v_apto_ia := true;
            v_apto_nic41 := true;
            v_flags := '{}'::jsonb;
        ELSIF v_i <= 8 THEN
            v_clasif := 'APTO_CON_RESERVA';
            v_indice := 75;
            v_apto_ia := true;
            v_apto_nic41 := false;
            v_flags := '{"outlier_estadistico": {"activo": true}}'::jsonb;
        ELSE
            v_clasif := 'NO_APTO';
            v_indice := 25;
            v_apto_ia := false;
            v_apto_nic41 := false;
            v_flags := '{"sensor_congelado": {"activo": true, "severidad": "CRITICO"}}'::jsonb;
        END IF;

        INSERT INTO modulo3.telemetrias (
            id_sensor, id_variable, id_dispositivo_iot, valor_crudo, valor_ajustado,
            timestamp_captura, timestamp_procesamiento, origen, estado_calidad,
            calibrado, metadatos, categoria_variable, unidad_medida
        ) VALUES (
            v_sensor_id, v_var_id, v_disp_id, 24.0000 + (v_i * 0.05), 24.0000 + (v_i * 0.05),
            v_base_time + (50 + v_i) * interval '1 second', now(),
            'TIEMPO_REAL', 'OPTIMA', true,
            '{"seed_id": "TC_M03_G164_SEED"}'::jsonb, 'AMBIENTAL', '°C'
        ) RETURNING id_telemetria INTO v_id_telem;

        INSERT INTO modulo3.telemetria_calidad (
            id_evaluacion, id_telemetria, id_sensor, timestamp_evaluacion,
            indice_calidad, clasificacion_calidad, apto_para_ia, apto_para_nic41,
            flags_detectados, parametros_aplicados, parametros_calibracion_aplicados,
            estado_evaluacion, motivo_reevaluacion, id_evaluacion_superada, version_evaluacion
        ) VALUES (
            gen_random_uuid(), v_id_telem, v_sensor_id, v_base_time + (50 + v_i) * interval '1 second',
            v_indice, v_clasif, v_apto_ia, v_apto_nic41,
            v_flags,
            '{"k": 3.0, "M": 5, "N": 20, "umbral_drift": 5.0, "seed_id": "TC_M03_G164_SEED"}'::jsonb,
            '{"offset": "0.0000", "ganancia": "1.0000"}'::jsonb,
            'VIGENTE', NULL, NULL, '1.0'
        );
    END LOOP;

    -- 5. Sembrar 200 evaluaciones masivas concentradas en v_s308_id para TC-308 (F-HG10)
    -- Alterna clasificaciones con coherencia estricta de índice y aptitud
    FOR v_i IN 1..200 LOOP
        v_calidad_idx := v_i % 4;
        IF v_calidad_idx = 0 THEN
            v_clasif := 'APTO';
            v_indice := 95;
            v_apto_ia := true;
            v_apto_nic41 := true;
            v_flags := '{}'::jsonb;
        ELSIF v_calidad_idx = 1 THEN
            v_clasif := 'APTO_CON_RESERVA';
            v_indice := 75;
            v_apto_ia := true;
            v_apto_nic41 := false;
            v_flags := '{"outlier_estadistico": {"activo": true}}'::jsonb;
        ELSIF v_calidad_idx = 2 THEN
            v_clasif := 'NO_APTO';
            v_indice := 25;
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
            v_s308_id, v_s308_var, v_s308_disp, 20.0000 + (v_i * 0.01), 20.0000 + (v_i * 0.01),
            v_base_time + (1000 + v_i) * interval '1 second', now(),
            'TIEMPO_REAL', 'OPTIMA', true,
            '{"seed_id": "TC_M03_G164_SEED"}'::jsonb, 'AMBIENTAL', '°C'
        ) RETURNING id_telemetria INTO v_id_telem;

        INSERT INTO modulo3.telemetria_calidad (
            id_evaluacion, id_telemetria, id_sensor, timestamp_evaluacion,
            indice_calidad, clasificacion_calidad, apto_para_ia, apto_para_nic41,
            flags_detectados, parametros_aplicados, parametros_calibracion_aplicados,
            estado_evaluacion, motivo_reevaluacion, id_evaluacion_superada, version_evaluacion
        ) VALUES (
            gen_random_uuid(), v_id_telem, v_s308_id, v_base_time + (1000 + v_i) * interval '1 second',
            v_indice, v_clasif, v_apto_ia, v_apto_nic41,
            v_flags,
            '{"k": 3.0, "M": 5, "N": 20, "umbral_drift": 5.0, "seed_id": "TC_M03_G164_SEED"}'::jsonb,
            '{"offset": "0.0000", "ganancia": "1.0000"}'::jsonb,
            'VIGENTE', NULL, NULL, '1.0'
        );
    END LOOP;

    RAISE NOTICE 'Seed TC-M03-G164 completado exitosamente: 216 registros sembrados (6 TC-307 + 10 TC-305 + 200 TC-308).';
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
