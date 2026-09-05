"""RF-07/RF-09: validar reutilización mediante bcrypt en aplicación.

Revision ID: b7e19f07a038
Revises: f19e0ca62445
Create Date: 2026-09-04 21:00:00.000000

El trigger anterior comparaba los textos de dos hashes bcrypt. Cada hash usa
un salt distinto, por lo que no detectaba la misma contraseña cifrada de nuevo.
La comparación correcta usa bcrypt.checkpw antes de reemplazar el hash.
"""
from typing import Sequence, Union

from alembic import op


revision: str = "b7e19f07a038"
down_revision: Union[str, Sequence[str], None] = "f19e0ca62445"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_no_reutilizar_contrasena ON modulo1.usuarios")
    op.execute("DROP FUNCTION IF EXISTS modulo1.trg_fn_no_reutilizar_contrasena()")


def downgrade() -> None:
    op.execute(
        """
        CREATE FUNCTION modulo1.trg_fn_no_reutilizar_contrasena()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $function$
        BEGIN
            IF NEW.contrasena_cifrada = OLD.contrasena_cifrada THEN
                RAISE EXCEPTION
                    'CONSTRAINT_VIOLATION: La nueva contraseña no puede ser idéntica a la anterior.'
                    USING ERRCODE = 'P0001';
            END IF;
            RETURN NEW;
        END;
        $function$
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_no_reutilizar_contrasena
        BEFORE UPDATE OF contrasena_cifrada ON modulo1.usuarios
        FOR EACH ROW
        WHEN (OLD.contrasena_cifrada IS NOT NULL)
        EXECUTE FUNCTION modulo1.trg_fn_no_reutilizar_contrasena()
        """
    )
