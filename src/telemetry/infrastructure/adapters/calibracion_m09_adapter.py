from decimal import Decimal
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.telemetry.domain.entities.telemetria import ParametrosCalibacion
from src.telemetry.domain.repositories.calibracion_port import CalibracionPort


class CalibracionM09Adapter(CalibracionPort):
    """Adaptador de calibración contra modulo9.calibraciones (RF-24).

    Desde RF-24 (#1635) la tabla guarda ganancia y offset_calibracion reales
    (modelo lineal valor_ajustado = ganancia * crudo + offset), así que el
    adaptador ya no aproxima.
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
                'SELECT ganancia, offset_calibracion, fecha_calibracion '
                'FROM modulo9.calibraciones '
                'WHERE id_sensor = :sensor_id AND id_dispositivo_iot = :device_id '
                'ORDER BY fecha_calibracion DESC LIMIT 1'
            ),
            {'sensor_id': sensor_id, 'device_id': id_dispositivo_iot},
        ).fetchone()

        if row is None:
            return None

        return ParametrosCalibacion(
            ganancia=Decimal(str(row.ganancia)),
            offset=Decimal(str(row.offset_calibracion)),
            version=str(row.fecha_calibracion.date()),
        )
