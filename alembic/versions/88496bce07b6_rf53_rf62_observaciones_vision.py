"""rf53_rf62_observaciones_vision

Revision ID: 88496bce07b6
Revises: d7a41c9e2b58
Create Date: 2026-10-08

RF-53/RF-56/RF-62 v2.0 (RFC-011), INC-M09-77-G137 (#513): M03 recibe las
observaciones de visión por área (vector de comportamiento) que la calibración
VISION de RF-24 (d7a41c9e2b58) necesita para calcular la línea base.

- `modulo3.observaciones_vision`: una fila por (cámara, instante de captura),
  con las dimensiones de calidad de RF-62 v2.0 (`cobertura_ventana`, tracks,
  `fps_efectivo`, `estado_calibracion`), el índice y su clasificación por la
  regla 80/40, y el vector en `json_vector`.
- Contrato PROVISIONAL: la ficha no fija el esquema del vector (ET-01) ni la
  fórmula del índice de calidad de visión. Los valores admitidos de
  `estado_calibracion` y la fórmula (pesos iguales) quedan sujetos a Análisis/AIoT.
- `apto_para_nic41` no se guarda: para visión es siempre false (RF-62 v2.0).

Sin RLS, igual que el resto de `modulo3` (la ingesta la hace el dispositivo con
su serial, no un usuario).
"""
from typing import Sequence, Union

from alembic import op


revision: str = '88496bce07b6'
down_revision: Union[str, Sequence[str], None] = 'd7a41c9e2b58'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Observación inmutable: solo INSERT y SELECT, para la app, los roles de
# desarrollo y AIoT (el Edge de visión). Solo los roles que existan.
_GRANTS = """
DO $$
DECLARE r text;
BEGIN
    FOR r IN SELECT rolname FROM pg_roles
             WHERE rolname IN ('sgpmp_app', 'rol_app', 'rol_dev', 'rol_impl', 'rol_migracion', 'rol_aiot') LOOP
        EXECUTE format('GRANT INSERT, SELECT ON modulo3.observaciones_vision TO %I', r);
        EXECUTE format(
            'GRANT USAGE, SELECT ON SEQUENCE modulo3.observaciones_vision_id_observacion_vision_seq TO %I', r
        );
    END LOOP;
END $$;
"""


def upgrade() -> None:
    op.execute("""
        CREATE TABLE modulo3.observaciones_vision (
            id_observacion_vision SERIAL,
            id_dispositivo_iot INTEGER NOT NULL,
            id_infraestructura INTEGER NOT NULL,
            fecha_observacion TIMESTAMPTZ NOT NULL,
            cobertura_ventana NUMERIC(5, 4) NOT NULL,
            cantidad_tracks INTEGER NOT NULL,
            cantidad_tracks_perdidos INTEGER NOT NULL,
            fps_efectivo NUMERIC(6, 2) NOT NULL,
            estado_calibracion VARCHAR(15) NOT NULL,
            json_vector JSONB NOT NULL,
            indice_calidad SMALLINT NOT NULL,
            clasificacion_calidad VARCHAR(20) NOT NULL,
            es_apto_para_ia BOOLEAN NOT NULL,
            fecha_creacion TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT observaciones_vision_pkey PRIMARY KEY (id_observacion_vision),
            CONSTRAINT observaciones_vision_id_dispositivo_iot_fkey
                FOREIGN KEY (id_dispositivo_iot) REFERENCES modulo9.dispositivos_iot (id_dispositivo_iot)
                ON DELETE RESTRICT ON UPDATE CASCADE,
            CONSTRAINT observaciones_vision_id_infraestructura_fkey
                FOREIGN KEY (id_infraestructura) REFERENCES modulo9.infraestructuras (id_infraestructura)
                ON DELETE RESTRICT ON UPDATE CASCADE,
            -- Un reenvío del buffer del Edge no duplica la observación. También
            -- sirve de índice para la consulta por cámara y ventana de RF-24.
            CONSTRAINT uq_observacion_vision_id_dispositivo_iot_fecha_observacion
                UNIQUE (id_dispositivo_iot, fecha_observacion),
            CONSTRAINT ck_observacion_vision_cobertura_ventana
                CHECK (cobertura_ventana BETWEEN 0 AND 1),
            CONSTRAINT ck_observacion_vision_cantidad_tracks
                CHECK (cantidad_tracks >= 0 AND cantidad_tracks_perdidos >= 0),
            CONSTRAINT ck_observacion_vision_fps_efectivo CHECK (fps_efectivo >= 0),
            CONSTRAINT ck_observacion_vision_estado_calibracion
                CHECK (estado_calibracion IN ('CALIBRADA', 'DEGRADADA', 'SIN_DETECCION')),
            CONSTRAINT ck_observacion_vision_indice_calidad CHECK (indice_calidad BETWEEN 0 AND 100),
            CONSTRAINT ck_observacion_vision_clasificacion_calidad
                CHECK (clasificacion_calidad IN ('APTO', 'APTO_CON_RESERVA', 'NO_APTO'))
        )
    """)
    op.execute(_GRANTS)


def downgrade() -> None:
    op.execute("DROP TABLE modulo3.observaciones_vision")
