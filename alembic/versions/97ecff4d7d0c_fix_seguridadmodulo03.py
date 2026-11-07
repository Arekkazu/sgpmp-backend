# | Fecha      | Nombre  | Que se hizo |
# |------------|---------|-------------|
# | 2026-10-22 | Leandro | DEV-47 RF-63: integra DB-11 oficial sin cambiar sus protecciones |
# | 2026-10-23 | Arekkazu | INTEG RFC-012..016 DB-11: encadenada tras DB-10 (un solo head) |
"""fix_seguridadModulo03

Revision ID: 97ecff4d7d0c
Revises: 15cb081c4835
Create Date: 2026-10-21 22:27:20.070659

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '97ecff4d7d0c'
down_revision: Union[str, Sequence[str], None] = '15cb081c4835'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():

    op.execute(
        """
        CREATE OR REPLACE FUNCTION auditoria.fn_forzar_inmutabilidad()
        RETURNS TRIGGER AS $$
        BEGIN
            RAISE EXCEPTION 'Operación denegada: La tabla % es Append-Only y no permite UPDATE ni DELETE.', TG_TABLE_NAME;
        END;
        $$ LANGUAGE plpgsql;
        """
    )

    op.execute(
        """
        CREATE TRIGGER trg_no_update_auditoria_iot
        BEFORE UPDATE OR DELETE ON modulo3.bitacora_auditoria_iot
        FOR EACH ROW EXECUTE FUNCTION auditoria.fn_forzar_inmutabilidad();
        """
    )

    op.execute(
        """
        CREATE TRIGGER trg_no_update_bitacora_ingest
        BEFORE UPDATE OR DELETE ON modulo3.bitacora_ingest
        FOR EACH ROW EXECUTE FUNCTION auditoria.fn_forzar_inmutabilidad();
        """
    )

    op.execute(
        """
        CREATE TRIGGER trg_no_update_auditoria_m04
        BEFORE UPDATE OR DELETE ON modulo4.eventos_auditoria_m04
        FOR EACH ROW EXECUTE FUNCTION auditoria.fn_forzar_inmutabilidad();
        """
    )


def downgrade():

    op.execute("DROP TRIGGER IF EXISTS trg_no_update_auditoria_iot ON modulo3.bitacora_auditoria_iot;")
    op.execute("DROP TRIGGER IF EXISTS trg_no_update_bitacora_ingest ON modulo3.bitacora_ingest;")
    op.execute("DROP TRIGGER IF EXISTS trg_no_update_auditoria_m04 ON modulo4.eventos_auditoria_m04;")


    op.execute("DROP FUNCTION IF EXISTS auditoria.fn_forzar_inmutabilidad();")