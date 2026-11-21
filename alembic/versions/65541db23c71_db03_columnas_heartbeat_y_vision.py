"""DB-03 (RF-56/RF-60): columnas nuevas de heartbeats y observaciones_vision

Revision ID: 65541db23c71
Revises: 3a9d5e7c1b24
Create Date: 2026-10-19 15:00:00

Primera parte del lote de esquema de la Ventana 2 AIoT
(`AIOT-DEV-03_Acuerdo_Consolidado_Desarrollo_AIoT.md`, D4 y D11). Solo agrega
columnas nullable: las filas existentes y el firmware viejo siguen igual.

- `modulo3.heartbeats` (D11): `json_sensores_operativos`
  (`[{"sensor": "<id>", "operativo": true}]`) y `temperatura_dispositivo` en
  °C. El broker (BRK-07) ya las detecta por `information_schema` y las llena
  solo si existen.
- `modulo3.observaciones_vision` (D4): `fecha_inicio_ventana` y
  `json_version_cascada` (`{"detector": "", "seguimiento": "", "metricas": "",
  "anomalias": ""}`).

El acuerdo las nombra `sensores_operativos`, `ventana_inicio` y
`version_cascada`. Aquí van con los prefijos `json_` y `fecha_` de
`anotaciones/convencion_nomenclatura_bd.md`. El sobre MQTT/HTTP conserva los
nombres del acuerdo y el DTO hace la traducción.

Sin CHECK sobre la forma del JSON: un `None` de SQLAlchemy llega como
`'null'::jsonb` y un CHECK de `jsonb_typeof` tumbaría el heartbeat completo.
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '65541db23c71'
down_revision: Union[str, Sequence[str], None] = '3a9d5e7c1b24'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE modulo3.heartbeats
            ADD COLUMN json_sensores_operativos JSONB,
            ADD COLUMN temperatura_dispositivo  NUMERIC(5,2);

        COMMENT ON COLUMN modulo3.heartbeats.json_sensores_operativos IS
            'RF-60 / D11: estado por sensor reportado por el nodo, [{"sensor": "<id>", "operativo": bool}]. NULL si el firmware no lo envía.';
        COMMENT ON COLUMN modulo3.heartbeats.temperatura_dispositivo IS
            'RF-60 / D11: temperatura interna del nodo en °C. NULL si el firmware no la envía.';

        ALTER TABLE modulo3.observaciones_vision
            ADD COLUMN fecha_inicio_ventana TIMESTAMPTZ,
            ADD COLUMN json_version_cascada JSONB;

        COMMENT ON COLUMN modulo3.observaciones_vision.fecha_inicio_ventana IS
            'RF-56 / D4: inicio de la ventana de observación (ventana_inicio del sobre de visión).';
        COMMENT ON COLUMN modulo3.observaciones_vision.json_version_cascada IS
            'RF-56 / D4: versión de cada componente de la cascada Edge, {"detector", "seguimiento", "metricas", "anomalias"}.';
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE modulo3.observaciones_vision
            DROP COLUMN json_version_cascada,
            DROP COLUMN fecha_inicio_ventana;

        ALTER TABLE modulo3.heartbeats
            DROP COLUMN temperatura_dispositivo,
            DROP COLUMN json_sensores_operativos;
        """
    )
