"""v5.3.0_rf49_permiso_productor_asociacion_sensor

Revision ID: 1d7d6069da52
Revises: d014e2cc785d
Create Date: 2026-09-16 20:50:42.443520

INC-M02-37-G87 v2.0 / issue #349: RF-49 define al Productor Agropecuario
como actor principal para asociar sensores a sus activos, pero el catálogo
RBAC solo le concedía lectura sobre ``asociacion_sensor_activo``.
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '1d7d6069da52'
down_revision: Union[str, Sequence[str], None] = 'd014e2cc785d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM modulo1.roles
                WHERE id_rol = 2 AND lower(btrim(nombre_rol)) = 'productor'
            ) THEN
                RAISE EXCEPTION 'RF49: id_rol=2 no corresponde al rol Productor';
            END IF;

            IF NOT EXISTS (
                SELECT 1
                FROM modulo1.recursos
                WHERE id_recurso = 30
                  AND lower(btrim(nombre_recurso)) = 'asociacion_sensor_activo'
            ) THEN
                RAISE EXCEPTION 'RF49: id_recurso=30 no corresponde a asociacion_sensor_activo';
            END IF;

            IF NOT EXISTS (
                SELECT 1
                FROM modulo1.acciones
                WHERE id_accion = 1 AND upper(btrim(codigo)) = 'C'
            ) THEN
                RAISE EXCEPTION 'RF49: id_accion=1 no corresponde a CREATE';
            END IF;

            INSERT INTO modulo1.permisos (
                nombre,
                descripcion,
                id_rol,
                id_recurso,
                id_accion,
                es_activo
            )
            VALUES (
                'prod_crear_asociacion_sensor_activo',
                'Permite al Productor asociar sensores IoT a activos e infraestructuras de sus propias fincas (RF-49).',
                2,
                30,
                1,
                TRUE
            )
            ON CONFLICT (id_rol, id_recurso, id_accion)
            DO UPDATE SET
                nombre = EXCLUDED.nombre,
                descripcion = EXCLUDED.descripcion,
                es_activo = TRUE;
        END
        $$;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DELETE FROM modulo1.permisos
        WHERE id_rol = 2
          AND id_recurso = 30
          AND id_accion = 1
          AND nombre = 'prod_crear_asociacion_sensor_activo';
        """
    )
