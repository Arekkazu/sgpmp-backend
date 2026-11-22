# | Fecha      | Nombre   | Que se hizo                                                     |
# |------------|----------|-----------------------------------------------------------------|
# | 2026-10-30 | Arekkazu | RF-66: persistencia de los resultados del motor IA               |
"""Escritura de ``modulo4.resultados_inferencia``. Bajo RLS, solo el usuario de
servicio puede insertar (``pol_resultado_inferencia_servicio_insert``): el router
usa ``get_db_sistema``."""
from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy.orm import Session

from src.prediction.domain.entities.resultado_inferencia import ResultadoInferencia
from src.prediction.domain.repositories.resultado_inferencia_repository import ResultadoInferenciaRepository
from src.prediction.infrastructure.models.resultado_inferencia_model import ResultadoInferenciaModel
from src.shared.db_error_translator import raise_from_db_error

_CAMPOS = (
    "id_resultado_inferencia", "id_paquete_inferencia", "id_activo_biologico", "id_especie", "fase_productiva",
    "tipo_modelo", "id_version_modelo", "nivel_riesgo", "probabilidad_riesgo", "id_patologia",
    "probabilidad_enfermedad", "confianza_global", "contexto_incompleto", "modo_ejecucion", "latencia_ms",
    "fecha_inicio_ventana", "fecha_fin_ventana", "fecha_inferencia", "tiene_alerta_generada", "modo_sombra",
)


class SqlAlchemyResultadoInferenciaRepository(ResultadoInferenciaRepository):
    def __init__(self, db: Session) -> None:
        self._db = db

    def obtener(self, id_resultado: uuid.UUID) -> Optional[ResultadoInferencia]:
        orm = self._db.get(ResultadoInferenciaModel, id_resultado)
        return None if orm is None else ResultadoInferencia(**{c: getattr(orm, c) for c in _CAMPOS})

    def guardar(self, resultado: ResultadoInferencia) -> ResultadoInferencia:
        try:
            orm = ResultadoInferenciaModel(
                **{c: getattr(resultado, c) for c in _CAMPOS},
                latencia_excedida=resultado.latencia_excedida,
            )
            self._db.add(orm)
            self._db.flush()
            return resultado
        except Exception as exc:
            raise_from_db_error(exc)
