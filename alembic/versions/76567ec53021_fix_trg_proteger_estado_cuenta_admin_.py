"""fix_trg_proteger_estado_cuenta_admin_bloqueo

Revision ID: 76567ec53021
Revises: 2dbb6d44046f
Create Date: 2026-09-04 21:40:14.171668

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '76567ec53021'
down_revision: Union[str, Sequence[str], None] = '2dbb6d44046f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.execute("""
    CREATE OR REPLACE FUNCTION trg_fn_proteger_estado_cuenta_admin()
    RETURNS TRIGGER AS $$
    DECLARE
        v_es_protegido BOOLEAN;
        v_nombre_rol   VARCHAR(100);
        v_id_bloqueado INTEGER;
    BEGIN
        IF NEW.id_estado_cuenta = OLD.id_estado_cuenta THEN
            RETURN NEW;
        END IF;
        SELECT id_estado_cuenta INTO v_id_bloqueado
          FROM modulo1.estados_cuenta WHERE nombre_estado = 'Bloqueado';
        IF NEW.id_estado_cuenta = v_id_bloqueado THEN
            RETURN NEW;
        END IF;
        SELECT r.es_protegido, r.nombre_rol INTO v_es_protegido, v_nombre_rol
          FROM modulo1.usuarios u JOIN modulo1.roles r ON r.id_rol = u.id_rol
         WHERE u.id_usuario = NEW.id_usuario;
        IF v_es_protegido = TRUE THEN
            RAISE EXCEPTION
                'PROTECTED_ADMIN: No se puede cambiar el estado de la cuenta del usuario con rol protegido "%".',
                v_nombre_rol USING ERRCODE = 'P0004';
        END IF;
        RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    """)

def downgrade():
    op.execute("""
    CREATE OR REPLACE FUNCTION trg_fn_proteger_estado_cuenta_admin()
    RETURNS TRIGGER AS $$
    DECLARE
        v_es_protegido BOOLEAN;
        v_nombre_rol   VARCHAR(100);
    BEGIN
        IF NEW.id_estado_cuenta = OLD.id_estado_cuenta THEN
            RETURN NEW;
        END IF;
        SELECT r.es_protegido, r.nombre_rol INTO v_es_protegido, v_nombre_rol
          FROM modulo1.usuarios u JOIN modulo1.roles r ON r.id_rol = u.id_rol
         WHERE u.id_usuario = NEW.id_usuario;
        IF v_es_protegido = TRUE THEN
            RAISE EXCEPTION
                'PROTECTED_ADMIN: No se puede cambiar el estado de la cuenta del usuario con rol protegido "%".',
                v_nombre_rol USING ERRCODE = 'P0004';
        END IF;
        RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    """)