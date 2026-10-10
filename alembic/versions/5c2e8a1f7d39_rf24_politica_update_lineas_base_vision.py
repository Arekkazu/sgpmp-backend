"""RF-24 v2.0: restaurar la politica RLS de UPDATE de lineas_base_vision

Revision ID: 5c2e8a1f7d39
Revises: 7b3d9e2f4a61
Create Date: 2026-10-10 12:00:00.000000

La migracion de VISION (d7a41c9e2b58) creo pol_lineas_base_vision_update, pero
la F5 de modulo9 (bd9cea80dea6) reconstruyo las politicas de la tabla solo con
SELECT, INSERT y servicio. Sin politica de UPDATE, el SELECT ... FOR UPDATE con
el que el repositorio localiza la linea vigente no devuelve filas: el
repositorio cree que no existe, inserta y choca con el indice unico
linea_base_vision_id_infraestructura_id_especie (409 RECURSO_DUPLICADO). Toda
recalibracion de un par (area, especie) fallaba (TC-M09-276, G137).

Se restaura con el mismo criterio F5 que SELECT e INSERT: infraestructuras del
usuario actual.
"""
from alembic import op

revision = '5c2e8a1f7d39'
down_revision = '7b3d9e2f4a61'
branch_labels = None
depends_on = None

_INFRA_SUBQ = (
    "SELECT i.id_infraestructura FROM modulo9.fn_infraestructuras_del_usuario("
    "(SELECT modulo1.fn_id_usuario_actual())) i"
)


def upgrade() -> None:
    op.execute("DROP POLICY IF EXISTS pol_lineas_base_vision_update ON modulo9.lineas_base_vision;")
    op.execute(f"""
        CREATE POLICY pol_lineas_base_vision_update ON modulo9.lineas_base_vision
          FOR UPDATE
          USING (id_infraestructura IN ({_INFRA_SUBQ}))
          WITH CHECK (id_infraestructura IN ({_INFRA_SUBQ}));
    """)


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS pol_lineas_base_vision_update ON modulo9.lineas_base_vision;")
