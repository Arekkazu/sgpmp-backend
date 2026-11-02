# | Fecha      | Nombre   | Que se hizo                                                     |
# |------------|----------|-----------------------------------------------------------------|
# | 2026-11-02 | Arekkazu | RF-66: cámaras de visión de un área por SQL (con la RLS del usuario) |
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.prediction.domain.repositories.camaras_area_port import CamarasAreaPort

_SQL = text("""
    SELECT d.id_dispositivo_iot FROM modulo9.dispositivos_iot d
    JOIN modulo9.tipos_dispositivo_iot t ON t.id_tipo_dispositivo = d.id_tipo_dispositivo
    WHERE d.id_infraestructura = :id_area AND t.categoria::text = 'CAMARA'
    ORDER BY d.id_dispositivo_iot
""")


class CamarasAreaM09Adapter(CamarasAreaPort):

    def __init__(self, db: Session) -> None:
        self._db = db

    def camaras(self, id_area: int) -> list[int]:
        return list(self._db.execute(_SQL, {"id_area": id_area}).scalars())
