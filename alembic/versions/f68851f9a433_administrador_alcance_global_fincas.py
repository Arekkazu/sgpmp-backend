"""RF-19: el Administrador ve y gestiona todas las fincas

Revision ID: f68851f9a433
Revises: 5c2e8a1f7d39
Create Date: 2026-10-10 18:00:00.000000

RF-19 y todo M01 tratan al Administrador como "Administrador del sistema": hace
y ve todo. La F4 (PR #485) dejo a todos los roles, Administrador incluido,
limitados a sus filas de modulo9.usuarios_fincas. Un admin sin vinculo veia
listas vacias, 404 o `200 null`, y tampoco podia editar fincas ajenas porque el
UPDATE tambien exige pasar la politica SELECT.

Toda politica de modulo2/modulo9 que filtra por finca llega a
fn_fincas_del_usuario, directamente o a traves de fn_infraestructuras_/
fn_dispositivos_/fn_sensores_/fn_activos_del_usuario. Se cambia solo esta
funcion: si el rol del usuario es el protegido (roles.es_protegido, que solo
tiene el Administrador y que las politicas de roles impiden asignar a otro), el
usuario recibe todas las fincas. Para el resto de roles la consulta sobre
usuarios_fincas no cambia. No se toca ninguna politica.

Se decide por el rol de p_usuario_id, no por app.current_role, para que la
funcion responda igual sin importar quien la invoque. CREATE OR REPLACE
conserva el dueno y los GRANT de la funcion.
"""
from alembic import op

revision = 'f68851f9a433'
down_revision = '5c2e8a1f7d39'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE OR REPLACE FUNCTION modulo9.fn_fincas_del_usuario(p_usuario_id bigint)
        RETURNS TABLE (id_finca int)
        LANGUAGE sql
        STABLE
        SECURITY DEFINER
        SET search_path = pg_catalog, modulo9
        AS $$
            SELECT f.id_finca FROM modulo9.fincas f
            WHERE EXISTS (
                SELECT 1 FROM modulo1.usuarios u
                JOIN modulo1.roles r ON r.id_rol = u.id_rol
                WHERE u.id_usuario = p_usuario_id AND r.es_protegido
            )
            UNION
            SELECT uf.id_finca FROM modulo9.usuarios_fincas uf
            WHERE uf.id_usuario = p_usuario_id AND uf.es_activo IS TRUE;
        $$;
    """)


def downgrade() -> None:
    op.execute("""
        CREATE OR REPLACE FUNCTION modulo9.fn_fincas_del_usuario(p_usuario_id bigint)
        RETURNS TABLE (id_finca int)
        LANGUAGE sql
        STABLE
        SECURITY DEFINER
        SET search_path = pg_catalog, modulo9
        AS $$
            SELECT id_finca FROM modulo9.usuarios_fincas
            WHERE id_usuario = p_usuario_id AND es_activo IS TRUE;
        $$;
    """)
