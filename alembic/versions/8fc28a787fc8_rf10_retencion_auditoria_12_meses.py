"""RF-10: retención y archivo histórico de auditoría por 12 meses.

Revision ID: 8fc28a787fc8
Revises: d4e2f8a15c9b
Create Date: 2026-08-27 09:27:03.955132

Los eventos originales permanecen en ``modulo1.eventos`` porque RF-10 los
declara inmutables y ``modulo1.notificaciones`` conserva una FK hacia ellos.
La migración crea una copia histórica igualmente inmutable, sin claves
foráneas, para preservar el registro aunque en el futuro cambien los catálogos
operacionales.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ENUM, JSONB


# revision identifiers, used by Alembic.
revision: str = '8fc28a787fc8'
down_revision: Union[str, Sequence[str], None] = 'd4e2f8a15c9b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    resultado_evento = ENUM(
        "exitoso",
        "fallido",
        name="enum_evento_resultado",
        schema="modulo1",
        create_type=False,
    )
    op.create_table(
        "eventos_archivados",
        sa.Column("id_evento", sa.Integer(), autoincrement=False, nullable=False),
        sa.Column("tipo_evento", sa.Integer(), nullable=False),
        sa.Column("fecha_evento", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("modulo", sa.String(length=50), nullable=False),
        sa.Column("resultado", resultado_evento, nullable=False),
        sa.Column("detalle", JSONB(), nullable=False),
        sa.Column("id_usuario", sa.Integer(), nullable=False),
        sa.Column("categoria", sa.String(length=30), nullable=False),
        sa.Column("estado", sa.String(length=30), nullable=False),
        sa.Column("descripcion", sa.Text(), nullable=True),
        sa.Column("id_sesion", sa.Integer(), nullable=True),
        sa.Column("hash_integridad", sa.Text(), nullable=True),
        sa.Column(
            "fecha_archivado",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.CheckConstraint(
            "fecha_archivado >= fecha_evento",
            name="chk_eventos_archivados_fecha",
        ),
        sa.PrimaryKeyConstraint("id_evento", name="eventos_archivados_pkey"),
        schema="modulo1",
        comment=(
            "Copia histórica inmutable de eventos de auditoría con antigüedad "
            "superior a la política mínima de retención de 12 meses."
        ),
    )
    op.create_index(
        "ix_eventos_archivados_fecha",
        "eventos_archivados",
        [sa.text("fecha_evento DESC"), sa.text("id_evento DESC")],
        schema="modulo1",
    )
    op.create_index(
        "ix_eventos_archivados_usuario_fecha",
        "eventos_archivados",
        ["id_usuario", sa.text("fecha_evento DESC")],
        schema="modulo1",
    )

    op.execute(
        """
        CREATE FUNCTION modulo1.trg_fn_proteger_eventos_archivados()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            RAISE EXCEPTION
                'IMMUTABLE_RECORD: Los eventos archivados no pueden ser modificados ni eliminados. Operación bloqueada: %',
                TG_OP
                USING ERRCODE = 'P0002';
            RETURN NULL;
        END;
        $$;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_proteger_eventos_archivados
        BEFORE UPDATE OR DELETE ON modulo1.eventos_archivados
        FOR EACH ROW
        EXECUTE FUNCTION modulo1.trg_fn_proteger_eventos_archivados();
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS trg_proteger_eventos_archivados "
        "ON modulo1.eventos_archivados"
    )
    op.execute(
        "DROP FUNCTION IF EXISTS modulo1.trg_fn_proteger_eventos_archivados()"
    )
    op.drop_index(
        "ix_eventos_archivados_usuario_fecha",
        table_name="eventos_archivados",
        schema="modulo1",
    )
    op.drop_index(
        "ix_eventos_archivados_fecha",
        table_name="eventos_archivados",
        schema="modulo1",
    )
    op.drop_table("eventos_archivados", schema="modulo1")
