# | Fecha      | Nombre   | Que se hizo                                                     |
# |------------|----------|-----------------------------------------------------------------|
# | 2026-11-02 | Arekkazu | RFC-021 RF-110 C21.1: aristas de transmisión entre áreas + RBAC 87 |
"""rfc021_rf110_aristas_transmision

Revision ID: 33ae7f41e560
Revises: c9a8cc1ef814
Create Date: 2026-11-02

RFC-021 (aprobado 2026-11-01), C21.1 mínimo: la topología sanitaria de la finca para que
RF-68 sume la exposición de un área a los focos de sus vecinas (C21.4).

- `modulo9.aristas_transmision`: una arista por (área origen, área destino, vía). Las 7 vías de
  RFC-021 §1.1; `intensidad` (0, 1] y `factor_barrera` [0, 1] dan el peso de la arista
  (w = intensidad × factor_barrera; el término de bioseguridad de RF-20 v2.2 llega con C21.2).
  `direccion` DIRIGIDA (origen → destino) o BIDIRECCIONAL. `origen_dato` DECLARADA / SUGERIDA /
  DERIVADA (RF-110). Única por (origen, destino, vía) mientras esté activa. Las dos áreas deben ser
  de la misma finca (lo valida el caso de uso; la FK no puede).
- RLS como `sensores_areas_asociadas`: por las áreas del usuario (`fn_infraestructuras_del_usuario`)
  más el usuario de servicio (el disparo de RF-68 corre como sistema).
- Recurso RBAC 87 `topologia_sanitaria`: Administrador y Veterinario C/R/U/D; Productor e Ingeniero R.

Fuera de alcance (RF-110 completo, pendiente de RF-110-especificacion.md): rutas de trabajo,
parámetros de la finca, aristas sugeridas/derivadas automáticas y versión de topología.
"""
from typing import Sequence, Union

from alembic import op


revision: str = '33ae7f41e560'
down_revision: Union[str, Sequence[str], None] = 'c9a8cc1ef814'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLA = 'modulo9.aristas_transmision'
_ENUM_VIA = 'modulo9.enum_arista_transmision_via'
_ENUM_DIRECCION = 'modulo9.enum_arista_transmision_direccion'
_ENUM_ORIGEN = 'modulo9.enum_arista_transmision_origen_dato'
_ID_RECURSO = 87
_NOMBRE_RECURSO = 'topologia_sanitaria'
_PERMISOS = (
    ('admin_crear_topologia_sanitaria', 'Administrador declara una arista de transmisión entre áreas (RF-110).', 1, 1),
    ('admin_leer_topologia_sanitaria', 'Administrador consulta la topología sanitaria de la finca (RF-110).', 1, 2),
    ('admin_actualizar_topologia_sanitaria', 'Administrador modifica una arista de transmisión (RF-110).', 1, 3),
    ('admin_desactivar_topologia_sanitaria', 'Administrador desactiva una arista de transmisión (RF-110).', 1, 4),
    ('vet_crear_topologia_sanitaria', 'Veterinario declara una arista de transmisión entre áreas (RF-110).', 3, 1),
    ('vet_leer_topologia_sanitaria', 'Veterinario consulta la topología sanitaria de la finca (RF-110).', 3, 2),
    ('vet_actualizar_topologia_sanitaria', 'Veterinario modifica una arista de transmisión (RF-110).', 3, 3),
    ('vet_desactivar_topologia_sanitaria', 'Veterinario desactiva una arista de transmisión (RF-110).', 3, 4),
    ('prod_leer_topologia_sanitaria', 'Productor consulta la topología sanitaria de la finca (RF-110).', 2, 2),
    ('ing_leer_topologia_sanitaria', 'Ingeniero de Campo consulta la topología sanitaria de la finca (RF-110).', 4, 2),
)
_ROLES_APP = "('sgpmp_app', 'rol_app', 'rol_dev', 'rol_impl', 'rol_migracion')"
_AREAS_DEL_USUARIO = (
    "id_infraestructura_origen IN (SELECT i.id_infraestructura FROM modulo9.fn_infraestructuras_del_usuario("
    "(SELECT modulo1.fn_id_usuario_actual())) i(id_infraestructura))"
)


def upgrade() -> None:
    op.execute(f"""
        CREATE TYPE {_ENUM_VIA} AS ENUM
            ('PROXIMIDAD', 'AIRE', 'AGUA', 'PERSONAL', 'FOMITES', 'ALIMENTO', 'MOVIMIENTO_ANIMAL')
    """)
    op.execute(f"CREATE TYPE {_ENUM_DIRECCION} AS ENUM ('DIRIGIDA', 'BIDIRECCIONAL')")
    op.execute(f"CREATE TYPE {_ENUM_ORIGEN} AS ENUM ('DECLARADA', 'SUGERIDA', 'DERIVADA')")
    op.execute(f"""
        CREATE TABLE {_TABLA} (
            id_arista_transmision SERIAL,
            id_infraestructura_origen INTEGER NOT NULL,
            id_infraestructura_destino INTEGER NOT NULL,
            via {_ENUM_VIA} NOT NULL,
            direccion {_ENUM_DIRECCION} NOT NULL DEFAULT 'DIRIGIDA',
            intensidad NUMERIC(4, 3) NOT NULL,
            factor_barrera NUMERIC(4, 3) NOT NULL DEFAULT 1,
            origen_dato {_ENUM_ORIGEN} NOT NULL DEFAULT 'DECLARADA',
            descripcion VARCHAR(200),
            es_activo BOOLEAN NOT NULL DEFAULT TRUE,
            id_usuario INTEGER,
            fecha_creacion TIMESTAMPTZ NOT NULL DEFAULT now(),
            fecha_actualizacion TIMESTAMPTZ,
            CONSTRAINT aristas_transmision_pkey PRIMARY KEY (id_arista_transmision),
            CONSTRAINT aristas_transmision_id_infraestructura_origen_fkey
                FOREIGN KEY (id_infraestructura_origen) REFERENCES modulo9.infraestructuras (id_infraestructura)
                ON DELETE RESTRICT ON UPDATE CASCADE,
            CONSTRAINT aristas_transmision_id_infraestructura_destino_fkey
                FOREIGN KEY (id_infraestructura_destino) REFERENCES modulo9.infraestructuras (id_infraestructura)
                ON DELETE RESTRICT ON UPDATE CASCADE,
            CONSTRAINT aristas_transmision_id_usuario_fkey
                FOREIGN KEY (id_usuario) REFERENCES modulo1.usuarios (id_usuario)
                ON DELETE RESTRICT ON UPDATE CASCADE,
            CONSTRAINT ck_arista_transmision_areas_distintas
                CHECK (id_infraestructura_origen <> id_infraestructura_destino),
            CONSTRAINT ck_arista_transmision_intensidad CHECK (intensidad > 0 AND intensidad <= 1),
            CONSTRAINT ck_arista_transmision_factor_barrera CHECK (factor_barrera >= 0 AND factor_barrera <= 1)
        )
    """)
    op.execute(f"""
        CREATE UNIQUE INDEX uq_arista_transmision_origen_destino_via
            ON {_TABLA} (id_infraestructura_origen, id_infraestructura_destino, via) WHERE es_activo
    """)
    op.execute(f"CREATE INDEX idx_arista_transmision_id_infraestructura_destino ON {_TABLA} (id_infraestructura_destino)")
    op.execute(f"""
        COMMENT ON TABLE {_TABLA} IS
        'RFC-021 RF-110: vías de transmisión entre áreas de una finca. Peso = intensidad x factor_barrera; '
        'RF-68 las usa para la exposición de un área a los focos de sus vecinas (C21.4).'
    """)

    op.execute(f"ALTER TABLE {_TABLA} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {_TABLA} FORCE ROW LEVEL SECURITY")
    op.execute(f"CREATE POLICY pol_arista_transmision_select ON {_TABLA} FOR SELECT USING ({_AREAS_DEL_USUARIO})")
    op.execute(f"CREATE POLICY pol_arista_transmision_insert ON {_TABLA} FOR INSERT WITH CHECK ({_AREAS_DEL_USUARIO})")
    op.execute(
        f"CREATE POLICY pol_arista_transmision_update ON {_TABLA} FOR UPDATE "
        f"USING ({_AREAS_DEL_USUARIO}) WITH CHECK ({_AREAS_DEL_USUARIO})"
    )
    op.execute(f"""
        CREATE POLICY pol_arista_transmision_servicio ON {_TABLA}
            USING ((SELECT modulo1.fn_es_usuario_servicio()))
            WITH CHECK ((SELECT modulo1.fn_es_usuario_servicio()))
    """)

    op.execute(f"""
        DO $$
        DECLARE r text;
        BEGIN
            FOR r IN SELECT rolname FROM pg_roles WHERE rolname IN {_ROLES_APP} LOOP
                EXECUTE format('GRANT SELECT, INSERT, UPDATE ON {_TABLA} TO %I', r);
                EXECUTE format('GRANT USAGE, SELECT ON SEQUENCE modulo9.aristas_transmision_id_arista_transmision_seq TO %I', r);
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
                SELECT id_recurso INTO v_id_recurso FROM modulo1.recursos WHERE nombre_recurso = '{_NOMBRE_RECURSO}';
            ELSIF EXISTS (SELECT 1 FROM modulo1.recursos WHERE id_recurso = {_ID_RECURSO}) THEN
                RAISE EXCEPTION 'RFC-021: id_recurso={_ID_RECURSO} ya está en uso por otro recurso; reasignar el id fijo de esta migración.';
            ELSE
                INSERT INTO modulo1.recursos (id_recurso, nombre_recurso, descripcion)
                VALUES ({_ID_RECURSO}, '{_NOMBRE_RECURSO}',
                        'Topología sanitaria de la finca: aristas de transmisión entre áreas (RF-110, RFC-021)');
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
    """Retira la tabla, los tipos y los permisos reversibles.

    ``trg_fn_proteger_permisos_admin_delete`` impide borrar los ``admin_*`` y, por su FK, el recurso:
    se conservan y un upgrade posterior los reutiliza (``ON CONFLICT DO NOTHING``).
    """
    nombres_reversibles = ", ".join(f"'{nombre}'" for nombre, *_ in _PERMISOS if not nombre.startswith("admin_"))
    op.execute(f"""
        DO $$
        BEGIN
            PERFORM set_config('app.current_role', 'Administrador', true);
            PERFORM set_config('app.current_user_id', '1', true);
            DELETE FROM modulo1.permisos WHERE id_recurso = {_ID_RECURSO} AND nombre IN ({nombres_reversibles});
        END
        $$;
    """)
    op.execute(f"DROP TABLE IF EXISTS {_TABLA}")
    op.execute(f"DROP TYPE IF EXISTS {_ENUM_ORIGEN}")
    op.execute(f"DROP TYPE IF EXISTS {_ENUM_DIRECCION}")
    op.execute(f"DROP TYPE IF EXISTS {_ENUM_VIA}")
