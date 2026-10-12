"""agregar constraint de coherencia en bitacora

Revision ID: 6d8b88392ac8
Revises: 1147428cd8fb
Create Date: 2026-09-18 16:57:04.223997

INC-M02-G22: el constraint se crea ``NOT VALID``. Antes de 9c05d30d toda
consulta de un lote POBLACIONAL se auditaba como ``ACTIVO_INDIVIDUAL_CONSULTA``,
así que la bitácora ya trae filas históricas que lo violan y el ``ADD
CONSTRAINT`` validado abortaba ``alembic upgrade head``. La bitácora es
histórica: no se reescribe, solo se exige la regla a las filas nuevas. De paso
el nombre pasa de ``chk_`` a ``ck_`` (convención de nomenclatura de BD); esta
revisión no había llegado a aplicarse en DEV ni en TEST (el deploy de
#387 cortó en el check de heads, antes del upgrade).
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
        'ck_coherencia_auditoria_evento',
        'bitacora_auditoria_m02',
        "NOT (tipo_activo = 'POBLACIONAL' AND tipo_evento = 'ACTIVO_INDIVIDUAL_CONSULTA')",
        schema='modulo2',
        postgresql_not_valid=True,
    )

def downgrade():
    op.drop_constraint(
        'ck_coherencia_auditoria_evento',
        'bitacora_auditoria_m02',
        type_='check',
        schema='modulo2'
    )
