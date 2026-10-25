"""RF-17: política DELETE en niveles_alerta_ambientales

Revision ID: b4e7c91d2a63
Revises: 7e1d4c2b9a30
Create Date: 2026-10-12 19:30:00

Editar o desactivar un umbral (CU-M09-03) respondía 500 "Error inesperado en
base de datos" con sgpmp_app. El repositorio reemplaza los tres niveles del
umbral (delete-then-insert, patrón de CLAUDE.md) y la F5 de modulo9 dejó la
tabla con políticas de SELECT, INSERT y UPDATE pero sin DELETE: bajo RLS el
DELETE borraba 0 filas sin error, y el INSERT de los niveles nuevos chocaba con
los viejos en trg_fn_niveles_alerta_solapamiento (P0113 OVERLAPPING_ALERT).

El borrado de niveles es parte de actualizar el umbral, así que exige el mismo
permiso que la política de UPDATE.
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'b4e7c91d2a63'
down_revision: Union[str, Sequence[str], None] = '7e1d4c2b9a30'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "CREATE POLICY pol_niveles_alerta_delete ON modulo9.niveles_alerta_ambientales "
        "FOR DELETE "
        "USING ((SELECT modulo1.fn_tiene_permiso('umbrales_ambientales', 'U')));"
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS pol_niveles_alerta_delete ON modulo9.niveles_alerta_ambientales;")
