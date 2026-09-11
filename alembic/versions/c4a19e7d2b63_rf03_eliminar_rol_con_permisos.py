"""RF-03: permitir eliminar roles sin usuarios junto con sus permisos.

Revision ID: c4a19e7d2b63
Revises: f1c62d8b04a7
Create Date: 2026-08-31 18:00:00.000000

``modulo1.permisos.id_rol`` usaba ``NO ACTION``. Por eso todo rol creado por
el flujo normal (que exige al menos un permiso) era imposible de eliminar:
la FK rechazaba el ``DELETE`` del padre.

La FK pasa a ``ON DELETE CASCADE``. El trigger que impide retirar manualmente
el ultimo permiso se conserva, pero omite esa validacion cuando el rol padre
ya no existe porque PostgreSQL esta ejecutando la cascada. Tambien se corrige
``trg_fn_proteger_rol_admin``: en DELETE devolvia ``NEW`` (NULL) y cancelaba el
borrado de roles no protegidos; ahora devuelve ``OLD``. Las protecciones del
rol Administrador y de roles con usuarios se mantienen y la FK
``usuarios.id_rol`` permanece en ``NO ACTION``.
"""
from typing import Sequence, Union

from alembic import op


revision: str = "c4a19e7d2b63"
down_revision: Union[str, Sequence[str], None] = "f1c62d8b04a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_FUNCION_CON_EXCEPCION_DE_CASCADA = """
CREATE OR REPLACE FUNCTION modulo1.trg_fn_validar_permiso_minimo_rol()
RETURNS trigger
LANGUAGE plpgsql
AS $function$
DECLARE
    v_count INTEGER;
BEGIN
    -- En un ON DELETE CASCADE la fila padre ya no es visible cuando se
    -- ejecutan los triggers de los permisos. Esa es la unica situacion en la
    -- que un rol puede quedar sin permisos: el propio rol esta desapareciendo.
    IF NOT EXISTS (
        SELECT 1
        FROM modulo1.roles
        WHERE id_rol = OLD.id_rol
    ) THEN
        RETURN OLD;
    END IF;

    SELECT COUNT(*) INTO v_count
    FROM modulo1.permisos
    WHERE id_rol = OLD.id_rol
      AND id_permiso <> OLD.id_permiso
      AND es_activo = TRUE;

    IF v_count = 0 THEN
        RAISE EXCEPTION
            'MIN_PERMISSION: No se puede eliminar el ultimo permiso activo.'
            USING ERRCODE = 'P0006';
    END IF;

    RETURN OLD;
END;
$function$;
"""


_FUNCION_ANTERIOR = """
CREATE OR REPLACE FUNCTION modulo1.trg_fn_validar_permiso_minimo_rol()
RETURNS trigger
LANGUAGE plpgsql
AS $function$
DECLARE
    v_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO v_count
    FROM modulo1.permisos
    WHERE id_rol = OLD.id_rol
      AND id_permiso <> OLD.id_permiso
      AND es_activo = TRUE;

    IF v_count = 0 THEN
        RAISE EXCEPTION
            'MIN_PERMISSION: No se puede eliminar el ultimo permiso activo.'
            USING ERRCODE = 'P0006';
    END IF;

    RETURN OLD;
END;
$function$;
"""


_FUNCION_PROTEGER_ROL_CORREGIDA = """
CREATE OR REPLACE FUNCTION modulo1.trg_fn_proteger_rol_admin()
RETURNS trigger
LANGUAGE plpgsql
AS $function$
BEGIN
    IF TG_OP = 'DELETE' THEN
        IF OLD.es_protegido = TRUE THEN
            RAISE EXCEPTION 'PROTECTED_ROLE: Rol protegido.'
                USING ERRCODE = 'P0004';
        END IF;

        -- En un trigger BEFORE DELETE debe retornarse OLD. Retornar NEW
        -- (NULL para DELETE) cancela silenciosamente la eliminacion.
        RETURN OLD;
    END IF;

    IF OLD.es_protegido = TRUE AND NEW.nombre_rol <> OLD.nombre_rol THEN
        RAISE EXCEPTION 'PROTECTED_ROLE: No se puede modificar.'
            USING ERRCODE = 'P0004';
    END IF;

    IF OLD.es_protegido = TRUE AND NEW.es_protegido = FALSE THEN
        RAISE EXCEPTION 'PROTECTED_ROLE: No se puede desproteger.'
            USING ERRCODE = 'P0004';
    END IF;

    RETURN NEW;
END;
$function$;
"""


_FUNCION_PROTEGER_ROL_ANTERIOR = """
CREATE OR REPLACE FUNCTION modulo1.trg_fn_proteger_rol_admin()
RETURNS trigger
LANGUAGE plpgsql
AS $function$
BEGIN
    IF TG_OP = 'DELETE' AND OLD.es_protegido = TRUE THEN
        RAISE EXCEPTION 'PROTECTED_ROLE: Rol protegido.'
            USING ERRCODE = 'P0004';
    END IF;

    IF TG_OP = 'UPDATE' AND OLD.es_protegido = TRUE AND NEW.nombre_rol <> OLD.nombre_rol THEN
        RAISE EXCEPTION 'PROTECTED_ROLE: No se puede modificar.'
            USING ERRCODE = 'P0004';
    END IF;

    IF TG_OP = 'UPDATE' AND OLD.es_protegido = TRUE AND NEW.es_protegido = FALSE THEN
        RAISE EXCEPTION 'PROTECTED_ROLE: No se puede desproteger.'
            USING ERRCODE = 'P0004';
    END IF;

    RETURN NEW;
END;
$function$;
"""


def upgrade() -> None:
    op.execute(_FUNCION_CON_EXCEPCION_DE_CASCADA)
    op.execute(_FUNCION_PROTEGER_ROL_CORREGIDA)
    op.drop_constraint(
        "fk_recurso_rol",
        "permisos",
        schema="modulo1",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "fk_recurso_rol",
        "permisos",
        "roles",
        ["id_rol"],
        ["id_rol"],
        source_schema="modulo1",
        referent_schema="modulo1",
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_recurso_rol",
        "permisos",
        schema="modulo1",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "fk_recurso_rol",
        "permisos",
        "roles",
        ["id_rol"],
        ["id_rol"],
        source_schema="modulo1",
        referent_schema="modulo1",
    )
    op.execute(_FUNCION_ANTERIOR)
    op.execute(_FUNCION_PROTEGER_ROL_ANTERIOR)
