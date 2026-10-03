"""v5.5.0_rf35_permiso_actualizar_vet_activo_biologico

Revision ID: e5ce9d42b2ec
Revises: c8d4f1a9b7e2
Create Date: 2026-09-23 01:00:00.000000

Tarea Taiga "RF-35: RBAC Veterinario, validar eventos pendientes,
concurrencia optimista" (issue histórico #30). RF-35 lista a Veterinario
explícitamente como actor de la gestión individual de activos biológicos,
pero `modulo1.permisos` no tenía la fila de Actualizar (U=3) para ese rol
sobre el recurso 29 (`activos_biologicos`). Confirmado en vivo vía MCP de
Postgres antes de escribir esta migración: Veterinario es `id_rol=3`,
Actualizar es `id_accion=3`, el recurso 29 corresponde a
`activos_biologicos`, y no existía ninguna fila con esa combinación
(Administrador, Productor e Ingeniero de Campo sí la tenían desde CU02).
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "e5ce9d42b2ec"
down_revision: Union[str, Sequence[str], None] = "c8d4f1a9b7e2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Siembra `vet_actualizar_activo_biologico` si no existe todavía."""
    op.execute(
        """
        DO $$
        DECLARE
            v_permiso RECORD;
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM modulo1.roles
                WHERE id_rol = 3
                  AND lower(btrim(nombre_rol)) = 'veterinario'
            ) THEN
                RAISE EXCEPTION
                    'RF-35: id_rol=3 no corresponde al rol Veterinario';
            END IF;

            IF NOT EXISTS (
                SELECT 1
                FROM modulo1.recursos
                WHERE id_recurso = 29
                  AND lower(btrim(nombre_recurso)) = 'activos_biologicos'
            ) THEN
                RAISE EXCEPTION
                    'RF-35: id_recurso=29 no corresponde al recurso activos_biologicos';
            END IF;

            IF NOT EXISTS (
                SELECT 1
                FROM modulo1.acciones
                WHERE id_accion = 3
                  AND btrim(codigo) = 'U'
            ) THEN
                RAISE EXCEPTION
                    'RF-35: id_accion=3 no corresponde a Actualizar (U)';
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
                'vet_actualizar_activo_biologico',
                'Permite al Veterinario actualizar el detalle individual de un activo biologico (RF-35)',
                3,
                29,
                3,
                TRUE
            )
            ON CONFLICT (id_rol, id_recurso, id_accion) DO NOTHING;

            SELECT id_permiso, nombre, es_activo
            INTO STRICT v_permiso
            FROM modulo1.permisos
            WHERE id_rol = 3
              AND id_recurso = 29
              AND id_accion = 3;

            IF NOT v_permiso.es_activo THEN
                UPDATE modulo1.permisos
                SET es_activo = TRUE,
                    fecha_actualizacion = now()
                WHERE id_permiso = v_permiso.id_permiso;
            END IF;

            IF NOT EXISTS (
                SELECT 1
                FROM modulo1.permisos
                WHERE id_rol = 3
                  AND id_recurso = 29
                  AND id_accion = 3
                  AND es_activo = TRUE
            ) THEN
                RAISE EXCEPTION
                    'RF-35: no fue posible sembrar el permiso de actualizacion para Veterinario';
            END IF;
        END
        $$;
        """
    )


def downgrade() -> None:
    """Elimina únicamente la fila sembrada por esta migración."""
    op.execute(
        """
        DELETE FROM modulo1.permisos
        WHERE id_rol = 3
          AND id_recurso = 29
          AND id_accion = 3
          AND nombre = 'vet_actualizar_activo_biologico';
        """
    )
