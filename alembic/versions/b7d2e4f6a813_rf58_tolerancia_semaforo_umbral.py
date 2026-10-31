# | Fecha      | Nombre | Que se hizo                                                        |
# |------------|--------|--------------------------------------------------------------------|
# | 2026-10-31 | Claude | INC-M03-246-G88 RF-58: tolerancia T del semáforo configurable en M09 |
# | 2026-10-31 | Arekkazu | INC-M03-246-G88 RF-58: encadena tras 785022cc8ef9 (#870/#891/#890) para no dejar dos heads |
"""rf58: tolerancia T del semáforo configurable en el umbral (M09)

Revision ID: b7d2e4f6a813
Revises: 785022cc8ef9
Create Date: 2026-10-31

INC-M03-246-G88 (#889, TC-M03-172). RF-58 Fase 3 clasifica la lectura contra el
umbral con una tolerancia T: VERDE dentro de [valor_min, valor_max], AMARILLO
fuera pero a menos de T del borde y ROJO más allá. T estaba fija en el código
(10 % del rango) y M09 no tenía dónde configurarla.

- `modulo9.umbrales_ambientales.tolerancia_semaforo`: T en la unidad del umbral.
  NULL conserva el valor por defecto (10 % del rango) para los umbrales existentes.
- `ck_umbral_ambiental_tolerancia_semaforo`: T no puede ser negativa.

La columna entra sola en la auditoría genérica (`trg_auditoria`) y en la del umbral
(`_snapshot`). No cambia RLS: las políticas existentes son por fila, no por columna.
"""
from typing import Sequence, Union

from alembic import op


revision: str = 'b7d2e4f6a813'
down_revision: Union[str, Sequence[str], None] = '785022cc8ef9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE modulo9.umbrales_ambientales
            ADD COLUMN IF NOT EXISTS tolerancia_semaforo NUMERIC(5,2)
    """)
    op.execute("""
        ALTER TABLE modulo9.umbrales_ambientales
            ADD CONSTRAINT ck_umbral_ambiental_tolerancia_semaforo
            CHECK (tolerancia_semaforo IS NULL OR tolerancia_semaforo >= 0)
    """)
    op.execute("""
        COMMENT ON COLUMN modulo9.umbrales_ambientales.tolerancia_semaforo IS
        'RF-58 Fase 3: tolerancia T del semáforo en la unidad del umbral. NULL = 10 % del rango.'
    """)


def downgrade() -> None:
    op.execute("""
        ALTER TABLE modulo9.umbrales_ambientales
            DROP CONSTRAINT IF EXISTS ck_umbral_ambiental_tolerancia_semaforo
    """)
    op.execute("ALTER TABLE modulo9.umbrales_ambientales DROP COLUMN IF EXISTS tolerancia_semaforo")
