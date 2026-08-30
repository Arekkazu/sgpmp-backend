"""rf06 trigger revoca tokens al inactivar, bloquear o eliminar

Revision ID: e8bb4f321a44
Revises: f2c84d91a6e7
Create Date: 2026-08-29 00:00:00.000000

RF-06 — "El sistema invalida sesiones activas al cambiar el estado a INACTIVO,
BLOQUEADO o ELIMINADO".

`trg_fn_invalidar_sesiones_por_estado` solo hacía
`UPDATE modulo1.sesiones SET es_activa = FALSE`, pero la autenticación no mira
esa columna: `get_current_user` acepta un JWT mientras `modulo1.tokens.fecha_uso`
siga en NULL. Es decir, el trigger marcaba la sesión como cerrada y el token
seguía sirviendo. Cualquier cambio de estado hecho fuera de la aplicación (SQL
directo, script de mantenimiento) dejaba las sesiones vivas.

Se le añade la revocación real de los tokens de acceso y de refresco.

Acotado a los estados 3/4/5 a propósito: si revocara en *cualquier* cambio de
estado, activar una cuenta PENDIENTE_DATOS echaría de la sesión al usuario que
acaba de completar su perfil. El `UPDATE` de `es_activa` conserva su alcance
original (todo cambio de estado) para no alterar conducta existente.

Es una red de seguridad, no el camino principal: la aplicación sigue revocando
explícitamente vía `SqlAlchemySesionRepository.invalidar_todas_sesiones`, que
además registra `fecha_finalizacion`. Los dos son idempotentes entre sí gracias
al filtro `fecha_uso IS NULL`.
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'e8bb4f321a44'
down_revision: Union[str, Sequence[str], None] = 'f2c84d91a6e7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Estados que obligan a revocar la sesión según RF-06.
_INACTIVO, _BLOQUEADO, _ELIMINADO = 3, 4, 5


def upgrade() -> None:
    op.execute(
        f"""
        CREATE OR REPLACE FUNCTION modulo1.trg_fn_invalidar_sesiones_por_estado()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $function$
        BEGIN
            IF NEW.id_estado_cuenta <> OLD.id_estado_cuenta THEN
                UPDATE modulo1.sesiones
                SET es_activa = FALSE
                WHERE id_cuenta_usuario = NEW.id_cuenta_usuario;

                -- RF-06: marcar la sesion como inactiva no basta. La
                -- autenticacion valida contra tokens.fecha_uso, asi que sin
                -- esto el JWT seguia siendo aceptado.
                IF NEW.id_estado_cuenta IN ({_INACTIVO}, {_BLOQUEADO}, {_ELIMINADO}) THEN
                    UPDATE modulo1.tokens AS t
                    SET fecha_uso = now()
                    FROM modulo1.sesiones AS s
                    WHERE s.id_cuenta_usuario = NEW.id_cuenta_usuario
                      AND (t.id_token = s.id_token OR t.id_token = s.id_token_refresco)
                      AND t.fecha_uso IS NULL;
                END IF;
            END IF;
            RETURN NEW;
        END;
        $function$
        """
    )


def downgrade() -> None:
    # Vuelve a la version previa: solo desactiva las sesiones.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION modulo1.trg_fn_invalidar_sesiones_por_estado()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $function$
        BEGIN
            IF NEW.id_estado_cuenta <> OLD.id_estado_cuenta THEN
                UPDATE modulo1.sesiones
                SET es_activa = FALSE
                WHERE id_cuenta_usuario = NEW.id_cuenta_usuario;
            END IF;
            RETURN NEW;
        END;
        $function$
        """
    )
