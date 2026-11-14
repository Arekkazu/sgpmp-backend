# | Fecha | Nombre | Que se hizo |
# |-------|--------|-------------|
# | 2026-11-13 | Leandro | TC-M06-G61 RF-92: permitir leer los supuestos persistidos por RF-83. |
"""Permite a RF-92 consultar el detalle de las mediciones bajo las políticas vigentes."""
from alembic import op

revision = "f110692a0001"
down_revision = "0884ba08a944"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        DO $$
        DECLARE rol text;
        BEGIN
            FOR rol IN SELECT rolname FROM pg_roles WHERE rolname IN ('sgpmp_app', 'rol_app') LOOP
                EXECUTE format('GRANT SELECT (id_calculo_actual, id_activo_biologico, id_periodo_contable,
                    fecha_medicion, id_medicion_posterior, supuestos_aplicados)
                    ON modulo6.mediciones_posteriores TO %I', rol);
            END LOOP;
        END $$;
    """)


def downgrade() -> None:
    # Conservar ACL que el ambiente podía tener antes de esta revisión, como en RF-82.
    pass
