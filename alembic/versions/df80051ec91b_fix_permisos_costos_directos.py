# | Fecha      | Nombre | Que se hizo |
# |------------|--------|-------------|
# | 2026-11-09 | DBA    | RNF-05: retira Crear del costeo directo (recurso 55) a Productor y Veterinario (INC-M05-261-G29) |
# | 2026-11-10 | Arekkazu | Lote M05/M06: RNF-05: el recurso de costeo directo se ubica por nombre, no por id |
"""m05 rbac: solo Administrador, Contador y Gestor de Granja registran costos directos

Revision ID: df80051ec91b
Revises: b7e2d94c1a68
Create Date: 2026-11-09 12:46:36.468938

RNF-05: registrar costos directos del ciclo (recurso 55, acción Crear) es exclusivo de
Administrador, Contador y Gestor de Granja. La matriz sembrada lo concedía también a
Productor y Veterinario. Se desactiva (no se borra) para conservar la trazabilidad.

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'df80051ec91b'
down_revision: Union[str, Sequence[str], None] = 'b7e2d94c1a68'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_RECURSO_COSTEO_DIRECTO = 'costeo_directo_suministros'
_ID_ACCION_CREAR = 1
_ROLES_SIN_CREAR = "('Productor', 'Veterinario')"


def _cambiar_estado(es_activo: bool) -> None:
    op.execute(f"""
        DO $$
        DECLARE v_filas integer;
        BEGIN
            -- Los triggers de M01 exigen un actor en la sesión para tocar la matriz.
            PERFORM set_config('app.current_role', 'Administrador', true);
            PERFORM set_config('app.current_user_id', '1', true);

            UPDATE modulo1.permisos p
               SET es_activo = {str(es_activo).upper()}
              FROM modulo1.roles r
             WHERE r.id_rol = p.id_rol
               AND r.nombre_rol IN {_ROLES_SIN_CREAR}
               AND p.id_recurso = (SELECT id_recurso FROM modulo1.recursos
                                    WHERE nombre_recurso = '{_RECURSO_COSTEO_DIRECTO}')
               AND p.id_accion = {_ID_ACCION_CREAR};
            GET DIAGNOSTICS v_filas = ROW_COUNT;
            RAISE NOTICE 'RNF-05: % permiso(s) Crear de costeo directo quedaron con es_activo = %',
                v_filas, {str(es_activo).upper()};
        END $$;
    """)


def upgrade() -> None:
    _cambiar_estado(False)


def downgrade() -> None:
    _cambiar_estado(True)