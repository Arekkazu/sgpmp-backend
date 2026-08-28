"""rf01 validar formato del numero de identificacion

Revision ID: e7b31f4a6c20
Revises: c8e4a5b13d72
Create Date: 2026-08-27 00:00:00.000000

RF-01 exige rechazar caracteres alfabeticos en `numero_identificacion`, pero
tambien admite `Pasaporte` como tipo de documento — y un pasaporte es
alfanumerico. La regla depende por tanto del tipo declarado: digitos para
`CC`/`CE`, alfanumerico para `Pasaporte`. La restriccion
`chk_usuario_tipo_identificacion` ya limita la columna a esos tres valores.

DEV contiene registros historicos no numericos. El trigger protege nuevas altas
y cambios del documento sin impedir que esas filas actualicen otros campos.
Despues de depurar los datos heredados podra reemplazarse por un CHECK validado
sobre toda la tabla.
"""
from typing import Sequence, Union

from alembic import op


revision: str = "e7b31f4a6c20"
down_revision: Union[str, Sequence[str], None] = "c8e4a5b13d72"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION modulo1.trg_fn_validar_identificacion_numerica()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $func$
        DECLARE
            patron text := CASE
                WHEN NEW.tipo_identificacion = 'Pasaporte' THEN '^[A-Za-z0-9]+$'
                ELSE '^[0-9]+$'
            END;
        BEGIN
            IF NEW.numero_identificacion IS NOT NULL
               AND (
                   TG_OP = 'INSERT'
                   OR NEW.numero_identificacion IS DISTINCT FROM OLD.numero_identificacion
                   OR NEW.tipo_identificacion IS DISTINCT FROM OLD.tipo_identificacion
               )
               AND NEW.numero_identificacion !~ patron
            THEN
                RAISE EXCEPTION USING
                    ERRCODE = '23514',
                    MESSAGE = 'numero_identificacion no cumple el formato exigido '
                              || 'para el tipo '
                              || coalesce(NEW.tipo_identificacion, '(sin tipo)')
                              || ': se esperaba ' || patron,
                    CONSTRAINT = 'chk_usuario_numero_identificacion_formato';
            END IF;

            RETURN NEW;
        END;
        $func$;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_validar_identificacion_numerica
        BEFORE INSERT OR UPDATE OF numero_identificacion, tipo_identificacion
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
