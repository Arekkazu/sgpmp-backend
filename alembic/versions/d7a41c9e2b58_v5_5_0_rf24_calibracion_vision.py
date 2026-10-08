"""v5.5.0_rf24_calibracion_vision

Revision ID: d7a41c9e2b58
Revises: a3c9e5d17b42
Create Date: 2026-10-07

RF-24 v2.0 (RFC-011), INC-M09-78-G138 (#514): modalidad VISION de la
calibración — línea base de comportamiento por (área, especie).

- `modulo9.calibraciones_vision`: historial de cada intento de cálculo. Guarda
  también los FALLIDOS y NO CONVERGIDOS con la etapa y el motivo, porque la
  ficha pide registrar "la calibración como FALLIDA con el motivo de la etapa".
  `modulo9.calibraciones` no sirve: exige `id_sensor` y `id_dispositivo_iot`.
- `modulo9.lineas_base_vision`: la línea base vigente, una por (área, especie).
  Un cálculo exitoso la reemplaza; uno fallido no la toca.
- `modulo1.tipos_eventos` 30 `CALIBRACION_VISION`: auditoría RF-10 del cálculo
  exitoso. Los rechazos siguen usando el 29 `CALIBRACION_RECHAZADA`.

RLS igual que `modulo9.calibraciones` (5243bbbb28de): lectura y escritura solo
para Administrador e Ingeniero de Campo; sin DELETE. El historial no tiene
política de UPDATE (es inmutable); la línea base vigente sí, porque se reemplaza.
"""
from typing import Sequence, Union

from alembic import op


revision: str = 'd7a41c9e2b58'
down_revision: Union[str, Sequence[str], None] = 'a3c9e5d17b42'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ID_TIPO_EVENTO = 30
NOMBRE_TIPO_EVENTO = "CALIBRACION_VISION"
ACCION_TIPO_EVENTO = "Calculo de linea base por vision"  # varchar(50)

_ROLES_RLS = "('Administrador', 'Ingeniero de Campo')"

# Mismos roles de BD que reciben permisos en las demás migraciones recientes;
# solo los que existan (TEST no tiene los rol_*).
_GRANTS = """
DO $$
DECLARE r text; t text;
BEGIN
    FOREACH t IN ARRAY ARRAY['calibraciones_vision', 'lineas_base_vision'] LOOP
        FOR r IN SELECT rolname FROM pg_roles
                 WHERE rolname IN ('sgpmp_app', 'rol_app', 'rol_dev', 'rol_impl', 'rol_migracion') LOOP
            EXECUTE format('GRANT INSERT, SELECT, UPDATE ON modulo9.%I TO %I', t, r);
        END LOOP;
    END LOOP;
    FOR r IN SELECT rolname FROM pg_roles
             WHERE rolname IN ('sgpmp_app', 'rol_app', 'rol_dev', 'rol_impl', 'rol_migracion') LOOP
        EXECUTE format(
            'GRANT USAGE, SELECT ON SEQUENCE modulo9.calibraciones_vision_id_calibracion_vision_seq TO %I', r
        );
    END LOOP;
END $$;
"""


def upgrade() -> None:
    op.execute("""
        CREATE TABLE modulo9.calibraciones_vision (
            id_calibracion_vision SERIAL,
            id_infraestructura INTEGER NOT NULL,
            id_especie INTEGER NOT NULL,
            origen_disparo VARCHAR(10) NOT NULL,
            id_usuario INTEGER,
            json_ventana_observacion JSONB NOT NULL,
            fecha_calibracion TIMESTAMPTZ NOT NULL,
            estado VARCHAR(15) NOT NULL,
            etapa_fallo VARCHAR(15),
            motivo TEXT,
            json_linea_base JSONB,
            n_observaciones INTEGER NOT NULL DEFAULT 0,
            n_observaciones_validas INTEGER NOT NULL DEFAULT 0,
            iteraciones INTEGER,
            observaciones TEXT,
            fecha_creacion TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT calibraciones_vision_pkey PRIMARY KEY (id_calibracion_vision),
            CONSTRAINT calibraciones_vision_id_infraestructura_fkey
                FOREIGN KEY (id_infraestructura) REFERENCES modulo9.infraestructuras (id_infraestructura)
                ON DELETE RESTRICT ON UPDATE CASCADE,
            CONSTRAINT calibraciones_vision_id_especie_fkey
                FOREIGN KEY (id_especie) REFERENCES modulo9.especies (id_especie)
                ON DELETE RESTRICT ON UPDATE CASCADE,
            CONSTRAINT ck_calibracion_vision_origen_disparo
                CHECK (origen_disparo IN ('MANUAL', 'AUTOMATICO')),
            -- Disparo manual: siempre hay usuario. Automático (Módulo 02): nulo.
            CONSTRAINT ck_calibracion_vision_usuario_manual
                CHECK (origen_disparo = 'AUTOMATICO' OR id_usuario IS NOT NULL),
            CONSTRAINT ck_calibracion_vision_estado
                CHECK (estado IN ('EXITOSA', 'FALLIDA', 'NO_CONVERGIDA')),
            CONSTRAINT ck_calibracion_vision_etapa_fallo
                CHECK (etapa_fallo IS NULL OR etapa_fallo IN ('FILTRADO', 'RECORTE', 'REFINAMIENTO')),
            -- Exitosa: con línea base y sin etapa de fallo. Si no, al revés.
            CONSTRAINT ck_calibracion_vision_resultado_coherente CHECK (
                (estado = 'EXITOSA' AND json_linea_base IS NOT NULL AND etapa_fallo IS NULL)
                OR (estado <> 'EXITOSA' AND json_linea_base IS NULL AND etapa_fallo IS NOT NULL)
            )
        )
    """)
    op.execute("""
        CREATE INDEX idx_calibracion_vision_id_infraestructura_fecha_calibracion
            ON modulo9.calibraciones_vision (id_infraestructura, fecha_calibracion DESC)
    """)

    op.execute("""
        CREATE TABLE modulo9.lineas_base_vision (
            id_infraestructura INTEGER NOT NULL,
            id_especie INTEGER NOT NULL,
            id_calibracion_vision INTEGER NOT NULL,
            json_valor JSONB NOT NULL,
            fecha_publicacion TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT lineas_base_vision_pkey PRIMARY KEY (id_infraestructura, id_especie),
            CONSTRAINT lineas_base_vision_id_infraestructura_fkey
                FOREIGN KEY (id_infraestructura) REFERENCES modulo9.infraestructuras (id_infraestructura)
                ON DELETE RESTRICT ON UPDATE CASCADE,
            CONSTRAINT lineas_base_vision_id_especie_fkey
                FOREIGN KEY (id_especie) REFERENCES modulo9.especies (id_especie)
                ON DELETE RESTRICT ON UPDATE CASCADE,
            CONSTRAINT lineas_base_vision_id_calibracion_vision_fkey
                FOREIGN KEY (id_calibracion_vision)
                REFERENCES modulo9.calibraciones_vision (id_calibracion_vision)
                ON DELETE RESTRICT ON UPDATE CASCADE
        )
    """)

    for tabla in ("calibraciones_vision", "lineas_base_vision"):
        op.execute(f"ALTER TABLE modulo9.{tabla} ENABLE ROW LEVEL SECURITY")
        op.execute(f"""
            CREATE POLICY pol_{tabla}_select ON modulo9.{tabla}
              FOR SELECT USING (modulo1.fn_rol_actual() IN {_ROLES_RLS})
        """)
    op.execute(f"""
        CREATE POLICY pol_calibraciones_vision_insert ON modulo9.calibraciones_vision
          FOR INSERT WITH CHECK (
            modulo1.fn_rol_actual() IN {_ROLES_RLS}
            AND id_usuario = modulo1.fn_id_usuario_actual()
          )
    """)
    # Sin política de UPDATE en el historial: cada intento es un registro inmutable.
    op.execute(f"""
        CREATE POLICY pol_lineas_base_vision_insert ON modulo9.lineas_base_vision
          FOR INSERT WITH CHECK (modulo1.fn_rol_actual() IN {_ROLES_RLS})
    """)
    op.execute(f"""
        CREATE POLICY pol_lineas_base_vision_update ON modulo9.lineas_base_vision
          FOR UPDATE
          USING (modulo1.fn_rol_actual() IN {_ROLES_RLS})
          WITH CHECK (modulo1.fn_rol_actual() IN {_ROLES_RLS})
    """)
    op.execute(_GRANTS)

    op.execute(
        f"""
        INSERT INTO modulo1.tipos_eventos (id_tipo_evento, nombre, accion)
        SELECT {ID_TIPO_EVENTO}, '{NOMBRE_TIPO_EVENTO}', '{ACCION_TIPO_EVENTO}'
        WHERE NOT EXISTS (
            SELECT 1 FROM modulo1.tipos_eventos
            WHERE id_tipo_evento = {ID_TIPO_EVENTO} OR nombre = '{NOMBRE_TIPO_EVENTO}'
        )
        """
    )
    op.execute(
        "SELECT setval('modulo1.tipos_evento_id_tipo_evento_seq', "
        "(SELECT max(id_tipo_evento) FROM modulo1.tipos_eventos))"
    )


def downgrade() -> None:
    op.execute(
        f"""
        DELETE FROM modulo1.tipos_eventos
        WHERE id_tipo_evento = {ID_TIPO_EVENTO}
          AND NOT EXISTS (SELECT 1 FROM modulo1.eventos WHERE tipo_evento = {ID_TIPO_EVENTO})
        """
    )
    op.execute("DROP TABLE modulo9.lineas_base_vision")
    op.execute("DROP TABLE modulo9.calibraciones_vision")
