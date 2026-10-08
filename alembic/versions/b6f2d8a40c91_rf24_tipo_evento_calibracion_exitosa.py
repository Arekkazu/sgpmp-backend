"""RF-24/RF-10: tipo de evento para calibraciones exitosas (issue #508).

Revision ID: b6f2d8a40c91
Revises: a3c9e5d17b42

El catálogo se referencia por ID desde el dominio. Se valida la identidad
antes de insertar para no reutilizar un ID o nombre de otro evento.
"""
from alembic import op


revision = "b6f2d8a40c91"
down_revision = "a3c9e5d17b42"
branch_labels = None
depends_on = None

ID_TIPO_EVENTO = 30
NOMBRE_TIPO_EVENTO = "CALIBRACION_EXITOSA"
ACCION_TIPO_EVENTO = "Registro exitoso de calibracion de sensor"


def upgrade() -> None:
    op.execute(
        f"""
        DO $$
        BEGIN
            LOCK TABLE modulo1.tipos_eventos IN SHARE ROW EXCLUSIVE MODE;
            IF EXISTS (
                SELECT 1 FROM modulo1.tipos_eventos
                 WHERE (id_tipo_evento = {ID_TIPO_EVENTO} AND nombre <> '{NOMBRE_TIPO_EVENTO}')
                    OR (nombre = '{NOMBRE_TIPO_EVENTO}' AND id_tipo_evento <> {ID_TIPO_EVENTO})
            ) THEN
                RAISE EXCEPTION 'RF-24: conflicto de identidad del tipo CALIBRACION_EXITOSA (30)';
            END IF;

            INSERT INTO modulo1.tipos_eventos (id_tipo_evento, nombre, accion)
            VALUES ({ID_TIPO_EVENTO}, '{NOMBRE_TIPO_EVENTO}', '{ACCION_TIPO_EVENTO}')
            ON CONFLICT (id_tipo_evento) DO NOTHING;
        END;
        $$;
        """
    )
    # No retroceder una secuencia que ya esté por delante del catálogo.
    op.execute(
        """
        SELECT setval(
            'modulo1.tipos_evento_id_tipo_evento_seq',
            GREATEST(
                (SELECT max(id_tipo_evento) FROM modulo1.tipos_eventos),
                (SELECT last_value FROM modulo1.tipos_evento_id_tipo_evento_seq)
            ),
            true
        )
        """
    )


def downgrade() -> None:
    # Conservar el catálogo si hay eventos activos o archivados que lo utilizan.
    op.execute(
        f"""
        DELETE FROM modulo1.tipos_eventos
         WHERE id_tipo_evento = {ID_TIPO_EVENTO}
           AND nombre = '{NOMBRE_TIPO_EVENTO}'
           AND NOT EXISTS (
               SELECT 1 FROM modulo1.eventos WHERE tipo_evento = {ID_TIPO_EVENTO}
           )
           AND NOT EXISTS (
               SELECT 1 FROM modulo1.eventos_archivados WHERE tipo_evento = {ID_TIPO_EVENTO}
           )
        """
    )
