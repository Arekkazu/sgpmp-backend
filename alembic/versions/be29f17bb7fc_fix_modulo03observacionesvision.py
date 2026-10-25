# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-23 | Arekkazu | INTEG RFC-012..016 DB-09: encadenada tras DB-08 (un solo head) |
"""fix_modulo03ObservacionesVision

Revision ID: be29f17bb7fc
Revises: 495a6545bdb1
Create Date: 2026-10-21 21:20:11.916204

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'be29f17bb7fc'
down_revision: Union[str, Sequence[str], None] = '495a6545bdb1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


TABLA = "modulo3.observaciones_vision"
CK_CALIBRACION = "ck_observacion_vision_estado_calibracion"


def upgrade() -> None:
    # El DEFAULT del enum falla de forma poco clara si la etiqueta no existe: se valida antes.
    existe = op.get_bind().execute(sa.text("""
        SELECT count(*) FROM pg_enum e
        JOIN pg_type t ON t.oid = e.enumtypid
        JOIN pg_namespace n ON n.oid = t.typnamespace
        WHERE n.nspname = 'modulo3' AND t.typname = 'enum_telemetria_origen' AND e.enumlabel = 'TIEMPO_REAL'
    """)).scalar()
    if existe != 1:
        raise RuntimeError("modulo3.enum_telemetria_origen no tiene el valor 'TIEMPO_REAL'")

    # 1. Nuevas columnas
    op.execute(f"""
        ALTER TABLE {TABLA}
            ADD COLUMN n_individuos_observados integer,
            ADD COLUMN origen modulo3.enum_telemetria_origen DEFAULT 'TIEMPO_REAL',
            ADD COLUMN json_flags_detectados jsonb,
            ADD COLUMN es_confianza_baja boolean
    """)
    op.execute(f"""
        ALTER TABLE {TABLA}
            ADD CONSTRAINT ck_observacion_vision_n_individuos_observados
            CHECK (n_individuos_observados >= 0)
    """)
    op.execute(f"COMMENT ON COLUMN {TABLA}.n_individuos_observados IS 'AIOT-SPEC-01: conteo de individuos observados en la ventana.'")
    op.execute(f"COMMENT ON COLUMN {TABLA}.origen IS 'AIOT-SPEC-01: origen de la observación (enum_telemetria_origen).'")
    op.execute(f"COMMENT ON COLUMN {TABLA}.json_flags_detectados IS 'AIOT-SPEC-01: flags detectados por el pipeline Edge/IA.'")
    op.execute(f"COMMENT ON COLUMN {TABLA}.es_confianza_baja IS 'AIOT-SPEC-01: indica que el nivel de confianza de la observación es bajo.'")

    # 2. Vocabulario de calibración: quitar CHECK obsoleto, migrar datos, crear CHECK nuevo
    op.execute(f"ALTER TABLE {TABLA} DROP CONSTRAINT {CK_CALIBRACION}")
    op.execute(f"""
        UPDATE {TABLA}
        SET estado_calibracion = CASE estado_calibracion
            WHEN 'CALIBRADA'     THEN 'CALIBRADO'
            WHEN 'DEGRADADA'     THEN 'EN_CALIBRACION'
            WHEN 'SIN_DETECCION' THEN 'SIN_LINEA_BASE'
        END
        WHERE estado_calibracion IN ('CALIBRADA', 'DEGRADADA', 'SIN_DETECCION')
    """)
    op.execute(f"""
        ALTER TABLE {TABLA}
            ADD CONSTRAINT {CK_CALIBRACION}
            CHECK (estado_calibracion::text = ANY (ARRAY['CALIBRADO'::text, 'EN_CALIBRACION'::text, 'SIN_LINEA_BASE'::text]))
    """)

    # 3. Imágenes estáticas: cantidad_tracks deja de ser obligatoria
    op.execute(f"ALTER TABLE {TABLA} ALTER COLUMN cantidad_tracks DROP NOT NULL")


def downgrade() -> None:
    # Evita que SET NOT NULL falle por filas creadas con la analítica de imágenes estáticas
    op.execute(f"UPDATE {TABLA} SET cantidad_tracks = 0 WHERE cantidad_tracks IS NULL")
    op.execute(f"ALTER TABLE {TABLA} ALTER COLUMN cantidad_tracks SET NOT NULL")

    op.execute(f"ALTER TABLE {TABLA} DROP CONSTRAINT {CK_CALIBRACION}")
    op.execute(f"""
        UPDATE {TABLA}
        SET estado_calibracion = CASE estado_calibracion
            WHEN 'CALIBRADO'      THEN 'CALIBRADA'
            WHEN 'EN_CALIBRACION' THEN 'DEGRADADA'
            WHEN 'SIN_LINEA_BASE' THEN 'SIN_DETECCION'
        END
        WHERE estado_calibracion IN ('CALIBRADO', 'EN_CALIBRACION', 'SIN_LINEA_BASE')
    """)
    op.execute(f"""
        ALTER TABLE {TABLA}
            ADD CONSTRAINT {CK_CALIBRACION}
            CHECK (estado_calibracion::text = ANY (ARRAY['CALIBRADA'::character varying, 'DEGRADADA'::character varying, 'SIN_DETECCION'::character varying]::text[]))
    """)

    op.execute(f"ALTER TABLE {TABLA} DROP CONSTRAINT IF EXISTS ck_observacion_vision_n_individuos_observados")
    op.execute(f"""
        ALTER TABLE {TABLA}
            DROP COLUMN IF EXISTS es_confianza_baja,
            DROP COLUMN IF EXISTS json_flags_detectados,
            DROP COLUMN IF EXISTS origen,
            DROP COLUMN IF EXISTS n_individuos_observados
    """)