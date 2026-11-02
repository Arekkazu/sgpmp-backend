# | Fecha      | Nombre   | Que se hizo                                                     |
# |------------|----------|-----------------------------------------------------------------|
# | 2026-11-02 | Arekkazu | RF-66: cámaras de visión de un área por SQL (con la RLS del usuario) |
# | 2026-11-02 | Arekkazu | RF-66 POBLACIONAL: inventario del área y conteos de la cámara      |
from __future__ import annotations

from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.prediction.domain.repositories.camaras_area_port import CamarasAreaPort

_SQL = text("""
    SELECT d.id_dispositivo_iot FROM modulo9.dispositivos_iot d
    JOIN modulo9.tipos_dispositivo_iot t ON t.id_tipo_dispositivo = d.id_tipo_dispositivo
    WHERE d.id_infraestructura = :id_area AND t.categoria::text = 'CAMARA'
    ORDER BY d.id_dispositivo_iot
""")


_SQL_INVENTARIO = text("""
    SELECT sum(d.cantidad_actual) FROM modulo2.activos_biologicos ab
    JOIN modulo2.detalles_activos_biologicos_poblacionales d ON d.id_activo_biologico = ab.id_activo_biologico
    JOIN modulo2.estados_activos_biologicos ea ON ea.id_estado_activo_biologico = ab.id_estado
    WHERE ab.id_infraestructura = :id_area AND ab.tipo::text = 'POBLACIONAL'
      AND ea.nombre::text <> ALL (ARRAY['INACTIVO', 'CERRADO', 'BAJA'])
""")

_SQL_CONTEOS = text("""
    SELECT n_individuos_observados FROM modulo3.observaciones_vision
    WHERE id_infraestructura = :id_area AND es_apto_para_ia AND n_individuos_observados IS NOT NULL
    ORDER BY fecha_observacion DESC LIMIT :limite
""")


class CamarasAreaM09Adapter(CamarasAreaPort):

    def __init__(self, db: Session) -> None:
        self._db = db

    def camaras(self, id_area: int) -> list[int]:
        return list(self._db.execute(_SQL, {"id_area": id_area}).scalars())

    def cantidad_registrada(self, id_area: int) -> Optional[int]:
        total = self._db.execute(_SQL_INVENTARIO, {"id_area": id_area}).scalar()
        return int(total) if total is not None else None

    def conteos_recientes(self, id_area: int, limite: int) -> list[int]:
        return list(self._db.execute(_SQL_CONTEOS, {"id_area": id_area, "limite": limite}).scalars())
