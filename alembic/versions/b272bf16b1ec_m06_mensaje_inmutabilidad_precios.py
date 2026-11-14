# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-08 | Arekkazu | INC-M06-295-G78 RF-89: el aviso de inmutabilidad de precios nombra id_precio_corregido |
"""m06 mensaje inmutabilidad precios: el aviso nombra la columna corregida

Revision ID: b272bf16b1ec
Revises: b7e2d94c1a68
Create Date: 2026-11-08

Requiere la autorización de SamuelPR21 (DBA) antes de desplegar.

La migración ``c4d81e6f2a95`` renombró ``modulo6.precios_mercado.id_precio_coregido`` a
``id_precio_corregido``, pero el mensaje del trigger ``tgr_m06_07_inmutabilidad_precios`` (del
baseline) seguía nombrando la columna vieja. Solo cambia el texto: misma función, misma firma, mismo
trigger; el mensaje deja de citar requisitos (regla de textos visibles de CLAUDE.md).
"""
from typing import Sequence, Union

from alembic import op


revision: str = 'b272bf16b1ec'
down_revision: Union[str, Sequence[str], None] = 'b7e2d94c1a68'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_FUNCION = """
CREATE OR REPLACE FUNCTION modulo6.fn_tgr_m06_07_inmutabilidad_precios()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$
BEGIN
    IF TG_OP = 'UPDATE' THEN
        RAISE EXCEPTION
            '[TGR-M06-07] El precio de mercado id=% no puede modificarse. '
            'El repositorio de precios es append-only e inmutable. '
            'Para corregir un precio erróneo, registre un nuevo precio con '
            '{columna}=% y la fecha_vigencia correspondiente.{cita_update}',
            OLD.id_precio_mercado, OLD.id_precio_mercado
        USING ERRCODE = 'P0001';
    END IF;

    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION
            '[TGR-M06-07] El precio de mercado id=% no puede eliminarse. '
            'El historial de precios es inmutable y permanente. '
            'Los registros históricos sustentan los cálculos de valor razonable auditados.{cita_delete}',
            OLD.id_precio_mercado
        USING ERRCODE = 'P0001';
    END IF;

    RETURN NEW;
END;
$function$
"""


def upgrade() -> None:
    op.execute(_FUNCION.format(columna="id_precio_corregido", cita_update="", cita_delete=""))


def downgrade() -> None:
    # Texto original del baseline.
    op.execute(_FUNCION.format(
        columna="id_precio_coregido",
        cita_update=" '\n            'Requerimiento RF-89, Restricciones y FA-6.",
        cita_delete=" '\n            'Requerimiento RF-89, Restricciones y CA-6.",
    ))
