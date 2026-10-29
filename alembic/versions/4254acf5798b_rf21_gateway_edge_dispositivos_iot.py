"""rf21_gateway_edge_dispositivos_iot

Revision ID: 4254acf5798b
Revises: 315eaa6c5dc1
Create Date: 2026-10-04 02:43:54

RF-21 / RF-23 (TC-M09-250/251), aprobado por el DBA: relacion N:1 entre
dispositivos IoT y su Gateway Edge. El Edge (la computadora de borde del sitio,
hoy una Raspberry) es un dispositivo mas de modulo9.dispositivos_iot con el
tipo nuevo GATEWAY_EDGE; cada dispositivo que atiende apunta a el con
id_dispositivo_gateway (autorreferencia, opcional). Es el "Gateway IoT" que
M03 describe: recibe la radio de varios nodos, la pasa a IP y habla MQTT con el
broker, que deriva de esta columna los topics que su credencial puede usar.

Las reglas que la BD no puede expresar por si sola (apuntar solo a un
GATEWAY_EDGE activo de la misma finca, un Edge no tiene Edge) las valida el
caso de uso de RF-21. Los rangos del tipo son amplios a proposito: un Edge no
captura datos y RF-23 no le aplica.
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '4254acf5798b'
down_revision: Union[str, Sequence[str], None] = '315eaa6c5dc1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE modulo9.dispositivos_iot
            ADD COLUMN id_dispositivo_gateway INTEGER NULL
                REFERENCES modulo9.dispositivos_iot (id_dispositivo_iot),
            ADD CONSTRAINT ck_dispositivo_iot_no_es_su_propio_gateway
                CHECK (id_dispositivo_gateway <> id_dispositivo_iot)
        """
    )
    op.execute(
        "CREATE INDEX ix_dispositivos_iot_id_dispositivo_gateway "
        "ON modulo9.dispositivos_iot (id_dispositivo_gateway)"
    )
    op.execute(
        "COMMENT ON COLUMN modulo9.dispositivos_iot.id_dispositivo_gateway IS "
        "'Gateway Edge (dispositivo tipo GATEWAY_EDGE) que atiende a este dispositivo. "
        "NULL: es un Edge o todavia no tiene uno asignado (RF-21).'"
    )
    op.execute(
        """
        INSERT INTO modulo9.tipos_dispositivo_iot (
            nombre, frecuencia_captura_min, frecuencia_captura_max,
            intervalo_transmision_min, intervalo_transmision_max, fecha_creacion
        )
        SELECT 'GATEWAY_EDGE', 1, 1440, 1, 1440, now()
        WHERE NOT EXISTS (
            SELECT 1 FROM modulo9.tipos_dispositivo_iot WHERE nombre = 'GATEWAY_EDGE'
        )
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM modulo9.dispositivos_iot d
                JOIN modulo9.tipos_dispositivo_iot t USING (id_tipo_dispositivo)
                WHERE t.nombre = 'GATEWAY_EDGE'
            ) THEN
                RAISE EXCEPTION 'RF21: hay dispositivos GATEWAY_EDGE registrados; reasignarlos antes de revertir';
            END IF;
        END
        $$
        """
    )
    op.execute("DELETE FROM modulo9.tipos_dispositivo_iot WHERE nombre = 'GATEWAY_EDGE'")
    op.execute("DROP INDEX modulo9.ix_dispositivos_iot_id_dispositivo_gateway")
    op.execute(
        """
        ALTER TABLE modulo9.dispositivos_iot
            DROP CONSTRAINT ck_dispositivo_iot_no_es_su_propio_gateway,
            DROP COLUMN id_dispositivo_gateway
        """
    )
