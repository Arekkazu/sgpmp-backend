"""RF-10: tipo de evento para la exportación del historial de auditoría.

Revision ID: d9a47c30e5b1
Revises: e8bb4f321a44
Create Date: 2026-08-31 10:40:00.000000

Exportar el historial completo se hacía paginando de a 50 registros, así que una
sola descarga dejaba hasta 200 eventos ``CONSULTA_AUDITORIA``: el log quedaba
contaminado con el ruido de leerlo. El endpoint de exportación registra ahora un
único evento, y necesita un tipo propio para que "quién exportó la auditoría" sea
una consulta directa sobre ``tipo_evento`` y no una búsqueda dentro del JSON de
``detalle``.

El ``id_tipo_evento`` se fija explícitamente porque el catálogo se referencia por
número desde el código; tras el insert se reposiciona la secuencia para que los
inserts automáticos posteriores no choquen contra la clave primaria.
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'd9a47c30e5b1'
down_revision: Union[str, Sequence[str], None] = 'e8bb4f321a44'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ID_TIPO_EVENTO = 26
NOMBRE = "EXPORTACION_AUDITORIA"
# `accion` es varchar(50): descripcion corta, mismo estilo que el resto del catalogo.
ACCION = "Exportacion del historial de auditoria"


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
    # Los eventos ya registrados con este tipo tienen FK hacia el catálogo y son
    # inmutables, así que solo se retira la fila si nadie la referencia.
    op.execute(
        f"""
        DELETE FROM modulo1.tipos_eventos
        WHERE id_tipo_evento = {ID_TIPO_EVENTO}
          AND NOT EXISTS (
              SELECT 1 FROM modulo1.eventos WHERE tipo_evento = {ID_TIPO_EVENTO}
          )
        """
    )
