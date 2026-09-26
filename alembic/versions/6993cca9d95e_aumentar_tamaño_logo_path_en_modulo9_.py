"""Aumentar tamaño logo_path en modulo9.indentdiades visuales

Revision ID: 6993cca9d95e
Revises: a50010e91978
Create Date: 2026-09-07 10:04:08.646427

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6993cca9d95e'
down_revision: Union[str, Sequence[str], None] = 'a50010e91978'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.execute("DROP VIEW IF EXISTS modulo9.vw_rf26_identidad_visual_activa;")
    
    op.execute("ALTER TABLE modulo9.identidad_visuales ALTER COLUMN logo_path TYPE VARCHAR(500);")
    
    op.execute("""
    CREATE OR REPLACE VIEW modulo9.vw_rf26_identidad_visual_activa AS
    SELECT DISTINCT ON (iv.id_finca) iv.id_finca,
        iv.id_identidad_visual,
        iv.logo_path,
        iv.primary_color,
        iv.secondary_color,
        iv.org_display_name,
        iv.version,
        iv.fecha_creacion,
        f.nombre AS finca,
        iv.id_usuario,
        concat_ws(' '::text, u.nombre, u.apellidos) AS modificado_por
    FROM modulo9.identidad_visuales iv
        JOIN modulo9.fincas f ON f.id_finca = iv.id_finca
        JOIN modulo1.usuarios u ON u.id_usuario = iv.id_usuario
    ORDER BY iv.id_finca, iv.version DESC NULLS LAST, iv.fecha_creacion DESC NULLS LAST, iv.id_identidad_visual DESC;
    """)

def downgrade():
    op.execute("DROP VIEW IF EXISTS modulo9.vw_rf26_identidad_visual_activa;")
    
    op.execute("ALTER TABLE modulo9.identidad_visuales ALTER COLUMN logo_path TYPE VARCHAR(255);")
    
    op.execute("""
    CREATE OR REPLACE VIEW modulo9.vw_rf26_identidad_visual_activa AS
    SELECT DISTINCT ON (iv.id_finca) iv.id_finca,
        iv.id_identidad_visual,
        iv.logo_path,
        iv.primary_color,
        iv.secondary_color,
        iv.org_display_name,
        iv.version,
        iv.fecha_creacion,
        f.nombre AS finca,
        iv.id_usuario,
        concat_ws(' '::text, u.nombre, u.apellidos) AS modificado_por
    FROM modulo9.identidad_visuales iv
        JOIN modulo9.fincas f ON f.id_finca = iv.id_finca
        JOIN modulo1.usuarios u ON u.id_usuario = iv.id_usuario
    ORDER BY iv.id_finca, iv.version DESC NULLS LAST, iv.fecha_creacion DESC NULLS LAST, iv.id_identidad_visual DESC;
    """)