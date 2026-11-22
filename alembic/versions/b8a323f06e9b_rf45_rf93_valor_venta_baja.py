# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-15 | Arekkazu | INC-M06-364-G71 RF-45/RF-93: valor y referencia de la venta en la baja de un activo |
"""RF-45 / RF-93: valor y referencia de la venta en la baja de un activo biológico.

La baja por venta (RF-45) guarda lo que se recibió y el documento que la respalda. El estado de resultados
(RF-93) lo presenta como ingreso por venta, sin asiento: la factura de venta se registra en la contabilidad
externa (RFC-018). Las dos columnas aceptan nulos (las bajas anteriores y las que no son venta no tienen valor)
y solo se llenan en una baja de tipo venta. ``eventos_bajas`` es inmutable (triggers de UPDATE y DELETE), así
que no hay datos que migrar.
"""

from alembic import op

revision = "b8a323f06e9b"
down_revision = "f0d5920d51b6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE modulo2.eventos_bajas
            ADD COLUMN valor_venta numeric(18,2),
            ADD COLUMN referencia_venta varchar(100),
            ADD CONSTRAINT ck_evento_baja_valor_venta
                CHECK (valor_venta IS NULL OR (valor_venta > 0 AND tipo = 'venta')),
            ADD CONSTRAINT ck_evento_baja_referencia_venta
                CHECK (referencia_venta IS NULL OR (tipo = 'venta' AND char_length(btrim(referencia_venta)) > 0))
    """)
    op.execute("COMMENT ON COLUMN modulo2.eventos_bajas.valor_venta IS "
               "'Valor total recibido por la venta (solo tipo venta). RF-45; ingreso por venta de RF-93'")
    op.execute("COMMENT ON COLUMN modulo2.eventos_bajas.referencia_venta IS "
               "'Factura o remisión de la venta (solo tipo venta). RF-45'")


def downgrade() -> None:
    op.execute("""
        ALTER TABLE modulo2.eventos_bajas
            DROP CONSTRAINT IF EXISTS ck_evento_baja_referencia_venta,
            DROP CONSTRAINT IF EXISTS ck_evento_baja_valor_venta,
            DROP COLUMN IF EXISTS referencia_venta,
            DROP COLUMN IF EXISTS valor_venta
    """)
