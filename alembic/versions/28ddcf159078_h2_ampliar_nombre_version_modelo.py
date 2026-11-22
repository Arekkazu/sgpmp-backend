# | Fecha      | Nombre   | Que se hizo                                                        |
# |------------|----------|--------------------------------------------------------------------|
# | 2026-10-31 | Arekkazu | RFC-010 H2 RF-69: nombre_version a varchar(100)                    |
"""h2: nombre_version de versiones_modelos a varchar(100) (RF-69, RFC-010)

Revision ID: 28ddcf159078
Revises: 622431450902
Create Date: 2026-10-31

H2 del plan del motor M04: ``nombre_version varchar(40)`` no alcanza para el modelo por
animal (RFC-010): el nombre lleva el id del activo y la versión de ET-02 mide 46
caracteres. Pasa a ``varchar(100)``.

Postgres no deja cambiar el tipo de una columna que usa una vista, y seis vistas de
``modulo4`` la usan (``vw_configuracion_motor``, ``vw_m04_*``). Algunos ambientes tienen
vistas o permisos creados fuera de Alembic, así que el bloque no las reescribe a mano:
toma de ``pg_catalog`` la definición, el dueño, los permisos y el comentario de cada vista
que depende de la columna, las borra, cambia el tipo y las recrea igual. Si alguna otra
vista dependiera de esas, el ``DROP`` falla y la migración se revierte entera.
"""
from typing import Sequence, Union

from alembic import op


revision: str = '28ddcf159078'
down_revision: Union[str, Sequence[str], None] = '622431450902'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_CAMBIAR_TIPO_CON_VISTAS = """
DO $$
DECLARE
    v record;
    g record;
BEGIN
    CREATE TEMP TABLE vistas_nombre_version ON COMMIT DROP AS
    SELECT DISTINCT c.oid, n.nspname, c.relname, pg_get_viewdef(c.oid) AS definicion,
           pg_get_userbyid(c.relowner) AS dueno, c.relacl, obj_description(c.oid, 'pg_class') AS comentario
    FROM pg_depend d
    JOIN pg_rewrite r ON r.oid = d.objid
    JOIN pg_class c ON c.oid = r.ev_class
    JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE d.refobjid = 'modulo4.versiones_modelos'::regclass
      AND d.refobjsubid = (SELECT attnum FROM pg_attribute
                           WHERE attrelid = 'modulo4.versiones_modelos'::regclass AND attname = 'nombre_version')
      AND c.oid <> 'modulo4.versiones_modelos'::regclass;

    FOR v IN SELECT * FROM vistas_nombre_version LOOP
        EXECUTE format('DROP VIEW %I.%I', v.nspname, v.relname);
    END LOOP;

    ALTER TABLE modulo4.versiones_modelos ALTER COLUMN nombre_version TYPE varchar({largo});

    FOR v IN SELECT * FROM vistas_nombre_version LOOP
        EXECUTE format('CREATE VIEW %I.%I AS %s', v.nspname, v.relname, v.definicion);
        EXECUTE format('ALTER VIEW %I.%I OWNER TO %I', v.nspname, v.relname, v.dueno);
        FOR g IN SELECT a.grantee, a.privilege_type, a.is_grantable
                 FROM aclexplode(v.relacl) a
                 WHERE a.grantee <> (SELECT oid FROM pg_roles WHERE rolname = v.dueno) LOOP
            EXECUTE format(
                'GRANT %s ON %I.%I TO %s%s', g.privilege_type, v.nspname, v.relname,
                CASE WHEN g.grantee = 0 THEN 'PUBLIC' ELSE quote_ident(pg_get_userbyid(g.grantee)) END,
                CASE WHEN g.is_grantable THEN ' WITH GRANT OPTION' ELSE '' END
            );
        END LOOP;
        IF v.comentario IS NOT NULL THEN
            EXECUTE format('COMMENT ON VIEW %I.%I IS %L', v.nspname, v.relname, v.comentario);
        END IF;
    END LOOP;
END $$;
"""


def upgrade() -> None:
    op.execute(_CAMBIAR_TIPO_CON_VISTAS.replace("{largo}", "100"))


def downgrade() -> None:
    # Falla si ya se registró un nombre de más de 40 caracteres (ids de activo de 7+ dígitos):
    # habría que retirar esas versiones antes, y RF-69 es append-only.
    op.execute(_CAMBIAR_TIPO_CON_VISTAS.replace("{largo}", "40"))
