"""RF-23 v1.1: fps en la configuracion remota de camaras

Revision ID: 7b3d9e2f4a61
Revises: 4e7b2a9c1d05
Create Date: 2026-10-09 22:30:00.000000

RF-23 v1.1 (completacion RFC-011): para la categoria CAMARA no aplican
frecuencia_captura ni intervalo_transmision; su parametro operativo es fps
(rango 1-60, RF-21). modulo9.configuraciones_remotas guarda ahora uno de dos
juegos de parametros, nunca ambos:

  - SENSOR: frecuencia_captura + intervalo_transmision, fps NULL.
  - CAMARA: fps, frecuencia_captura e intervalo_transmision NULL.

El trigger de tiempos solo valida el juego SENSOR.
"""
from alembic import op

revision = '7b3d9e2f4a61'
down_revision = '4e7b2a9c1d05'
branch_labels = None
depends_on = None

_TRIGGER_FN = """
CREATE OR REPLACE FUNCTION modulo9.trg_fn_configuracion_remota_tiempos_validos() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    {guarda_camara}
    IF NEW.frecuencia_captura IS NULL OR NEW.frecuencia_captura <= 0 THEN
        RAISE EXCEPTION 'INVALID_CONFIG: La frecuencia de captura debe ser un entero positivo mayor a 0. Valor recibido: %.',
            NEW.frecuencia_captura
            USING ERRCODE = 'P0137';
    END IF;

    IF NEW.intervalo_transmision IS NULL OR NEW.intervalo_transmision <= 0 THEN
        RAISE EXCEPTION 'INVALID_CONFIG: El intervalo de transmisión debe ser un entero positivo mayor a 0. Valor recibido: %.',
            NEW.intervalo_transmision
            USING ERRCODE = 'P0137';
    END IF;

    IF NEW.intervalo_transmision < NEW.frecuencia_captura THEN
        RAISE EXCEPTION 'INVALID_CONFIG: El intervalo de transmisión (%) no puede ser menor a la frecuencia de captura (%). No se puede transmitir antes de capturar.',
            NEW.intervalo_transmision, NEW.frecuencia_captura
            USING ERRCODE = 'P0138';
    END IF;

    RETURN NEW;
END;
$$;
"""

# Una configuracion de camara (fps) no lleva tiempos de sensor: el CHECK
# ck_configuracion_remota_parametros ya garantiza que vengan en NULL.
_GUARDA_CAMARA = "IF NEW.fps IS NOT NULL THEN RETURN NEW; END IF;"


def upgrade() -> None:
    op.execute("ALTER TABLE modulo9.configuraciones_remotas ADD COLUMN fps integer")
    op.execute("ALTER TABLE modulo9.configuraciones_remotas ALTER COLUMN frecuencia_captura DROP NOT NULL")
    op.execute("ALTER TABLE modulo9.configuraciones_remotas ALTER COLUMN intervalo_transmision DROP NOT NULL")
    op.execute("""
        ALTER TABLE modulo9.configuraciones_remotas
        ADD CONSTRAINT ck_configuracion_remota_parametros CHECK (
            (fps IS NULL AND frecuencia_captura IS NOT NULL AND intervalo_transmision IS NOT NULL)
            OR (fps BETWEEN 1 AND 60 AND frecuencia_captura IS NULL AND intervalo_transmision IS NULL)
        )
    """)
    op.execute(_TRIGGER_FN.format(guarda_camara=_GUARDA_CAMARA))


def downgrade() -> None:
    # Las configuraciones de camara no caben en el esquema anterior (NOT NULL).
    op.execute("DELETE FROM modulo9.configuraciones_remotas WHERE fps IS NOT NULL")
    op.execute(_TRIGGER_FN.format(guarda_camara=""))
    op.execute("ALTER TABLE modulo9.configuraciones_remotas DROP CONSTRAINT ck_configuracion_remota_parametros")
    op.execute("ALTER TABLE modulo9.configuraciones_remotas ALTER COLUMN intervalo_transmision SET NOT NULL")
    op.execute("ALTER TABLE modulo9.configuraciones_remotas ALTER COLUMN frecuencia_captura SET NOT NULL")
    op.execute("ALTER TABLE modulo9.configuraciones_remotas DROP COLUMN fps")
