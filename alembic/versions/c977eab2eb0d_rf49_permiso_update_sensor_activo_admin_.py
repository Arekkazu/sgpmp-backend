"""rf49_permiso_update_sensor_activo_admin_productor

Revision ID: c977eab2eb0d
Revises: c8d4f1a9b7e2
Create Date: 2026-09-22 21:18:43.709062

INC-M02-49-G84 / issue #397: el Administrador (y el Productor) recibian
403 ACCESO_DENEGADO al hacer PATCH sobre una asociacion sensor-activo
(activar/desactivar, RF-49 Regla 5) porque la migracion 1d7d6069da52
(PR #286) solo habia insertado el permiso de CREAR (id_accion=1) para
Productor sobre el recurso 30 (asociacion_sensor_activo), sin las tuplas
de ACTUALIZAR (id_accion=3) que ese mismo PATCH exige para Admin y
Productor. RF-49 declara explicitamente al Administrador como actor que
"puede crear, modificar, desactivar y consultar el historial de
asociaciones de cualquier granja".
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'c977eab2eb0d'
down_revision: Union[str, Sequence[str], None] = 'c8d4f1a9b7e2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM modulo1.recursos
                WHERE id_recurso = 30
                  AND lower(btrim(nombre_recurso)) = 'asociacion_sensor_activo'
            ) THEN
                RAISE EXCEPTION 'RF49: id_recurso=30 no corresponde a asociacion_sensor_activo';
            END IF;

            IF NOT EXISTS (
                SELECT 1 FROM modulo1.acciones
                WHERE id_accion = 3 AND upper(btrim(codigo)) = 'U'
            ) THEN
                RAISE EXCEPTION 'RF49: id_accion=3 no corresponde a UPDATE';
            END IF;

            -- Fila de Administrador: modulo1.trg_fn_proteger_permisos_admin_update
            -- bloquea CUALQUIER UPDATE sobre un permiso 'admin_%' ya existente
            -- (inmutable por diseño, ver CLAUDE.md). DO NOTHING respeta esa regla:
            -- si la fila ya existe (insertada a mano antes de esta migracion, con
            -- otra descripcion), se deja intacta; si no existe, se crea.
            INSERT INTO modulo1.permisos (
                nombre, descripcion, id_rol, id_recurso, id_accion, es_activo
            )
            VALUES (
                'admin_actualizar_asociacion_sensor_activo',
                'Permite al Administrador activar/desactivar asociaciones sensor-activo de cualquier finca (RF-49 Regla 5).',
                1, 30, 3, TRUE
            )
            ON CONFLICT (id_rol, id_recurso, id_accion) DO NOTHING;

            -- Fila de Productor: sin proteccion de inmutabilidad, mismo patron
            -- idempotente que la migracion 1d7d6069da52.
            INSERT INTO modulo1.permisos (
                nombre, descripcion, id_rol, id_recurso, id_accion, es_activo
            )
            VALUES (
                'prod_actualizar_asociacion_sensor_activo',
                'Permite al Productor activar/desactivar asociaciones sensor-activo de sus propias fincas (RF-49 Regla 5).',
                2, 30, 3, TRUE
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
        WHERE id_rol IN (1, 2)
          AND id_recurso = 30
          AND id_accion = 3
          AND nombre IN (
              'admin_actualizar_asociacion_sensor_activo',
              'prod_actualizar_asociacion_sensor_activo'
          );
        """
    )
