# | Fecha      | Nombre       | Que se hizo                                                              |
# |------------|--------------|--------------------------------------------------------------------------|
# | 2026-11-10 | destroyerban | INC-M06-336-G36 RF-86: solicitudes de correctivo de variaciones           |
"""v5.5.0 inc_m06_336: solicitudes de correctivo de variaciones de valor razonable

Revision ID: e6a2c48f9d13
Revises: b7e2d94c1a68
Create Date: 2026-11-10

Requiere la autorización de SamuelPR21 (DBA) antes de desplegar.

INC-M06-336-G36 (#1023). RF-86 restricción 5 y CA-13: una variación errónea se corrige con un
registro correctivo de monto opuesto que referencia el original y exige la aprobación del Contador.
``variaciones_valor_razonable`` ya tiene ``id_variacion_corregida`` y es append-only
(``tgr_m06_10_inmutabilidad_variaciones``), así que el correctivo no puede nacer pendiente y luego
aprobarse: la solicitud pendiente va en una tabla propia y la variación correctiva se inserta al
aprobarla.

- ``modulo6.solicitudes_correctivos_variaciones``: una solicitud por intento, con estado
  PENDIENTE / APROBADA / RECHAZADA, solicitante y quien la resuelve (doble control: distintos).
  Una sola solicitud PENDIENTE o APROBADA por variación (``uq_solicitud_correctivo_variacion_vigente``).
  ``trg_antes_modificar_solicitud_correctivo_variacion``: no se elimina; resuelta, es inmutable.
- Los nombres de dos FK pasan de 63 caracteres y PostgreSQL los trunca, como ya pasa con las de
  ``ampliaciones_ventana_retroalimentacion`` (RF-72, 6bd01d026ac4).
- Tres tipos de evento de auditoría para la solicitud, la aprobación y el rechazo.

downgrade: borra la tabla. Los valores agregados al ENUM se dejan (PostgreSQL no permite quitarlos
sin recrear el tipo; no rompen nada si no se usan).
"""
from typing import Sequence, Union

from alembic import op

revision: str = 'e6a2c48f9d13'
down_revision: Union[str, Sequence[str], None] = 'b7e2d94c1a68'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_ROLES_APP = "('sgpmp_app', 'rol_app', 'rol_dev', 'rol_impl', 'rol_migracion')"
_TIPOS_EVENTO = ('CORRECTIVO_VARIACION_SOLICITADO', 'CORRECTIVO_VARIACION_APROBADO', 'CORRECTIVO_VARIACION_RECHAZADO')


def upgrade() -> None:
    for tipo in _TIPOS_EVENTO:
        op.execute(f"ALTER TYPE modulo6.enum_auditoria_financiera_tipo_evento ADD VALUE IF NOT EXISTS '{tipo}'")

    op.execute("""
        CREATE TABLE modulo6.solicitudes_correctivos_variaciones (
            id_solicitud_correctivo_variacion serial NOT NULL,
            id_variacion_valor_razonable integer NOT NULL,
            motivo text NOT NULL,
            estado varchar(10) NOT NULL DEFAULT 'PENDIENTE',
            id_usuario_solicitante integer NOT NULL,
            fecha_solicitud timestamptz NOT NULL DEFAULT now(),
            id_usuario_resolutor integer,
            fecha_resolucion timestamptz,
            motivo_rechazo text,
            id_variacion_correctiva integer,
            CONSTRAINT solicitudes_correctivos_variaciones_pkey PRIMARY KEY (id_solicitud_correctivo_variacion),
            CONSTRAINT ck_solicitud_correctivo_variacion_estado CHECK (estado IN ('PENDIENTE', 'APROBADA', 'RECHAZADA')),
            CONSTRAINT ck_solicitud_correctivo_variacion_motivo CHECK (char_length(trim(motivo)) >= 20),
            CONSTRAINT ck_solicitud_correctivo_variacion_resolucion CHECK (
                (estado = 'PENDIENTE' AND id_usuario_resolutor IS NULL AND fecha_resolucion IS NULL
                    AND id_variacion_correctiva IS NULL AND motivo_rechazo IS NULL)
                OR (estado = 'APROBADA' AND id_usuario_resolutor IS NOT NULL AND fecha_resolucion IS NOT NULL
                    AND id_variacion_correctiva IS NOT NULL AND motivo_rechazo IS NULL)
                OR (estado = 'RECHAZADA' AND id_usuario_resolutor IS NOT NULL AND fecha_resolucion IS NOT NULL
                    AND id_variacion_correctiva IS NULL AND char_length(trim(motivo_rechazo)) >= 20)),
            CONSTRAINT ck_solicitud_correctivo_variacion_doble_control CHECK (
                id_usuario_resolutor IS NULL OR id_usuario_resolutor <> id_usuario_solicitante),
            CONSTRAINT solicitudes_correctivos_variaciones_id_variacion_valor_razonable_fkey
                FOREIGN KEY (id_variacion_valor_razonable)
                REFERENCES modulo6.variaciones_valor_razonable (id_variacion_valor_razonable)
                ON DELETE RESTRICT ON UPDATE CASCADE,
            CONSTRAINT solicitudes_correctivos_variaciones_id_variacion_correctiva_fkey
                FOREIGN KEY (id_variacion_correctiva)
                REFERENCES modulo6.variaciones_valor_razonable (id_variacion_valor_razonable)
                ON DELETE RESTRICT ON UPDATE CASCADE,
            CONSTRAINT solicitudes_correctivos_variaciones_id_usuario_solicitante_fkey FOREIGN KEY (id_usuario_solicitante)
                REFERENCES modulo1.usuarios (id_usuario) ON DELETE RESTRICT ON UPDATE CASCADE,
            CONSTRAINT solicitudes_correctivos_variaciones_id_usuario_resolutor_fkey FOREIGN KEY (id_usuario_resolutor)
                REFERENCES modulo1.usuarios (id_usuario) ON DELETE RESTRICT ON UPDATE CASCADE
        )
    """)
    op.execute("""
        CREATE UNIQUE INDEX uq_solicitud_correctivo_variacion_vigente
            ON modulo6.solicitudes_correctivos_variaciones (id_variacion_valor_razonable)
            WHERE estado IN ('PENDIENTE', 'APROBADA')
    """)
    op.execute("CREATE INDEX idx_solicitud_correctivo_variacion_estado "
               "ON modulo6.solicitudes_correctivos_variaciones (estado)")
    op.execute("""
        COMMENT ON TABLE modulo6.solicitudes_correctivos_variaciones IS
        'Solicitudes de correctivo de una variación de valor razonable (RF-86 restricción 5, CA-13). La variación es '
        'append-only: al aprobarse la solicitud se inserta la variación correctiva (monto opuesto, '
        'id_variacion_corregida) y sus líneas inversas. Doble control: quien resuelve es distinto de quien solicita.'
    """)
    # Mismo criterio que TGR-M06-01 (reconocimiento) y la línea de asiento: la solicitud resuelta es rastro
    # de auditoría. Solo se permite la resolución de una PENDIENTE, sin tocar lo que el solicitante registró.
    op.execute("""
        CREATE OR REPLACE FUNCTION modulo6.fn_proteger_solicitud_correctivo_variacion()
        RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE
            v_mutables text[] := ARRAY['estado', 'id_usuario_resolutor', 'fecha_resolucion', 'motivo_rechazo',
                                       'id_variacion_correctiva'];
        BEGIN
            IF TG_OP = 'DELETE' THEN
                RAISE EXCEPTION 'La solicitud de correctivo id=% no puede eliminarse (RF-86 CA-13).',
                    OLD.id_solicitud_correctivo_variacion USING ERRCODE = 'P0001';
            END IF;
            IF OLD.estado <> 'PENDIENTE' OR (to_jsonb(NEW) - v_mutables) <> (to_jsonb(OLD) - v_mutables) THEN
                RAISE EXCEPTION 'La solicitud de correctivo id=% tiene estado % y es inmutable (RF-86 CA-13).',
                    OLD.id_solicitud_correctivo_variacion, OLD.estado USING ERRCODE = 'P0001';
            END IF;
            RETURN NEW;
        END;
        $$
    """)
    op.execute("""
        CREATE TRIGGER trg_antes_modificar_solicitud_correctivo_variacion
            BEFORE UPDATE OR DELETE ON modulo6.solicitudes_correctivos_variaciones
            FOR EACH ROW EXECUTE FUNCTION modulo6.fn_proteger_solicitud_correctivo_variacion()
    """)
    op.execute(f"""
        DO $$
        DECLARE r text;
        BEGIN
            FOR r IN SELECT rolname FROM pg_roles WHERE rolname IN {_ROLES_APP} LOOP
                EXECUTE format('GRANT SELECT, INSERT, UPDATE ON modulo6.solicitudes_correctivos_variaciones TO %I', r);
                EXECUTE format('GRANT USAGE, SELECT ON SEQUENCE %s TO %I',
                    pg_get_serial_sequence('modulo6.solicitudes_correctivos_variaciones',
                                           'id_solicitud_correctivo_variacion'), r);
            END LOOP;
        END $$;
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS modulo6.solicitudes_correctivos_variaciones")
    op.execute("DROP FUNCTION IF EXISTS modulo6.fn_proteger_solicitud_correctivo_variacion()")
