# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-07 | Arekkazu | M05/M06: USAGE sobre public para que los triggers de hash vean pgcrypto |
"""grant usage public: los roles de la app ven pgcrypto en todos los ambientes

Revision ID: b7e2d94c1a68
Revises: 94b14a6931d6
Create Date: 2026-11-07

Requiere la autorización de SamuelPR21 (DBA) antes de desplegar.

``pgcrypto`` vive en ``public`` y los triggers de hash de M05 (``calcular_hash_integridad``) y M06
(``calcular_hash_auditoria``) llaman ``digest(...)`` sin esquema. El ACL de ``public`` se había
configurado a mano por ambiente: DEV lo da a ``rol_app``, TEST no lo daba a nadie y ``sgpmp_app``
fallaba con ``function digest(text, unknown) does not exist`` al vencer cotizaciones. El GRANT es
idempotente y solo se aplica a los roles que existen en cada base.
"""
from typing import Sequence, Union

from alembic import op


revision: str = 'b7e2d94c1a68'
down_revision: Union[str, Sequence[str], None] = '94b14a6931d6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_ROLES_APP = "('sgpmp_app', 'rol_app', 'rol_dev', 'rol_impl', 'rol_migracion')"


def upgrade() -> None:
    op.execute(f"""
        DO $$
        DECLARE r record;
        BEGIN
            FOR r IN SELECT rolname FROM pg_roles WHERE rolname IN {_ROLES_APP} LOOP
                EXECUTE format('GRANT USAGE ON SCHEMA public TO %I', r.rolname);
            END LOOP;
        END $$;
    """)


def downgrade() -> None:
    # Sin REVOKE: en DEV el permiso existía antes de esta migración y quitarlo rompería los triggers.
    pass
