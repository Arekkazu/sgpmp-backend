"""fix_trg_unicidad_produccion_rfc009

Revision ID: a9d4d253ac97
Revises: 3a9d5e7c1b24
Create Date: 2026-10-19 09:39:11.260260

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a9d4d253ac97'
down_revision: Union[str, Sequence[str], None] = '3a9d5e7c1b24'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Se modifica la función del trigger para que la unicidad de esta_produccion 
    se evalúe agrupando por (algoritmo, tipo_modelo, componente) y no solo por algoritmo.
    Esto evita que activar un modelo de AVES apague el de PORCINOS.
    """
    op.execute("""
        CREATE OR REPLACE FUNCTION modulo4.trg_fn_versiones_modelos_unicidad_produccion()
        RETURNS TRIGGER AS $$
        BEGIN
            IF NEW.esta_produccion = true THEN
                UPDATE modulo4.versiones_modelos
                SET    esta_produccion = false
                WHERE  algoritmo         = NEW.algoritmo
                  AND  tipo_modelo       = NEW.tipo_modelo
                  AND  componente        = NEW.componente
                  AND  esta_produccion   = true
                  AND  id_version_modelo <> NEW.id_version_modelo;
            END IF;

            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)


def downgrade() -> None:
    """
    Revierte la función al comportamiento anterior (bug) que agrupaba solo por algoritmo.
    """
    op.execute("""
        CREATE OR REPLACE FUNCTION modulo4.trg_fn_versiones_modelos_unicidad_produccion()
        RETURNS TRIGGER AS $$
        BEGIN
            IF NEW.esta_produccion = true THEN
                UPDATE modulo4.versiones_modelos
                SET    esta_produccion = false
                WHERE  algoritmo        = NEW.algoritmo
                  AND  esta_produccion  = true
                  AND  id_version_modelo <> NEW.id_version_modelo;
            END IF;

            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)
