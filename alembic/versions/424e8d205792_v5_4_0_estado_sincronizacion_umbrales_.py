"""v5.4.0_estado_sincronizacion_umbrales_edge

Revision ID: 424e8d205792
Revises: d014e2cc785d
Create Date: 2026-09-17 00:30:07.776071

INC-M09-104-G29 (RF-17, TC-M09-G29): la creación/edición de un umbral ambiental
terminaba en persistencia + auditoría, sin ningún intento de propagarlo hacia
los Nodos Edge ni forma de saber si esa propagación ocurrió. Esta migración
solo agrega el estado -- la propagación real vía MQTT queda detrás de un
adaptador stub (ver anotaciones/modulo_9/inc_m09_104_g29_sincronizacion_edge_
umbrales.md) hasta que el equipo de IoT defina el contrato del broker para
umbrales (topic, payload, ACK), tal como pide el propio hallazgo de QA.

Mismo vocabulario de estados que ``configuraciones_remotas_estado_check``
(RF-23, migración 7e2d5f3bf17a): PENDIENTE / APLICADA / NO_CONF -- una
configuración recién creada nunca ha sido propagada, así que arranca en
PENDIENTE (server_default, también para las filas ya existentes: honesto,
nunca hubo intento de sincronización antes de este cambio).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '424e8d205792'
down_revision: Union[str, Sequence[str], None] = 'd014e2cc785d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'umbrales_ambientales',
        sa.Column(
            'estado_sincronizacion',
            sa.String(20),
            nullable=False,
            server_default=sa.text("'PENDIENTE'::character varying"),
        ),
        schema='modulo9',
    )
    op.add_column(
        'umbrales_ambientales',
        sa.Column('fecha_ultima_sincronizacion', sa.DateTime(timezone=True), nullable=True),
        schema='modulo9',
    )
    op.add_column(
        'umbrales_ambientales',
        sa.Column('motivo_fallo_sincronizacion', sa.Text(), nullable=True),
        schema='modulo9',
    )
    op.create_check_constraint(
        'umbrales_ambientales_estado_sincronizacion_check',
        'umbrales_ambientales',
        "estado_sincronizacion IN ('PENDIENTE', 'APLICADA', 'NO_CONF')",
        schema='modulo9',
    )


def downgrade() -> None:
    op.drop_constraint(
        'umbrales_ambientales_estado_sincronizacion_check',
        'umbrales_ambientales',
        schema='modulo9',
        type_='check',
    )
    op.drop_column('umbrales_ambientales', 'motivo_fallo_sincronizacion', schema='modulo9')
    op.drop_column('umbrales_ambientales', 'fecha_ultima_sincronizacion', schema='modulo9')
    op.drop_column('umbrales_ambientales', 'estado_sincronizacion', schema='modulo9')
