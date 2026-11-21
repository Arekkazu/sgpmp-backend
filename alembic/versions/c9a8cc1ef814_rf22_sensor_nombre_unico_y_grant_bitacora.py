# | Fecha      | Nombre   | Que se hizo                                                        |
# |------------|----------|--------------------------------------------------------------------|
# | 2026-11-01 | Arekkazu | RF-22/RF-53: nombre de sensor único por dispositivo y FOR UPDATE de RF-53 |
"""rf22: nombre de sensor único por dispositivo y permiso de bloqueo en bitacora_ingest

Revision ID: c9a8cc1ef814
Revises: 28ddcf159078
Create Date: 2026-11-01

1. ``uq_sensores_nombre`` — UNIQUE (id_dispositivo_iot, nombre) en ``modulo9.sensores``.
   El firmware identifica cada lectura con el nombre del sensor y el broker lo busca por
   (dispositivo, nombre). Sin unicidad esa búsqueda es ambigua (el broker se queda con el de
   menor id) y una lectura puede caer en el sensor equivocado. Si un ambiente ya tiene nombres
   repetidos en un dispositivo, la migración falla y los lista: hay que renombrarlos antes,
   porque no hay forma segura de elegir cuál conservar.

2. ``GRANT UPDATE (id_bitacora_ingest)`` a ``sgpmp_app`` en ``modulo3.bitacora_ingest``. La
   etapa postcommit RF53_AUDITORIA reclama la fila con ``SELECT ... FOR UPDATE SKIP LOCKED`` y
   PostgreSQL exige UPDATE en al menos una columna para bloquearla; sin él falla con 42501 en
   cada lectura ("Postcommit pendiente: etapa=RF53_AUDITORIA ... ProgrammingError"). La tabla
   sigue siendo de solo inserción: ``trg_no_update_bitacora_ingest`` rechaza cualquier UPDATE.
   Mismo patrón que ``8c4e2a6f1b93`` en ``observaciones_vision``.
"""
from typing import Sequence, Union

from alembic import op


revision: str = 'c9a8cc1ef814'
down_revision: Union[str, Sequence[str], None] = '28ddcf159078'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        DO $$
        DECLARE
            v_repetidos text;
        BEGIN
            SELECT string_agg(format('dispositivo %s: "%s" (%s veces)', id_dispositivo_iot, nombre, n), '; ')
            INTO v_repetidos
            FROM (
                SELECT id_dispositivo_iot, nombre, count(*) AS n
                FROM modulo9.sensores
                GROUP BY id_dispositivo_iot, nombre
                HAVING count(*) > 1
            ) d;
            IF v_repetidos IS NOT NULL THEN
                RAISE EXCEPTION 'Sensores con nombre repetido en el mismo dispositivo; renombrarlos antes de migrar: %', v_repetidos;
            END IF;
        END $$;

        ALTER TABLE modulo9.sensores
            ADD CONSTRAINT uq_sensores_nombre UNIQUE (id_dispositivo_iot, nombre);
        COMMENT ON CONSTRAINT uq_sensores_nombre ON modulo9.sensores IS
            'RF-22: el firmware identifica la lectura por el nombre del sensor dentro de su dispositivo.';

        GRANT UPDATE (id_bitacora_ingest) ON modulo3.bitacora_ingest TO sgpmp_app;
    """)


def downgrade() -> None:
    op.execute("""
        REVOKE UPDATE (id_bitacora_ingest) ON modulo3.bitacora_ingest FROM sgpmp_app;
        ALTER TABLE modulo9.sensores DROP CONSTRAINT uq_sensores_nombre;
    """)
