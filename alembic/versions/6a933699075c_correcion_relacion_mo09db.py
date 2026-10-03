"""correcion relacion MO09DB

Revision ID: 6a933699075c
Revises: 315eaa6c5dc1
Create Date: 2026-10-03 13:06:18.893558

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6a933699075c'
down_revision: Union[str, Sequence[str], None] = '315eaa6c5dc1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # =========================================================
    # Datos de prueba/semilla, no hay nada real que preservar.
    # Se descartan explicitamente en vez de intentar backfill
    # a ciegas sobre que finca "deberia" tener cada fila.
    # =========================================================
    op.execute("TRUNCATE TABLE modulo9.configuraciones_globales;")
    op.execute("TRUNCATE TABLE modulo9.plantillas, modulo9.aplicaciones_plantillas CASCADE;")
    op.execute("TRUNCATE TABLE modulo9.dashboard_layouts_default;")

    # =========================================================
    # configuraciones_globales: de "una activa en todo el sistema"
    # a "una activa por finca"
    # =========================================================
    op.execute("""
        ALTER TABLE modulo9.configuraciones_globales
          ADD COLUMN id_finca integer NOT NULL
          REFERENCES modulo9.fincas(id_finca);
    """)
    op.execute("""
        CREATE UNIQUE INDEX uq_config_global_activa_por_finca
          ON modulo9.configuraciones_globales(id_finca)
          WHERE es_activo = true;
    """)

    # =========================================================
    # plantillas: de "nombre unico en todo el sistema" a
    # "nombre unico por finca". Cada finca crea las suyas.
    # =========================================================
    op.execute("""
        ALTER TABLE modulo9.plantillas
          ADD COLUMN id_finca integer NOT NULL
          REFERENCES modulo9.fincas(id_finca);
    """)
    op.execute("ALTER TABLE modulo9.plantillas DROP CONSTRAINT uq_plantillas_nombre_version;")
    op.execute("""
        ALTER TABLE modulo9.plantillas
          ADD CONSTRAINT uq_plantillas_finca_nombre_version
          UNIQUE (id_finca, template_name, version);
    """)

    # =========================================================
    # aplicaciones_plantillas: hereda el id_finca de su plantilla.
    # Se denormaliza en vez de resolverla por join en cada politica,
    # igual que decidimos para fincas/infraestructuras en F4.
    # =========================================================
    op.execute("""
        ALTER TABLE modulo9.aplicaciones_plantillas
          ADD COLUMN id_finca integer NOT NULL
          REFERENCES modulo9.fincas(id_finca);
    """)

    # =========================================================
    # dashboard_layouts_default: de "un default por rol" a
    # "un default por rol y por finca" -- clave compuesta.
    # =========================================================
    op.execute("""
        ALTER TABLE modulo9.dashboard_layouts_default
          ADD COLUMN id_finca integer NOT NULL
          REFERENCES modulo9.fincas(id_finca);
    """)
    op.execute("ALTER TABLE modulo9.dashboard_layouts_default DROP CONSTRAINT dashboard_layouts_default_pkey;")
    op.execute("""
        ALTER TABLE modulo9.dashboard_layouts_default
          ADD CONSTRAINT dashboard_layouts_default_pkey
          PRIMARY KEY (id_rol, id_finca);
    """)


def downgrade() -> None:
    op.execute("ALTER TABLE modulo9.dashboard_layouts_default DROP CONSTRAINT dashboard_layouts_default_pkey;")
    op.execute("ALTER TABLE modulo9.dashboard_layouts_default DROP COLUMN id_finca;")
    op.execute("""
        ALTER TABLE modulo9.dashboard_layouts_default
          ADD CONSTRAINT dashboard_layouts_default_pkey PRIMARY KEY (id_rol);
    """)

    op.execute("ALTER TABLE modulo9.aplicaciones_plantillas DROP COLUMN id_finca;")

    op.execute("ALTER TABLE modulo9.plantillas DROP CONSTRAINT uq_plantillas_finca_nombre_version;")
    op.execute("ALTER TABLE modulo9.plantillas DROP COLUMN id_finca;")
    op.execute("""
        ALTER TABLE modulo9.plantillas
          ADD CONSTRAINT uq_plantillas_nombre_version UNIQUE (template_name, version);
    """)

    op.execute("DROP INDEX IF EXISTS modulo9.uq_config_global_activa_por_finca;")
    op.execute("ALTER TABLE modulo9.configuraciones_globales DROP COLUMN id_finca;")