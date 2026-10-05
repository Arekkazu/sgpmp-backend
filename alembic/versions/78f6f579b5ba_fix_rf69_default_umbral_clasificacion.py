"""RF-69: el default de umbral_clasificacion no cabía en su columna

Revision ID: 78f6f579b5ba
Revises: cf12e716a4ec
Create Date: 2026-10-05

`modulo4.versiones_modelos.umbral_clasificacion` es `numeric(5,4)` (máximo
9.9999) pero su default era `70.00`. Como RegistrarVersionModeloUseCase no envía
ese campo, todo INSERT caía en "numeric field overflow" y RF-69 respondía 400
VALOR_FUERA_DE_RANGO para cualquier versión, en DEV incluido.

La columna es una fracción, igual que las demás métricas de la tabla
(`f1_score`, `accuracy`... en `numeric(5,4)`), que los umbrales de la app (RF-65:
0.50–0.95) y que los datos que ya hay en DEV (0.70 y 0.75). El `70.00` y el CHECK
0–100 eran restos de un diseño en porcentaje que solo usan procedimientos de BD
que la aplicación no invoca (`sp_ejecutar_inferencia`, con probabilidad simulada).
Se alinean default y CHECK a la fracción; la columna, los datos y la vista
`vw_m04_caracteristicas_version_modelo` no cambian.
"""
from typing import Sequence, Union

from alembic import op


revision: str = '78f6f579b5ba'
down_revision: Union[str, Sequence[str], None] = 'cf12e716a4ec'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE modulo4.versiones_modelos
            ALTER COLUMN umbral_clasificacion SET DEFAULT 0.7000,
            DROP CONSTRAINT chk_umbral_version,
            ADD CONSTRAINT chk_umbral_version CHECK (umbral_clasificacion BETWEEN 0 AND 1);
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE modulo4.versiones_modelos
            DROP CONSTRAINT chk_umbral_version,
            ADD CONSTRAINT chk_umbral_version CHECK (umbral_clasificacion >= 0 AND umbral_clasificacion <= 100),
            ALTER COLUMN umbral_clasificacion SET DEFAULT 70.00;
        """
    )
