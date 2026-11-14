# | Fecha | Nombre | Que se hizo |
# |-------|--------|-------------|
# | 2026-11-12 | Leandro | INC-M05-350/351-G05 RF-74: persistir el motivo y recuperar el catálogo de causas manuales históricas. |
"""RF-74: separar la causa de la interrupción del motivo informado por el operador."""

import sqlalchemy as sa
from alembic import op

revision = "f108174bc001"
down_revision = "603631775892"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("ejecuciones_batch_ica", sa.Column("motivo_interrupcion", sa.Text()), schema="modulo5")
    # El endpoint anterior siempre registraba el actor de una interrupción manual.
    # El corte por ventana y la recuperación al arrancar dejaban ese campo vacío.
    op.execute("""
        UPDATE modulo5.ejecuciones_batch_ica
           SET motivo_interrupcion = causa_interrupcion, causa_interrupcion = 'MANUAL'
         WHERE estado = 'INTERRUMPIDO' AND id_usuario_interrupcion IS NOT NULL
           AND causa_interrupcion IS DISTINCT FROM 'MANUAL'
    """)


def downgrade() -> None:
    # La columna anterior admite hasta 50 caracteres. Si existen motivos más
    # largos, el UPDATE falla y PostgreSQL revierte la migración sin perder texto.
    op.execute("""
        UPDATE modulo5.ejecuciones_batch_ica SET causa_interrupcion = motivo_interrupcion
         WHERE causa_interrupcion = 'MANUAL' AND motivo_interrupcion IS NOT NULL
    """)
    op.drop_column("ejecuciones_batch_ica", "motivo_interrupcion", schema="modulo5")
