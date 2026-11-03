# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-03 | Arekkazu | RF-62: listado de observaciones de visión evaluadas (el panel mostraba datos de ejemplo) |
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.shared.db_error_translator import raise_from_db_error
from src.telemetry.domain.entities.calidad_vision_listado import ObservacionVisionEvaluada
from src.telemetry.domain.repositories.calidad_vision_repository import CalidadVisionRepository

# Literales fijos; los filtros van como parámetros. clasificacion_calidad y estado_calibracion son
# varchar con CHECK (no ENUM); la RLS (pol_observaciones_vision_select) limita a las áreas del usuario.
_SQL_LISTAR = text("""
    SELECT o.id_observacion_vision, o.id_dispositivo_iot, d.serial AS serial_camara, o.id_infraestructura,
           i.nombre AS nombre_area, o.fecha_inicio_ventana, o.fecha_observacion, o.n_individuos_observados,
           o.cobertura_ventana, o.fps_efectivo, o.cantidad_tracks_perdidos, o.estado_calibracion,
           o.indice_calidad_vision, o.clasificacion_calidad, o.es_apto_para_ia, o.es_confianza_baja,
           o.json_flags_detectados AS flags_detectados, o.fecha_evaluacion_calidad,
           count(*) OVER () AS total
    FROM modulo3.observaciones_vision o
    LEFT JOIN modulo9.dispositivos_iot d ON d.id_dispositivo_iot = o.id_dispositivo_iot
    LEFT JOIN modulo9.infraestructuras i ON i.id_infraestructura = o.id_infraestructura
    WHERE o.fecha_observacion >= :desde AND o.fecha_observacion <= :hasta
      AND (CAST(:fincas AS int[]) IS NULL OR i.id_finca = ANY(CAST(:fincas AS int[])))
      AND (CAST(:dispositivo AS int) IS NULL OR o.id_dispositivo_iot = CAST(:dispositivo AS int))
      AND (CAST(:clase AS text) IS NULL
           OR (CAST(:clase AS text) = 'SIN_EVALUAR' AND o.fecha_evaluacion_calidad IS NULL)
           OR o.clasificacion_calidad::text = CAST(:clase AS text))
    ORDER BY o.fecha_observacion DESC, o.id_observacion_vision DESC
    LIMIT :limite OFFSET :desplazamiento
""")

_COLUMNAS = tuple(ObservacionVisionEvaluada.__dataclass_fields__)


class SqlAlchemyCalidadVisionRepository(CalidadVisionRepository):

    def __init__(self, db: Session) -> None:
        self._db = db

    def listar(self, filtros):
        try:
            filas = self._db.execute(_SQL_LISTAR, {
                "desde": filtros.desde, "hasta": filtros.hasta, "fincas": filtros.ids_fincas,
                "dispositivo": filtros.id_dispositivo_iot, "clase": filtros.clasificacion,
                "limite": filtros.por_pagina, "desplazamiento": (filtros.pagina - 1) * filtros.por_pagina,
            }).mappings().all()
        except Exception as exc:
            raise_from_db_error(exc)
        total = int(filas[0]["total"]) if filas else 0
        return [ObservacionVisionEvaluada(**{c: f[c] for c in _COLUMNAS}) for f in filas], total
