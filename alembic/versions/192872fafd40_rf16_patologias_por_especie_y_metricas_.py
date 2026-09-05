"""rf16 patologias por especie y metricas checks

Revision ID: 192872fafd40
Revises: aa24fc52896e
Create Date: 2026-08-23 06:52:23.086279

RF-16 / #1633 — Patologías por especie.

Convierte `modulo9.especies_patologias` (antes pivot puro especie↔patología) en la
entidad M09 de patologías por especie: agrega nombre/descripcion/es_activo/
fecha_actualizacion/fecha_creacion, hace `id_patologia` opcional (vínculo al
catálogo clínico M04) y fuerza unicidad del nombre por especie (case-insensitive)
vía índice funcional `uq_especie_patologia_nombre (id_especie, lower(nombre))`.

`modulo9.patologias` (catálogo M04) y su constraint `uq_enfermedad_nombre` NO se
tocan: son propiedad de M04 (src/prediction) — FK modulo4.patologias_variables_sensoricas.

Además agrega, como defensa en profundidad, CHECKs sobre `modulo9.metricas_produccion`
para `tipo_medicion` y `aplica_a_tipo_activo` (la coherencia unidad↔tipo se valida en
la capa de aplicación). No se crean tipos ENUM (evita el conflicto de SQLAlchemy con
columnas varchar existentes; ver CLAUDE.md).

Idempotente (IF [NOT] EXISTS + guardas DO $$) para ser no-op seguro en entornos donde
ya se aplicó a mano (sgpmp / pruebas).
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '192872fafd40'
down_revision: Union[str, Sequence[str], None] = 'aa24fc52896e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- Patologías por especie: nuevas columnas en especies_patologias ---
    op.execute(
        """
        ALTER TABLE modulo9.especies_patologias
            ADD COLUMN IF NOT EXISTS nombre              varchar(60),
            ADD COLUMN IF NOT EXISTS descripcion         varchar(255),
            ADD COLUMN IF NOT EXISTS es_activo           boolean,
            ADD COLUMN IF NOT EXISTS fecha_actualizacion timestamptz,
            ADD COLUMN IF NOT EXISTS fecha_creacion      timestamptz;
        """
    )
    # Backfill desde el catálogo M04 para las filas pivot existentes.
    op.execute(
        """
        UPDATE modulo9.especies_patologias ep
        SET nombre         = p.nombre,
            descripcion    = p.descripcion,
            es_activo      = COALESCE(ep.es_activo, p.es_activo, true),
            fecha_creacion = COALESCE(ep.fecha_creacion, p.fecha_creacion_m04, now())
        FROM modulo9.patologias p
        WHERE p.id_patologia = ep.id_patologia
          AND ep.nombre IS NULL;
        """
    )
    # Fallback defensivo para filas huérfanas sin catálogo asociado.
    op.execute(
        """
        UPDATE modulo9.especies_patologias
        SET nombre         = COALESCE(nombre, 'patologia_' || id_especies_patologias),
            es_activo      = COALESCE(es_activo, true),
            fecha_creacion = COALESCE(fecha_creacion, now())
        WHERE nombre IS NULL;
        """
    )
    op.execute(
        """
        ALTER TABLE modulo9.especies_patologias
            ALTER COLUMN nombre         SET NOT NULL,
            ALTER COLUMN es_activo      SET NOT NULL,
            ALTER COLUMN es_activo      SET DEFAULT true,
            ALTER COLUMN fecha_creacion SET NOT NULL,
            ALTER COLUMN fecha_creacion SET DEFAULT now(),
            ALTER COLUMN id_patologia   DROP NOT NULL;
        """
    )
    # Unicidad por especie (case-insensitive) — reemplaza la unicidad por (id_patologia, id_especie).
    op.execute("ALTER TABLE modulo9.especies_patologias DROP CONSTRAINT IF EXISTS uq_especie_patologia;")
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_especie_patologia_nombre
        ON modulo9.especies_patologias (id_especie, lower(nombre));
        """
    )

    # --- Auditoría: apuntar a la fila por especie ---
    op.execute(
        """
        ALTER TABLE modulo9.auditorias_patologias
            ADD COLUMN IF NOT EXISTS id_especies_patologias integer;
        ALTER TABLE modulo9.auditorias_patologias
            ALTER COLUMN id_patologia DROP NOT NULL;
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'auditorias_patologias_id_especies_patologias_fkey'
            ) THEN
                ALTER TABLE modulo9.auditorias_patologias
                    ADD CONSTRAINT auditorias_patologias_id_especies_patologias_fkey
                    FOREIGN KEY (id_especies_patologias)
                    REFERENCES modulo9.especies_patologias(id_especies_patologias);
            END IF;
        END
        $$;
        """
    )

    # --- Métricas: CHECKs de dominio (defensa en profundidad) ---
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'chk_metricas_tipo_medicion') THEN
                ALTER TABLE modulo9.metricas_produccion
                    ADD CONSTRAINT chk_metricas_tipo_medicion
                    CHECK (tipo_medicion IN ('PESO','VOLUMEN','LONGITUD','CONTEO','OTRO')) NOT VALID;
            END IF;
            IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'chk_metricas_aplica_a_tipo_activo') THEN
                ALTER TABLE modulo9.metricas_produccion
                    ADD CONSTRAINT chk_metricas_aplica_a_tipo_activo
                    CHECK (aplica_a_tipo_activo IN ('INDIVIDUAL','LOTE','AMBOS')) NOT VALID;
            END IF;
        END
        $$;
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM modulo9.metricas_produccion
                WHERE tipo_medicion NOT IN ('PESO','VOLUMEN','LONGITUD','CONTEO','OTRO')
            ) THEN
                ALTER TABLE modulo9.metricas_produccion VALIDATE CONSTRAINT chk_metricas_tipo_medicion;
            END IF;
            IF NOT EXISTS (
                SELECT 1 FROM modulo9.metricas_produccion
                WHERE aplica_a_tipo_activo NOT IN ('INDIVIDUAL','LOTE','AMBOS')
            ) THEN
                ALTER TABLE modulo9.metricas_produccion VALIDATE CONSTRAINT chk_metricas_aplica_a_tipo_activo;
            END IF;
        END
        $$;
        """
    )


def downgrade() -> None:
    op.execute("ALTER TABLE modulo9.metricas_produccion DROP CONSTRAINT IF EXISTS chk_metricas_aplica_a_tipo_activo;")
    op.execute("ALTER TABLE modulo9.metricas_produccion DROP CONSTRAINT IF EXISTS chk_metricas_tipo_medicion;")

    op.execute(
        "ALTER TABLE modulo9.auditorias_patologias "
        "DROP CONSTRAINT IF EXISTS auditorias_patologias_id_especies_patologias_fkey;"
    )
    op.execute("ALTER TABLE modulo9.auditorias_patologias DROP COLUMN IF EXISTS id_especies_patologias;")
    # id_patologia NOT NULL no se restaura: puede haber quedado nullable con filas históricas.

    op.execute("DROP INDEX IF EXISTS modulo9.uq_especie_patologia_nombre;")
    op.execute(
        """
        ALTER TABLE modulo9.especies_patologias
            DROP COLUMN IF EXISTS fecha_creacion,
            DROP COLUMN IF EXISTS fecha_actualizacion,
            DROP COLUMN IF EXISTS es_activo,
            DROP COLUMN IF EXISTS descripcion,
            DROP COLUMN IF EXISTS nombre;
        """
    )
    # Restauración best-effort de la unicidad antigua (solo si no hay id_patologia NULL,
    # p.ej. filas creadas por M09 sin vínculo a catálogo M04).
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM modulo9.especies_patologias WHERE id_patologia IS NULL)
               AND NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'uq_especie_patologia') THEN
                ALTER TABLE modulo9.especies_patologias
                    ADD CONSTRAINT uq_especie_patologia UNIQUE (id_patologia, id_especie);
            END IF;
        END
        $$;
        """
    )
