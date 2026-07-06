from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.telemetry.domain.entities.telemetria import DispositivoInfo
from src.telemetry.domain.repositories.dispositivo_port import DispositivoPort


class DispositivoM09Adapter(DispositivoPort):

    def __init__(self, db: Session) -> None:
        self.db = db

    def obtener_dispositivo_activo(
        self,
        device_id: int,
        sensor_id: int,
        access_key: str,
    ) -> Optional[DispositivoInfo]:
        # El access_key se valida contra el serial del dispositivo (RF-02 / M09)
        row = self.db.execute(
            text(
                'SELECT d.id_dispositivo_iot, d.es_activo AS activo_disp, '
                '       d.id_infraestructura, '
                '       s.id_sensores, s.es_activo AS activo_sensor '
                'FROM modulo9.dispositivos_iot d '
                'JOIN modulo9.sensores s ON s.id_dispositivo_iot = d.id_dispositivo_iot '
                'WHERE d.id_dispositivo_iot = :device_id '
                '  AND s.id_sensores = :sensor_id '
                '  AND d.serial = :access_key'
            ),
            {'device_id': device_id, 'sensor_id': sensor_id, 'access_key': access_key},
        ).fetchone()

        if row is None:
            return None

        return DispositivoInfo(
            id_dispositivo_iot=row.id_dispositivo_iot,
            id_sensor=row.id_sensores,
            es_activo_dispositivo=row.activo_disp,
            es_activo_sensor=row.activo_sensor,
            id_infraestructura=row.id_infraestructura,
        )
