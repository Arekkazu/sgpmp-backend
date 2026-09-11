"""RF-44: distinguir el origen del cambio de estado (MANUAL/RF-38/RF-45).

Revision ID: f19e0ca62445
Revises: 2dbb6d44046f
Create Date: 2026-09-04 13:28:23.057542

El CHECK ``chk_historico_modulo_origen_valido`` solo aceptaba literales
``modulo1``..``modulo9``, por lo que los tres flujos de cambio de estado de
RF-44 (manual, cierre de ciclo RF-38 y baja RF-45) quedaban indistinguibles:
todos grababan ``modulo2``. El propio RF-44 exige ``MANUAL``/``RF-38``/``RF-45``.

Se amplía el CHECK para aceptar esos tres valores. Se conservan
``modulo1``..``modulo9`` porque otros módulos escriben legítimamente su
identificador en esta tabla (p. ej. supplies/modulo5 vía el adaptador de
estado activo de RF-76), y para no romper filas históricas ya existentes.
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'f19e0ca62445'
down_revision: Union[str, Sequence[str], None] = '2dbb6d44046f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_VALORES_ORIGEN = (
    "'MANUAL', 'RF-38', 'RF-45', "
    "'modulo1', 'modulo2', 'modulo3', 'modulo4', 'modulo5', "
    "'modulo6', 'modulo7', 'modulo8', 'modulo9'"
)


def upgrade() -> None:
    op.drop_constraint(
        "chk_historico_modulo_origen_valido",
        "historicos_estados_activos",
        schema="modulo2",
        type_="check",
    )
    op.create_check_constraint(
        "chk_historico_modulo_origen_valido",
        "historicos_estados_activos",
        f"modulo_origen IN ({_VALORES_ORIGEN})",
        schema="modulo2",
    )


def downgrade() -> None:
    op.drop_constraint(
        "chk_historico_modulo_origen_valido",
        "historicos_estados_activos",
        schema="modulo2",
        type_="check",
    )
    op.create_check_constraint(
        "chk_historico_modulo_origen_valido",
        "historicos_estados_activos",
        "modulo_origen IN ("
        "'modulo1', 'modulo2', 'modulo3', 'modulo4', 'modulo5', "
        "'modulo6', 'modulo7', 'modulo8', 'modulo9'"
        ")",
        schema="modulo2",
    )
