"""RF-29: tipo de evento para el cambio de idioma personal

Revision ID: 5c844a858bde
Revises: c461638a6714
Create Date: 2026-09-18

TC-M09-G103 (#311): PATCH /configuracion/personalizacion/idioma persiste el
cambio correctamente pero nunca quedaba registrado en el historial de
auditoría (GET /auditoria/), aunque la tabla modulo1.eventos ya cubre "todos
los módulos del sistema" (comentario de la propia tabla) y el mecanismo ya
está construido -- solo faltaba el tipo de evento y la llamada a registrar().

El id_tipo_evento se fija explícitamente porque el catálogo se referencia por
número desde el código (mismo patrón que d9a47c30e5b1 y a3b7c1d95e40); tras
el insert se reposiciona la secuencia para que los inserts automáticos
posteriores no choquen contra la clave primaria.
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '5c844a858bde'
down_revision: Union[str, Sequence[str], None] = 'c461638a6714'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ID_TIPO_EVENTO = 27
NOMBRE = "CAMBIO_IDIOMA_PERSONAL"
ACCION = "Cambio de preferencia de idioma personal"


def upgrade() -> None:
    op.execute(
        f"""
        INSERT INTO modulo1.tipos_eventos (id_tipo_evento, nombre, accion)
        SELECT {ID_TIPO_EVENTO}, '{NOMBRE}', '{ACCION}'
        WHERE NOT EXISTS (
            SELECT 1 FROM modulo1.tipos_eventos
            WHERE id_tipo_evento = {ID_TIPO_EVENTO} OR nombre = '{NOMBRE}'
        )
        """
    )
    op.execute(
        """
        SELECT setval(
            'modulo1.tipos_evento_id_tipo_evento_seq',
            (SELECT max(id_tipo_evento) FROM modulo1.tipos_eventos)
        )
        """
    )


def downgrade() -> None:
    op.execute(
        f"""
        DELETE FROM modulo1.tipos_eventos
        WHERE id_tipo_evento = {ID_TIPO_EVENTO}
          AND NOT EXISTS (
              SELECT 1 FROM modulo1.eventos WHERE tipo_evento = {ID_TIPO_EVENTO}
          )
        """
    )
