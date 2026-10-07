"""Fase 4 roles

Revision ID: bc82ffbdf797
Revises: 0618e6f7b308
Create Date: 2026-10-04 14:53:21.410249

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'bc82ffbdf797'
down_revision: Union[str, Sequence[str], None] = '0618e6f7b308'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:

    op.execute("ALTER TABLE modulo9.fincas FORCE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE modulo9.infraestructuras FORCE ROW LEVEL SECURITY;")
    # =========================================================
    # 1. Ayudante de segundo nivel: infraestructuras alcanzables
    #    a traves de las fincas del usuario.
    # =========================================================
    op.execute("""
        CREATE OR REPLACE FUNCTION modulo9.fn_infraestructuras_del_usuario(p_usuario_id bigint)
        RETURNS TABLE (id_infraestructura int)
        LANGUAGE sql
        STABLE
        SECURITY DEFINER
        SET search_path = pg_catalog, modulo9
        AS $$
            SELECT i.id_infraestructura
            FROM modulo9.infraestructuras i
            WHERE i.id_finca IN (
                SELECT f.id_finca FROM modulo9.fn_fincas_del_usuario(p_usuario_id) f
            );
        $$;
    """)
    op.execute("REVOKE ALL ON FUNCTION modulo9.fn_infraestructuras_del_usuario(bigint) FROM PUBLIC;")
    op.execute("GRANT EXECUTE ON FUNCTION modulo9.fn_infraestructuras_del_usuario(bigint) TO sgpmp_app;")

    # =========================================================
    # 2. activos_biologicos nunca tuvo RLS habilitado (no estaba
    #    en el CREATE TABLE original) -- hay que ENABLE antes de
    #    FORCE, o las politicas no se evaluan para nadie.
    # =========================================================
    op.execute("ALTER TABLE modulo2.activos_biologicos ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE modulo2.activos_biologicos FORCE ROW LEVEL SECURITY;")

    # =========================================================
    # 3. Politicas: SELECT/INSERT/UPDATE scoped por finca via
    #    infraestructura. Sin politica de DELETE a proposito:
    #    el trigger trg_activo_biologico_no_delete ya bloquea
    #    cualquier DELETE; sin politica tampoco, queda doblemente
    #    bloqueado por defecto.
    # =========================================================
    op.execute("""
        CREATE POLICY pol_activos_biologicos_select ON modulo2.activos_biologicos
          FOR SELECT
          USING (
            id_infraestructura IN (
              SELECT ai.id_infraestructura
              FROM modulo9.fn_infraestructuras_del_usuario(modulo1.fn_id_usuario_actual()) ai
            )
          );
    """)

    op.execute("""
        CREATE POLICY pol_activos_biologicos_insert ON modulo2.activos_biologicos
          FOR INSERT
          WITH CHECK (
            id_infraestructura IN (
              SELECT ai.id_infraestructura
              FROM modulo9.fn_infraestructuras_del_usuario(modulo1.fn_id_usuario_actual()) ai
            )
          );
    """)

    op.execute("""
        CREATE POLICY pol_activos_biologicos_update ON modulo2.activos_biologicos
          FOR UPDATE
          USING (
            id_infraestructura IN (
              SELECT ai.id_infraestructura
              FROM modulo9.fn_infraestructuras_del_usuario(modulo1.fn_id_usuario_actual()) ai
            )
          )
          WITH CHECK (
            id_infraestructura IN (
              SELECT ai.id_infraestructura
              FROM modulo9.fn_infraestructuras_del_usuario(modulo1.fn_id_usuario_actual()) ai
            )
          );
    """)


def downgrade() -> None:
    op.execute("ALTER TABLE modulo9.fincas NO FORCE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE modulo9.infraestructuras NO FORCE ROW LEVEL SECURITY;")
    op.execute("DROP POLICY IF EXISTS pol_activos_biologicos_update ON modulo2.activos_biologicos;")
    op.execute("DROP POLICY IF EXISTS pol_activos_biologicos_insert ON modulo2.activos_biologicos;")
    op.execute("DROP POLICY IF EXISTS pol_activos_biologicos_select ON modulo2.activos_biologicos;")
    op.execute("ALTER TABLE modulo2.activos_biologicos NO FORCE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE modulo2.activos_biologicos DISABLE ROW LEVEL SECURITY;")
    op.execute("DROP FUNCTION IF EXISTS modulo9.fn_infraestructuras_del_usuario(bigint);")