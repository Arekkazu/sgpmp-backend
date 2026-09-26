"""fix/RIGGER ADMIN CAMBIO DE ESTADO

Revision ID: fa915f4d113e
Revises: 6993cca9d95e
Create Date: 2026-09-09 14:54:44.033185

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'fa915f4d113e'
down_revision: Union[str, Sequence[str], None] = '6993cca9d95e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
    CREATE OR REPLACE FUNCTION modulo1.trg_fn_proteger_estado_cuenta_admin()
    RETURNS TRIGGER AS $$
    DECLARE
        v_es_protegido BOOLEAN;
        v_nombre_rol   VARCHAR(100);
        v_id_bloqueado INTEGER;
        v_id_activo    INTEGER;
    BEGIN
        IF NEW.id_estado_cuenta = OLD.id_estado_cuenta THEN
            RETURN NEW;
        END IF;

        SELECT id_estado_cuenta INTO v_id_bloqueado
          FROM modulo1.estados_cuentas WHERE nombre = 'Bloqueado';

        IF NEW.id_estado_cuenta = v_id_bloqueado THEN
            RETURN NEW;
        END IF;

        SELECT id_estado_cuenta INTO v_id_activo
          FROM modulo1.estados_cuentas WHERE nombre = 'Activo';

        IF OLD.id_estado_cuenta = v_id_bloqueado
           AND NEW.id_estado_cuenta = v_id_activo
           AND OLD.bloqueado_hasta IS NOT NULL
           AND OLD.bloqueado_hasta <= now() THEN
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


def downgrade() -> None:
    op.execute("""
    CREATE OR REPLACE FUNCTION modulo1.trg_fn_proteger_estado_cuenta_admin()
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
          FROM modulo1.estados_cuentas WHERE nombre = 'Bloqueado';

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