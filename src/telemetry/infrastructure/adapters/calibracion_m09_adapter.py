from decimal import Decimal
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.telemetry.domain.entities.telemetria import ParametrosCalibacion
from src.telemetry.domain.repositories.calibracion_port import CalibracionPort


class CalibracionM09Adapter(CalibracionPort):
    """Adaptador de calibración contra modulo9.calibraciones (RF-24).

    Nota: La tabla modulo9.calibraciones solo tiene valor_referencia (sin ganancia/offset).
    Se usa ganancia=1.0 y offset=valor_referencia como aproximación hasta que M09
    implemente parámetros de calibración completos.
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    def obtener_parametros(
        self,
        sensor_id: int,
        id_dispositivo_iot: int,
    ) -> Optional[ParametrosCalibacion]:
        # Obtiene la calibración más reciente del sensor
        row = self.db.execute(
            text(
                'SELECT valor_referencia, fecha_calibracion '
                'FROM modulo9.calibraciones '
                'WHERE id_sensor = :sensor_id AND id_dispositivo_iot = :device_id '
                'ORDER BY fecha_calibracion DESC LIMIT 1'
            ),
            {'sensor_id': sensor_id, 'device_id': id_dispositivo_iot},
        ).fetchone()

        if row is None:
            return None

        # Simplificación: ganancia=1.0, offset=valor_referencia (ajuste de cero)
        return ParametrosCalibacion(
            ganancia=Decimal('1.0'),
            offset=Decimal(str(row.valor_referencia)),
            version=str(row.fecha_calibracion.date()),
        )
