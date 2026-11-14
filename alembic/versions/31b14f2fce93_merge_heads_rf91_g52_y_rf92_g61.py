# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-13 | Arekkazu | Lote M05/M06 13-11 RF-91/RF-92: une los heads de #1115 y #1119 |
"""Une los dos heads del lote M05/M06 del 13-11.

#1115 (f110491a0001, lectura de las fuentes auditadas de la trazabilidad, RF-91) y
#1119 (f110692a0001, lectura de los supuestos de medición, RF-92) cuelgan ambos de
0884ba08a944 y solo dan GRANT sobre tablas distintas, así que el orden entre ellos da igual.

Revision ID: 31b14f2fce93
Revises: f110491a0001, f110692a0001
Create Date: 2026-11-13

"""
from typing import Sequence, Union


# revision identifiers, used by Alembic.
revision: str = '31b14f2fce93'
down_revision: Union[str, Sequence[str], None] = ('f110491a0001', 'f110692a0001')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
