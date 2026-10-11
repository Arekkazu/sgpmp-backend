"""inc_m02_72_g80_compatibilidad_tipo_infraestructura_especie

Revision ID: e83264b0b9cd
Revises: 68232a1efcc2
Create Date: 2026-09-12 06:51:47.580659

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'e83264b0b9cd'
down_revision: Union[str, Sequence[str], None] = '68232a1efcc2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # INC-M02-72-G80 (C2 / RF-48): no existia ningun modelo de compatibilidad
    # entre el tipo de infraestructura (modulo9.tipos_area, ya administrable)
    # y la especie del activo -- una transferencia de un bovino hacia un
    # Estanque se aceptaba sin rechazo. Ausencia de fila para un id_tipo_area
    # = sin restriccion configurada todavia (compatible por defecto, no rompe
    # infraestructuras existentes sin regla definida); presencia de al menos
    # una fila = lista blanca para ese tipo.
    op.execute("""
        CREATE TABLE modulo9.compatibilidades_tipo_area_especie (
            id_compatibilidad_tipo_area_especie SERIAL,
            id_tipo_area INTEGER NOT NULL,
            id_especie INTEGER NOT NULL,
            fecha_creacion TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT compatibilidades_tipo_area_especie_pkey
                PRIMARY KEY (id_compatibilidad_tipo_area_especie),
            CONSTRAINT compatibilidades_tipo_area_especie_id_tipo_area_fkey
                FOREIGN KEY (id_tipo_area) REFERENCES modulo9.tipos_area (id_tipo_area),
            CONSTRAINT compatibilidades_tipo_area_especie_id_especie_fkey
                FOREIGN KEY (id_especie) REFERENCES modulo9.especies (id_especie),
            CONSTRAINT uq_compatibilidad_tipo_area_especie UNIQUE (id_tipo_area, id_especie)
        )
    """)

    # Seed minimo para el caso real reportado: Estanque solo es compatible con
    # especies acuicolas. Coincide por nombre (no por id, que difiere entre
    # ambientes) -- si el nombre no existe en esta base, simplemente no se
    # inserta nada para esa especie, no falla la migracion.
    op.execute("""
        INSERT INTO modulo9.compatibilidades_tipo_area_especie (id_tipo_area, id_especie)
        SELECT ta.id_tipo_area, e.id_especie
        FROM modulo9.tipos_area ta
        CROSS JOIN modulo9.especies e
        WHERE ta.nombre = 'Estanque'
          AND e.nombre IN (
              'Trucha Arcoíris', 'Camarón Blanco', 'Cachama Blanca',
              'Mojarra Plateada', 'Tilapia', 'Tilapia Roja'
          )
    """)


def downgrade() -> None:
    op.execute("DROP TABLE modulo9.compatibilidades_tipo_area_especie")
