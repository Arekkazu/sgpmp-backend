# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-28 | Arekkazu | Lote fixes M03/M04 RF-55: une el head del lote (#831) con el CRUD de reglas (#834) |
"""Une los dos heads del lote de fixes M03/M04 del 28-10 (segunda tanda).

- c83690f30edd (#831): unión de #806, #807, #811 y #813.
- 46252dbd62b4 (#834, RF-55 BE-0): recurso y permisos ``reglas_alertas``, trigger
  de versión de ``modulo3.reglas_alertas`` y GRANT a los roles de la app.

Las dos cuelgan de ebbb160365e5. #834 escribe en modulo1 (recursos/permisos) y
reemplaza ``modulo3.fn_regla_alerta_versionamiento``; ninguna de las cuatro ramas de
c83690f30edd toca esos objetos, así que el orden entre ellas da igual (probado
aplicándolas por separado y juntas, también el downgrade).

Revision ID: fa8be230f1bf
Revises: c83690f30edd, 46252dbd62b4
Create Date: 2026-10-28 22:00:00.000000

"""
from typing import Sequence, Union


# revision identifiers, used by Alembic.
revision: str = 'fa8be230f1bf'
down_revision: Union[str, Sequence[str], None] = ('c83690f30edd', '46252dbd62b4')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
