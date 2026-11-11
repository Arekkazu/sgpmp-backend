"""fix_update_recepciones_provisionbes_mo5

Revision ID: 024944b01b4d
Revises: b7e2d94c1a68
Create Date: 2026-11-09 10:44:31.928534

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '024944b01b4d'
down_revision: Union[str, Sequence[str], None] = 'b7e2d94c1a68'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None



_ROLES_APP = "('sgpmp_app', 'rol_app', 'rol_dev', 'rol_impl')"


def upgrade() -> None:
    # M06 marca la recepción procesada (RF-90). Solo esas dos columnas, por mínimo privilegio.
    op.execute(f"""
        DO $$
        DECLARE r text;
        BEGIN
            FOR r IN SELECT rolname FROM pg_roles WHERE rolname IN {_ROLES_APP} LOOP
                EXECUTE format('GRANT USAGE ON SCHEMA modulo6 TO %I', r);
                EXECUTE format('GRANT SELECT ON modulo6.recepciones_provisiones_m05 TO %I', r);
                EXECUTE format('GRANT UPDATE (fecha_procesamiento, resultado_procesamiento) '
                               'ON modulo6.recepciones_provisiones_m05 TO %I', r);
            END LOOP;
        END $$;
    """)


def downgrade() -> None:
    op.execute(f"""
        DO $$
        DECLARE r text;
        BEGIN
            FOR r IN SELECT rolname FROM pg_roles WHERE rolname IN {_ROLES_APP} LOOP
                EXECUTE format('REVOKE UPDATE (fecha_procesamiento, resultado_procesamiento) '
                               'ON modulo6.recepciones_provisiones_m05 FROM %I', r);
            END LOOP;
        END $$;
    """)