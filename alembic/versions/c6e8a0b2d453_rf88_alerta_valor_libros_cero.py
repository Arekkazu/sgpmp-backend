# | Fecha      | Nombre         | Que se hizo                                                              |
# |------------|----------------|--------------------------------------------------------------------------|
# | 2026-11-09 | LuisfNarvaez01 | INC-M06-281-G68-07 RF-88: alerta persistente al llevar el valor en libros a cero |
"""rf88: tipo de evento VALOR_LIBROS_AJUSTADO_A_CERO en la auditoría financiera

Revision ID: c6e8a0b2d453
Revises: b3d5f7a9c142
Create Date: 2026-11-09

INC-M06-281-G68-07 (#968). RF-88: el valor en libros de un activo valorado por costo
(costo − depreciación acumulada − deterioro) nunca es negativo; cuando el resultado
matemático lo es, se ajusta a cero. El ajuste ya se aplicaba, pero solo quedaba el evento
genérico DETERIORO_REGISTRADO y un aviso en la respuesta. Este tipo de evento deja una
alerta persistente, consultable por activo en la auditoría financiera, con el valor
calculado y el aplicado.

``downgrade`` no quita el valor: PostgreSQL no borra valores de un ENUM.
"""
from typing import Sequence, Union

from alembic import op

revision: str = 'c6e8a0b2d453'
down_revision: Union[str, Sequence[str], None] = 'b3d5f7a9c142'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE modulo6.enum_auditoria_financiera_tipo_evento "
                   "ADD VALUE IF NOT EXISTS 'VALOR_LIBROS_AJUSTADO_A_CERO' AFTER 'DETERIORO_REGISTRADO'")


def downgrade() -> None:
    pass
