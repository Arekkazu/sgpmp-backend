# | Fecha      | Nombre   | Que se hizo                                                        |
# |------------|----------|--------------------------------------------------------------------|
# | 2026-10-31 | Arekkazu | RF-71: conteo de retroalimentaciones nuevas por modelo individual  |
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from src.prediction.domain.entities.retroalimentacion_clinica import RetroalimentacionClinica
from src.prediction.domain.repositories.retroalimentacion_clinica_repository import RetroalimentacionClinicaRepository
from src.prediction.infrastructure.models.retroalimentacion_clinica_model import RetroalimentacionClinicaModel
from src.shared.db_error_translator import raise_from_db_error


#: Última versión por tipo de modelo; cuenta cada resultado retroalimentado después de ella.
_SQL_NUEVAS_POR_TIPO = text("""
    WITH ultima AS (
        SELECT tipo_modelo::text AS tipo, max(COALESCE(fecha_entrenamiento, fecha_registro)) AS desde
        FROM modulo4.versiones_modelos
        WHERE tipo_modelo::text = ANY(CAST(:tipos AS text[]))
        GROUP BY tipo_modelo
    )
    SELECT t.tipo, u.desde, count(DISTINCT r.id_resultado_inferencia)
    FROM unnest(CAST(:tipos AS text[])) AS t(tipo)
    LEFT JOIN ultima u ON u.tipo = t.tipo
    LEFT JOIN modulo4.resultados_inferencia ri ON ri.tipo_modelo::text = t.tipo
    LEFT JOIN modulo4.retroalimentaciones_clinicas r
      ON r.id_resultado_inferencia = ri.id_resultado_inferencia AND r.estado_registro = 'ACTIVO'
     AND (u.desde IS NULL OR r.fecha_retroalimentacion > u.desde)
    GROUP BY t.tipo, u.desde
""")


class SqlAlchemyRetroalimentacionClinicaRepository(RetroalimentacionClinicaRepository):
    def __init__(self, db: Session) -> None:
        self._db = db

    def _a_entidad(self, orm: RetroalimentacionClinicaModel) -> RetroalimentacionClinica:
        return RetroalimentacionClinica(
            id_retroalimentacion=orm.id_retroalimentacion,
            id_resultado_inferencia=orm.id_resultado_inferencia,
            id_activo_biologico=orm.id_activo_biologico,
            estado_retroalimentacion=orm.estado_retroalimentacion,
            diagnosticos_reales=list(orm.diagnosticos_reales) if orm.diagnosticos_reales else None,
            fuente_diagnostico=orm.fuente_diagnostico,
            es_fuente_desconocida=orm.es_fuente_desconocida,
            es_conflicto_retroalimentacion=orm.es_conflicto_retroalimentacion,
            observaciones_clinicas=orm.observaciones_clinicas,
            id_usuario_veterinario=orm.id_usuario_veterinario,
            fecha_retroalimentacion=orm.fecha_retroalimentacion,
            estado_registro=orm.estado_registro,
        )

    def guardar(self, entidad: RetroalimentacionClinica) -> RetroalimentacionClinica:
        try:
            orm = RetroalimentacionClinicaModel(
                id_resultado_inferencia=entidad.id_resultado_inferencia,
                id_activo_biologico=entidad.id_activo_biologico,
                estado_retroalimentacion=entidad.estado_retroalimentacion,
                diagnosticos_reales=entidad.diagnosticos_reales,
                fuente_diagnostico=entidad.fuente_diagnostico,
                es_fuente_desconocida=entidad.es_fuente_desconocida,
                es_conflicto_retroalimentacion=entidad.es_conflicto_retroalimentacion,
                observaciones_clinicas=entidad.observaciones_clinicas,
                id_usuario_veterinario=entidad.id_usuario_veterinario,
                estado_registro=entidad.estado_registro,
            )
            self._db.add(orm)
            self._db.flush()
            self._db.refresh(orm)
            return self._a_entidad(orm)
        except Exception as exc:
            raise_from_db_error(exc)

    def obtener_por_resultado_y_usuario(
        self, id_resultado: uuid.UUID, id_usuario: int
    ) -> Optional[RetroalimentacionClinica]:
        stmt = select(RetroalimentacionClinicaModel).where(
            RetroalimentacionClinicaModel.id_resultado_inferencia == id_resultado,
            RetroalimentacionClinicaModel.id_usuario_veterinario == id_usuario,
        )
        orm = self._db.execute(stmt).scalar_one_or_none()
        return self._a_entidad(orm) if orm else None

    def listar_por_resultado(
        self, id_resultado: uuid.UUID
    ) -> list[RetroalimentacionClinica]:
        stmt = select(RetroalimentacionClinicaModel).where(
            RetroalimentacionClinicaModel.id_resultado_inferencia == id_resultado,
        )
        return [self._a_entidad(r) for r in self._db.execute(stmt).scalars().all()]

    def contar_nuevas_por_tipo_modelo(
        self, tipos_modelo: list[str]
    ) -> dict[str, tuple[int, Optional[datetime]]]:
        try:
            filas = self._db.execute(_SQL_NUEVAS_POR_TIPO, {"tipos": list(tipos_modelo)}).all()
        except Exception as exc:
            raise_from_db_error(exc)
        return {tipo: (int(n), desde) for tipo, desde, n in filas}
