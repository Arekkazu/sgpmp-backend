"""F3: crear fn_fincas_del_usuario, actualizar politicas modulo9 y retirar
fincas.id_usuario

Revision ID: 315eaa6c5dc1
Revises: 4c1700760710
Create Date: 2026-09-30 23:14:52.967017

D2 resuelta como "se retira": el acceso vive solo en modulo9.usuarios_fincas
(creada en 1b9536d4411c). Antes de borrar la columna se reescribe
trg_fn_finca_nombre_unique, que leia NEW.id_usuario: sin ese cambio todo INSERT
y todo UPDATE OF nombre sobre fincas falla con 'record "new" has no field
"id_usuario"'. La unicidad por productor (P0120) era redundante: la global
(P0119) ya impide cualquier nombre repetido.

"""
from typing import Sequence, Union

from alembic import op


revision: str = '315eaa6c5dc1'
down_revision: Union[str, Sequence[str], None] = '4c1700760710'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Cuerpo de baseline (identico al de sgpmp_dev). {declarar_productor} y
# {validar_productor} quedan vacios en upgrade y se restauran en downgrade.
_FN_NOMBRE_UNIQUE = r"""
CREATE OR REPLACE FUNCTION modulo9.trg_fn_finca_nombre_unique() RETURNS trigger
    LANGUAGE plpgsql
    AS $_$
DECLARE
    v_count_global    INTEGER;
{declarar_productor}BEGIN
    NEW.nombre := TRIM(NEW.nombre);

    -- Validar formato: solo letras, espacios, acentos y ñ  (operador !~ correcto)
    IF NEW.nombre !~ '^[A-Za-záéíóúÁÉÍÓÚñÑüÜ\s]+$' THEN
        RAISE EXCEPTION
            'INVALID_FORMAT: El nombre de la finca solo permite letras, espacios '
            'y caracteres del español. No se admiten números ni símbolos. Valor: "%".',
            NEW.nombre
        USING ERRCODE = 'P0118';
    END IF;

    -- Validar unicidad global
    SELECT COUNT(*) INTO v_count_global
    FROM modulo9.fincas
    WHERE LOWER(TRIM(nombre)) = LOWER(NEW.nombre)
      AND id_finca <> COALESCE(NEW.id_finca, -1);

    IF v_count_global > 0 THEN
        RAISE EXCEPTION
            'DUPLICATE_FARM_GLOBAL: Ya existe una finca con el nombre "%" '
            'en el sistema (unicidad global).',
            NEW.nombre
        USING ERRCODE = 'P0119';
    END IF;
{validar_productor}
    RETURN NEW;
END;
$_$;
"""

_DECLARAR_PRODUCTOR = "    v_count_productor INTEGER;\n"

_VALIDAR_PRODUCTOR = """
    -- Validar unicidad por productor
    IF NEW.id_usuario IS NOT NULL THEN
        SELECT COUNT(*) INTO v_count_productor
        FROM modulo9.fincas
        WHERE LOWER(TRIM(nombre)) = LOWER(NEW.nombre)
          AND id_usuario = NEW.id_usuario
          AND id_finca <> COALESCE(NEW.id_finca, -1);

        IF v_count_productor > 0 THEN
            RAISE EXCEPTION
                'DUPLICATE_FARM_PRODUCER: El productor ya tiene una finca '
                'registrada con el nombre "%".',
                NEW.nombre
            USING ERRCODE = 'P0120';
        END IF;
    END IF;
"""

# DROP VIEW no conserva los GRANT: se re-otorgan los que tienen hoy las tres
# vistas en sgpmp_dev, solo a los roles que existan (TEST no tiene los rol_*).
_GRANTS_VISTAS = """
DO $$
DECLARE r text; v text;
BEGIN
    FOREACH v IN ARRAY ARRAY['vw_rf19_fincas_nombre_normalizado',
                             'vw_rf19_fincas_productor_resumen',
                             'vw_rf20_fincas_activas_selector'] LOOP
        FOR r IN SELECT rolname FROM pg_roles
                 WHERE rolname IN ('sgpmp_app', 'rol_app', 'rol_dev', 'rol_impl', 'rol_migracion') LOOP
            EXECUTE format('GRANT INSERT, SELECT, UPDATE, DELETE ON modulo9.%I TO %I', v, r);
        END LOOP;
        FOR r IN SELECT rolname FROM pg_roles WHERE rolname = 'rol_aiot' LOOP
            EXECUTE format('GRANT INSERT, SELECT ON modulo9.%I TO %I', v, r);
        END LOOP;
    END LOOP;
END $$;
"""


def upgrade() -> None:
    # =========================================================
    # 1. Funcion de resolucion de fincas (M:N)
    # =========================================================
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
    op.execute("REVOKE ALL ON FUNCTION modulo9.fn_fincas_del_usuario(bigint) FROM PUBLIC;")
    op.execute("GRANT EXECUTE ON FUNCTION modulo9.fn_fincas_del_usuario(bigint) TO sgpmp_app;")

    # =========================================================
    # 2. Politicas de fincas/infraestructuras: 1:1 -> M:N
    #    (usan los nombres ya reubicados por la migracion de Alex)
    # =========================================================
    op.execute("DROP POLICY IF EXISTS pol_fincas_select ON modulo9.fincas;")
    op.execute("""
        CREATE POLICY pol_fincas_select ON modulo9.fincas
        FOR SELECT
        USING (
            id_finca IN (
                SELECT f.id_finca
                FROM modulo9.fn_fincas_del_usuario(modulo1.fn_id_usuario_actual()) f
            )
            OR modulo1.fn_rol_actual() = 'Administrador'
        );
    """)

    op.execute("DROP POLICY IF EXISTS pol_infraestructuras_select ON modulo9.infraestructuras;")
    op.execute("""
        CREATE POLICY pol_infraestructuras_select ON modulo9.infraestructuras
        FOR SELECT
        USING (
            id_finca IN (
                SELECT f.id_finca
                FROM modulo9.fn_fincas_del_usuario(modulo1.fn_id_usuario_actual()) f
            )
            OR modulo1.fn_rol_actual() = 'Administrador'
        );
    """)

    # =========================================================
    # 3. Vistas dependientes de fincas.id_usuario
    # =========================================================
    op.execute("DROP VIEW IF EXISTS modulo9.vw_rf19_fincas_nombre_normalizado;")
    op.execute("DROP VIEW IF EXISTS modulo9.vw_rf19_fincas_productor_resumen;")
    op.execute("DROP VIEW IF EXISTS modulo9.vw_rf20_fincas_activas_selector;")

    # El trigger lee NEW.id_usuario; se reescribe antes de que la columna desaparezca.
    op.execute(_FN_NOMBRE_UNIQUE.format(declarar_productor="", validar_productor=""))
    op.execute("ALTER TABLE modulo9.fincas DROP COLUMN id_usuario;")

    op.execute("""
        CREATE VIEW modulo9.vw_rf19_fincas_nombre_normalizado AS
        SELECT id_finca, nombre, lower(nombre::text) AS nombre_normalizado
        FROM modulo9.fincas f;
    """)

    op.execute("""
        CREATE VIEW modulo9.vw_rf19_fincas_productor_resumen AS
        SELECT
            f.id_finca, f.nombre, f.ubicacion, f.tamano_h, f.es_activo,
            f.fecha_creacion, f.fecha_actualizacion,
            p.productores AS productor,
            p.correos_productores AS correo_electronico,
            COALESCE(a.areas_activas, 0) AS areas_activas,
            COALESCE(a.total_areas, 0) AS total_areas
        FROM modulo9.fincas f
        LEFT JOIN (
            SELECT uf.id_finca,
                   string_agg(concat_ws(' ', u.nombre, u.apellidos), ', ') AS productores,
                   string_agg(u.correo_electronico, ', ') AS correos_productores
            FROM modulo9.usuarios_fincas uf
            JOIN modulo1.usuarios u ON u.id_usuario = uf.id_usuario
            JOIN modulo1.roles r ON r.id_rol = u.id_rol
            WHERE r.nombre_rol = 'Productor'
            GROUP BY uf.id_finca
        ) p ON p.id_finca = f.id_finca
        LEFT JOIN (
            SELECT id_finca,
                   count(*) FILTER (WHERE es_activo IS TRUE) AS areas_activas,
                   count(*) AS total_areas
            FROM modulo9.infraestructuras
            GROUP BY id_finca
        ) a ON a.id_finca = f.id_finca;
    """)

    op.execute("""
        CREATE VIEW modulo9.vw_rf20_fincas_activas_selector AS
        SELECT
            f.id_finca, f.nombre,
            (f.ubicacion ->> 'municipio') AS municipio,
            (f.ubicacion ->> 'departamento') AS departamento,
            f.es_activo,
            p.productores AS productor,
            COALESCE(a.areas_activas, 0) AS areas_activas,
            COALESCE(a.total_areas, 0) AS total_areas
        FROM modulo9.fincas f
        LEFT JOIN (
            SELECT uf.id_finca,
                   string_agg(concat_ws(' ', u.nombre, u.apellidos), ', ') AS productores
            FROM modulo9.usuarios_fincas uf
            JOIN modulo1.usuarios u ON u.id_usuario = uf.id_usuario
            JOIN modulo1.roles r ON r.id_rol = u.id_rol
            WHERE r.nombre_rol = 'Productor'
            GROUP BY uf.id_finca
        ) p ON p.id_finca = f.id_finca
        LEFT JOIN (
            SELECT id_finca,
                   count(*) FILTER (WHERE es_activo IS TRUE) AS areas_activas,
                   count(*) AS total_areas
            FROM modulo9.infraestructuras
            GROUP BY id_finca
        ) a ON a.id_finca = f.id_finca
        WHERE f.es_activo IS TRUE;
    """)
    op.execute(_GRANTS_VISTAS)


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS modulo9.vw_rf20_fincas_activas_selector;")
    op.execute("DROP VIEW IF EXISTS modulo9.vw_rf19_fincas_productor_resumen;")
    op.execute("DROP VIEW IF EXISTS modulo9.vw_rf19_fincas_nombre_normalizado;")

    op.execute("ALTER TABLE modulo9.fincas ADD COLUMN id_usuario integer;")
    op.execute(
        "ALTER TABLE modulo9.fincas ADD CONSTRAINT finca_id_usuario_fkey "
        "FOREIGN KEY (id_usuario) REFERENCES modulo1.usuarios(id_usuario) NOT VALID;"
    )
    op.execute(
        "COMMENT ON COLUMN modulo9.fincas.id_usuario IS "
        "'Usuario propietario o responsable de la finca (opcional).';"
    )
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

    op.execute("""
        CREATE VIEW modulo9.vw_rf19_fincas_nombre_normalizado AS
        SELECT id_finca, id_usuario, nombre, lower(nombre::text) AS nombre_normalizado
        FROM modulo9.fincas f;
    """)
    op.execute("""
        CREATE VIEW modulo9.vw_rf19_fincas_productor_resumen AS
        SELECT f.id_usuario, f.id_finca, f.nombre, f.ubicacion, f.tamano_h, f.es_activo,
            f.fecha_creacion, f.fecha_actualizacion,
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
        SELECT f.id_finca, f.nombre,
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
    op.execute(_GRANTS_VISTAS)
    op.execute(_FN_NOMBRE_UNIQUE.format(
        declarar_productor=_DECLARAR_PRODUCTOR, validar_productor=_VALIDAR_PRODUCTOR,
    ))

    op.execute("DROP POLICY IF EXISTS pol_infraestructuras_select ON modulo9.infraestructuras;")
    op.execute("""
        CREATE POLICY pol_infraestructuras_select ON modulo9.infraestructuras
        FOR SELECT
        USING (
            id_finca IN (SELECT id_finca FROM modulo9.fincas WHERE id_usuario = modulo1.fn_id_usuario_actual())
            OR modulo1.fn_rol_actual() = 'Administrador'
        );
    """)
    op.execute("DROP POLICY IF EXISTS pol_fincas_select ON modulo9.fincas;")
    op.execute("""
        CREATE POLICY pol_fincas_select ON modulo9.fincas
        FOR SELECT
        USING (
            id_usuario = modulo1.fn_id_usuario_actual()
            OR modulo1.fn_rol_actual() = 'Administrador'
        );
    """)

    op.execute("DROP FUNCTION IF EXISTS modulo9.fn_fincas_del_usuario(bigint);")