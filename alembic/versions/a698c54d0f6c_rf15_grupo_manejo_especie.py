"""RF-15 v1.1: grupo_manejo de la especie (renombra especies.tipo_modelo)

Revision ID: a698c54d0f6c
Revises: 18d21ad171ee
Create Date: 2026-10-11

RF-15 v1.1 (completación de RFC-009) llama `grupo_manejo` a la clasificación
productiva de la especie, con los valores AVES, PORCINOS, ACUICULTURA,
ESPECIES_MEDIANAS y ESPECIES_GRANDES. `cf12e716a4ec` la había creado como
`tipo_modelo` con los valores del modelo de M04 (MODELO_*). El mapeo es 1:1
(`AVES` -> `MODELO_AVES`), así que se renombra la columna y se quita el
prefijo; el modelo de la especie lo deriva la aplicación.

Ninguna vista, función ni política referencia la columna (verificado en DEV):
solo el CHECK, que se reemplaza.

La ficha la declara obligatoria, pero la columna sigue admitiendo NULL: las
especies existentes sin clasificar en TEST/PROD no tienen un grupo que se
pueda inferir. La API ya lo exige al registrar; el NOT NULL va en una
migración posterior, cuando todos los ambientes estén completos.
"""
from typing import Sequence, Union

from alembic import op


revision: str = 'a698c54d0f6c'
down_revision: Union[str, Sequence[str], None] = '18d21ad171ee'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE modulo9.especies DROP CONSTRAINT ck_especie_tipo_modelo;
        ALTER TABLE modulo9.especies RENAME COLUMN tipo_modelo TO grupo_manejo;
        UPDATE modulo9.especies
           SET grupo_manejo = substring(grupo_manejo FROM 8)
         WHERE grupo_manejo LIKE 'MODELO\\_%';
        ALTER TABLE modulo9.especies
            ADD CONSTRAINT ck_especie_grupo_manejo CHECK (grupo_manejo IN (
                'AVES', 'PORCINOS', 'ACUICULTURA', 'ESPECIES_MEDIANAS', 'ESPECIES_GRANDES'
            ));
        COMMENT ON COLUMN modulo9.especies.grupo_manejo IS
            'Clasificación productiva de la especie (RF-15 v1.1). Determina el tipo_modelo_asignado admisible de sus áreas (RF-20), mapeo 1:1 AVES -> MODELO_AVES.';
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE modulo9.especies DROP CONSTRAINT ck_especie_grupo_manejo;
        UPDATE modulo9.especies
           SET grupo_manejo = 'MODELO_' || grupo_manejo
         WHERE grupo_manejo IS NOT NULL;
        ALTER TABLE modulo9.especies RENAME COLUMN grupo_manejo TO tipo_modelo;
        ALTER TABLE modulo9.especies
            ADD CONSTRAINT ck_especie_tipo_modelo CHECK (tipo_modelo IN (
                'MODELO_AVES', 'MODELO_PORCINOS', 'MODELO_ACUICULTURA',
                'MODELO_ESPECIES_MEDIANAS', 'MODELO_ESPECIES_GRANDES'
            ));
        COMMENT ON COLUMN modulo9.especies.tipo_modelo IS
            'Familia de modelo de IA de la especie (RFC-009); base de la coherencia de RF-20.';
        """
    )
