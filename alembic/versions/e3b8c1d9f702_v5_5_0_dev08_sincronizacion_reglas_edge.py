"""v5.5.0_dev08_sincronizacion_reglas_edge

Revision ID: e3b8c1d9f702
Revises: 3a9d5e7c1b24
Create Date: 2026-10-19

DEV-08 (RF-55 Restricción 4, RF-57 E14/E15): las reglas compuestas de
`modulo3.reglas_alertas` (THI, síndrome respiratorio, riesgo hídrico...) se
propagan a los Gateway Edge por el broker con `origen: "regla_compuesta"`
(BRK-05: `tipo_comando = REGLA_COMPUESTA`, confirmación `ACK_REGLA`), igual
que los umbrales de RF-17. Esta migración agrega lo que la propagación necesita
en BD:

- `modulo3.enum_sincronizacion_regla_edge_estado_sincronizacion`: los tres
  veredictos del broker (`APLICADA`, `PENDIENTE`, `NO_CONF`).
- `modulo3.sincronizaciones_reglas_edge`: el estado vigente de cada regla en
  cada Gateway Edge, una fila por (regla, Gateway)
  (`uq_sincronizacion_regla_edge_id_regla_alertas_id_dispositivo_iot`). Cada
  intento la actualiza; `version_regla` dice qué versión se intentó y
  `fecha_aplicacion` cuándo el Edge confirmó por última vez.
- `modulo3.fn_gateways_edge_por_regla_alerta(id_regla_alertas)`: a qué Gateway
  Edge le corresponde la regla. Áreas activas de la finca de la regla (si tiene
  `id_finca`) y de su especie (si tiene `id_especie`, por `id_especie` del área
  o por activos biológicos vivos, el mismo criterio que
  `modulo9.fn_seriales_gateway_edge_por_especie`, a3c9e5d17b42); una regla sin
  finca ni especie es global y va a todas las áreas activas. De ellas, los
  Gateway Edge activos instalados en el área o que atienden un dispositivo
  activo del área. `SECURITY DEFINER` como la de umbrales, pero eso ya no
  evita la RLS: `infraestructuras`, `dispositivos_iot` y `activos_biologicos`
  tienen FORCE ROW LEVEL SECURITY y `sgpmp_owner` no tiene BYPASSRLS. Por eso
  el backend la llama como el usuario de servicio (`como_sistema`).
- Recurso RBAC 65 `sincronizacion_reglas_edge` con Leer (2) y Ejecutar (5)
  para Administrador e Ingeniero de Campo, los mismos roles que gestionan la
  infraestructura IoT (recursos 35 y 36). El downgrade no puede borrar los
  `admin_*` ni el recurso (`trg_fn_proteger_permisos_admin_delete`): quedan,
  y un upgrade posterior los reutiliza (`ON CONFLICT DO NOTHING`).

Sin RLS en la tabla nueva, como el resto de `modulo3`.
"""
from typing import Sequence, Union

from alembic import op


revision: str = 'e3b8c1d9f702'
down_revision: Union[str, Sequence[str], None] = '3a9d5e7c1b24'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_ID_RECURSO = 65
_NOMBRE_RECURSO = 'sincronizacion_reglas_edge'
_FUNCION = 'modulo3.fn_gateways_edge_por_regla_alerta(integer)'
_ENUM = 'modulo3.enum_sincronizacion_regla_edge_estado_sincronizacion'
_PERMISOS = (
    ('admin_leer_sincronizacion_regla_edge', 'Administrador consulta el estado de una regla compuesta en cada Gateway Edge (RF-55).', 1, 2),
    ('admin_ejecutar_sincronizacion_regla_edge', 'Administrador propaga una regla compuesta a los Gateway Edge (RF-55).', 1, 5),
    ('ing_leer_sincronizacion_regla_edge', 'Ingeniero de Campo consulta el estado de una regla compuesta en cada Gateway Edge (RF-55).', 4, 2),
    ('ing_ejecutar_sincronizacion_regla_edge', 'Ingeniero de Campo propaga una regla compuesta a los Gateway Edge (RF-55).', 4, 5),
)

# Mismos roles de BD que reciben permisos en las demás migraciones recientes;
# solo los que existan (TEST no tiene los rol_*).
_ROLES_APP = "('sgpmp_app', 'rol_app', 'rol_dev', 'rol_impl', 'rol_migracion')"


def upgrade() -> None:
    op.execute(f"CREATE TYPE {_ENUM} AS ENUM ('APLICADA', 'PENDIENTE', 'NO_CONF')")

    op.execute(f"""
        CREATE TABLE modulo3.sincronizaciones_reglas_edge (
            id_sincronizacion_regla_edge SERIAL,
            id_regla_alertas INTEGER NOT NULL,
            id_dispositivo_iot INTEGER NOT NULL,
            version_regla INTEGER NOT NULL,
            estado_sincronizacion {_ENUM} NOT NULL DEFAULT 'PENDIENTE',
            mensaje TEXT,
            intentos_sincronizacion INTEGER NOT NULL DEFAULT 1,
            fecha_ultimo_intento TIMESTAMPTZ NOT NULL DEFAULT now(),
            fecha_aplicacion TIMESTAMPTZ,
            id_usuario INTEGER,
            CONSTRAINT sincronizaciones_reglas_edge_pkey PRIMARY KEY (id_sincronizacion_regla_edge),
            CONSTRAINT uq_sincronizacion_regla_edge_id_regla_alertas_id_dispositivo_iot
                UNIQUE (id_regla_alertas, id_dispositivo_iot),
            CONSTRAINT sincronizaciones_reglas_edge_id_regla_alertas_fkey
                FOREIGN KEY (id_regla_alertas) REFERENCES modulo3.reglas_alertas (id_regla_alertas)
                ON DELETE CASCADE ON UPDATE CASCADE,
            CONSTRAINT sincronizaciones_reglas_edge_id_dispositivo_iot_fkey
                FOREIGN KEY (id_dispositivo_iot) REFERENCES modulo9.dispositivos_iot (id_dispositivo_iot)
                ON DELETE RESTRICT ON UPDATE CASCADE,
            CONSTRAINT sincronizaciones_reglas_edge_id_usuario_fkey
                FOREIGN KEY (id_usuario) REFERENCES modulo1.usuarios (id_usuario)
                ON DELETE RESTRICT ON UPDATE CASCADE,
            CONSTRAINT ck_sincronizacion_regla_edge_version_regla CHECK (version_regla >= 1),
            CONSTRAINT ck_sincronizacion_regla_edge_intentos_sincronizacion
                CHECK (intentos_sincronizacion >= 1)
        )
    """)
    op.execute("""
        COMMENT ON TABLE modulo3.sincronizaciones_reglas_edge IS
        'DEV-08 (RF-55/RF-57): estado vigente de cada regla compuesta en cada Gateway Edge. '
        'Una fila por (regla, Gateway); cada propagación la actualiza con el veredicto del broker.'
    """)

    op.execute("""
        CREATE OR REPLACE FUNCTION modulo3.fn_gateways_edge_por_regla_alerta(p_id_regla_alertas integer)
        RETURNS TABLE (id_dispositivo_iot integer, serial varchar)
        LANGUAGE sql
        STABLE
        SECURITY DEFINER
        SET search_path = pg_catalog, modulo3, modulo9
        AS $$
            WITH regla AS (
                SELECT r.id_finca, r.id_especie
                FROM modulo3.reglas_alertas r
                WHERE r.id_regla_alertas = p_id_regla_alertas
            ),
            areas_de_la_regla AS (
                SELECT i.id_infraestructura
                FROM regla r
                JOIN modulo9.infraestructuras i
                  ON i.es_activo
                 AND (r.id_finca IS NULL OR i.id_finca = r.id_finca)
                WHERE r.id_especie IS NULL
                   OR i.id_especie = r.id_especie
                   OR EXISTS (
                        SELECT 1
                        FROM modulo2.activos_biologicos a
                        JOIN modulo2.estados_activos_biologicos ea
                          ON ea.id_estado_activo_biologico = a.id_estado
                        WHERE a.id_infraestructura = i.id_infraestructura
                          AND a.id_especie = r.id_especie
                          AND ea.nombre::text <> ALL (ARRAY['INACTIVO', 'CERRADO', 'BAJA'])
                   )
            )
            SELECT DISTINCT g.id_dispositivo_iot, g.serial
            FROM areas_de_la_regla ar
            JOIN modulo9.dispositivos_iot d
              ON d.id_infraestructura = ar.id_infraestructura
             AND d.es_activo
            JOIN modulo9.dispositivos_iot g
              ON g.id_dispositivo_iot = COALESCE(d.id_dispositivo_gateway, d.id_dispositivo_iot)
             AND g.es_activo
            JOIN modulo9.tipos_dispositivo_iot t
              ON t.id_tipo_dispositivo = g.id_tipo_dispositivo
             AND t.nombre = 'GATEWAY_EDGE'
            ORDER BY g.serial;
        $$;
    """)

    op.execute(f"""
        DO $$
        DECLARE r text;
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'sgpmp_owner')
               AND pg_has_role(current_user, 'sgpmp_owner', 'MEMBER') THEN
                ALTER FUNCTION {_FUNCION} OWNER TO sgpmp_owner;
            END IF;
            REVOKE ALL ON FUNCTION {_FUNCION} FROM PUBLIC;
            FOR r IN SELECT rolname FROM pg_roles WHERE rolname IN {_ROLES_APP} LOOP
                EXECUTE format('GRANT EXECUTE ON FUNCTION {_FUNCION} TO %I', r);
                EXECUTE format('GRANT INSERT, SELECT, UPDATE ON modulo3.sincronizaciones_reglas_edge TO %I', r);
                EXECUTE format(
                    'GRANT USAGE, SELECT ON SEQUENCE '
                    'modulo3.sincronizaciones_reglas_edge_id_sincronizacion_regla_edge_seq TO %I', r
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
            IF EXISTS (SELECT 1 FROM modulo1.recursos WHERE nombre_recurso = '{_NOMBRE_RECURSO}') THEN
                SELECT id_recurso INTO v_id_recurso
                FROM modulo1.recursos WHERE nombre_recurso = '{_NOMBRE_RECURSO}';
            ELSIF EXISTS (SELECT 1 FROM modulo1.recursos WHERE id_recurso = {_ID_RECURSO}) THEN
                RAISE EXCEPTION 'DEV-08: id_recurso={_ID_RECURSO} ya está en uso por otro recurso; reasignar el id fijo de esta migración.';
            ELSE
                INSERT INTO modulo1.recursos (id_recurso, nombre_recurso, descripcion)
                VALUES (
                    {_ID_RECURSO},
                    '{_NOMBRE_RECURSO}',
                    'Propagación de reglas compuestas de alerta a los Gateway Edge (RF-55/RF-57)'
                );
                v_id_recurso := {_ID_RECURSO};
            END IF;

            INSERT INTO modulo1.permisos (nombre, descripcion, id_rol, id_recurso, id_accion, es_activo)
            VALUES
                {valores}
            ON CONFLICT (id_rol, id_recurso, id_accion) DO NOTHING;
        END
        $$;
    """)


def downgrade() -> None:
    """Retira la tabla, la función y los permisos reversibles.

    ``trg_fn_proteger_permisos_admin_delete`` impide eliminar los permisos
    ``admin_*`` y, por su FK, tampoco el recurso 65. Se conservan, igual que en
    96621b225009: sin el router que los consulta no habilitan nada.
    """
    nombres_reversibles = ", ".join(
        f"'{nombre}'" for nombre, *_ in _PERMISOS if not nombre.startswith("admin_")
    )
    op.execute(f"""
        DO $$
        BEGIN
            PERFORM set_config('app.current_role', 'Administrador', true);
            PERFORM set_config('app.current_user_id', '1', true);
            DELETE FROM modulo1.permisos
             WHERE id_recurso = {_ID_RECURSO} AND nombre IN ({nombres_reversibles});
        END
        $$;
    """)
    op.execute(f"DROP FUNCTION IF EXISTS {_FUNCION}")
    op.execute("DROP TABLE IF EXISTS modulo3.sincronizaciones_reglas_edge")
    op.execute(f"DROP TYPE IF EXISTS {_ENUM}")
