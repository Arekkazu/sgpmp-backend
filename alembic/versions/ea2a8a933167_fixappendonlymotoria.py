"""FixAppendOnlyMotorIA

Revision ID: ea2a8a933167
Revises: e5a3c9b17d42
Create Date: 2026-10-21 23:58:20.248329

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ea2a8a933167'
down_revision: Union[str, Sequence[str], None] = 'e5a3c9b17d42'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None



def upgrade() -> None:
    # ------------------------------------------------------------------
    # 1. Tabla de log
    # ------------------------------------------------------------------
    op.execute(
        """
        CREATE TABLE modulo4.configuracion_ia_log
        (
            id_log bigint GENERATED ALWAYS AS IDENTITY,
            id_configuracion_motor integer NOT NULL,
            operacion varchar(10) NOT NULL,

            -- Snapshot de la fila anterior de configuraciones_motor_ia
            tipo_modelo modulo4.enum_tipo_modelo NOT NULL,
            umbral_riesgo_alto numeric(4,3),
            umbral_alerta_critica numeric(4,3),
            ventana_temporal_min integer NOT NULL,
            id_version_modelo_activa integer,
            modo_ejecucion modulo4.enum_modo_ejecucion NOT NULL,
            config_version integer NOT NULL,
            w_factor_sanitario numeric(4,3) NOT NULL,
            w_factor_ambiental numeric(4,3) NOT NULL,
            w_factor_densidad numeric(4,3) NOT NULL,
            temp_min_config numeric(6,2),
            temp_max_config numeric(6,2),
            hr_min_config numeric(6,2),
            hr_max_config numeric(6,2),
            densidad_maxima_config numeric(10,4),
            es_activa boolean NOT NULL,
            id_usuario_responsable integer NOT NULL,
            fecha_creacion_config timestamp with time zone NOT NULL,
            umbral_score_anomalia numeric(4,3),
            versiones_activas_por_componente jsonb,

            -- Metadatos del cambio
            id_usuario_cambio integer,
            fecha_cambio timestamp with time zone NOT NULL DEFAULT now(),

            CONSTRAINT configuracion_ia_log_pkey PRIMARY KEY (id_log),
            CONSTRAINT ck_configuracion_ia_log_operacion
                CHECK (operacion IN ('UPDATE', 'DELETE'))
        )
        """
    )

    op.execute(
        """
        CREATE INDEX idx_configuracion_ia_log_config_version
            ON modulo4.configuracion_ia_log
            (id_configuracion_motor, config_version DESC, id_log DESC)
        """
    )
    op.execute(
        """
        CREATE INDEX idx_configuracion_ia_log_fecha
            ON modulo4.configuracion_ia_log (fecha_cambio DESC)
        """
    )

    op.execute("ALTER TABLE modulo4.configuracion_ia_log OWNER TO sgpmp_owner")

    # Solo lectura para los roles; los INSERT los hace la función del trigger
    # (SECURITY DEFINER, owner sgpmp_owner).
    for rol in (
        "rol_aiot", "rol_app", "rol_dev", "rol_impl", "rol_migracion", "sgpmp_app",
    ):
        op.execute(f"REVOKE ALL ON TABLE modulo4.configuracion_ia_log FROM {rol}")
        op.execute(f"GRANT SELECT ON TABLE modulo4.configuracion_ia_log TO {rol}")
    op.execute("GRANT ALL ON TABLE modulo4.configuracion_ia_log TO sgpmp_owner")

    op.execute(
        """
        COMMENT ON TABLE modulo4.configuracion_ia_log IS
        'RF-65 (Restricción 5): historial append-only de modulo4.configuraciones_motor_ia. Cada fila es la versión ANTERIOR de la configuración al momento de un UPDATE/DELETE, con su config_version, el usuario que hizo el cambio y la fecha. Inmutable: no admite UPDATE, DELETE ni TRUNCATE.'
        """
    )
    op.execute(
        """
        COMMENT ON COLUMN modulo4.configuracion_ia_log.id_usuario_cambio IS
        'Usuario que realizó el cambio (id_usuario_responsable de la fila nueva). NULL en DELETE.'
        """
    )
    op.execute(
        """
        COMMENT ON COLUMN modulo4.configuracion_ia_log.fecha_creacion_config IS
        'fecha_creacion de la fila de configuración original (no la fecha del cambio; esa es fecha_cambio).'
        """
    )

    # ------------------------------------------------------------------
    # 2. Función que copia OLD al log
    # ------------------------------------------------------------------
    op.execute(
        r"""
CREATE OR REPLACE FUNCTION modulo4.fn_rf65_log_configuracion_motor()
    RETURNS trigger
    LANGUAGE 'plpgsql'
    COST 100
    VOLATILE NOT LEAKPROOF
    SECURITY DEFINER
    SET search_path = pg_catalog, pg_temp
AS $BODY$
BEGIN
    INSERT INTO modulo4.configuracion_ia_log (
        id_configuracion_motor, operacion,
        tipo_modelo, umbral_riesgo_alto, umbral_alerta_critica,
        ventana_temporal_min, id_version_modelo_activa, modo_ejecucion,
        config_version,
        w_factor_sanitario, w_factor_ambiental, w_factor_densidad,
        temp_min_config, temp_max_config, hr_min_config, hr_max_config,
        densidad_maxima_config, es_activa,
        id_usuario_responsable, fecha_creacion_config,
        umbral_score_anomalia, versiones_activas_por_componente,
        id_usuario_cambio, fecha_cambio
    ) VALUES (
        OLD.id_configuracion_motor, TG_OP,
        OLD.tipo_modelo, OLD.umbral_riesgo_alto, OLD.umbral_alerta_critica,
        OLD.ventana_temporal_min, OLD.id_version_modelo_activa, OLD.modo_ejecucion,
        OLD.config_version,
        OLD.w_factor_sanitario, OLD.w_factor_ambiental, OLD.w_factor_densidad,
        OLD.temp_min_config, OLD.temp_max_config, OLD.hr_min_config, OLD.hr_max_config,
        OLD.densidad_maxima_config, OLD.es_activa,
        OLD.id_usuario_responsable, OLD.fecha_creacion,
        OLD.umbral_score_anomalia, OLD.versiones_activas_por_componente,
        CASE WHEN TG_OP = 'UPDATE' THEN NEW.id_usuario_responsable END,
        now()
    );

    RETURN NULL;  -- trigger AFTER: el valor de retorno se ignora
END;
$BODY$;
        """
    )
    op.execute(
        "ALTER FUNCTION modulo4.fn_rf65_log_configuracion_motor() OWNER TO sgpmp_owner"
    )

    # ------------------------------------------------------------------
    # 3. Función que protege el log (append-only)
    # ------------------------------------------------------------------
    op.execute(
        r"""
CREATE OR REPLACE FUNCTION modulo4.fn_rf65_log_inmutable()
    RETURNS trigger
    LANGUAGE 'plpgsql'
    COST 100
    VOLATILE NOT LEAKPROOF
AS $BODY$
BEGIN
    RAISE EXCEPTION
        'RF-65 [APPEND-ONLY]: modulo4.configuracion_ia_log es inmutable (% no permitido).',
        TG_OP;
    RETURN NULL;
END;
$BODY$;
        """
    )
    op.execute("ALTER FUNCTION modulo4.fn_rf65_log_inmutable() OWNER TO sgpmp_owner")

    # ------------------------------------------------------------------
    # 4. Triggers
    # ------------------------------------------------------------------
    # 4a. Sobre la tabla de configuración: alimentan el log
    op.execute(
        """
        CREATE TRIGGER trg_rf65_01_log_update
            AFTER UPDATE ON modulo4.configuraciones_motor_ia
            FOR EACH ROW
            WHEN (OLD.* IS DISTINCT FROM NEW.*)
            EXECUTE FUNCTION modulo4.fn_rf65_log_configuracion_motor()
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_rf65_02_log_delete
            AFTER DELETE ON modulo4.configuraciones_motor_ia
            FOR EACH ROW
            EXECUTE FUNCTION modulo4.fn_rf65_log_configuracion_motor()
        """
    )

    # 4b. Sobre el log: lo vuelven inmutable
    op.execute(
        """
        CREATE TRIGGER trg_rf65_log_01_inmutable
            BEFORE UPDATE OR DELETE ON modulo4.configuracion_ia_log
            FOR EACH ROW
            EXECUTE FUNCTION modulo4.fn_rf65_log_inmutable()
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_rf65_log_02_no_truncate
            BEFORE TRUNCATE ON modulo4.configuracion_ia_log
            FOR EACH STATEMENT
            EXECUTE FUNCTION modulo4.fn_rf65_log_inmutable()
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS trg_rf65_02_log_delete ON modulo4.configuraciones_motor_ia"
    )
    op.execute(
        "DROP TRIGGER IF EXISTS trg_rf65_01_log_update ON modulo4.configuraciones_motor_ia"
    )
    op.execute(
        "DROP TRIGGER IF EXISTS trg_rf65_log_02_no_truncate ON modulo4.configuracion_ia_log"
    )
    op.execute(
        "DROP TRIGGER IF EXISTS trg_rf65_log_01_inmutable ON modulo4.configuracion_ia_log"
    )

    op.execute("DROP FUNCTION IF EXISTS modulo4.fn_rf65_log_inmutable()")
    op.execute("DROP FUNCTION IF EXISTS modulo4.fn_rf65_log_configuracion_motor()")

    # Se pierde el historial acumulado
    op.execute("DROP TABLE IF EXISTS modulo4.configuracion_ia_log")