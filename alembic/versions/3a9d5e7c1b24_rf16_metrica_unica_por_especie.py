"""RF-16: nombre de métrica productiva único por especie, no global

Revision ID: 3a9d5e7c1b24
Revises: b4e7c91d2a63
Create Date: 2026-10-13 12:00:00

RF-16 exige que el nombre de cada métrica productiva sea "único por especie"
(case-insensitive). El caso de uso ya valida así, pero
`trg_fn_metricas_produccion_nombre_unique_ci` contaba coincidencias en todas
las especies: registrar "Peso vivo" en Tilapia Roja Dos fallaba con
P0109 DUPLICATE_METRIC porque Cachama Blanca ya tenía "peso vivo".

Se agrega el filtro por especie, igual que el trigger hermano de etapas
(`trg_fn_ciclos_biologicos_nombre_unique_ci`). `IS NOT DISTINCT FROM` y no `=`
porque `id_especie` admite NULL (métricas sin especie): con `=` dos de ellas
con el mismo nombre dejarían de chocar.
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '3a9d5e7c1b24'
down_revision: Union[str, Sequence[str], None] = 'b4e7c91d2a63'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _funcion(filtro_especie: str) -> str:
    return f"""
    CREATE OR REPLACE FUNCTION modulo9.trg_fn_metricas_produccion_nombre_unique_ci()
    RETURNS trigger
    LANGUAGE plpgsql
    AS $function$
    DECLARE
        v_count INTEGER;
    BEGIN
        SELECT COUNT(*) INTO v_count
        FROM modulo9.metricas_produccion
        WHERE LOWER(TRIM(nombre))    = LOWER(TRIM(NEW.nombre)){filtro_especie}
          AND es_activo              = true
          AND id_metrica_produccion <> COALESCE(NEW.id_metrica_produccion, -1);

        IF v_count > 0 THEN
            RAISE EXCEPTION 'DUPLICATE_METRIC: Ya existe una métrica productiva con el nombre "%" (case-insensitive).',
                NEW.nombre
                USING ERRCODE = 'P0109';
        END IF;

        RETURN NEW;
    END;
    $function$
    """


def upgrade() -> None:
    op.execute(_funcion("\n          AND id_especie IS NOT DISTINCT FROM NEW.id_especie"))


def downgrade() -> None:
    op.execute(_funcion(""))
