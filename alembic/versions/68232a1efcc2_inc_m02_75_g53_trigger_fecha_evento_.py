"""inc_m02_75_g53_trigger_fecha_evento_clock_timestamp

Revision ID: 68232a1efcc2
Revises: b92f7e1a4c63
Create Date: 2026-09-12 06:27:23.311686

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '68232a1efcc2'
down_revision: Union[str, Sequence[str], None] = 'b92f7e1a4c63'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # INC-M02-75-G53: `now()` (alias de `CURRENT_TIMESTAMP`) queda fijo al
    # inicio de la transaccion, no al momento del INSERT. El use case abre la
    # transaccion en su primera consulta (ej. obtener_por_id del activo) y
    # calcula `fecha = datetime.now(timezone.utc)` despues, ya con la
    # transaccion abierta -> `NEW.fecha` (reloj real, mas tardio) siempre
    # termina siendo posterior al `now()` congelado, y el trigger rechaza un
    # evento que en tiempo real nunca fue futuro. `clock_timestamp()` no se
    # congela por transaccion, se reevalua en cada llamada.
    op.execute("""
    CREATE OR REPLACE FUNCTION modulo2.trg_fn_evento_fecha_coherente()
    RETURNS trigger
    LANGUAGE plpgsql
    AS $function$
    DECLARE
        v_fecha_creacion TIMESTAMPTZ;
    BEGIN
        IF NEW.fecha > clock_timestamp() THEN
            RAISE EXCEPTION 'INVALID_DATE: La fecha del evento (%) no puede ser futura. Fecha actual del sistema: %.', NEW.fecha, clock_timestamp()
            USING ERRCODE = 'P0215';
        END IF;

        SELECT fecha_creacion INTO v_fecha_creacion
        FROM modulo2.activos_biologicos
        WHERE id_activo_biologico = NEW.id_activo_biologico;

        IF v_fecha_creacion IS NOT NULL AND NEW.fecha < v_fecha_creacion THEN
            RAISE EXCEPTION 'INVALID_DATE: La fecha del evento (%) no puede ser anterior a la fecha de registro del activo (%).', NEW.fecha, v_fecha_creacion
            USING ERRCODE = 'P0215';
        END IF;

        RETURN NEW;
    END;
    $function$
    """)

    # Mismo problema, en el CHECK de columna de la misma tabla: `now()` fijo
    # por transaccion rechazaba la misma fecha valida que el trigger de arriba.
    op.execute("""
    ALTER TABLE modulo2.eventos_activos
    DROP CONSTRAINT chk_eventos_fecha_no_futura
    """)
    op.execute("""
    ALTER TABLE modulo2.eventos_activos
    ADD CONSTRAINT chk_eventos_fecha_no_futura CHECK (fecha <= clock_timestamp())
    """)


def downgrade() -> None:
    op.execute("""
    ALTER TABLE modulo2.eventos_activos
    DROP CONSTRAINT chk_eventos_fecha_no_futura
    """)
    op.execute("""
    ALTER TABLE modulo2.eventos_activos
    ADD CONSTRAINT chk_eventos_fecha_no_futura CHECK (fecha <= now())
    """)
    op.execute("""
    CREATE OR REPLACE FUNCTION modulo2.trg_fn_evento_fecha_coherente()
    RETURNS trigger
    LANGUAGE plpgsql
    AS $function$
    DECLARE
        v_fecha_creacion TIMESTAMPTZ;
    BEGIN
        IF NEW.fecha > now() THEN
            RAISE EXCEPTION 'INVALID_DATE: La fecha del evento (%) no puede ser futura. Fecha actual del sistema: %.', NEW.fecha, now()
            USING ERRCODE = 'P0215';
        END IF;

        SELECT fecha_creacion INTO v_fecha_creacion
        FROM modulo2.activos_biologicos
        WHERE id_activo_biologico = NEW.id_activo_biologico;

        IF v_fecha_creacion IS NOT NULL AND NEW.fecha < v_fecha_creacion THEN
            RAISE EXCEPTION 'INVALID_DATE: La fecha del evento (%) no puede ser anterior a la fecha de registro del activo (%).', NEW.fecha, v_fecha_creacion
            USING ERRCODE = 'P0215';
        END IF;

        RETURN NEW;
    END;
    $function$
    """)
