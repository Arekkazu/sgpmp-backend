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
    se evalúe agrupando por (tipo_modelo, componente) según RFC-009 y DB-01.
    
    Cambios:
    - Se elimina 'algoritmo' del WHERE (DB-01 pide agrupar solo por tipo_modelo y componente)
    - Se usa IS NOT DISTINCT FROM para manejar correctamente NULLs en componente
    - Esto evita que cambiar de algoritmo dentro del mismo componente deje dos versiones en producción
    - También maneja el caso de modelos sin componente (NULL)
    """
    op.execute("""
        CREATE OR REPLACE FUNCTION modulo4.trg_fn_versiones_modelos_unicidad_produccion()
        RETURNS TRIGGER AS $$
        BEGIN
            IF NEW.esta_produccion = true THEN
                UPDATE modulo4.versiones_modelos
                SET    esta_produccion = false
                WHERE  tipo_modelo       IS NOT DISTINCT FROM NEW.tipo_modelo
                  AND  componente        IS NOT DISTINCT FROM NEW.componente
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