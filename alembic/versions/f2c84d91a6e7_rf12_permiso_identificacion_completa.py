"""rf12 sembrar permiso para ver identificacion completa

Revision ID: f2c84d91a6e7
Revises: d4e2f8a15c9b
Create Date: 2026-08-27 00:00:00.000000

RF-12 representa la capacidad especial ``ver_identificacion_completa`` como
Ejecutar (E=5) sobre el recurso Usuarios (id_recurso=1). La semilla se concede
exclusivamente al rol Administrador (id_rol=1).
"""
from typing import Sequence, Union

from alembic import op


revision: str = "f2c84d91a6e7"
down_revision: Union[str, Sequence[str], None] = "e7b31f4a6c20"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Valida los catálogos y deja activo el permiso especial de RF-12."""
    op.execute(
        """
        DO $$
        DECLARE
            v_permiso RECORD;
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM modulo1.roles
                WHERE id_rol = 1
                  AND lower(btrim(nombre_rol)) = 'administrador'
            ) THEN
                RAISE EXCEPTION
                    'RF-12: id_rol=1 no corresponde al rol Administrador';
            END IF;

            IF NOT EXISTS (
                SELECT 1
                FROM modulo1.recursos
                WHERE id_recurso = 1
                  AND lower(btrim(nombre_recurso)) IN ('usuario', 'usuarios')
            ) THEN
                RAISE EXCEPTION
                    'RF-12: id_recurso=1 no corresponde al recurso Usuarios';
            END IF;

            IF NOT EXISTS (
                SELECT 1
                FROM modulo1.acciones
                WHERE id_accion = 5
                  AND btrim(codigo) = 'E'
            ) THEN
                RAISE EXCEPTION
                    'RF-12: id_accion=5 no corresponde a Ejecutar (E)';
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
                'admin_ejecutar_identificacion_completa',
                'Permite ver el numero de identificacion completo en RF-12',
                1,
                1,
                5,
                TRUE
            )
            ON CONFLICT (id_rol, id_recurso, id_accion) DO NOTHING;

            SELECT id_permiso, nombre, es_activo
            INTO STRICT v_permiso
            FROM modulo1.permisos
            WHERE id_rol = 1
              AND id_recurso = 1
              AND id_accion = 5;

            IF NOT v_permiso.es_activo THEN
                IF v_permiso.nombre ILIKE 'admin_%' THEN
                    RAISE EXCEPTION
                        'RF-12: el permiso administrativo existente esta inactivo y es inmutable';
                END IF;

                UPDATE modulo1.permisos
                SET es_activo = TRUE,
                    fecha_actualizacion = now()
                WHERE id_permiso = v_permiso.id_permiso;
            END IF;

            IF NOT EXISTS (
                SELECT 1
                FROM modulo1.permisos
                WHERE id_rol = 1
                  AND id_recurso = 1
                  AND id_accion = 5
                  AND es_activo = TRUE
            ) THEN
                RAISE EXCEPTION
                    'RF-12: no fue posible sembrar el permiso de identificacion completa';
            END IF;
        END
        $$;
        """
    )


def downgrade() -> None:
    """Conserva el permiso porque los ``admin_*`` son inmutables en la BD.

    ``trg_proteger_permisos_admin_delete`` y
    ``trg_proteger_permisos_admin_update`` prohíben eliminarlo o desactivarlo.
    El seed es idempotente, por lo que conservarlo también permite reaplicar el
    upgrade sin duplicar datos.
    """
