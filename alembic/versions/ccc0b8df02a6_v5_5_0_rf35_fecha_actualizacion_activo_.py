"""v5.5.0_rf35_fecha_actualizacion_activo_biologico

Revision ID: ccc0b8df02a6
Revises: e5ce9d42b2ec
Create Date: 2026-09-23 01:05:00.000000

Tarea Taiga "RF-35: RBAC Veterinario, validar eventos pendientes,
concurrencia optimista" (issue histórico #30). El PATCH de activo individual
(RF-35) no tenía concurrencia optimista (412), a diferencia del patrón
estándar del proyecto (CLAUDE.md). Confirmado en vivo vía MCP de Postgres
antes de escribir esta migración: `modulo2.activos_biologicos` no tenía
ninguna columna `fecha_actualizacion` (ni ninguna otra columna de auditoría
de última modificación). Se agrega `nullable` y sin default, siguiendo el
mismo patrón usado para `modulo9.especies` (RF-15): permanece NULL para los
activos existentes y para los recién creados hasta su primera edición vía
PATCH, momento en el que el use case la establece por primera vez.
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "ccc0b8df02a6"
down_revision: Union[str, Sequence[str], None] = "e5ce9d42b2ec"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE modulo2.activos_biologicos
            ADD COLUMN IF NOT EXISTS fecha_actualizacion timestamptz;
        """
    )
    op.execute(
        """
        COMMENT ON COLUMN modulo2.activos_biologicos.fecha_actualizacion IS
            'Fecha y hora de la última modificación. Usada para control de concurrencia optimista (RF-35).';
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE modulo2.activos_biologicos
            DROP COLUMN IF EXISTS fecha_actualizacion;
        """
    )
