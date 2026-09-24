"""v5.3.0_rf36_densidad_maxima_por_especie

Revision ID: 7abae1ee50f6
Revises: c8d4f1a9b7e2
Create Date: 2026-09-20 20:58:55.373100

RF-36 exige que la densidad máxima sea una validación por especie definida en
M09. La implementación anterior la infería de ``infraestructuras.capacidad_maxima``
(cupo físico de una instalación), dato que además está en NULL en los ambientes
actuales. Esta revisión agrega la parametrización contractual a la especie.

Las filas existentes quedan en NULL deliberadamente: no se inventan límites
biológicos. Mientras el Administrador no configure el valor mediante RF-15,
M02 rechaza los flujos poblacionales con un error controlado y no omite la
validación silenciosamente.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7abae1ee50f6'
down_revision: Union[str, Sequence[str], None] = 'c8d4f1a9b7e2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'especies',
        sa.Column(
            'densidad_maxima_por_especie',
            sa.Numeric(10, 4),
            nullable=True,
            comment=(
                'Densidad máxima permitida para lotes de la especie, expresada '
                'en individuos por unidad de superficie (RF-36).'
            ),
        ),
        schema='modulo9',
    )
    op.create_check_constraint(
        'ck_especies_densidad_maxima_positiva',
        'especies',
        'densidad_maxima_por_especie IS NULL OR densidad_maxima_por_especie > 0',
        schema='modulo9',
    )


def downgrade() -> None:
    op.drop_constraint(
        'ck_especies_densidad_maxima_positiva',
        'especies',
        schema='modulo9',
        type_='check',
    )
    op.drop_column('especies', 'densidad_maxima_por_especie', schema='modulo9')
