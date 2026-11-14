# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-02 | Arekkazu | AJF-14 RF-71: tabla de procesos de reentrenamiento con RLS por finca del animal |
"""rf71: procesos de reentrenamiento por animal (AJF-14)

Revision ID: 21fe51f2aea1
Revises: 9b7d64203f48
Create Date: 2026-11-02

Requiere la autorización de SamuelPR21 (DBA) antes de desplegar.

Hasta ahora ``POST /prediccion/modelos/reentrenamiento/solicitudes`` solo dejaba el
evento en la bitácora: no había dónde seguir un reentrenamiento. Esta tabla guarda
cada proceso (uno por animal, RFC-010) desde que se solicita hasta que el motor de IA
lo termina, con la fase en curso (1–7), el latido y la versión que produjo.

- DB-1 ``modulo4.procesos_reentrenamiento`` + tres ENUM nuevos. Índice único parcial:
  un solo proceso PENDIENTE o EN_CURSO por animal.
- DB-2 no hace falta: ``REENTRENAMIENTO_INICIADO``, ``_COMPLETADO`` y ``_FALLIDO`` ya
  existen en ``modulo4.enum_tipo_evento_auditoria_m04`` (baseline).
- DB-3 grants para los roles de la app y RLS forzada: el usuario ve los procesos de los
  animales de sus infraestructuras e inserta solo con permiso E de ``version_modelo``
  y a su nombre; el motor (usuario de servicio) toma y actualiza procesos.
Nomenclatura: ``anotaciones/convencion_nomenclatura_bd.md``.
"""
from typing import Sequence, Union

from alembic import op


revision: str = '21fe51f2aea1'
down_revision: Union[str, Sequence[str], None] = '9b7d64203f48'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLA = "modulo4.procesos_reentrenamiento"
_ROLES_APP = "('sgpmp_app', 'rol_app', 'rol_dev', 'rol_impl', 'rol_migracion')"
_UID = "(SELECT modulo1.fn_id_usuario_actual())"
_SERVICIO = "(SELECT modulo1.fn_es_usuario_servicio())"
_ACTIVO_VISIBLE = (
    "EXISTS (SELECT 1 FROM modulo2.activos_biologicos ab "
    "WHERE ab.id_activo_biologico = procesos_reentrenamiento.id_activo_biologico "
    "AND ab.id_infraestructura IN (SELECT i.id_infraestructura "
    f"FROM modulo9.fn_infraestructuras_del_usuario({_UID}) i))"
)


def upgrade() -> None:
    op.execute(f"""
        CREATE TYPE modulo4.enum_proceso_reentrenamiento_disparador AS ENUM ('MANUAL', 'PROGRAMADO', 'DEGRADACION');
        CREATE TYPE modulo4.enum_proceso_reentrenamiento_modo_generacion AS ENUM ('REENTRENAMIENTO', 'CALIBRACION_EN_SITIO');
        CREATE TYPE modulo4.enum_proceso_reentrenamiento_estado AS ENUM (
            'PENDIENTE', 'EN_CURSO', 'COMPLETADO', 'FALLIDO', 'INTERRUMPIDO', 'CANCELADO');

        CREATE TABLE {_TABLA} (
            id_proceso_reentrenamiento UUID NOT NULL DEFAULT gen_random_uuid(),
            tipo_modelo modulo4.enum_tipo_modelo NOT NULL,
            id_activo_biologico INTEGER NOT NULL,
            disparador modulo4.enum_proceso_reentrenamiento_disparador NOT NULL DEFAULT 'MANUAL',
            modo_generacion modulo4.enum_proceso_reentrenamiento_modo_generacion NOT NULL DEFAULT 'REENTRENAMIENTO',
            estado modulo4.enum_proceso_reentrenamiento_estado NOT NULL DEFAULT 'PENDIENTE',
            fase_actual SMALLINT NOT NULL DEFAULT 0,
            porcentaje_progreso SMALLINT NOT NULL DEFAULT 0,
            json_fases JSONB NOT NULL DEFAULT '[]'::jsonb,
            porcentaje_cpu NUMERIC(5, 2),
            memoria_ram_mb INTEGER,
            codigo_error VARCHAR(60),
            json_motivos JSONB,
            id_version_modelo_referencia INTEGER,
            id_version_modelo_resultante INTEGER,
            id_usuario_solicitante INTEGER,
            fecha_solicitud TIMESTAMPTZ NOT NULL DEFAULT now(),
            fecha_inicio TIMESTAMPTZ,
            fecha_fin TIMESTAMPTZ,
            fecha_ultimo_latido TIMESTAMPTZ,
            CONSTRAINT procesos_reentrenamiento_pkey PRIMARY KEY (id_proceso_reentrenamiento),
            CONSTRAINT procesos_reentrenamiento_id_activo_biologico_fkey
                FOREIGN KEY (id_activo_biologico) REFERENCES modulo2.activos_biologicos (id_activo_biologico)
                ON DELETE RESTRICT ON UPDATE CASCADE,
            CONSTRAINT procesos_reentrenamiento_id_version_modelo_referencia_fkey
                FOREIGN KEY (id_version_modelo_referencia) REFERENCES modulo4.versiones_modelos (id_version_modelo)
                ON DELETE RESTRICT ON UPDATE CASCADE,
            CONSTRAINT procesos_reentrenamiento_id_version_modelo_resultante_fkey
                FOREIGN KEY (id_version_modelo_resultante) REFERENCES modulo4.versiones_modelos (id_version_modelo)
                ON DELETE RESTRICT ON UPDATE CASCADE,
            CONSTRAINT procesos_reentrenamiento_id_usuario_solicitante_fkey
                FOREIGN KEY (id_usuario_solicitante) REFERENCES modulo1.usuarios (id_usuario)
                ON DELETE RESTRICT ON UPDATE CASCADE,
            CONSTRAINT ck_proceso_reentrenamiento_fase_actual CHECK (fase_actual BETWEEN 0 AND 7),
            CONSTRAINT ck_proceso_reentrenamiento_porcentaje_progreso CHECK (porcentaje_progreso BETWEEN 0 AND 100),
            CONSTRAINT ck_proceso_reentrenamiento_porcentaje_cpu CHECK (porcentaje_cpu IS NULL OR porcentaje_cpu BETWEEN 0 AND 100),
            CONSTRAINT ck_proceso_reentrenamiento_memoria_ram_mb CHECK (memoria_ram_mb IS NULL OR memoria_ram_mb >= 0),
            CONSTRAINT ck_proceso_reentrenamiento_completado_con_version
                CHECK (estado <> 'COMPLETADO' OR id_version_modelo_resultante IS NOT NULL),
            CONSTRAINT ck_proceso_reentrenamiento_fallido_con_codigo
                CHECK (estado <> 'FALLIDO' OR codigo_error IS NOT NULL),
            CONSTRAINT ck_proceso_reentrenamiento_fechas
                CHECK (fecha_fin IS NULL OR fecha_inicio IS NULL OR fecha_fin >= fecha_inicio)
        );

        -- Un solo proceso abierto por animal (BE-1 responde 409 antes; esto lo garantiza en BD).
        CREATE UNIQUE INDEX uq_proceso_reentrenamiento_id_activo_biologico
            ON {_TABLA} (id_activo_biologico) WHERE estado IN ('PENDIENTE', 'EN_CURSO');
        -- La cola del motor y el listado de la pantalla (estado + antigüedad).
        CREATE INDEX idx_proceso_reentrenamiento_estado_fecha_solicitud
            ON {_TABLA} (estado, fecha_solicitud);

        COMMENT ON TABLE {_TABLA} IS
            'RF-71 (AJF-14): proceso de reentrenamiento del modelo individual de un animal, de la solicitud '
            'al registro de la versión (RF-69). Lo toma y actualiza el motor de IA con el usuario de servicio.';
        COMMENT ON COLUMN {_TABLA}.json_fases IS
            'Lista de fases 1-7: [{{"fase": n, "nombre": ..., "fecha_inicio": ..., "fecha_fin": ..., "resultado": ...}}].';

        ALTER TABLE {_TABLA} ENABLE ROW LEVEL SECURITY;
        ALTER TABLE {_TABLA} FORCE ROW LEVEL SECURITY;

        CREATE POLICY pol_proceso_reentrenamiento_select ON {_TABLA}
            FOR SELECT USING ({_ACTIVO_VISIBLE});
        CREATE POLICY pol_proceso_reentrenamiento_insert ON {_TABLA}
            FOR INSERT WITH CHECK (
                (SELECT modulo1.fn_tiene_permiso('version_modelo'::text, 'E'::text))
                AND id_usuario_solicitante = {_UID}
                AND {_ACTIVO_VISIBLE}
            );
        CREATE POLICY pol_proceso_reentrenamiento_servicio ON {_TABLA}
            FOR ALL USING ({_SERVICIO}) WITH CHECK ({_SERVICIO});

        DO $$
        DECLARE r text;
        BEGIN
            FOR r IN SELECT rolname FROM pg_roles WHERE rolname IN {_ROLES_APP} LOOP
                EXECUTE format('GRANT SELECT, INSERT, UPDATE ON {_TABLA} TO %I', r);
            END LOOP;
        END $$;
    """)


def downgrade() -> None:
    op.execute(f"""
        DROP TABLE {_TABLA};
        DROP TYPE modulo4.enum_proceso_reentrenamiento_estado;
        DROP TYPE modulo4.enum_proceso_reentrenamiento_modo_generacion;
        DROP TYPE modulo4.enum_proceso_reentrenamiento_disparador;
    """)
