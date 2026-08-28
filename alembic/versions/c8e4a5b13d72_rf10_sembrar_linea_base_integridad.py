"""RF-10: siembra de la línea base de integridad de auditoría.

Revision ID: c8e4a5b13d72
Revises: b5d81f27ac93
Create Date: 2026-08-28 05:20:00.000000

Registra, una sola vez y por ambiente, los eventos que ya no eran verificables
al adoptar la verificación estricta del hash. Son de dos clases:

- ``SIN_HASH``: se escribieron antes de que el hash fuera obligatorio.
- ``ESQUEMA_ANTERIOR``: tienen hash, pero calculado con una fórmula distinta a
  la actual, así que nunca volverá a coincidir.

Ambas son inmutables por trigger, de modo que no se pueden reparar. Sin esta
línea base, el 500 del flujo alterno de hash mismatch sería permanente sobre
registros legítimos.

Se guarda el hash **recalculado** en el momento de la siembra, no el almacenado:
así, si el contenido de uno de estos registros cambiara después, el recálculo
dejaría de coincidir con la línea base y el evento pasaría a reportarse como
manipulado, que es justamente lo que el RF quiere detectar.

La fórmula del hash se replica aquí de forma literal en vez de importarla del
repositorio: una migración debe seguir produciendo el mismo resultado aunque el
código de la aplicación cambie más adelante.
"""
import hashlib
import json
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c8e4a5b13d72'
down_revision: Union[str, Sequence[str], None] = 'b5d81f27ac93'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _hash_del_contenido(fila) -> str:
    contenido = json.dumps(
        {
            "tipo_evento": fila.tipo_evento,
            "fecha_evento": fila.fecha_evento.isoformat() if fila.fecha_evento else None,
            "id_usuario": fila.id_usuario,
            "resultado": fila.resultado,
            "modulo": fila.modulo,
            "detalle": fila.detalle,
        },
        sort_keys=True,
        default=str,
    )
    return hashlib.sha256(contenido.encode("utf-8")).hexdigest()


def upgrade() -> None:
    conexion = op.get_bind()
    filas = conexion.execute(
        sa.text(
            """
            SELECT e.id_evento, e.tipo_evento, e.fecha_evento, e.modulo,
                   e.resultado::text AS resultado, e.detalle, e.id_usuario,
                   e.hash_integridad
            FROM modulo1.eventos AS e
            WHERE NOT EXISTS (
                SELECT 1 FROM modulo1.integridad_baseline AS b
                WHERE b.id_evento = e.id_evento
            )
            """
        )
    ).all()

    pendientes = []
    for fila in filas:
        calculado = _hash_del_contenido(fila)
        if fila.hash_integridad is None:
            pendientes.append(
                {"id": fila.id_evento, "hash": calculado, "motivo": "SIN_HASH"}
            )
        elif calculado != fila.hash_integridad:
            pendientes.append(
                {"id": fila.id_evento, "hash": calculado, "motivo": "ESQUEMA_ANTERIOR"}
            )

    if pendientes:
        conexion.execute(
            sa.text(
                """
                INSERT INTO modulo1.integridad_baseline
                    (id_evento, hash_calculado, motivo)
                VALUES (:id, :hash, :motivo)
                ON CONFLICT (id_evento) DO NOTHING
                """
            ),
            pendientes,
        )


def downgrade() -> None:
    # El trigger de inmutabilidad bloquea DELETE fila a fila, así que la única
    # forma de revertir es recrear la tabla; eso lo hace el downgrade de
    # b5d81f27ac93. Aquí no hay nada que deshacer por separado.
    pass
