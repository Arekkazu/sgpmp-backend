# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-26 | Arekkazu | Lote fixes M03/M04 RF-62/RF-68: une los heads de #790 y #786 |
"""Une los dos heads del lote de fixes M03/M04 del 26-10.

#790 (8d13c7e9a624, snapshot de calibración en fn_ingesta_telemetria, RF-62) y
#786 (9d3b6f1a2c74, alerta RIESGO_CONTAGIO y permiso E, RF-68) cuelgan ambos de
30168ab97bd4 y no tocan objetos en común, así que el orden entre ellos da igual.

Revision ID: ebbb160365e5
Revises: 8d13c7e9a624, 9d3b6f1a2c74
Create Date: 2026-10-26 22:07:51.961003

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ebbb160365e5'
down_revision: Union[str, Sequence[str], None] = ('8d13c7e9a624', '9d3b6f1a2c74')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
