# | Fecha      | Nombre   | Que se hizo                                                     |
# |------------|----------|-----------------------------------------------------------------|
# | 2026-11-02 | Arekkazu | RF-66 POBLACIONAL: observación, lotes y línea base por SQL       |
"""Lecturas de M02/M03/M09 para RF-66 POBLACIONAL (sin escribir nada)."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.prediction.domain.repositories.observacion_poblacional_port import (
    LotePoblacional,
    ObservacionPoblacional,
    ObservacionPoblacionalPort,
)
from src.shared.tipo_modelo import es_poblacional

_SQL_OBSERVACION = text("""
    SELECT id_observacion_vision, id_infraestructura, json_vector, es_apto_para_ia, es_confianza_baja,
           fecha_inicio_ventana, fecha_observacion
    FROM modulo3.observaciones_vision WHERE id_observacion_vision = :id
""")

_SQL_LOTES = text("""
    SELECT ab.id_activo_biologico, ab.id_especie, i.tipo_modelo_asignado::text
    FROM modulo2.activos_biologicos ab
    JOIN modulo9.infraestructuras i ON i.id_infraestructura = ab.id_infraestructura
    JOIN modulo2.estados_activos_biologicos ea ON ea.id_estado_activo_biologico = ab.id_estado
    WHERE ab.id_infraestructura = :id_area AND ab.tipo::text = 'POBLACIONAL'
      AND ea.nombre::text <> ALL (ARRAY['INACTIVO', 'CERRADO', 'BAJA'])
    ORDER BY ab.id_activo_biologico
""")

_SQL_LINEA_BASE = text("""
    SELECT json_valor -> 'valores' FROM modulo9.lineas_base_vision
    WHERE id_infraestructura = :id_area AND id_especie = :id_especie
""")

_SQL_YA_EVALUADO = text("""
    SELECT EXISTS (SELECT 1 FROM modulo4.resultados_inferencia
                   WHERE id_activo_biologico = :id_activo AND tipo_modelo::text = :tipo AND fecha_fin_ventana = :fin)
""")


class ObservacionPoblacionalM03M09Adapter(ObservacionPoblacionalPort):

    def __init__(self, db: Session) -> None:
        self._db = db

    def obtener(self, id_observacion: int) -> Optional[ObservacionPoblacional]:
        fila = self._db.execute(_SQL_OBSERVACION, {"id": id_observacion}).first()
        if fila is None:
            return None
        return ObservacionPoblacional(fila[0], fila[1], dict(fila[2] or {}), bool(fila[3]), bool(fila[4]), fila[5], fila[6])

    def lotes(self, id_area: int) -> list[LotePoblacional]:
        filas = self._db.execute(_SQL_LOTES, {"id_area": id_area}).all()
        return [LotePoblacional(f[0], f[1], f[2]) for f in filas if es_poblacional(f[2])]

    def linea_base(self, id_area: int, id_especie: int) -> Optional[dict]:
        valores = self._db.execute(_SQL_LINEA_BASE, {"id_area": id_area, "id_especie": id_especie}).scalar()
        return dict(valores) if valores else None

    def ya_evaluado(self, id_activo: int, tipo_modelo: str, fecha_fin: datetime) -> bool:
        return bool(self._db.execute(
            _SQL_YA_EVALUADO, {"id_activo": id_activo, "tipo": tipo_modelo, "fin": fecha_fin},
        ).scalar())
