"""rf14 bandeja notificaciones indice

Revision ID: aa24fc52896e
Revises: 7e2d5f3bf17a
Create Date: 2026-08-22 15:24:35.643409

RF-14 — índice parcial para paginar la bandeja de notificaciones internas por
usuario (id_notificacion_canal = 2). Equivalente formal a
anotaciones/modulo_1/rf14_bandeja_notificaciones.sql, ya aplicado a mano en
sgpmp y pruebas; usa CREATE INDEX IF NOT EXISTS para que "upgrade head" sea
un no-op seguro en esos entornos y cree el índice de cero en cualquier otro.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'aa24fc52896e'
down_revision: Union[str, Sequence[str], None] = '7e2d5f3bf17a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM modulo1.notificaciones_canal
                WHERE id_notificacion_canal = 2
                  AND upper(btrim(nombre)) = 'INTERNO'
            ) THEN
                RAISE EXCEPTION
                    'RF-14: id_notificacion_canal=2 no corresponde al canal INTERNO';
            END IF;
        END
        $$;
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_notificaciones_bandeja_usuario
        ON modulo1.notificaciones (id_usuario, fecha_envio DESC, id_notificacion DESC)
        WHERE id_notificacion_canal = 2
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS modulo1.ix_notificaciones_bandeja_usuario")
