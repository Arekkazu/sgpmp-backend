"""v5.3.0_sesiones_catalogo_eventos_refresh.

Revision ID: d8e232bc81a3
Revises: d014e2cc785d
Create Date: 2026-09-17 19:47:30.228203

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "d8e232bc81a3"
down_revision: Union[str, Sequence[str], None] = "d014e2cc785d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Formaliza los tipos que el flujo de refresh referencia por ID.

    El soporte de refresh se desplegó originalmente con un ``INSERT`` manual.
    Una base que sí recibió las columnas y el enum, pero no ese seed, acepta el
    login y falla al registrar la auditoría de la primera rotación. Como la
    auditoría es obligatoria, el ``commit`` revierte y el endpoint termina en
    HTTP 500.

    Los chequeos evitan apropiarse silenciosamente de un ID o nombre que otro
    ambiente hubiese usado para una operación distinta. Si la fila correcta ya
    existe, ``ON CONFLICT`` normaliza únicamente su descripción.
    """
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM modulo1.tipos_eventos
                WHERE id_tipo_evento = 23
                  AND nombre <> 'REFRESH_TOKEN_ROTADO'
            ) OR EXISTS (
                SELECT 1
                FROM modulo1.tipos_eventos
                WHERE nombre = 'REFRESH_TOKEN_ROTADO'
                  AND id_tipo_evento <> 23
            ) THEN
                RAISE EXCEPTION
                    'Conflicto en catalogo: REFRESH_TOKEN_ROTADO debe usar id 23';
            END IF;

            IF EXISTS (
                SELECT 1
                FROM modulo1.tipos_eventos
                WHERE id_tipo_evento = 24
                  AND nombre <> 'REUSO_TOKEN_REFRESCO_DETECTADO'
            ) OR EXISTS (
                SELECT 1
                FROM modulo1.tipos_eventos
                WHERE nombre = 'REUSO_TOKEN_REFRESCO_DETECTADO'
                  AND id_tipo_evento <> 24
            ) THEN
                RAISE EXCEPTION
                    'Conflicto en catalogo: REUSO_TOKEN_REFRESCO_DETECTADO debe usar id 24';
            END IF;
        END
        $$
        """
    )
    op.execute(
        """
        INSERT INTO modulo1.tipos_eventos (id_tipo_evento, nombre, accion)
        VALUES
            (23, 'REFRESH_TOKEN_ROTADO',
             'Renovacion de sesion via refresh token'),
            (24, 'REUSO_TOKEN_REFRESCO_DETECTADO',
             'Reuso de refresh token detectado - sesion revocada')
        ON CONFLICT (id_tipo_evento) DO UPDATE
        SET nombre = EXCLUDED.nombre,
            accion = EXCLUDED.accion
        """
    )


def downgrade() -> None:
    # La auditoría es inmutable y referencia el catálogo por FK. Solo se retira
    # cada fila cuando todavía no existen eventos de ese tipo.
    op.execute(
        """
        DELETE FROM modulo1.tipos_eventos AS t
        WHERE t.id_tipo_evento IN (23, 24)
          AND NOT EXISTS (
              SELECT 1
              FROM modulo1.eventos AS e
              WHERE e.tipo_evento = t.id_tipo_evento
          )
        """
    )
