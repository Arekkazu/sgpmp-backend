"""v5.2.0_rf41_reloj_eventos_activos

Revision ID: d6a8f2c941b7
Revises: b92f7e1a4c63
Create Date: 2026-09-12

``now()`` permanece fijo desde el inicio de la transacción. Los casos de uso
leen primero el activo y después generan la fecha del evento, por lo que una
fecha válida podía quedar unos milisegundos por delante de ``now()`` y activar
falsamente ``P0215``. ``clock_timestamp()`` representa el instante real de la
sentencia y conserva el rechazo de fechas verdaderamente futuras.
"""
from typing import Sequence, Union

from alembic import op


revision: str = "d6a8f2c941b7"
down_revision: Union[str, Sequence[str], None] = "b92f7e1a4c63"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_FUNCTION_TEMPLATE = """
CREATE OR REPLACE FUNCTION modulo2.trg_fn_evento_fecha_coherente()
RETURNS trigger
LANGUAGE plpgsql
AS $function$
DECLARE
    v_fecha_creacion TIMESTAMPTZ;
BEGIN
    IF NEW.fecha > {reloj} THEN
        RAISE EXCEPTION 'INVALID_DATE: La fecha del evento (%) no puede ser futura. Fecha actual del sistema: %.', NEW.fecha, {reloj}
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
$function$;
"""


def _recrear_validaciones_temporales(reloj: str) -> None:
    op.execute(_FUNCTION_TEMPLATE.format(reloj=reloj))
    op.drop_constraint(
        "chk_eventos_fecha_no_futura",
        "eventos_activos",
        schema="modulo2",
        type_="check",
    )
    op.create_check_constraint(
        "chk_eventos_fecha_no_futura",
        "eventos_activos",
        f"fecha <= {reloj}",
        schema="modulo2",
    )


def upgrade() -> None:
    _recrear_validaciones_temporales("clock_timestamp()")


def downgrade() -> None:
    _recrear_validaciones_temporales("now()")
