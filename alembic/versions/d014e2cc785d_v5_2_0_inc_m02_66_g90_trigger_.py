"""v5.2.0_inc_m02_66_g90_trigger_asociacion_sensor_unica

Revision ID: d014e2cc785d
Revises: 0b9cdb05af53
Create Date: 2026-09-15 02:06:25.960998

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd014e2cc785d'
down_revision: Union[str, Sequence[str], None] = '0b9cdb05af53'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # INC-M02-66-G90 (issue #216): el trigger evaluaba `fecha_fin > now()` para
    # detectar conflicto de unicidad en asociaciones DIRECTA. `now()` (alias de
    # `transaction_timestamp()`) queda congelado al inicio de la transaccion;
    # el use case actualiza la asociacion previa a SUPERADA con
    # `fecha_fin = clock_timestamp()` (posterior al inicio de la transaccion)
    # y luego inserta la nueva -- `fecha_fin > now()` evalua TRUE incluso para
    # la fila que la propia transaccion acaba de superar, bloqueando el INSERT
    # con `P0229` y devolviendo 500 al reemplazar un sensor DIRECTA sobre el
    # mismo activo (mismo patron de bug que INC-M02-75-G53, otro trigger de
    # este modulo). Ademas nunca excluia el propio id_activo_biologico ni las
    # filas ya en estado SUPERADA/INACTIVA del conteo.
    #
    # Esta migracion formaliza una correccion que ya estaba aplicada
    # manualmente en la base de datos compartida (fuera de Alembic, sin
    # ninguna revision que la registrara) -- se verifico con
    # `pg_get_functiondef` contra la funcion en vivo y este `CREATE OR REPLACE`
    # reproduce exactamente ese texto, para que una base de datos nueva
    # construida desde `baseline + migraciones` tambien quede corregida.
    op.execute("""
    CREATE OR REPLACE FUNCTION modulo2.trg_fn_asociacion_sensor_activo_unica()
    RETURNS trigger
    LANGUAGE plpgsql
    AS $function$
    DECLARE
        v_count INTEGER;
    BEGIN
        IF NEW.tipo = 'directa' THEN
            SELECT COUNT(*) INTO v_count
            FROM modulo2.asociaciones_activos_sensores
            WHERE id_sensor = NEW.id_sensor
              AND tipo = 'directa'
              AND estado_asociacion = 'ACTIVA'
              AND fecha_fin IS NULL
              AND id_activo_biologico IS DISTINCT FROM NEW.id_activo_biologico;

            IF v_count > 0 THEN
                RAISE EXCEPTION 'SENSOR_CONFLICT: El sensor ID % ya tiene una asociación directa activa con otro activo individual. Desactive la asociación existente antes de crear una nueva.', NEW.id_sensor
                USING ERRCODE = 'P0229';
            END IF;
        END IF;

        RETURN NEW;
    END;
    $function$
    """)


def downgrade() -> None:
    op.execute("""
    CREATE OR REPLACE FUNCTION modulo2.trg_fn_asociacion_sensor_activo_unica()
    RETURNS trigger
    LANGUAGE plpgsql
    AS $function$
    DECLARE
        v_count INTEGER;
    BEGIN
        IF NEW.tipo = 'directa' THEN
            SELECT COUNT(*) INTO v_count
            FROM modulo2.asociaciones_activos_sensores
            WHERE id_sensor  = NEW.id_sensor
              AND fecha_fin  > now()
              AND tipo       = 'directa';

            IF v_count > 0 THEN
                RAISE EXCEPTION 'SENSOR_CONFLICT: El sensor ID % ya tiene una asociación directa activa con otro activo individual. Desactive la asociación existente antes de crear una nueva.', NEW.id_sensor
                USING ERRCODE = 'P0229';
            END IF;
        END IF;

        RETURN NEW;
    END;
    $function$
    """)
