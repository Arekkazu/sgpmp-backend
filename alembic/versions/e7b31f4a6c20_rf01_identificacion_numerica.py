"""rf01 validar numero de identificacion numerico

Revision ID: e7b31f4a6c20
Revises: d4e2f8a15c9b
Create Date: 2026-08-27 00:00:00.000000

DEV contiene registros históricos no numéricos. El trigger protege nuevas
altas y cambios del documento sin impedir que esas filas actualicen otros
campos. Después de depurar los datos heredados podrá reemplazarse por un CHECK
validado sobre toda la tabla.
"""
from typing import Sequence, Union

from alembic import op


revision: str = "e7b31f4a6c20"
down_revision: Union[str, Sequence[str], None] = "d4e2f8a15c9b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION modulo1.trg_fn_validar_identificacion_numerica()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            IF NEW.numero_identificacion IS NOT NULL
               AND NEW.numero_identificacion !~ '^[0-9]+$'
               AND (
                   TG_OP = 'INSERT'
                   OR NEW.numero_identificacion IS DISTINCT FROM OLD.numero_identificacion
               )
            THEN
                RAISE EXCEPTION USING
                    ERRCODE = '23514',
                    MESSAGE = 'numero_identificacion debe contener únicamente dígitos del 0 al 9',
                    CONSTRAINT = 'chk_usuario_numero_identificacion_numerico';
            END IF;

            RETURN NEW;
        END;
        $$;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_validar_identificacion_numerica
        BEFORE INSERT OR UPDATE OF numero_identificacion
        ON modulo1.usuarios
        FOR EACH ROW
        EXECUTE FUNCTION modulo1.trg_fn_validar_identificacion_numerica();
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DROP TRIGGER IF EXISTS trg_validar_identificacion_numerica
        ON modulo1.usuarios;
        """
    )
    op.execute(
        """
        DROP FUNCTION IF EXISTS modulo1.trg_fn_validar_identificacion_numerica();
        """
    )
