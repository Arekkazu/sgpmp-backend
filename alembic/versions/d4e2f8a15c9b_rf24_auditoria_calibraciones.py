"""rf24 auditoria inmutable de calibraciones

Revision ID: d4e2f8a15c9b
Revises: c3f1a9e42b7d
Create Date: 2026-08-25 00:30:00.000000

RF-24 (#1635) — flujo alterno "Fallo en el registro de auditoría" (RF-10).

El registro de calibración debe dejar traza en un historial de auditoría
INMUTABLE; si esa escritura falla, la calibración hace rollback y se responde
500. Se agrega `modulo9.auditorias_calibraciones` siguiendo el patrón de las
demás auditorías de módulo 9 (mismo esquema que auditorias_sensores_areas) y la
inmutabilidad por trigger de auditorias_especies (bloquea UPDATE/DELETE).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


# revision identifiers, used by Alembic.
revision: str = 'd4e2f8a15c9b'
down_revision: Union[str, Sequence[str], None] = 'c3f1a9e42b7d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "auditorias_calibraciones",
        sa.Column("id_auditoria_calibracion", sa.Integer, primary_key=True),
        sa.Column("id_calibracion", sa.Integer, nullable=False),
        sa.Column("id_usuario", sa.Integer, nullable=False),
        sa.Column("tipo_operacion", sa.String(20), nullable=False),
        sa.Column("valores_anteriores", JSONB, nullable=True),
        sa.Column("valores_nuevos", JSONB, nullable=False),
        sa.Column("fecha_gestion", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("tipo_operacion IN ('CREATE','GET')", name="chk_tipo_operacion_calibracion"),
        sa.ForeignKeyConstraint(
            ["id_calibracion"], ["modulo9.calibraciones.id_calibracion"],
            name="auditoria_calibracion_id_calibracion_fkey",
        ),
        sa.ForeignKeyConstraint(
            ["id_usuario"], ["modulo1.usuarios.id_usuario"],
            name="auditoria_calibracion_id_usuario_fkey",
        ),
        schema="modulo9",
    )

    # Inmutabilidad (RF-10): bloquear UPDATE/DELETE incluso para el rol postgres.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION modulo9.trg_fn_auditorias_calibraciones_inmutable()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION
                '[AUDIT-CALIBRACIONES] Operación no permitida. Los registros de auditoría '
                'son inmutables y no pueden ser modificados ni eliminados.';
        END;
        $$;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_auditorias_calibraciones_inmutable
        BEFORE UPDATE OR DELETE ON modulo9.auditorias_calibraciones
        FOR EACH ROW EXECUTE FUNCTION modulo9.trg_fn_auditorias_calibraciones_inmutable();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_auditorias_calibraciones_inmutable ON modulo9.auditorias_calibraciones")
    op.execute("DROP FUNCTION IF EXISTS modulo9.trg_fn_auditorias_calibraciones_inmutable()")
    op.drop_table("auditorias_calibraciones", schema="modulo9")
