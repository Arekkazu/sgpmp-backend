-- SQL de las migraciones 21fe51f2aea1 y bb5526687aae (generado con: alembic upgrade 9b7d64203f48:bb5526687aae --sql).
-- Lo normal es aplicarlas con 'alembic upgrade head'; este archivo es para que el DBA las revise.
BEGIN;

-- Running upgrade 9b7d64203f48 -> 21fe51f2aea1

CREATE TYPE modulo4.enum_proceso_reentrenamiento_disparador AS ENUM ('MANUAL', 'PROGRAMADO', 'DEGRADACION');
        CREATE TYPE modulo4.enum_proceso_reentrenamiento_modo_generacion AS ENUM ('REENTRENAMIENTO', 'CALIBRACION_EN_SITIO');
        CREATE TYPE modulo4.enum_proceso_reentrenamiento_estado AS ENUM (
            'PENDIENTE', 'EN_CURSO', 'COMPLETADO', 'FALLIDO', 'INTERRUMPIDO', 'CANCELADO');

        CREATE TABLE modulo4.procesos_reentrenamiento (
            id_proceso_reentrenamiento UUID NOT NULL DEFAULT gen_random_uuid(),
            tipo_modelo modulo4.enum_tipo_modelo NOT NULL,
            id_activo_biologico INTEGER NOT NULL,
            disparador modulo4.enum_proceso_reentrenamiento_disparador NOT NULL DEFAULT 'MANUAL',
            modo_generacion modulo4.enum_proceso_reentrenamiento_modo_generacion NOT NULL DEFAULT 'REENTRENAMIENTO',
            estado modulo4.enum_proceso_reentrenamiento_estado NOT NULL DEFAULT 'PENDIENTE',
            fase_actual SMALLINT NOT NULL DEFAULT 0,
            porcentaje_progreso SMALLINT NOT NULL DEFAULT 0,
            json_fases JSONB NOT NULL DEFAULT '[]'::jsonb,
            porcentaje_cpu NUMERIC(5, 2),
            memoria_ram_mb INTEGER,
            codigo_error VARCHAR(60),
            json_motivos JSONB,
            id_version_modelo_referencia INTEGER,
            id_version_modelo_resultante INTEGER,
            id_usuario_solicitante INTEGER,
            fecha_solicitud TIMESTAMPTZ NOT NULL DEFAULT now(),
            fecha_inicio TIMESTAMPTZ,
            fecha_fin TIMESTAMPTZ,
            fecha_ultimo_latido TIMESTAMPTZ,
            CONSTRAINT procesos_reentrenamiento_pkey PRIMARY KEY (id_proceso_reentrenamiento),
            CONSTRAINT procesos_reentrenamiento_id_activo_biologico_fkey
                FOREIGN KEY (id_activo_biologico) REFERENCES modulo2.activos_biologicos (id_activo_biologico)
                ON DELETE RESTRICT ON UPDATE CASCADE,
            CONSTRAINT procesos_reentrenamiento_id_version_modelo_referencia_fkey
                FOREIGN KEY (id_version_modelo_referencia) REFERENCES modulo4.versiones_modelos (id_version_modelo)
                ON DELETE RESTRICT ON UPDATE CASCADE,
            CONSTRAINT procesos_reentrenamiento_id_version_modelo_resultante_fkey
                FOREIGN KEY (id_version_modelo_resultante) REFERENCES modulo4.versiones_modelos (id_version_modelo)
                ON DELETE RESTRICT ON UPDATE CASCADE,
            CONSTRAINT procesos_reentrenamiento_id_usuario_solicitante_fkey
                FOREIGN KEY (id_usuario_solicitante) REFERENCES modulo1.usuarios (id_usuario)
                ON DELETE RESTRICT ON UPDATE CASCADE,
            CONSTRAINT ck_proceso_reentrenamiento_fase_actual CHECK (fase_actual BETWEEN 0 AND 7),
            CONSTRAINT ck_proceso_reentrenamiento_porcentaje_progreso CHECK (porcentaje_progreso BETWEEN 0 AND 100),
            CONSTRAINT ck_proceso_reentrenamiento_porcentaje_cpu CHECK (porcentaje_cpu IS NULL OR porcentaje_cpu BETWEEN 0 AND 100),
            CONSTRAINT ck_proceso_reentrenamiento_memoria_ram_mb CHECK (memoria_ram_mb IS NULL OR memoria_ram_mb >= 0),
            CONSTRAINT ck_proceso_reentrenamiento_completado_con_version
                CHECK (estado <> 'COMPLETADO' OR id_version_modelo_resultante IS NOT NULL),
            CONSTRAINT ck_proceso_reentrenamiento_fallido_con_codigo
                CHECK (estado <> 'FALLIDO' OR codigo_error IS NOT NULL),
            CONSTRAINT ck_proceso_reentrenamiento_fechas
                CHECK (fecha_fin IS NULL OR fecha_inicio IS NULL OR fecha_fin >= fecha_inicio)
        );

        -- Un solo proceso abierto por animal (BE-1 responde 409 antes; esto lo garantiza en BD).
        CREATE UNIQUE INDEX uq_proceso_reentrenamiento_id_activo_biologico
            ON modulo4.procesos_reentrenamiento (id_activo_biologico) WHERE estado IN ('PENDIENTE', 'EN_CURSO');
        -- La cola del motor y el listado de la pantalla (estado + antigüedad).
        CREATE INDEX idx_proceso_reentrenamiento_estado_fecha_solicitud
            ON modulo4.procesos_reentrenamiento (estado, fecha_solicitud);

        COMMENT ON TABLE modulo4.procesos_reentrenamiento IS
            'RF-71 (AJF-14): proceso de reentrenamiento del modelo individual de un animal, de la solicitud '
            'al registro de la versión (RF-69). Lo toma y actualiza el motor de IA con el usuario de servicio.';
        COMMENT ON COLUMN modulo4.procesos_reentrenamiento.json_fases IS
            'Lista de fases 1-7: [{"fase": n, "nombre": ..., "fecha_inicio": ..., "fecha_fin": ..., "resultado": ...}].';

        ALTER TABLE modulo4.procesos_reentrenamiento ENABLE ROW LEVEL SECURITY;
        ALTER TABLE modulo4.procesos_reentrenamiento FORCE ROW LEVEL SECURITY;

        CREATE POLICY pol_proceso_reentrenamiento_select ON modulo4.procesos_reentrenamiento
            FOR SELECT USING (EXISTS (SELECT 1 FROM modulo2.activos_biologicos ab WHERE ab.id_activo_biologico = procesos_reentrenamiento.id_activo_biologico AND ab.id_infraestructura IN (SELECT i.id_infraestructura FROM modulo9.fn_infraestructuras_del_usuario((SELECT modulo1.fn_id_usuario_actual())) i)));
        CREATE POLICY pol_proceso_reentrenamiento_insert ON modulo4.procesos_reentrenamiento
            FOR INSERT WITH CHECK (
                (SELECT modulo1.fn_tiene_permiso('version_modelo'::text, 'E'::text))
                AND id_usuario_solicitante = (SELECT modulo1.fn_id_usuario_actual())
                AND EXISTS (SELECT 1 FROM modulo2.activos_biologicos ab WHERE ab.id_activo_biologico = procesos_reentrenamiento.id_activo_biologico AND ab.id_infraestructura IN (SELECT i.id_infraestructura FROM modulo9.fn_infraestructuras_del_usuario((SELECT modulo1.fn_id_usuario_actual())) i))
            );
        CREATE POLICY pol_proceso_reentrenamiento_servicio ON modulo4.procesos_reentrenamiento
            FOR ALL USING ((SELECT modulo1.fn_es_usuario_servicio())) WITH CHECK ((SELECT modulo1.fn_es_usuario_servicio()));

        DO $$
        DECLARE r text;
        BEGIN
            FOR r IN SELECT rolname FROM pg_roles WHERE rolname IN ('sgpmp_app', 'rol_app', 'rol_dev', 'rol_impl', 'rol_migracion') LOOP
                EXECUTE format('GRANT SELECT, INSERT, UPDATE ON modulo4.procesos_reentrenamiento TO %I', r);
            END LOOP;
        END $$;;

UPDATE alembic_version SET version_num='21fe51f2aea1' WHERE alembic_version.version_num = '9b7d64203f48';

-- Running upgrade 21fe51f2aea1 -> bb5526687aae

DROP POLICY pol_bitacora_ingest_select ON modulo3.bitacora_ingest;
        CREATE POLICY pol_bitacora_ingest_select ON modulo3.bitacora_ingest
          FOR SELECT USING (
            ((SELECT modulo1.fn_tiene_permiso('bitacora_auditoria_iot', 'R'))
              OR (SELECT modulo1.fn_tiene_permiso('alertas_tecnicas_iot', 'R')))
            AND id_dispositivo_iot IN (SELECT d.id_dispositivo_iot FROM modulo9.fn_dispositivos_del_usuario((SELECT modulo1.fn_id_usuario_actual())) d));

        CREATE INDEX IF NOT EXISTS idx_bitacora_ingest_fecha_evento
            ON modulo3.bitacora_ingest (fecha_evento DESC);

        CREATE POLICY pol_parametro_mlops_select_operacion_iot ON modulo4.parametros_mlops
          FOR SELECT USING (
            (SELECT modulo1.fn_tiene_permiso('alertas_tecnicas_iot', 'R'))
            AND nombre_parametro IN ('intervalo_heartbeat_camara', 'intervalos_heartbeat_por_tipo', 'margen_tolerancia', 'tiempo_inactividad_extendida', 'ventanas_consecutivas_sin_deteccion', 'cobertura_minima_deteccion_valida', 'duracion_ventana_observacion'));;

UPDATE alembic_version SET version_num='bb5526687aae' WHERE alembic_version.version_num = '21fe51f2aea1';

COMMIT;

