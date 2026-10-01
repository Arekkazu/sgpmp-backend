"""F3: Mover funciones de contexto a modulo1, crear fn_fincas_del_usuario,
actualizar politicas modulo9 y retirar fincas.id_usuari

Revision ID: 315eaa6c5dc1
Revises: d7c4e9a1b2f6
Create Date: 2026-09-30 23:14:52.967017

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '315eaa6c5dc1'
down_revision: Union[str, Sequence[str], None] = 'd7c4e9a1b2f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_REASIGNAR_POLITICAS_APP_CTX_A_MODULO1 = """
DO $$
DECLARE
  pol RECORD;
  sql_stmt text;
  nuevo_qual text;
  nuevo_check text;
BEGIN
  FOR pol IN
    SELECT schemaname, tablename, policyname, qual, with_check
    FROM pg_policies
    WHERE qual LIKE '%app_ctx.current_user_id(%' OR qual LIKE '%app_ctx.current_role(%'
       OR with_check LIKE '%app_ctx.current_user_id(%' OR with_check LIKE '%app_ctx.current_role(%'
  LOOP
    sql_stmt := format('ALTER POLICY %I ON %I.%I', pol.policyname, pol.schemaname, pol.tablename);

    IF pol.qual IS NOT NULL THEN
      nuevo_qual := replace(replace(pol.qual,
                      'app_ctx.current_user_id(', 'modulo1.current_user_id('),
                      'app_ctx.current_role(', 'modulo1.current_role(');
      sql_stmt := sql_stmt || format(' USING (%s)', nuevo_qual);
    END IF;

    IF pol.with_check IS NOT NULL THEN
      nuevo_check := replace(replace(pol.with_check,
                       'app_ctx.current_user_id(', 'modulo1.current_user_id('),
                       'app_ctx.current_role(', 'modulo1.current_role(');
      sql_stmt := sql_stmt || format(' WITH CHECK (%s)', nuevo_check);
    END IF;

    EXECUTE sql_stmt;
  END LOOP;
END $$;
"""

_REASIGNAR_POLITICAS_MODULO1_A_APP_CTX = """
DO $$
DECLARE
  pol RECORD;
  sql_stmt text;
  nuevo_qual text;
  nuevo_check text;
BEGIN
  FOR pol IN
    SELECT schemaname, tablename, policyname, qual, with_check
    FROM pg_policies
    WHERE qual LIKE '%modulo1.current_user_id(%' OR qual LIKE '%modulo1.current_role(%'
       OR with_check LIKE '%modulo1.current_user_id(%' OR with_check LIKE '%modulo1.current_role(%'
  LOOP
    sql_stmt := format('ALTER POLICY %I ON %I.%I', pol.policyname, pol.schemaname, pol.tablename);

    IF pol.qual IS NOT NULL THEN
      nuevo_qual := replace(replace(pol.qual,
                      'modulo1.current_user_id(', 'app_ctx.current_user_id('),
                      'modulo1.current_role(', 'app_ctx.current_role(');
      sql_stmt := sql_stmt || format(' USING (%s)', nuevo_qual);
    END IF;

    IF pol.with_check IS NOT NULL THEN
      nuevo_check := replace(replace(pol.with_check,
                       'modulo1.current_user_id(', 'app_ctx.current_user_id('),
                       'modulo1.current_role(', 'app_ctx.current_role(');
      sql_stmt := sql_stmt || format(' WITH CHECK (%s)', nuevo_check);
    END IF;

    EXECUTE sql_stmt;
  END LOOP;
END $$;
"""


def upgrade() -> None:
    # =========================================================
    # 1. Crear las funciones de contexto en modulo1
    # =========================================================
    op.execute("""
        CREATE OR REPLACE FUNCTION modulo1.current_user_id()
        RETURNS bigint
        LANGUAGE sql
        STABLE
        AS $$
          SELECT NULLIF(current_setting('app.current_user_id', true), '')::bigint;
        $$;
    """)
    op.execute("""
        CREATE OR REPLACE FUNCTION modulo1.current_role()
        RETURNS text
        LANGUAGE sql
        STABLE
        AS $$
          SELECT NULLIF(current_setting('app.current_role', true), '');
        $$;
    """)

    # =========================================================
    # 2. Reapuntar dinamicamente todas las politicas existentes
    #    de app_ctx.* a modulo1.* (ALTER POLICY, no se pierde nada)
    # =========================================================
    op.execute(_REASIGNAR_POLITICAS_APP_CTX_A_MODULO1)

    # =========================================================
    # 3. Reapuntar las dos funciones trigger que tambien usan
    #    app_ctx.* en su cuerpo
    # =========================================================
    op.execute("""
        CREATE OR REPLACE FUNCTION modulo1.fn_prevenir_autocambio_rol()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
          IF OLD.id_usuario = modulo1.current_user_id()
             AND NEW.id_rol IS DISTINCT FROM OLD.id_rol THEN
            RAISE EXCEPTION 'Un usuario no puede modificar su propio rol (RF-05)';
          END IF;
          RETURN NEW;
        END;
        $$;
    """)
    op.execute("""
        CREATE OR REPLACE FUNCTION modulo9.fn_proteger_activo_especie()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
          IF NEW.es_activo IS DISTINCT FROM OLD.es_activo
             AND modulo1.current_role() <> 'Administrador' THEN
            RAISE EXCEPTION 'Solo Administrador puede activar/desactivar especies (RF-15)';
          END IF;
          RETURN NEW;
        END;
        $$;
    """)

    # =========================================================
    # 4. Verificacion: abortar si algo quedo sin reapuntar
    # =========================================================
    op.execute("""
        DO $$
        DECLARE
          restantes int;
        BEGIN
          SELECT count(*) INTO restantes
          FROM pg_policies
          WHERE qual LIKE '%app_ctx.current_user_id(%' OR qual LIKE '%app_ctx.current_role(%'
             OR with_check LIKE '%app_ctx.current_user_id(%' OR with_check LIKE '%app_ctx.current_role(%';

          IF restantes > 0 THEN
            RAISE EXCEPTION 'Quedan % politicas referenciando app_ctx; migracion abortada', restantes;
          END IF;
        END $$;
    """)

    # =========================================================
    # 5. Borrar app_ctx. Sin CASCADE: si algo no contemplado
    #    dependiera aun, esto falla ruidosamente.
    # =========================================================
    op.execute("DROP FUNCTION app_ctx.current_user_id();")
    op.execute("DROP FUNCTION app_ctx.current_role();")
    op.execute("DROP SCHEMA app_ctx;")

    # =========================================================
    # 6. Funcion de resolucion de fincas (M:N)
    # =========================================================
    op.execute("""
        CREATE OR REPLACE FUNCTION modulo9.fn_fincas_del_usuario(p_usuario_id bigint)
        RETURNS TABLE (id_finca int)
        LANGUAGE sql
        STABLE
        SECURITY DEFINER
        SET search_path = pg_catalog, modulo9
        AS $$
            SELECT id_finca FROM modulo9.usuarios_fincas WHERE id_usuario = p_usuario_id;
        $$;
    """)
    op.execute("REVOKE ALL ON FUNCTION modulo9.fn_fincas_del_usuario(bigint) FROM PUBLIC;")
    op.execute("GRANT EXECUTE ON FUNCTION modulo9.fn_fincas_del_usuario(bigint) TO sgpmp_app;")

    # =========================================================
    # 7. Politicas de fincas/infraestructuras: 1:1 -> M:N
    # =========================================================
    op.execute("DROP POLICY IF EXISTS pol_fincas_select ON modulo9.fincas;")
    op.execute("""
        CREATE POLICY pol_fincas_select ON modulo9.fincas
        FOR SELECT
        USING (
            id_finca IN (
                SELECT f.id_finca
                FROM modulo9.fn_fincas_del_usuario(modulo1.current_user_id()) f
            )
            OR modulo1.current_role() = 'Administrador'
        );
    """)

    op.execute("DROP POLICY IF EXISTS pol_infraestructuras_select ON modulo9.infraestructuras;")
    op.execute("""
        CREATE POLICY pol_infraestructuras_select ON modulo9.infraestructuras
        FOR SELECT
        USING (
            id_finca IN (
                SELECT f.id_finca
                FROM modulo9.fn_fincas_del_usuario(modulo1.current_user_id()) f
            )
            OR modulo1.current_role() = 'Administrador'
        );
    """)

    # =========================================================
    # 8. Borrar las 3 vistas dependientes de fincas.id_usuario
    #    (en orden explicito, no CASCADE, para que quede claro
    #    cuales se tocan)
    # =========================================================
    op.execute("DROP VIEW IF EXISTS modulo9.vw_rf19_fincas_nombre_normalizado;")
    op.execute("DROP VIEW IF EXISTS modulo9.vw_rf19_fincas_productor_resumen;")
    op.execute("DROP VIEW IF EXISTS modulo9.vw_rf20_fincas_activas_selector;")

    # =========================================================
    # 9. Retirar la columna
    # =========================================================
    op.execute("ALTER TABLE modulo9.fincas DROP COLUMN id_usuario;")

    # =========================================================
    # 10. Recrear las 3 vistas sobre el modelo M:N.
    #     Productor(es) = usuarios de usuarios_fincas cuyo rol es
    #     'Productor'. Se preagregan nombres/areas por separado
    #     para no inflar conteos al cruzar.
    # =========================================================
    op.execute("""
        CREATE VIEW modulo9.vw_rf19_fincas_nombre_normalizado AS
        SELECT id_finca,
               nombre,
               lower(nombre::text) AS nombre_normalizado
        FROM modulo9.fincas f;
    """)

    op.execute("""
        CREATE VIEW modulo9.vw_rf19_fincas_productor_resumen AS
        SELECT
            f.id_finca,
            f.nombre,
            f.ubicacion,
            f.tamano_h,
            f.es_activo,
            f.fecha_creacion,
            f.fecha_actualizacion,
            p.productores AS productor,
            p.correos_productores AS correo_electronico,
            COALESCE(a.areas_activas, 0) AS areas_activas,
            COALESCE(a.total_areas, 0) AS total_areas
        FROM modulo9.fincas f
        LEFT JOIN (
            SELECT
                uf.id_finca,
                string_agg(concat_ws(' ', u.nombre, u.apellidos), ', ') AS productores,
                string_agg(u.correo_electronico, ', ') AS correos_productores
            FROM modulo9.usuarios_fincas uf
            JOIN modulo1.usuarios u ON u.id_usuario = uf.id_usuario
            JOIN modulo1.roles r ON r.id_rol = u.id_rol
            WHERE r.nombre_rol = 'Productor'
            GROUP BY uf.id_finca
        ) p ON p.id_finca = f.id_finca
        LEFT JOIN (
            SELECT
                id_finca,
                count(*) FILTER (WHERE es_activo IS TRUE) AS areas_activas,
                count(*) AS total_areas
            FROM modulo9.infraestructuras
            GROUP BY id_finca
        ) a ON a.id_finca = f.id_finca;
    """)

    op.execute("""
        CREATE VIEW modulo9.vw_rf20_fincas_activas_selector AS
        SELECT
            f.id_finca,
            f.nombre,
            (f.ubicacion ->> 'municipio') AS municipio,
            (f.ubicacion ->> 'departamento') AS departamento,
            f.es_activo,
            p.productores AS productor,
            COALESCE(a.areas_activas, 0) AS areas_activas,
            COALESCE(a.total_areas, 0) AS total_areas
        FROM modulo9.fincas f
        LEFT JOIN (
            SELECT
                uf.id_finca,
                string_agg(concat_ws(' ', u.nombre, u.apellidos), ', ') AS productores
            FROM modulo9.usuarios_fincas uf
            JOIN modulo1.usuarios u ON u.id_usuario = uf.id_usuario
            JOIN modulo1.roles r ON r.id_rol = u.id_rol
            WHERE r.nombre_rol = 'Productor'
            GROUP BY uf.id_finca
        ) p ON p.id_finca = f.id_finca
        LEFT JOIN (
            SELECT
                id_finca,
                count(*) FILTER (WHERE es_activo IS TRUE) AS areas_activas,
                count(*) AS total_areas
            FROM modulo9.infraestructuras
            GROUP BY id_finca
        ) a ON a.id_finca = f.id_finca
        WHERE f.es_activo IS TRUE;
    """)


def downgrade() -> None:
    # ---- revertir vistas nuevas ----
    op.execute("DROP VIEW IF EXISTS modulo9.vw_rf20_fincas_activas_selector;")
    op.execute("DROP VIEW IF EXISTS modulo9.vw_rf19_fincas_productor_resumen;")
    op.execute("DROP VIEW IF EXISTS modulo9.vw_rf19_fincas_nombre_normalizado;")

    # ---- restaurar columna (best-effort: un usuario por finca,
    #      el de menor id_usuario en usuarios_fincas; la pertenencia
    #      multiple se pierde al volver al modelo 1:1) ----
    op.execute("ALTER TABLE modulo9.fincas ADD COLUMN id_usuario integer;")
    op.execute("""
        UPDATE modulo9.fincas f
        SET id_usuario = sub.id_usuario
        FROM (
            SELECT DISTINCT ON (id_finca) id_finca, id_usuario
            FROM modulo9.usuarios_fincas
            ORDER BY id_finca, id_usuario
        ) sub
        WHERE sub.id_finca = f.id_finca;
    """)

    # ---- recrear vistas originales (con id_usuario) ----
    op.execute("""
        CREATE VIEW modulo9.vw_rf19_fincas_nombre_normalizado AS
        SELECT id_finca,
               id_usuario,
               nombre,
               lower(nombre::text) AS nombre_normalizado
        FROM modulo9.fincas f;
    """)
    op.execute("""
        CREATE VIEW modulo9.vw_rf19_fincas_productor_resumen AS
        SELECT f.id_usuario,
            f.id_finca,
            f.nombre,
            f.ubicacion,
            f.tamano_h,
            f.es_activo,
            f.fecha_creacion,
            f.fecha_actualizacion,
            concat_ws(' ', u.nombre, u.apellidos) AS productor,
            u.correo_electronico,
            count(i.id_infraestructura) FILTER (WHERE i.es_activo IS TRUE) AS areas_activas,
            count(i.id_infraestructura) AS total_areas
        FROM modulo9.fincas f
        JOIN modulo1.usuarios u ON u.id_usuario = f.id_usuario
        LEFT JOIN modulo9.infraestructuras i ON i.id_finca = f.id_finca
        GROUP BY f.id_usuario, f.id_finca, f.nombre, f.ubicacion, f.tamano_h,
                 f.es_activo, f.fecha_creacion, f.fecha_actualizacion,
                 u.nombre, u.apellidos, u.correo_electronico;
    """)
    op.execute("""
        CREATE VIEW modulo9.vw_rf20_fincas_activas_selector AS
        SELECT f.id_finca,
            f.nombre,
            (f.ubicacion ->> 'municipio') AS municipio,
            (f.ubicacion ->> 'departamento') AS departamento,
            f.es_activo,
            concat_ws(' ', u.nombre, u.apellidos) AS productor,
            count(i.id_infraestructura) FILTER (WHERE i.es_activo IS TRUE) AS areas_activas,
            count(i.id_infraestructura) AS total_areas
        FROM modulo9.fincas f
        JOIN modulo1.usuarios u ON u.id_usuario = f.id_usuario
        LEFT JOIN modulo9.infraestructuras i ON i.id_finca = f.id_finca
        WHERE f.es_activo IS TRUE
        GROUP BY f.id_finca, f.nombre, f.ubicacion, f.es_activo, u.nombre, u.apellidos;
    """)

    # ---- revertir politicas de fincas/infraestructuras al modelo 1:1 ----
    op.execute("DROP POLICY IF EXISTS pol_infraestructuras_select ON modulo9.infraestructuras;")
    op.execute("""
        CREATE POLICY pol_infraestructuras_select ON modulo9.infraestructuras
        FOR SELECT
        USING (
            id_finca IN (
                SELECT id_finca FROM modulo9.fincas
                WHERE id_usuario = app_ctx.current_user_id()
            )
            OR app_ctx.current_role() = 'Administrador'
        );
    """)
    op.execute("DROP POLICY IF EXISTS pol_fincas_select ON modulo9.fincas;")
    op.execute("""
        CREATE POLICY pol_fincas_select ON modulo9.fincas
        FOR SELECT
        USING (
            id_usuario = app_ctx.current_user_id()
            OR app_ctx.current_role() = 'Administrador'
        );
    """)

    # ---- eliminar funcion M:N ----
    op.execute("DROP FUNCTION IF EXISTS modulo9.fn_fincas_del_usuario(bigint);")

    # ---- recrear app_ctx y reapuntar todo de vuelta ----
    op.execute("CREATE SCHEMA app_ctx;")
    op.execute("""
        CREATE OR REPLACE FUNCTION app_ctx.current_user_id()
        RETURNS bigint LANGUAGE sql STABLE
        AS $$ SELECT NULLIF(current_setting('app.current_user_id', true), '')::bigint; $$;
    """)
    op.execute("""
        CREATE OR REPLACE FUNCTION app_ctx.current_role()
        RETURNS text LANGUAGE sql STABLE
        AS $$ SELECT NULLIF(current_setting('app.current_role', true), ''); $$;
    """)

    op.execute(_REASIGNAR_POLITICAS_MODULO1_A_APP_CTX)

    op.execute("""
        CREATE OR REPLACE FUNCTION modulo1.fn_prevenir_autocambio_rol()
        RETURNS trigger LANGUAGE plpgsql
        AS $$
        BEGIN
          IF OLD.id_usuario = app_ctx.current_user_id()
             AND NEW.id_rol IS DISTINCT FROM OLD.id_rol THEN
            RAISE EXCEPTION 'Un usuario no puede modificar su propio rol (RF-05)';
          END IF;
          RETURN NEW;
        END;
        $$;
    """)
    op.execute("""
        CREATE OR REPLACE FUNCTION modulo9.fn_proteger_activo_especie()
        RETURNS trigger LANGUAGE plpgsql
        AS $$
        BEGIN
          IF NEW.es_activo IS DISTINCT FROM OLD.es_activo
             AND app_ctx.current_role() <> 'Administrador' THEN
            RAISE EXCEPTION 'Solo Administrador puede activar/desactivar especies (RF-15)';
          END IF;
          RETURN NEW;
        END;
        $$;
    """)

    op.execute("DROP FUNCTION IF EXISTS modulo1.current_user_id();")
    op.execute("DROP FUNCTION IF EXISTS modulo1.current_role();")