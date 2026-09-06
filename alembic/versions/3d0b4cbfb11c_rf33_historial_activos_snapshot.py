"""RF-33: tabla historial_activos para el snapshot inicial (Evento 0)

Revision ID: 3d0b4cbfb11c
Revises: 56cd2038ff06
Create Date: 2026-09-06 10:00:00.000000

Issue #28 — el RF-33 exige explícitamente que el registro de un activo
biológico deje un "snapshot inicial (Evento 0)" en una tabla `historial_activos`
con `version=1`, `tipo_evento='CREACION'`. Esa tabla nunca se creó: confirmado
en vivo por auditoría previa que `information_schema.tables` de `modulo2` solo
tiene `historial_infraestructura_activo` y 4 vistas. El método
`ActivoBiologico._snapshot()` ya existe en el dominio pero solo lo usa
`asociar_sensor_activo_use_case.py` para su propia auditoría (RF-49) — nunca
se invoca desde el registro (RF-33).

Esta migración solo crea la tabla. La invocación de `_snapshot()` en el
registro y la inserción del Evento 0 se agregan en
`RegistrarActivoBiologicoUseCase` (capa de aplicación), no aquí.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '3d0b4cbfb11c'
down_revision: Union[str, Sequence[str], None] = '56cd2038ff06'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'historial_activos',
        sa.Column(
            'id_historial_activo',
            sa.Integer,
            sa.Identity(start=1, increment=1),
            primary_key=True,
        ),
        sa.Column('id_activo_biologico', sa.Integer, nullable=False),
        sa.Column('version', sa.Integer, nullable=False),
        # 'CREACION' es el único valor emitido hoy (Evento 0); se deja abierto
        # para que futuras RF (ediciones, cambios de estado, etc.) agreguen
        # sus propios tipo_evento sin requerir otra migración.
        sa.Column('tipo_evento', sa.String(30), nullable=False),
        sa.Column('json_snapshot', postgresql.JSONB, nullable=False),
        sa.Column('fecha_evento', sa.DateTime(timezone=True), nullable=False),
        sa.Column('id_usuario', sa.Integer, nullable=False),
        sa.CheckConstraint('version > 0', name='ck_historial_activo_version_positiva'),
        sa.UniqueConstraint(
            'id_activo_biologico', 'version',
            name='uq_historial_activo_version',
        ),
        sa.ForeignKeyConstraint(
            ['id_activo_biologico'], ['modulo2.activos_biologicos.id_activo_biologico'],
            name='historial_activos_id_activo_biologico_fkey',
            ondelete='CASCADE',
        ),
        sa.ForeignKeyConstraint(
            ['id_usuario'], ['modulo1.usuarios.id_usuario'],
            name='historial_activos_id_usuario_fkey',
        ),
        schema='modulo2',
    )
    op.create_index(
        'idx_historial_activos_id_activo_biologico',
        'historial_activos',
        ['id_activo_biologico'],
        schema='modulo2',
    )


def downgrade() -> None:
    op.drop_index(
        'idx_historial_activos_id_activo_biologico',
        table_name='historial_activos',
        schema='modulo2',
    )
    op.drop_table('historial_activos', schema='modulo2')
