"""agregar constraint de coherencia en bitacora

Revision ID: 6d8b88392ac8
Revises: 1147428cd8fb
Create Date: 2026-09-18 16:57:04.223997

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6d8b88392ac8'
down_revision: Union[str, Sequence[str], None] = '1147428cd8fb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.create_check_constraint(
        'chk_coherencia_auditoria_eventos',
        'bitacora_auditoria_m02',
        "NOT (tipo_activo = 'POBLACIONAL' AND tipo_evento = 'ACTIVO_INDIVIDUAL_CONSULTA')",
        schema='modulo2'
    )

def downgrade():
    op.drop_constraint(
        'chk_coherencia_auditoria_eventos',
        'bitacora_auditoria_m02',
        type_='check',
        schema='modulo2'
    )