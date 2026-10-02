"""v5.5.0_rf34_permiso_datos_financieros_activo

Revision ID: 96621b225009
Revises: 731fb3997631
Create Date: 2026-09-28 11:07:33.098652

TC-M02-031-G15 / issue #465: la lectura general del recurso 29 permitía que
cualquier rol autorizado a consultar activos recibiera también
``costo_adquisicion`` y ``soporte_documental``. Se crea un recurso RBAC
independiente para aplicar autorización a nivel de campo.

Se conserva el acceso financiero para Administrador y Productor, responsables
del alta y la gestión del activo (RF-33), y para la identidad técnica de M06,
consumidora de valoración NIC-41. Ingeniero de Campo y Veterinario mantienen la
lectura operativa del activo, pero no reciben este permiso.
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '96621b225009'
down_revision: Union[str, Sequence[str], None] = '731fb3997631'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        DECLARE
            v_id_recurso INTEGER;
        BEGIN
            -- Las políticas RLS de modulo1 consultan este contexto. Es local a
            -- la transacción de Alembic y no deja estado de sesión persistente.
            PERFORM set_config('app.current_role', 'Administrador', true);
            PERFORM set_config('app.current_user_id', '1', true);

            IF NOT EXISTS (
                SELECT 1 FROM modulo1.acciones
                WHERE id_accion = 2 AND upper(btrim(codigo)) = 'R'
            ) THEN
                RAISE EXCEPTION 'RF34: id_accion=2 no corresponde a Leer (R)';
            END IF;

            IF NOT EXISTS (
                SELECT 1 FROM modulo1.roles
                WHERE lower(btrim(nombre_rol)) = 'administrador'
            ) OR NOT EXISTS (
                SELECT 1 FROM modulo1.roles
                WHERE lower(btrim(nombre_rol)) = 'productor'
            ) THEN
                RAISE EXCEPTION 'RF34: no se encontraron los roles Administrador y Productor';
            END IF;

            -- d944f4d8c215, ancestro de esta revisión, ya sincroniza la
            -- secuencia de recursos. Se usa el DEFAULT normal para no exigir
            -- el privilegio UPDATE/setval que member_dev no posee.
            INSERT INTO modulo1.recursos (
                nombre_recurso, descripcion, es_proceso_especial
            ) VALUES (
                'datos_financieros_activo',
                'RF-33/RF-34: costo de adquisición y soporte documental del activo biológico.',
                FALSE
            )
            ON CONFLICT (nombre_recurso) DO NOTHING;

            SELECT id_recurso
              INTO v_id_recurso
              FROM modulo1.recursos
             WHERE nombre_recurso = 'datos_financieros_activo';

            -- Los permisos admin_* son inmutables por diseño; un conflicto no
            -- puede normalizarse mediante UPDATE.
            INSERT INTO modulo1.permisos (
                nombre, descripcion, id_rol, id_recurso, id_accion, es_activo
            )
            SELECT
                'admin_leer_datos_financieros_activo',
                'Permite al Administrador consultar costo y soporte documental de activos biológicos.',
                id_rol, v_id_recurso, 2, TRUE
              FROM modulo1.roles
             WHERE lower(btrim(nombre_rol)) = 'administrador'
            ON CONFLICT (id_rol, id_recurso, id_accion) DO NOTHING;

            INSERT INTO modulo1.permisos (
                nombre, descripcion, id_rol, id_recurso, id_accion, es_activo
            )
            SELECT
                CASE lower(btrim(nombre_rol))
                    WHEN 'productor' THEN 'prod_leer_datos_financieros_activo'
                    WHEN 'integración m06' THEN 'm06_leer_datos_financieros_activo'
                END,
                CASE lower(btrim(nombre_rol))
                    WHEN 'productor' THEN 'Permite al Productor consultar costo y soporte documental de sus activos biológicos.'
                    WHEN 'integración m06' THEN 'Permite a M06 consumir costo y soporte documental para valoración NIC-41.'
                END,
                id_rol, v_id_recurso, 2, TRUE
              FROM modulo1.roles
             WHERE lower(btrim(nombre_rol)) IN ('productor', 'integración m06')
            ON CONFLICT (id_rol, id_recurso, id_accion) DO UPDATE
                SET nombre = EXCLUDED.nombre,
                    descripcion = EXCLUDED.descripcion,
                    es_activo = TRUE;
        END
        $$;
        """
    )


def downgrade() -> None:
    """Retira los permisos reversibles y conserva el catálogo requerido por admin.

    El trigger ``trg_fn_proteger_permisos_admin_delete`` impide eliminar el
    permiso ``admin_*``. En consecuencia, tampoco puede eliminarse el recurso
    referenciado. Sin el código que consulta este recurso, mantener esas filas
    no altera contratos ni habilita endpoints.
    """
    op.execute(
        """
        DO $$
        DECLARE
            v_id_recurso INTEGER;
        BEGIN
            PERFORM set_config('app.current_role', 'Administrador', true);
            PERFORM set_config('app.current_user_id', '1', true);

            SELECT id_recurso
              INTO v_id_recurso
              FROM modulo1.recursos
             WHERE nombre_recurso = 'datos_financieros_activo';

            IF v_id_recurso IS NOT NULL THEN
                DELETE FROM modulo1.permisos
                 WHERE id_recurso = v_id_recurso
                   AND nombre IN (
                       'prod_leer_datos_financieros_activo',
                       'm06_leer_datos_financieros_activo'
                   );
            END IF;
        END
        $$;
        """
    )
