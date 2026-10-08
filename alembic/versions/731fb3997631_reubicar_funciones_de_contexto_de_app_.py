"""reubicar funciones de contexto de app_ctx a modulo1 (F2)

Revision ID: 731fb3997631
Revises: b53fe19f276e
Create Date: 2026-10-01 14:55:35.814112

Directriz de SamuelPR21 en el PR #469: no mantener un schema dedicado solo
para las funciones de contexto de sesion; pertenecen a identidad y acceso.

  app_ctx.current_user_id()  ->  modulo1.fn_id_usuario_actual()
  app_ctx.current_role()     ->  modulo1.fn_rol_actual()

- SET SCHEMA + RENAME en vez de CREATE/DROP: las politicas RLS guardan la
  funcion por OID, asi que todas las pol_* que la usan siguen apuntando a la
  misma funcion sin recrearse (pg_get_expr ya las muestra con el nombre nuevo).
- Prefijo fn_ por convencion_nomenclatura_bd.md. Ademas `current_role` sin
  parentesis es la palabra reservada de SQL y devuelve el rol de Postgres
  (sgpmp_app), no el de la app: una politica que olvidara el schema compararia
  'sgpmp_app' = 'Administrador' y fallaria sin error.
- Los dos triggers PL/pgSQL que nombran estas funciones en su cuerpo se
  recrean: PL/pgSQL resuelve el nombre en cada sesion, no por OID.
- Sin app_ctx sobra el GRANT USAGE de b53fe19f276e: sgpmp_app ya tiene USAGE
  sobre modulo1. DROP SCHEMA sin CASCADE: si alguien agrego otro objeto a
  app_ctx, la migracion falla en vez de borrarlo.

La F3 de SamuelPR21 (315eaa6c5dc1) se rebasa encima de esta revision.
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "731fb3997631"
down_revision: Union[str, Sequence[str], None] = "b53fe19f276e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _recrear_triggers(usuario_id: str, rol: str) -> None:
    # Mismos cuerpos que 8d80fb56a30b / 5243bbbb28de, solo cambia el nombre
    # de la funcion de contexto.
    op.execute(f"""
        CREATE OR REPLACE FUNCTION modulo1.fn_prevenir_autocambio_rol()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
          IF OLD.id_usuario = {usuario_id}
             AND NEW.id_rol IS DISTINCT FROM OLD.id_rol THEN
            RAISE EXCEPTION 'Un usuario no puede modificar su propio rol (RF-05)';
          END IF;
          RETURN NEW;
        END;
        $$;
    """)
    op.execute(f"""
        CREATE OR REPLACE FUNCTION modulo9.fn_proteger_activo_especie()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
          IF NEW.es_activo IS DISTINCT FROM OLD.es_activo
             AND {rol} <> 'Administrador' THEN
            RAISE EXCEPTION 'Solo Administrador puede activar/desactivar especies (RF-15)';
          END IF;
          RETURN NEW;
        END;
        $$;
    """)


def upgrade() -> None:
    op.execute("ALTER FUNCTION app_ctx.current_user_id() SET SCHEMA modulo1;")
    op.execute("ALTER FUNCTION app_ctx.current_role() SET SCHEMA modulo1;")
    op.execute("ALTER FUNCTION modulo1.current_user_id() RENAME TO fn_id_usuario_actual;")
    op.execute("ALTER FUNCTION modulo1.current_role() RENAME TO fn_rol_actual;")
    _recrear_triggers("modulo1.fn_id_usuario_actual()", "modulo1.fn_rol_actual()")
    op.execute("DROP SCHEMA app_ctx;")


def downgrade() -> None:
    # Un schema recien creado no hereda los grants del anterior: sin este
    # GRANT los triggers fallan con "permission denied for schema app_ctx".
    op.execute("CREATE SCHEMA app_ctx;")
    op.execute("GRANT USAGE ON SCHEMA app_ctx TO sgpmp_app;")
    # current_role es palabra reservada: como nombre suelto va entre comillas.
    op.execute('ALTER FUNCTION modulo1.fn_rol_actual() RENAME TO "current_role";')
    op.execute("ALTER FUNCTION modulo1.fn_id_usuario_actual() RENAME TO current_user_id;")
    op.execute("ALTER FUNCTION modulo1.current_role() SET SCHEMA app_ctx;")
    op.execute("ALTER FUNCTION modulo1.current_user_id() SET SCHEMA app_ctx;")
    _recrear_triggers("app_ctx.current_user_id()", "app_ctx.current_role()")
