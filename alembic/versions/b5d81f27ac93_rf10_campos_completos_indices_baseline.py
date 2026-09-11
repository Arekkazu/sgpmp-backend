"""RF-10: campos obligatorios del registro, índices de consulta y línea base de integridad.

Revision ID: b5d81f27ac93
Revises: a3b7c1d95e40
Create Date: 2026-08-28 05:00:00.000000

Cubre tres huecos frente al RF:

1. La sección "Entradas" define ``nombre_usuario``, ``direccion_ip`` y
   ``user_agent``, y el criterio de aceptación exige "el sistema almacena IP y
   sesión". Ninguna de las tres existía como columna. Se agregan nullable porque
   los eventos ya registrados son inmutables y no se pueden rellenar.

2. Los RNF piden consulta < 3 s y soporte de alto volumen, pero
   ``modulo1.eventos`` sólo tenía la clave primaria como índice: todos los
   filtros del endpoint hacían sequential scan.

3. El flujo alterno de hash mismatch exige responder 500. En la base ya existen
   eventos escritos por un esquema de hash anterior cuyo valor es irreproducible
   con la fórmula actual; como son inmutables, nunca podrán repararse y harían
   que la consulta respondiera 500 de forma permanente. La línea base registra
   el hash recalculado de esos registros en el momento de adoptar la política,
   de modo que se reportan como no íntegros sin escalar a 500, pero cualquier
   manipulación posterior sí cambia el recálculo y dispara el 500.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b5d81f27ac93'
down_revision: Union[str, Sequence[str], None] = 'a3b7c1d95e40'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

COLUMNAS = (
    ("nombre_usuario", sa.String(length=80)),
    ("direccion_ip", sa.String(length=45)),
    ("user_agent", sa.String(length=255)),
)


def upgrade() -> None:
    # 1. Campos obligatorios que faltaban, en el log activo y en el histórico.
    for tabla in ("eventos", "eventos_archivados"):
        for nombre, tipo in COLUMNAS:
            op.add_column(
                tabla,
                sa.Column(nombre, tipo, nullable=True),
                schema="modulo1",
            )

    # 2. Índices para los filtros y el orden del endpoint de consulta.
    op.create_index(
        "ix_eventos_fecha",
        "eventos",
        [sa.text("fecha_evento DESC"), sa.text("id_evento DESC")],
        schema="modulo1",
    )
    op.create_index(
        "ix_eventos_usuario_fecha",
        "eventos",
        ["id_usuario", sa.text("fecha_evento DESC")],
        schema="modulo1",
    )
    op.create_index(
        "ix_eventos_tipo_fecha",
        "eventos",
        ["tipo_evento", sa.text("fecha_evento DESC")],
        schema="modulo1",
    )

    # 3. Línea base de integridad, append-only e inmutable como la auditoría.
    op.create_table(
        "integridad_baseline",
        sa.Column("id_evento", sa.Integer(), autoincrement=False, nullable=False),
        sa.Column(
            "hash_calculado",
            sa.Text(),
            nullable=True,
            comment=(
                "Hash recalculado del contenido al adoptar la política. NULL "
                "cuando el evento no tenía hash almacenado."
            ),
        ),
        sa.Column(
            "motivo",
            sa.String(length=40),
            nullable=False,
            comment="SIN_HASH o ESQUEMA_ANTERIOR.",
        ),
        sa.Column(
            "fecha_registro",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.PrimaryKeyConstraint("id_evento", name="integridad_baseline_pkey"),
        schema="modulo1",
        comment=(
            "Eventos ya no verificables antes de adoptar la verificación estricta "
            "de RF-10. Permite distinguir el legado irreparable de una "
            "manipulación posterior."
        ),
    )
    op.execute(
        """
        CREATE FUNCTION modulo1.trg_fn_proteger_integridad_baseline()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            RAISE EXCEPTION
                'IMMUTABLE_RECORD: La linea base de integridad no puede ser modificada ni eliminada. Operacion bloqueada: %',
                TG_OP
                USING ERRCODE = 'P0002';
            RETURN NULL;
        END;
        $$;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_proteger_integridad_baseline
        BEFORE UPDATE OR DELETE ON modulo1.integridad_baseline
        FOR EACH ROW
        EXECUTE FUNCTION modulo1.trg_fn_proteger_integridad_baseline();
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS trg_proteger_integridad_baseline "
        "ON modulo1.integridad_baseline"
    )
    op.execute(
        "DROP FUNCTION IF EXISTS modulo1.trg_fn_proteger_integridad_baseline()"
    )
    op.drop_table("integridad_baseline", schema="modulo1")
    op.drop_index("ix_eventos_tipo_fecha", table_name="eventos", schema="modulo1")
    op.drop_index("ix_eventos_usuario_fecha", table_name="eventos", schema="modulo1")
    op.drop_index("ix_eventos_fecha", table_name="eventos", schema="modulo1")
    for tabla in ("eventos", "eventos_archivados"):
        for nombre, _ in COLUMNAS:
            op.drop_column(tabla, nombre, schema="modulo1")
