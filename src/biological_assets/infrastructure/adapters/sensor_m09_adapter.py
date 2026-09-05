from __future__ import annotations

from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.biological_assets.domain.repositories.sensor_consulta_port import SensorConsulta, SensorConsultaPort


class SensorM09Adapter(SensorConsultaPort):
    """Consulta modulo9 para obtener datos del sensor, su dispositivo y su área asociada activa."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def obtener_sensor_con_contexto(self, sensor_id: int) -> Optional[SensorConsulta]:
        row = self.db.execute(
            text(
                'SELECT '
                '  s.id_sensores, s.nombre, s.es_activo, s.categoria, '
                '  s.id_dispositivo_iot, '
                '  d.es_activo AS dispositivo_es_activo, '
                '  d.id_infraestructura AS id_infraestructura_dispositivo, '
                '  saa.id_infraestructura AS id_infraestructura_area '
                'FROM modulo9.sensores s '
                'JOIN modulo9.dispositivos_iot d ON d.id_dispositivo_iot = s.id_dispositivo_iot '
                'LEFT JOIN modulo9.sensores_areas_asociadas saa '
                '  ON saa.id_sensor = s.id_sensores AND saa.tiene_estado = true '
                'WHERE s.id_sensores = :sensor_id'
            ),
            {'sensor_id': sensor_id},
        ).fetchone()

        if row is None:
            return None

        return SensorConsulta(
            id_sensor=row.id_sensores,
            nombre=row.nombre,
            es_activo=row.es_activo,
            id_dispositivo_iot=row.id_dispositivo_iot,
            dispositivo_es_activo=row.dispositivo_es_activo,
            id_infraestructura_dispositivo=row.id_infraestructura_dispositivo,
            categoria=row.categoria,
            id_infraestructura_area=row.id_infraestructura_area,
        )
