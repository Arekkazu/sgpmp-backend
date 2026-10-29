"""rf11_rf12_retirar_usuarios_a_productor

Revision ID: 2672a752c041
Revises: 9947f4621939
Create Date: 2026-10-08 11:00:00.000000

M1-01 (reporte de evaluación de usabilidad UAT, 07/10/2026, severidad crítica):
en TEST el Productor entra a Gestión de usuarios y ve los 84 usuarios con sus
correos, incluidos los administradores. RF-11 y RF-12 solo tienen como actor al
Administrador. El acceso viene de filas activas en `modulo1.permisos` para
(Productor, recurso 1 `usuarios`), así que la corrección es de datos: se
desactivan esas filas. Es idempotente: donde no existen (dev local) no hace nada.
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "2672a752c041"
down_revision: Union[str, Sequence[str], None] = "9947f4621939"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM modulo1.roles
                WHERE id_rol = 2 AND lower(btrim(nombre_rol)) = 'productor'
            ) THEN
                RAISE EXCEPTION 'M1-01: id_rol=2 no corresponde al rol Productor';
            END IF;

            IF NOT EXISTS (
                SELECT 1 FROM modulo1.recursos
                WHERE id_recurso = 1 AND lower(btrim(nombre_recurso)) = 'usuarios'
            ) THEN
                RAISE EXCEPTION 'M1-01: id_recurso=1 no corresponde al recurso usuarios';
            END IF;

            UPDATE modulo1.permisos
            SET es_activo = false
            WHERE id_rol = 2
              AND id_recurso = 1
              AND es_activo IS TRUE;
        END $$;
        """
    )


def downgrade() -> None:
    # No se reactivan: no hay forma de saber qué filas estaban activas antes y
    # reabrir el acceso a usuarios sería reintroducir el hallazgo. Si un rol lo
    # necesita, se asigna por `POST /roles/{id_rol}/permisos`.
    pass
