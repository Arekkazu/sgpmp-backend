"""FixVidaNacimientoCriticidad

Revision ID: 032b0b6db060
Revises: e5a3c9b17d42
Create Date: 2026-10-20 16:07:28.469311

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '032b0b6db060'
down_revision: Union[str, Sequence[str], None] = 'e5a3c9b17d42'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():

    op.add_column(
        'especies',
        sa.Column('esperanza_vida_dias', sa.Integer(), nullable=True),
        schema='modulo9'
    )
    
    op.execute(
        """
        ALTER TABLE modulo9.especies 
        ADD CONSTRAINT ck_especies_esperanza_vida 
        CHECK (esperanza_vida_dias IS NULL OR esperanza_vida_dias > 0);
        """
    )
    
    # Agregar constraint de densidad > 0 a la columna existente
    op.execute(
        """
        ALTER TABLE modulo9.especies 
        ADD CONSTRAINT ck_especies_densidad_mayor_cero 
        CHECK (densidad_maxima_por_especie IS NULL OR densidad_maxima_por_especie > 0);
        """
    )

    # ---------------------------------------------------------
    # 2. RFC-014: modulo2.detalles_activos_individuales
    # ---------------------------------------------------------
    # Hacer que la fecha de nacimiento sea opcional (DROP NOT NULL)
    op.alter_column(
        'detalles_activos_individuales',
        'fecha_nacimeinto', # Se conserva el typo intencionalmente
        existing_type=sa.DateTime(timezone=True),
        nullable=True,
        schema='modulo2'
    )

    # ---------------------------------------------------------
    # 3. RFC-016: modulo9.infraestructuras
    # ---------------------------------------------------------
    # Agregar nivel de criticidad
    # Al declarar server_default='MEDIA', PostgreSQL hace el backfill a las áreas existentes
    op.add_column(
        'infraestructuras',
        sa.Column('nivel_criticidad', sa.String(length=10), nullable=False, server_default='MEDIA'),
        schema='modulo9'
    )
    
    # Agregar constraint de valores válidos
    op.execute(
        """
        ALTER TABLE modulo9.infraestructuras 
        ADD CONSTRAINT ck_infraestructuras_criticidad 
        CHECK (nivel_criticidad IN ('ALTA', 'MEDIA', 'BAJA'));
        """
    )


def downgrade():
    # ---------------------------------------------------------
    # 3. RFC-016: modulo9.infraestructuras
    # ---------------------------------------------------------
    op.execute("ALTER TABLE modulo9.infraestructuras DROP CONSTRAINT ck_infraestructuras_criticidad;")
    op.drop_column('infraestructuras', 'nivel_criticidad', schema='modulo9')

    # ---------------------------------------------------------
    # 2. RFC-014: modulo2.detalles_activos_individuales
    # ---------------------------------------------------------
    # RIESGO: Si en prod ya se insertaron NULLs, el DROP NOT NULL fallará al revertir.
    # Asignamos la fecha_creacion del registro como fecha temporal para aquellos animales en NULL.
    op.execute(
        """
        UPDATE modulo2.detalles_activos_individuales 
        SET fecha_nacimeinto = fecha_creacion 
        WHERE fecha_nacimeinto IS NULL;
        """
    )
    
    # Restaurar obligatoriedad (SET NOT NULL)
    op.alter_column(
        'detalles_activos_individuales',
        'fecha_nacimeinto',
        existing_type=sa.DateTime(timezone=True),
        nullable=False,
        schema='modulo2'
    )

    # ---------------------------------------------------------
    # 1. RFC-014 y RFC-012: modulo9.especies
    # ---------------------------------------------------------
    op.execute("ALTER TABLE modulo9.especies DROP CONSTRAINT ck_especies_densidad_mayor_cero;")
    op.execute("ALTER TABLE modulo9.especies DROP CONSTRAINT ck_especies_esperanza_vida;")
    op.drop_column('especies', 'esperanza_vida_dias', schema='modulo9')