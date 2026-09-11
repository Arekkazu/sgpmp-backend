"""RF-16: tipo y obligatoriedad de atributos dinámicos

Revision ID: b92f7e1a4c63
Revises: fa915f4d113e
Create Date: 2026-09-09

INC-M02-47-G17 / #208. Agrega a las métricas productivas los metadatos que
RF-33 necesita para validar atributos dinámicos antes de persistir un activo.
"""
from typing import Sequence, Union

from alembic import op


revision: str = 'b92f7e1a4c63'
down_revision: Union[str, Sequence[str], None] = 'fa915f4d113e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE modulo9.metricas_produccion
            ADD COLUMN IF NOT EXISTS tipo_dato varchar(10),
            ADD COLUMN IF NOT EXISTS es_obligatorio boolean;

        UPDATE modulo9.metricas_produccion
        SET tipo_dato = CASE upper(tipo_medicion)
            WHEN 'CONTEO' THEN 'ENTERO'
            WHEN 'PESO' THEN 'NUMERICO'
            WHEN 'VOLUMEN' THEN 'NUMERICO'
            WHEN 'LONGITUD' THEN 'NUMERICO'
            ELSE 'TEXTO'
        END
        WHERE tipo_dato IS NULL;

        UPDATE modulo9.metricas_produccion
        SET es_obligatorio = false
        WHERE es_obligatorio IS NULL;

        ALTER TABLE modulo9.metricas_produccion
            ALTER COLUMN tipo_dato SET DEFAULT 'NUMERICO',
            ALTER COLUMN tipo_dato SET NOT NULL,
            ALTER COLUMN es_obligatorio SET DEFAULT false,
            ALTER COLUMN es_obligatorio SET NOT NULL;

        COMMENT ON COLUMN modulo9.metricas_produccion.tipo_dato IS
            'Tipo primitivo del atributo dinámico: NUMERICO, ENTERO, TEXTO o BOOLEANO.';
        COMMENT ON COLUMN modulo9.metricas_produccion.es_obligatorio IS
            'Indica si RF-33 exige el atributo al registrar el activo.';
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'ck_metrica_produccion_tipo_dato'
                  AND conrelid = 'modulo9.metricas_produccion'::regclass
            ) THEN
                ALTER TABLE modulo9.metricas_produccion
                    ADD CONSTRAINT ck_metrica_produccion_tipo_dato
                    CHECK (tipo_dato IN ('NUMERICO', 'ENTERO', 'TEXTO', 'BOOLEANO'));
            END IF;
        END
        $$;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE modulo9.metricas_produccion
            DROP CONSTRAINT IF EXISTS ck_metrica_produccion_tipo_dato,
            DROP COLUMN IF EXISTS es_obligatorio,
            DROP COLUMN IF EXISTS tipo_dato;
        """
    )
