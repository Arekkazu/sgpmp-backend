# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-28 | Arekkazu | BE-0 RF-55: recurso reglas_alertas y trigger de versión que no fallaba al editar |
"""RF-55 BE-0: CRUD de reglas de alerta (recurso RBAC y trigger de versión).

Hasta ahora las reglas de ``modulo3.reglas_alertas`` se cargaban por SQL. El
CRUD ``/iot/reglas-alertas`` necesita en BD:

- ``modulo3.fn_regla_alerta_versionamiento`` (``trg_aux_02_version_regla_alerta``)
  asignaba ``now()::time with time zone`` a ``fecha_actualizacion``, que es
  ``timestamptz``: cualquier UPDATE que cambiara un umbral fallaba con
  ``invalid input syntax for type timestamp with time zone``. Nadie editaba
  reglas, así que no se notaba. Ahora:
  * ``fecha_actualizacion := now()`` en todo UPDATE (es la marca de la
    concurrencia optimista del PUT, 412).
  * ``version_regla`` sube cuando cambia cualquier campo que viaja al Gateway
    Edge en ``payload_regla_compuesta`` (antes solo umbrales, ventana y
    ``es_regla_compuesta``: editar ``lectura_confirmacion_max``, el sensor o
    desactivar la regla no subía la versión, y el Edge no podía descartar la
    vieja).
- Recurso ``reglas_alertas`` con Crear, Leer, Actualizar y Desactivar para el
  Administrador (RF-57: "configurar reglas y umbrales") y Leer para el
  Ingeniero de Campo, que ya las propaga (recurso 65). El id sale de la
  secuencia: el código lo ubica por nombre (``require_permission_sobre``).
- INSERT/UPDATE sobre la tabla para los roles de la app que existan.

El downgrade vuelve al criterio de versión anterior (sin el error de tipo) y retira los permisos reversibles;
los ``admin_*`` y el recurso quedan (``trg_fn_proteger_permisos_admin_delete``).

Revision ID: 46252dbd62b4
Revises: ebbb160365e5
Create Date: 2026-10-28 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = "46252dbd62b4"
down_revision: Union[str, Sequence[str], None] = "ebbb160365e5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_NOMBRE_RECURSO = "reglas_alertas"
_PERMISOS = (
    ("admin_crear_regla_alerta", "Administrador crea reglas de alerta (RF-55/RF-57).", 1, 1),
    ("admin_leer_regla_alerta", "Administrador consulta reglas de alerta (RF-55/RF-57).", 1, 2),
    ("admin_actualizar_regla_alerta", "Administrador edita reglas de alerta (RF-55/RF-57).", 1, 3),
    ("admin_desactivar_regla_alerta", "Administrador desactiva y reactiva reglas de alerta (RF-55/RF-57).", 1, 4),
    ("ing_leer_regla_alerta", "Ingeniero de Campo consulta reglas de alerta (RF-55/RF-57).", 4, 2),
)
_ROLES_APP = "('sgpmp_app', 'rol_app', 'rol_dev', 'rol_impl', 'rol_migracion')"

# Campos de payload_regla_compuesta (lo que recibe el Gateway Edge).
_CAMPOS_EDGE = (
    "nombre", "descripcion", "tipo_sensor", "categoria_variable", "umbral_min", "umbral_max",
    "umbrales_severdiad", "ventana_confirmacion_min", "lectura_confirmacion_max", "mensaje",
    "id_finca", "id_especie", "es_activa", "es_regla_compuesta",
)


def upgrade() -> None:
    nuevos = ", ".join(f"NEW.{c}" for c in _CAMPOS_EDGE)
    viejos = ", ".join(f"OLD.{c}" for c in _CAMPOS_EDGE)
    op.execute(f"""
        CREATE OR REPLACE FUNCTION modulo3.fn_regla_alerta_versionamiento()
         RETURNS trigger
         LANGUAGE plpgsql
        AS $function$
        BEGIN
            IF ROW({nuevos}) IS DISTINCT FROM ROW({viejos}) THEN
                NEW.version_regla := OLD.version_regla + 1;
            END IF;
            NEW.fecha_actualizacion := now();
            RETURN NEW;
        END;
        $function$
    """)

    op.execute(f"""
        DO $$
        DECLARE r text;
        BEGIN
            FOR r IN SELECT rolname FROM pg_roles WHERE rolname IN {_ROLES_APP} LOOP
                EXECUTE format('GRANT INSERT, SELECT, UPDATE ON modulo3.reglas_alertas TO %I', r);
                EXECUTE format(
                    'GRANT USAGE, SELECT ON SEQUENCE modulo3.reglas_alertas_id_regla_alertas_seq TO %I', r
                );
            END LOOP;
        END $$;
    """)

    valores = ",\n".join(
        f"('{nombre}', '{descripcion}', {id_rol}, v_id_recurso, {id_accion}, TRUE)"
        for nombre, descripcion, id_rol, id_accion in _PERMISOS
    )
    op.execute(f"""
        DO $$
        DECLARE
            v_id_recurso INTEGER;
        BEGIN
            PERFORM set_config('app.current_role', 'Administrador', true);
            PERFORM set_config('app.current_user_id', '1', true);
            IF NOT EXISTS (
                SELECT 1 FROM modulo1.roles WHERE id_rol = 4 AND lower(btrim(nombre_rol)) = 'ingeniero de campo'
            ) THEN
                RAISE EXCEPTION 'RF-55: id_rol=4 no corresponde al rol Ingeniero de Campo';
            END IF;

            -- Recursos con id explícito (p. ej. 65) dejan la secuencia atrás en algunas bases.
            PERFORM setval(
                'modulo1.recursos_id_recurso_seq',
                GREATEST((SELECT max(id_recurso) FROM modulo1.recursos),
                         (SELECT last_value FROM modulo1.recursos_id_recurso_seq))
            );
            INSERT INTO modulo1.recursos (nombre_recurso, descripcion, es_proceso_especial)
            VALUES ('{_NOMBRE_RECURSO}', 'Reglas de alerta simples y compuestas evaluadas en backend y Edge (RF-55/RF-57)', FALSE)
            ON CONFLICT (nombre_recurso) DO NOTHING;
            SELECT id_recurso INTO STRICT v_id_recurso
            FROM modulo1.recursos WHERE nombre_recurso = '{_NOMBRE_RECURSO}';

            INSERT INTO modulo1.permisos (nombre, descripcion, id_rol, id_recurso, id_accion, es_activo)
            VALUES
                {valores}
            ON CONFLICT (id_rol, id_recurso, id_accion) DO NOTHING;
        END $$;
    """)


def downgrade() -> None:
    nombres_reversibles = ", ".join(
        f"'{nombre}'" for nombre, *_ in _PERMISOS if not nombre.startswith("admin_")
    )
    op.execute(f"""
        DO $$
        BEGIN
            PERFORM set_config('app.current_role', 'Administrador', true);
            PERFORM set_config('app.current_user_id', '1', true);
            DELETE FROM modulo1.permisos
             WHERE nombre IN ({nombres_reversibles})
               AND id_recurso = (SELECT id_recurso FROM modulo1.recursos
                                  WHERE nombre_recurso = '{_NOMBRE_RECURSO}');
        END $$;
    """)
    # Vuelve el criterio de versión anterior, pero sin su error de tipo: con
    # now()::time editar reglas fallaría otra vez tras un downgrade.
    op.execute("""
        CREATE OR REPLACE FUNCTION modulo3.fn_regla_alerta_versionamiento()
         RETURNS trigger
         LANGUAGE plpgsql
        AS $function$
        BEGIN
            IF OLD.umbral_min              IS DISTINCT FROM NEW.umbral_min              OR
               OLD.umbral_max              IS DISTINCT FROM NEW.umbral_max              OR
               OLD.umbrales_severdiad      IS DISTINCT FROM NEW.umbrales_severdiad      OR
               OLD.ventana_confirmacion_min IS DISTINCT FROM NEW.ventana_confirmacion_min OR
               OLD.es_regla_compuesta      IS DISTINCT FROM NEW.es_regla_compuesta
            THEN
                NEW.version_regla       := OLD.version_regla + 1;
                NEW.fecha_actualizacion := now();
            END IF;
            RETURN NEW;
        END;
        $function$
    """)
