"""rf30_auditoria_plantillas_lectura_y_fallos

Revision ID: c461638a6714
Revises: 281e99d58ecb
Create Date: 2026-09-18 00:37:17.457032

INC-M09-01-109 (#319): `modulo9.auditorias_plantillas` solo admitia
tipo_operacion='CREATE' con id_plantilla obligatorio, asi que no habia donde
registrar una consulta, una aplicacion, ni un intento fallido de cualquier
operacion (la creacion falla antes de que exista un id_plantilla). Se agrega
una columna `resultado` (EXITOSO/FALLIDO), se permite id_plantilla NULL, y se
amplia el catalogo de tipo_operacion a CREATE/READ/APPLY. El constraint viejo
`chk_tipo_operacion_plantilla` no seguia la convencion de nombres (`ck_` para
CHECK, ver anotaciones/convencion_nomenclatura_bd.md); se reemplaza en vez de
solo ampliarlo.
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'c461638a6714'
down_revision: Union[str, Sequence[str], None] = '281e99d58ecb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE modulo9.auditorias_plantillas
            ALTER COLUMN id_plantilla DROP NOT NULL,
            ADD COLUMN resultado VARCHAR(20) NOT NULL DEFAULT 'EXITOSO';

        COMMENT ON COLUMN modulo9.auditorias_plantillas.id_plantilla IS
            'Plantilla sobre la que se realizo la operacion. NULL si el fallo ocurrio antes de crearla.';
        COMMENT ON COLUMN modulo9.auditorias_plantillas.resultado IS
            'EXITOSO o FALLIDO. Permite auditar tambien los intentos fallidos.';

        ALTER TABLE modulo9.auditorias_plantillas
            DROP CONSTRAINT auditorias_plantillas_tipo_operacion_check,
            ADD CONSTRAINT ck_auditoria_plantilla_tipo_operacion
                CHECK (tipo_operacion IN ('CREATE', 'READ', 'APPLY')),
            ADD CONSTRAINT ck_auditoria_plantilla_resultado
                CHECK (resultado IN ('EXITOSO', 'FALLIDO'));
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DELETE FROM modulo9.auditorias_plantillas
        WHERE tipo_operacion <> 'CREATE' OR resultado <> 'EXITOSO' OR id_plantilla IS NULL;

        ALTER TABLE modulo9.auditorias_plantillas
            DROP CONSTRAINT ck_auditoria_plantilla_tipo_operacion,
            DROP CONSTRAINT ck_auditoria_plantilla_resultado,
            ADD CONSTRAINT auditorias_plantillas_tipo_operacion_check
                CHECK (tipo_operacion = 'CREATE');

        ALTER TABLE modulo9.auditorias_plantillas
            DROP COLUMN resultado,
            ALTER COLUMN id_plantilla SET NOT NULL;
        """
    )
