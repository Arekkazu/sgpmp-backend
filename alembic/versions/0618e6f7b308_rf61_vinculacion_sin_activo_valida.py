"""RF-61: una lectura sin activo (SIN_VINCULAR / AMBIGUA) es una vinculación válida

Revision ID: 0618e6f7b308
Revises: 785d330f7541
Create Date: 2026-10-06

INC-M09-64-G31 (#494). `chk_vinculacion_modelo` exigía activo en toda fila
INDIVIDUAL y lo prohibía en toda fila POBLACIONAL. Con eso:

- una lectura sin coincidencia automática (`SIN_VINCULAR`, o `AMBIGUA` con varios
  candidatos) nunca se podía guardar: el INSERT violaba el CHECK, la vinculación
  se descartaba como warning y la ingesta respondía 201 sin fila. RF-61
  (restricción 9) dice que SIN_VINCULAR "es válido" y se resuelve después;
- una lectura POBLACIONAL no podía apuntar a su lote, que en M02 es el activo
  POBLACIONAL, así que nunca se reclasificaba contra RF-17.

La regla que sí sostiene RF-61 (postcondición 2: una lectura CONFIRMADA tiene
trazabilidad directa hacia su activo) es: una vinculación INDIVIDUAL vigente
(`VINCULADA`) siempre apunta a su animal. Las filas que hoy existen la cumplen.

El CHECK modificado toma el nombre de la convención (`ck_`, ver
`anotaciones/convencion_nomenclatura_bd.md`).
"""
from typing import Sequence, Union

from alembic import op


revision: str = '0618e6f7b308'
down_revision: Union[str, Sequence[str], None] = '785d330f7541'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE modulo3.vinculaciones_lecturas
            DROP CONSTRAINT chk_vinculacion_modelo,
            ADD CONSTRAINT ck_vinculacion_lectura_modelo_manejo CHECK (
                modelo_manejo <> 'INDIVIDUAL'::modulo3.enum_modelo_manejo
                OR estado_vinculacion <> 'VINCULADA'::modulo3.enum_estado_vinculacion
                OR id_activo_biologico IS NOT NULL
            );

        COMMENT ON CONSTRAINT ck_vinculacion_lectura_modelo_manejo ON modulo3.vinculaciones_lecturas IS
            'RF-61: una vinculación INDIVIDUAL VINCULADA apunta a su activo; SIN_VINCULAR/AMBIGUA pueden no tenerlo y una POBLACIONAL puede apuntar a su lote (INC-M09-64-G31).';
        """
    )


def downgrade() -> None:
    # Falla si ya existen filas que solo admite la regla nueva (lecturas sin activo
    # o POBLACIONAL con lote): habría que resolverlas antes de volver atrás.
    op.execute(
        """
        ALTER TABLE modulo3.vinculaciones_lecturas
            DROP CONSTRAINT ck_vinculacion_lectura_modelo_manejo,
            ADD CONSTRAINT chk_vinculacion_modelo CHECK (
                (modelo_manejo = 'INDIVIDUAL'::modulo3.enum_modelo_manejo AND id_activo_biologico IS NOT NULL)
                OR (modelo_manejo = 'POBLACIONAL'::modulo3.enum_modelo_manejo AND id_activo_biologico IS NULL)
            );
        """
    )
