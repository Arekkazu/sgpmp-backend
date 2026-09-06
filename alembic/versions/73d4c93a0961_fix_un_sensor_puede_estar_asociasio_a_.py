"""fix: Un sensor puede estar asociasio a una area, en tanto eset disponible y no tenga otra asosiacion

Revision ID: 73d4c93a0961
Revises: 56cd2038ff06
Create Date: 2026-09-06 15:45:11.754734


"""

from alembic import op


# revision identifiers, used by Alembic.
revision = 'xxxx'
down_revision = '<pon aqui el head actual de dev>'
branch_labels = None
depends_on = None


def upgrade():
    # La regla "sensor fijo de por vida" queda obsoleta: RF-22 exige poder
    # reasignar un sensor entre areas (cierre de asociacion anterior +
    # apertura de la nueva). La unica regla vigente que debe permanecer es
    # trg_sensor_asociacion_unica_activa (una sola asociacion activa a la vez),
    # que no se toca en esta migracion.
    
    op.execute("""
        DROP TRIGGER IF EXISTS trg_sensor_asociacion_infraestructura_fija
        ON modulo9.sensores_areas_asociadas;
    """)
    op.execute("""
        DROP FUNCTION IF EXISTS modulo9.trg_fn_sensor_asociacion_infraestructura_fija();
    """)


def downgrade():
    op.execute("""
        CREATE FUNCTION modulo9.trg_fn_sensor_asociacion_infraestructura_fija() RETURNS trigger
            LANGUAGE plpgsql
            AS $$
        DECLARE
            v_infra_actual INTEGER;
        BEGIN
            SELECT DISTINCT id_infraestructura
            INTO v_infra_actual
            FROM modulo9.sensores_areas_asociadas
            WHERE id_sensor = NEW.id_sensor
            LIMIT 1;

            IF v_infra_actual IS NOT NULL AND v_infra_actual <> NEW.id_infraestructura THEN
                RAISE EXCEPTION
                    'SENSOR_INFRAESTRUCTURA_FIJA: El sensor ID % ya esta vinculado '
                    'de por vida a la infraestructura ID %. No puede ser reasignado a '
                    'la infraestructura ID %. Los sensores no se reubican en el sistema.',
                    NEW.id_sensor, v_infra_actual, NEW.id_infraestructura
                    USING ERRCODE = 'P0140';
            END IF;

            RETURN NEW;
        END;
        $$;
    """)
    op.execute("""
        CREATE TRIGGER trg_sensor_asociacion_infraestructura_fija
        BEFORE INSERT ON modulo9.sensores_areas_asociadas
        FOR EACH ROW EXECUTE FUNCTION modulo9.trg_fn_sensor_asociacion_infraestructura_fija();
    """)