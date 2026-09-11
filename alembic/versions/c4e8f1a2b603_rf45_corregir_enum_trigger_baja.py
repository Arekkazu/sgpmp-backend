"""RF-45: corregir el enum usado al actualizar la cantidad de un lote.

Revision ID: c4e8f1a2b603
Revises: b92f7e1a4c63
Create Date: 2026-09-11

``enum_activo_biologico_tipo`` usa valores en mayúsculas. Las funciones del
baseline comparaban contra ``'poblacional'`` y PostgreSQL abortaba cualquier
INSERT en ``eventos_bajas`` al intentar convertir ese literal al enum, incluso
para un activo individual. En ``sgpmp_dev`` la validación previa ya estaba
corregida, pero el trigger posterior todavía conservaba el literal inválido.
"""
from typing import Sequence, Union

from alembic import op


revision: str = 'c4e8f1a2b603'
down_revision: Union[str, Sequence[str], None] = 'b92f7e1a4c63'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_FUNCTION_TEMPLATE = """
CREATE OR REPLACE FUNCTION modulo2.trg_fn_baja_actualizar_cantidad_lote()
RETURNS trigger
LANGUAGE plpgsql
AS $function$
DECLARE
    v_activo_id   INTEGER;
    v_tipo_activo modulo2.enum_activo_biologico_tipo;
    v_infra_id    INTEGER;
    v_superficie  NUMERIC(10,2);
BEGIN
    SELECT a.id_activo_biologico, a.tipo, a.id_infraestructura
    INTO v_activo_id, v_tipo_activo, v_infra_id
    FROM modulo2.activos_biologicos a
    JOIN modulo2.eventos_activos ea
      ON ea.id_activo_biologico = a.id_activo_biologico
    WHERE ea.id_eventos = NEW.id_evento;

    IF v_tipo_activo <> '{tipo_poblacional}' THEN
        RETURN NEW;
    END IF;

    SELECT superficie INTO v_superficie
    FROM modulo9.infraestructuras
    WHERE id_infraestructura = v_infra_id;

    UPDATE modulo2.detalles_activos_biologicos_poblacionales
    SET cantidad_actual = GREATEST(0, cantidad_actual - NEW.cantidad_afectada),
        biomasa_total = GREATEST(0, cantidad_actual - NEW.cantidad_afectada) * peso_promedio,
        densidad = CASE
            WHEN v_superficie IS NOT NULL AND v_superficie > 0
            THEN GREATEST(0, cantidad_actual - NEW.cantidad_afectada)::NUMERIC / v_superficie
            ELSE 0
        END
    WHERE id_activo_biologico = v_activo_id;

    RETURN NEW;
END;
$function$;
"""


_VALIDATION_FUNCTION_TEMPLATE = """
CREATE OR REPLACE FUNCTION modulo2.trg_fn_baja_cantidad_valida()
RETURNS trigger
LANGUAGE plpgsql
AS $function$
DECLARE
    v_activo_id       INTEGER;
    v_tipo_activo     modulo2.enum_activo_biologico_tipo;
    v_cantidad_actual INTEGER;
BEGIN
    SELECT a.id_activo_biologico, a.tipo
    INTO v_activo_id, v_tipo_activo
    FROM modulo2.activos_biologicos a
    JOIN modulo2.eventos_activos ea
      ON ea.id_activo_biologico = a.id_activo_biologico
    WHERE ea.id_eventos = NEW.id_evento;

    IF v_tipo_activo = '{tipo_poblacional}' THEN
        IF NEW.cantidad_afectada IS NULL OR NEW.cantidad_afectada <= 0 THEN
            RAISE EXCEPTION 'INVALID_VALUE: Para bajas en lotes la cantidad_afectada debe ser mayor a cero. Valor recibido: %.', NEW.cantidad_afectada
            USING ERRCODE = 'P0224';
        END IF;

        SELECT cantidad_actual INTO v_cantidad_actual
        FROM modulo2.detalles_activos_biologicos_poblacionales
        WHERE id_activo_biologico = v_activo_id;

        IF NEW.cantidad_afectada > v_cantidad_actual THEN
            RAISE EXCEPTION 'INVENTORY_INCONSISTENCY: La cantidad a dar de baja (%) es superior a la existencia actual del lote (%). Activo ID %.', NEW.cantidad_afectada, v_cantidad_actual, v_activo_id
            USING ERRCODE = 'P0225';
        END IF;
    END IF;

    RETURN NEW;
END;
$function$;
"""


def upgrade() -> None:
    op.execute(_VALIDATION_FUNCTION_TEMPLATE.format(tipo_poblacional='POBLACIONAL'))
    op.execute(_FUNCTION_TEMPLATE.format(tipo_poblacional='POBLACIONAL'))


def downgrade() -> None:
    op.execute(_VALIDATION_FUNCTION_TEMPLATE.format(tipo_poblacional='poblacional'))
    op.execute(_FUNCTION_TEMPLATE.format(tipo_poblacional='poblacional'))
