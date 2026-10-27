# | Fecha | Nombre | Que se hizo |
# |-------|--------|-------------|
# | 2026-10-27 | Leandro | INC-M03-126-G27 RF-54: ampliar heartbeat con métricas opcionales sin restaurar modulo3.buffers. |
"""RF-54 / #681: snapshot opcional del estado de buffer reportado por el Edge.

Aplicar antes del código y coordinar el INSERT del broker y el firmware.
Los heartbeats existentes y los INSERT sin el campo conservan NULL.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = 'b68127f54a01'
down_revision = 'ebbb160365e5'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('heartbeats',sa.Column('json_metricas_buffer',postgresql.JSONB(),nullable=True),schema='modulo3')


def downgrade():
    op.drop_column('heartbeats','json_metricas_buffer',schema='modulo3')
