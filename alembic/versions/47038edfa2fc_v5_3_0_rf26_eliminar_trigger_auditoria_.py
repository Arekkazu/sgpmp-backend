"""v5.3.0_rf26_eliminar_trigger_auditoria_visual_duplicada

Revision ID: 47038edfa2fc
Revises: 1147428cd8fb
Create Date: 2026-09-17 19:03:15.340574

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '47038edfa2fc'
down_revision: Union[str, Sequence[str], None] = '1147428cd8fb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Deja una única fuente de auditoría para identidad visual.

    El caso de uso registra snapshots con ``id_finca`` en la misma transacción
    que el cambio. El trigger histórico registraba un segundo snapshot sin esa
    clave, por lo que cada PATCH producía dos filas y una de ellas no podía
    asociarse a la finca desde la API.

    Los registros históricos se conservan intactos. La consulta expuesta por
    RF-26 selecciona los registros canónicos que contienen ``id_finca``.
    """
    op.execute(
        "DROP TRIGGER IF EXISTS trg_identidad_visual_audit "
        "ON modulo9.identidad_visuales"
    )


def downgrade() -> None:
    op.execute(
        """
        CREATE TRIGGER trg_identidad_visual_audit
        AFTER INSERT OR UPDATE ON modulo9.identidad_visuales
        FOR EACH ROW
        EXECUTE FUNCTION modulo9.trg_fn_identidad_visual_audit()
        """
    )
