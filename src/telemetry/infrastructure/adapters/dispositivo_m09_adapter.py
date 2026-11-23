# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-25 | Arekkazu | INC-M03-134-G192 RF-62: cámara por id para su fps configurado |
# | 2026-10-29 | Arekkazu | INC-M03-134-G03 RF-60 CA-7/RF-53 E1: mantenimiento desde cualquier estado y lecturas rechazadas |
# | 2026-11-22 | Arekkazu | DOCS-pdoc: docstrings de módulo, clase y métodos |
"""Adaptador de dispositivos y cámaras contra el módulo de configuración (M09).

Implementa :class:`DispositivoPort` con consultas SQL directas: valida que el
dispositivo y el sensor estén activos, resuelve heartbeats y devuelve los datos
de cámara (incluido su FPS nominal) para telemetría y visión.
"""
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.telemetry.domain.entities.telemetria import DispositivoInfo
from src.telemetry.domain.repositories.dispositivo_port import CamaraInfo, DispositivoHeartbeatInfo, DispositivoPort


class DispositivoM09Adapter(DispositivoPort):
    """Adaptador SQLAlchemy/SQL de dispositivos IoT y cámaras de M09."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def obtener_dispositivo_activo(
        self,
        device_id: int,
        sensor_id: int,
        serial: str,
    ) -> Optional[DispositivoInfo]:
        """Devuelve el dispositivo y sensor activos que coinciden con el serial.

        Args:
            device_id: Identificador del dispositivo autenticado.
            sensor_id: Sensor que reporta la lectura.
            serial: Serial autenticado por el broker MQTT.

        Returns:
            La información del dispositivo, o ``None`` si no coincide.
        """
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
        """Valida un heartbeat por dispositivo y serial.

        Indica además si el dispositivo está en mantenimiento, para decidir si
        el heartbeat se rechaza o se registra.
        """
        row = self.db.execute(
            text(
                'SELECT d.id_dispositivo_iot, d.es_activo, d.id_infraestructura, '
                "       COALESCE(e.estado_actual = 'EN_MANTENIMIENTO', false) AS en_mantenimiento "
                'FROM modulo9.dispositivos_iot d '
                'LEFT JOIN modulo3.estados_dispositivos_iot e ON e.id_dispositivo_iot = d.id_dispositivo_iot '
                'WHERE d.id_dispositivo_iot = :device_id AND d.serial = :serial'
            ),
            {'device_id': device_id, 'serial': serial},
        ).fetchone()

        if row is None:
            return None

        return DispositivoHeartbeatInfo(
            id_dispositivo_iot=row.id_dispositivo_iot,
            id_infraestructura=row.id_infraestructura,
            es_activo=row.es_activo,
            en_mantenimiento=row.en_mantenimiento,
        )

    def obtener_por_serial(self, serial: str) -> Optional[DispositivoHeartbeatInfo]:
        """Busca un dispositivo por su serial para el flujo de heartbeat."""
        row = self.db.execute(
            text(
                'SELECT id_dispositivo_iot, es_activo, id_infraestructura '
                'FROM modulo9.dispositivos_iot WHERE serial = :serial'
            ),
            {'serial': serial},
        ).fetchone()
        if row is None:
            return None
        return DispositivoHeartbeatInfo(
            id_dispositivo_iot=row.id_dispositivo_iot,
            id_infraestructura=row.id_infraestructura,
            es_activo=row.es_activo,
        )

    def obtener_camara(self, device_id: int, serial: str) -> Optional[CamaraInfo]:
        """Devuelve la cámara por dispositivo y serial autenticados."""
        return self._camara(serial, device_id)

    def obtener_camara_por_serial(self, serial: str) -> Optional[CamaraInfo]:
        """Devuelve la cámara por su serial."""
        return self._camara(serial)

    def obtener_camara_por_id(self, id_dispositivo_iot: int) -> Optional[CamaraInfo]:
        """Devuelve la cámara por el id del dispositivo IoT."""
        return self._camara(None, id_dispositivo_iot)

    def _camara(self, serial: Optional[str], device_id: Optional[int] = None) -> Optional[CamaraInfo]:
        row = self.db.execute(
            text(
                'SELECT d.id_dispositivo_iot, d.id_infraestructura, d.es_activo, d.fps, t.categoria '
                'FROM modulo9.dispositivos_iot d '
                'JOIN modulo9.tipos_dispositivo_iot t ON t.id_tipo_dispositivo = d.id_tipo_dispositivo '
                'WHERE (:serial IS NULL OR d.serial = :serial) '
                'AND (:device_id IS NULL OR d.id_dispositivo_iot = :device_id)'
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
