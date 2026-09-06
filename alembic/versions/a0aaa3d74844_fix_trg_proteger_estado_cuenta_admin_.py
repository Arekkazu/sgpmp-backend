"""fix_trg_proteger_estado_cuenta_admin_schema_calificado

Revision ID: a0aaa3d74844
Revises: 52f259545ea8
Create Date: 2026-09-05 11:35:51.138399

Corrige de verdad la migración `76567ec53021` (INC-M01-23-045 / issue #116):
esa migración escribió `CREATE OR REPLACE FUNCTION trg_fn_proteger_estado_cuenta_admin()`
sin calificar el schema. Por el `search_path` de la sesión, Postgres creó una
función nueva en `public` en vez de reemplazar la real en `modulo1`, que sigue
siendo la que el trigger `trg_proteger_estado_cuenta_admin` de
`modulo1.cuentas_usuarios` invoca. Por eso el bloqueo automático de una cuenta
Administrador tras 5 intentos fallidos seguía respondiendo 500 en vez de 423:
el `UPDATE` a `id_estado_cuenta` disparaba la función vieja de `modulo1`, sin
la excepción para la propia transición a "Bloqueado".

Esta migración:
1. Reemplaza `modulo1.trg_fn_proteger_estado_cuenta_admin` (schema calificado
   esta vez) con la lógica correcta, corrigiendo también el nombre de tabla/
   columna que la función huérfana de `public` tenía mal
   (`modulo1.estados_cuenta`/`nombre_estado` no existen; la tabla real es
   `modulo1.estados_cuentas` con columna `nombre`).
2. Elimina la función huérfana `public.trg_fn_proteger_estado_cuenta_admin`
   (no la usa ningún trigger — confirmado antes de borrarla).
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'a0aaa3d74844'
down_revision: Union[str, Sequence[str], None] = '52f259545ea8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
    CREATE OR REPLACE FUNCTION modulo1.trg_fn_proteger_estado_cuenta_admin()
    RETURNS TRIGGER AS $$
    DECLARE
        v_es_protegido BOOLEAN;
        v_nombre_rol   VARCHAR(100);
        v_id_bloqueado INTEGER;
    BEGIN
        IF NEW.id_estado_cuenta = OLD.id_estado_cuenta THEN
            RETURN NEW;
        END IF;

        SELECT id_estado_cuenta INTO v_id_bloqueado
          FROM modulo1.estados_cuentas WHERE nombre = 'Bloqueado';
        IF NEW.id_estado_cuenta = v_id_bloqueado THEN
            RETURN NEW;
        END IF;

        SELECT r.es_protegido, r.nombre_rol INTO v_es_protegido, v_nombre_rol
          FROM modulo1.usuarios u JOIN modulo1.roles r ON r.id_rol = u.id_rol
         WHERE u.id_usuario = NEW.id_usuario;

        IF v_es_protegido = TRUE THEN
            RAISE EXCEPTION
                'PROTECTED_ADMIN: No se puede cambiar el estado de la cuenta del usuario con rol protegido "%".',
                v_nombre_rol USING ERRCODE = 'P0004';
        END IF;

        RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    """)
    op.execute("DROP FUNCTION IF EXISTS public.trg_fn_proteger_estado_cuenta_admin();")


def downgrade() -> None:
    op.execute("""
    CREATE OR REPLACE FUNCTION modulo1.trg_fn_proteger_estado_cuenta_admin()
    RETURNS TRIGGER AS $$
    DECLARE
        v_es_protegido BOOLEAN;
        v_nombre_rol   VARCHAR(100);
    BEGIN
        IF NEW.id_estado_cuenta = OLD.id_estado_cuenta THEN
            RETURN NEW;
        END IF;
        SELECT r.es_protegido, r.nombre_rol INTO v_es_protegido, v_nombre_rol
          FROM modulo1.usuarios u JOIN modulo1.roles r ON r.id_rol = u.id_rol
         WHERE u.id_usuario = NEW.id_usuario;
        IF v_es_protegido = TRUE THEN
            RAISE EXCEPTION
                'PROTECTED_ADMIN: No se puede cambiar el estado de la cuenta del usuario con rol protegido "%".',
                v_nombre_rol USING ERRCODE = 'P0004';
        END IF;
        RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    """)
    op.execute("""
    CREATE OR REPLACE FUNCTION public.trg_fn_proteger_estado_cuenta_admin()
    RETURNS trigger
    LANGUAGE plpgsql
    AS $function$
        DECLARE
            v_es_protegido BOOLEAN;
            v_nombre_rol   VARCHAR(100);
            v_id_bloqueado INTEGER;
        BEGIN
            IF NEW.id_estado_cuenta = OLD.id_estado_cuenta THEN
                RETURN NEW;
            END IF;
            SELECT id_estado_cuenta INTO v_id_bloqueado
              FROM modulo1.estados_cuenta WHERE nombre_estado = 'Bloqueado';
            IF NEW.id_estado_cuenta = v_id_bloqueado THEN
                RETURN NEW;
            END IF;
            SELECT r.es_protegido, r.nombre_rol INTO v_es_protegido, v_nombre_rol
              FROM modulo1.usuarios u JOIN modulo1.roles r ON r.id_rol = u.id_rol
             WHERE u.id_usuario = NEW.id_usuario;
            IF v_es_protegido = TRUE THEN
                RAISE EXCEPTION
                    'PROTECTED_ADMIN: No se puede cambiar el estado de la cuenta del usuario con rol protegido "%".',
                    v_nombre_rol USING ERRCODE = 'P0004';
            END IF;
            RETURN NEW;
        END;
        $function$
    """)
