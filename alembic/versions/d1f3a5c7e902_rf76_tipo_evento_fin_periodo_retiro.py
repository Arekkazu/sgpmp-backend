# | Fecha      | Nombre         | Que se hizo                                                               |
# |------------|----------------|---------------------------------------------------------------------------|
# | 2026-11-12 | LuisfNarvaez01 | INC-M05-352-G18 RF-76: aviso interno del fin del período de retiro         |
"""rf76: tipo de evento 42 FIN_PERIODO_RETIRO para la bandeja interna

Revision ID: d1f3a5c7e902
Revises: 603631775892
Create Date: 2026-11-12

INC-M05-352-G18 (#1072). RF-76 paso 13: «El sistema notifica internamente al Veterinario y
Productor que el período de retiro ha concluido». El fin de retiro solo se enviaba por correo
y solo al Productor. La notificación interna (RF-14) cuelga de un evento de
``modulo1.eventos``, así que necesita su tipo.

Id fijo (42), como los tipos 33-38 de M05 (``bf404c6f1018``): la categoría del evento se
resuelve por id en ``evento_categoria.py``. Si el 42 ya existe con otro nombre, la migración
falla en vez de dejar el catálogo desalineado.
"""
from typing import Sequence, Union

from alembic import op

revision: str = 'd1f3a5c7e902'
down_revision: Union[str, Sequence[str], None] = '603631775892'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_ID = 42
_NOMBRE = 'FIN_PERIODO_RETIRO'
_ACCION = 'Fin del periodo de retiro de un medicamento'


def upgrade() -> None:
    op.execute(f"""
        DO $$
        BEGIN
            LOCK TABLE modulo1.tipos_eventos IN SHARE ROW EXCLUSIVE MODE;
            IF EXISTS (
                SELECT 1 FROM modulo1.tipos_eventos
                 WHERE (id_tipo_evento = {_ID} AND nombre <> '{_NOMBRE}')
                    OR (nombre = '{_NOMBRE}' AND id_tipo_evento <> {_ID})
            ) THEN
                RAISE EXCEPTION 'M05: conflicto de identidad del tipo {_NOMBRE} ({_ID})';
            END IF;
            INSERT INTO modulo1.tipos_eventos (id_tipo_evento, nombre, accion)
            VALUES ({_ID}, '{_NOMBRE}', '{_ACCION}')
            ON CONFLICT (id_tipo_evento) DO NOTHING;
        END $$;
    """)
    # No retroceder una secuencia que ya esté por delante del catálogo.
    op.execute("""
        SELECT setval(
            'modulo1.tipos_evento_id_tipo_evento_seq',
            GREATEST(
                (SELECT max(id_tipo_evento) FROM modulo1.tipos_eventos),
                (SELECT last_value FROM modulo1.tipos_evento_id_tipo_evento_seq)
            ),
            true
        )
    """)


def downgrade() -> None:
    op.execute(f"""
        DELETE FROM modulo1.tipos_eventos t WHERE t.id_tipo_evento = {_ID} AND t.nombre = '{_NOMBRE}'
           AND NOT EXISTS (SELECT 1 FROM modulo1.eventos e WHERE e.tipo_evento = t.id_tipo_evento)
    """)
