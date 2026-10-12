"""rf41_recurso_datos_clinicos_activo

Revision ID: 4f453b6d2b90
Revises: c8d4f1a9b7e2
Create Date: 2026-09-22 21:45:00.000000

INC-M02-43-G52 / issue #413: GET /activos-biologicos/{id}/eventos devolvia
el historial sanitario completo (diagnostico, medicamento, dosis) a
cualquier usuario con el permiso generico de lectura sobre
activos_biologicos (id_recurso=29, accion=2), sin distinguir si el rol
tiene autorizacion clinica -- un Ingeniero de Campo sin ese contexto veia
los mismos datos clinicos que un Veterinario.

RF-46 (Consulta de Historial) ya define el precedente de visibilidad para
la categoria SANITARIO: sus actores son Productor, Veterinario y
Administrador -- Ingeniero de Campo no esta entre ellos, aunque si es
actor de RF-41 para *registrar* eventos sanitarios (RF-41 no define su
propia regla de lectura, hereda la de RF-46 como consulta de la misma
categoria). Este recurso nuevo formaliza esa distincion en RBAC en vez de
dejarla implicita en el codigo.
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '4f453b6d2b90'
down_revision: Union[str, Sequence[str], None] = 'c8d4f1a9b7e2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_ID_RECURSO = 59


def upgrade() -> None:
    op.execute(
        f"""
        DO $$
        DECLARE
            v_id_recurso INTEGER;
        BEGIN
            IF EXISTS (
                SELECT 1 FROM modulo1.recursos WHERE nombre_recurso = 'datos_clinicos_activo'
            ) THEN
                SELECT id_recurso INTO v_id_recurso
                FROM modulo1.recursos WHERE nombre_recurso = 'datos_clinicos_activo';
            ELSIF EXISTS (SELECT 1 FROM modulo1.recursos WHERE id_recurso = {_ID_RECURSO}) THEN
                RAISE EXCEPTION 'RF41: id_recurso={_ID_RECURSO} ya esta en uso por otro recurso; reasignar el id fijo de esta migracion.';
            ELSE
                INSERT INTO modulo1.recursos (id_recurso, nombre_recurso, descripcion)
                VALUES (
                    {_ID_RECURSO},
                    'datos_clinicos_activo',
                    'Campos clinicos (diagnostico, medicamento, dosis) del historial sanitario de un activo biologico (RF-41/RF-46)'
                );
                v_id_recurso := {_ID_RECURSO};
            END IF;

            INSERT INTO modulo1.permisos (nombre, descripcion, id_rol, id_recurso, id_accion, es_activo)
            VALUES
                (
                    'admin_leer_datos_clinicos_activo',
                    'Permite al Administrador ver diagnostico/medicamento/dosis en el historial sanitario de cualquier activo (RF-41/RF-46).',
                    1, v_id_recurso, 2, TRUE
                ),
                (
                    'vet_leer_datos_clinicos_activo',
                    'Permite al Veterinario ver diagnostico/medicamento/dosis en el historial sanitario de los activos que atiende (RF-41/RF-46).',
                    3, v_id_recurso, 2, TRUE
                ),
                (
                    'prod_leer_datos_clinicos_activo',
                    'Permite al Productor ver diagnostico/medicamento/dosis en el historial sanitario de sus propios activos (RF-41/RF-46).',
                    2, v_id_recurso, 2, TRUE
                )
            ON CONFLICT (id_rol, id_recurso, id_accion) DO NOTHING;
        END
        $$;
        """
    )


def downgrade() -> None:
    op.execute(
        f"""
        DELETE FROM modulo1.permisos
        WHERE id_recurso = {_ID_RECURSO}
          AND nombre IN (
              'admin_leer_datos_clinicos_activo',
              'vet_leer_datos_clinicos_activo',
              'prod_leer_datos_clinicos_activo'
          );
        """
    )
    op.execute(
        f"DELETE FROM modulo1.recursos WHERE id_recurso = {_ID_RECURSO} AND nombre_recurso = 'datos_clinicos_activo';"
    )
