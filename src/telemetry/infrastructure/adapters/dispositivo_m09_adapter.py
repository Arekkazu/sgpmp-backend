from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.telemetry.domain.entities.telemetria import DispositivoInfo
from src.telemetry.domain.repositories.dispositivo_port import CamaraInfo, DispositivoHeartbeatInfo, DispositivoPort


class DispositivoM09Adapter(DispositivoPort):

    def __init__(self, db: Session) -> None:
        self.db = db

    def obtener_dispositivo_activo(
        self,
        device_id: int,
        sensor_id: int,
        serial: str,
    ) -> Optional[DispositivoInfo]:
        # El serial lo autenticó el broker por MQTT (D3): aquí solo ata device_id a ese nodo.
        row = self.db.execute(
            text(
                'SELECT d.id_dispositivo_iot, d.es_activo AS activo_disp, '
                '       d.id_infraestructura, '
                '       s.id_sensores, s.es_activo AS activo_sensor '
                'FROM modulo9.dispositivos_iot d '
                'JOIN modulo9.sensores s ON s.id_dispositivo_iot = d.id_dispositivo_iot '
                'WHERE d.id_dispositivo_iot = :device_id '
                '  AND s.id_sensores = :sensor_id '
                '  AND d.serial = :serial'
            ),
            {'device_id': device_id, 'sensor_id': sensor_id, 'serial': serial},
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

    def validar_dispositivo_heartbeat(
        self,
        device_id: int,
        serial: str,
    ) -> Optional[DispositivoHeartbeatInfo]:
        row = self.db.execute(
            text(
                'SELECT id_dispositivo_iot, es_activo, id_infraestructura '
                'FROM modulo9.dispositivos_iot '
                'WHERE id_dispositivo_iot = :device_id AND serial = :serial'
            ),
            {'device_id': device_id, 'serial': serial},
        ).fetchone()

        if row is None:
            return None

        return DispositivoHeartbeatInfo(
            id_dispositivo_iot=row.id_dispositivo_iot,
            id_infraestructura=row.id_infraestructura,
            es_activo=row.es_activo,
        )

    def obtener_camara(self, device_id: int, serial: str) -> Optional[CamaraInfo]:
        return self._camara(serial, device_id)

    def obtener_camara_por_serial(self, serial: str) -> Optional[CamaraInfo]:
        return self._camara(serial)

    def _camara(self, serial: str, device_id: Optional[int] = None) -> Optional[CamaraInfo]:
        row = self.db.execute(
            text(
                'SELECT d.id_dispositivo_iot, d.id_infraestructura, d.es_activo, d.fps, t.categoria '
                'FROM modulo9.dispositivos_iot d '
                'JOIN modulo9.tipos_dispositivo_iot t ON t.id_tipo_dispositivo = d.id_tipo_dispositivo '
                'WHERE d.serial = :serial AND (:device_id IS NULL OR d.id_dispositivo_iot = :device_id)'
            ),
            {'device_id': device_id, 'serial': serial},
        ).fetchone()
        if row is None:
            return None
        return CamaraInfo(
            id_dispositivo_iot=row.id_dispositivo_iot,
            id_infraestructura=row.id_infraestructura,
            es_activo=row.es_activo,
            es_camara=row.categoria == 'CAMARA',
            fps_nominal=row.fps,
        )
