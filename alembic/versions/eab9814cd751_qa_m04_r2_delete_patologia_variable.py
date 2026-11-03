# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-03 | Arekkazu | QA-M04 ronda 2 CU01 H-14 RF-64: política DELETE para quitar variables de una patología |
"""qa m04 ronda 2: quitar variables de una patología bajo RLS

Revision ID: eab9814cd751
Revises: bb5526687aae
Create Date: 2026-11-03

Requiere la autorización de SamuelPR21 (DBA) antes de desplegar.

``4a4b067e7a24`` (RLS de modulo4) dejó ``modulo4.patologias_variables_sensoricas`` con
SELECT, INSERT y UPDATE para quien gestiona el catálogo, pero sin DELETE. Con FORCE RLS
un DELETE sin política no falla: no borra ninguna fila. Editar una patología personalizada
quitándole una variable (RF-64 proceso 4, CU-01 pasos 12-15) no podía aplicarse.

La política usa el mismo permiso que el INSERT y el UPDATE de la tabla (C, U o D sobre
``patologias``); el usuario de servicio ya tenía ``pol_patologia_variable_sensorica_servicio``
para todas las operaciones.
"""
from typing import Sequence, Union

from alembic import op


revision: str = 'eab9814cd751'
down_revision: Union[str, Sequence[str], None] = 'bb5526687aae'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE POLICY pol_patologia_variable_sensorica_delete ON modulo4.patologias_variables_sensoricas
          FOR DELETE USING (
            (SELECT modulo1.fn_tiene_permiso('patologias', 'C'))
            OR (SELECT modulo1.fn_tiene_permiso('patologias', 'U'))
            OR (SELECT modulo1.fn_tiene_permiso('patologias', 'D')));
    """)


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS pol_patologia_variable_sensorica_delete ON modulo4.patologias_variables_sensoricas;")
