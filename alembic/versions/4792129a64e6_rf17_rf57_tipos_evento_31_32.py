# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-23 | Arekkazu | DEV-25 RF-17 / DEV-32 RF-57: siembra los tipos de evento 31 y 32 |
"""RF-17 / RF-57 (RF-10): tipos de evento 31 CAMBIO_VARIABLE_CRITICA y 32 NOTIFICACION_ALERTA.

Revision ID: 4792129a64e6
Revises: 6af49e8c2d10

DEV-25 audita el cambio de es_critica con el tipo 31 y DEV-32 la notificación
de una alerta con el 32; sin estas filas el INSERT en modulo1.eventos falla por
FK. Mismo patrón que b6f2d8a40c91: se valida la identidad antes de insertar.
"""
from alembic import op


revision = "4792129a64e6"
down_revision = "6af49e8c2d10"
branch_labels = None
depends_on = None

TIPOS_EVENTO = (
    (31, "CAMBIO_VARIABLE_CRITICA", "Cambio de marca critica de variable ambiental"),
    (32, "NOTIFICACION_ALERTA", "Notificacion de una alerta operativa"),
)


def upgrade() -> None:
    for id_tipo, nombre, accion in TIPOS_EVENTO:
        op.execute(
            f"""
            DO $$
            BEGIN
                LOCK TABLE modulo1.tipos_eventos IN SHARE ROW EXCLUSIVE MODE;
                IF EXISTS (
                    SELECT 1 FROM modulo1.tipos_eventos
                     WHERE (id_tipo_evento = {id_tipo} AND nombre <> '{nombre}')
                        OR (nombre = '{nombre}' AND id_tipo_evento <> {id_tipo})
                ) THEN
                    RAISE EXCEPTION 'RF-10: conflicto de identidad del tipo {nombre} ({id_tipo})';
                END IF;

                INSERT INTO modulo1.tipos_eventos (id_tipo_evento, nombre, accion)
                VALUES ({id_tipo}, '{nombre}', '{accion}')
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
    for id_tipo, nombre, _ in TIPOS_EVENTO:
        op.execute(
            f"""
            DELETE FROM modulo1.tipos_eventos
             WHERE id_tipo_evento = {id_tipo}
               AND nombre = '{nombre}'
               AND NOT EXISTS (SELECT 1 FROM modulo1.eventos WHERE tipo_evento = {id_tipo})
               AND NOT EXISTS (SELECT 1 FROM modulo1.eventos_archivados WHERE tipo_evento = {id_tipo})
            """
        )
