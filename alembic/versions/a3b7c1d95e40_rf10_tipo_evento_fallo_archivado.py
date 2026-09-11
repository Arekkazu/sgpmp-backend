"""RF-10: tipo de evento para el fallo del archivado automático.

Revision ID: a3b7c1d95e40
Revises: 8fc28a787fc8
Create Date: 2026-08-27 12:10:00.000000

El flujo alterno "Error en el proceso de archivado automático" exige disparar una
alerta al administrador. La alerta se emite como notificación interna (RF-14), y
``modulo1.notificaciones.id_evento`` es NOT NULL con FK hacia ``modulo1.eventos``,
así que primero debe existir un tipo de evento propio para el fallo.

El ``id_tipo_evento`` se fija explícitamente porque el catálogo se referencia por
número desde el código; tras el insert se reposiciona la secuencia para que los
inserts automáticos posteriores no choquen contra la clave primaria.
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'a3b7c1d95e40'
down_revision: Union[str, Sequence[str], None] = '8fc28a787fc8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ID_TIPO_EVENTO = 25
NOMBRE = "FALLO_ARCHIVADO_AUDITORIA"
# `accion` es varchar(50): descripcion corta, mismo estilo que el resto del catalogo.
ACCION = "Fallo en la politica de retencion de auditoria"


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
