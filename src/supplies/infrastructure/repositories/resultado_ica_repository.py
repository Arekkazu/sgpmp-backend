"""Implementación SQLAlchemy de :class:`ResultadoICARepository` (RF-74 / CU-02).

Único punto que cruza la frontera ORM ↔ dominio para los resultados ICA. Usa
``flush()``/``refresh()`` (nunca ``commit()``) y traduce errores de BD con
``raise_from_db_error``. La auditoría la escribe un trigger de BD (no aquí).
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy import update
from sqlalchemy.orm import Session

from src.shared.db_error_translator import raise_from_db_error
from src.supplies.domain.entities.resultado_ica import ResultadoICA
from src.supplies.domain.repositories.resultado_ica_repository import ResultadoICARepository
from src.supplies.domain.value_objects.eficiencia_enums import (
    CausaNoCalculo,
    ClasificacionCA,
    EstadoResultadoCA,
    PeriodoEvaluacion,
    TipoCalculo,
)
from src.supplies.infrastructure.models.resultado_ica_model import ResultadoIcaModel


class SqlAlchemyResultadoICARepository(ResultadoICARepository):
    """Adaptador SQLAlchemy para ``modulo5.resultado_ica``."""

    def __init__(self, db: Session) -> None:
        self.db = db

    # ── Mapeo ORM → dominio ─────────────────────────────────────────────────
    @staticmethod
    def _a_entidad(orm: ResultadoIcaModel) -> ResultadoICA:
        return ResultadoICA(
            id_resultado_ica=orm.id_resultado_ica,
            id_activo_biologico=orm.id_activo_biologico,
            periodo_evaluacion=PeriodoEvaluacion(orm.periodo_evaluacion),
            fecha_inicio_periodo=orm.fecha_inicio_periodo,
            fecha_fin_periodo=orm.fecha_fin_periodo,
            estado_resultado=EstadoResultadoCA(orm.estado_resultado),
            tipo_calculo=TipoCalculo(orm.tipo_calculo) if orm.tipo_calculo else TipoCalculo.AUTOMATICO,
            data_quality_score=orm.data_quality_score or 0,
            es_vigente=orm.es_vigente,
            intento=orm.intento,
            alimento_consumido_total_kg=orm.alimento_consumido_total_kg,
            ganancia_peso_kg=orm.ganancia_peso_kg,
            ca_calculado=orm.ca_calculado,
            clasificacion_ca=ClasificacionCA(orm.clasificacion_ca) if orm.clasificacion_ca else None,
            causa_no_calculo=CausaNoCalculo(orm.causa_no_calculo) if orm.causa_no_calculo else None,
            id_usuario=orm.id_usuario,
            fecha_calculo=orm.fecha_calculo,
        )

    # ── Operaciones del puerto ──────────────────────────────────────────────
    def obtener_vigente(
        self, id_activo_biologico: int, periodo: PeriodoEvaluacion
    ) -> Optional[ResultadoICA]:
        orm = (
            self.db.query(ResultadoIcaModel)
            .filter(
                ResultadoIcaModel.id_activo_biologico == id_activo_biologico,
                ResultadoIcaModel.periodo_evaluacion == periodo.value,
                ResultadoIcaModel.es_vigente.is_(True),
            )
            .one_or_none()
        )
        return self._a_entidad(orm) if orm else None

    def listar_historial(
        self, id_activo_biologico: int, periodo: Optional[PeriodoEvaluacion] = None
    ) -> list[ResultadoICA]:
        query = self.db.query(ResultadoIcaModel).filter(
            ResultadoIcaModel.id_activo_biologico == id_activo_biologico
        )
        if periodo is not None:
            query = query.filter(ResultadoIcaModel.periodo_evaluacion == periodo.value)
        registros = query.order_by(
            ResultadoIcaModel.periodo_evaluacion.asc(),
            ResultadoIcaModel.fecha_calculo.desc(),
            ResultadoIcaModel.id_resultado_ica.desc(),
        ).all()
        return [self._a_entidad(o) for o in registros]

    def tiene_vigente_critica(self, id_activo_biologico: int) -> bool:
        existe = (
            self.db.query(ResultadoIcaModel.id_resultado_ica)
            .filter(
                ResultadoIcaModel.id_activo_biologico == id_activo_biologico,
                ResultadoIcaModel.es_vigente.is_(True),
                ResultadoIcaModel.clasificacion_ca == ClasificacionCA.CRITICA.value,
            )
            .first()
        )
        return existe is not None

    def guardar(self, resultado: ResultadoICA) -> ResultadoICA:
        try:
            if resultado.es_vigente:
                # Desmarca el vigente anterior (queda como histórico) antes de insertar.
                self.db.execute(
                    update(ResultadoIcaModel)
                    .where(
                        ResultadoIcaModel.id_activo_biologico == resultado.id_activo_biologico,
                        ResultadoIcaModel.periodo_evaluacion == resultado.periodo_evaluacion.value,
                        ResultadoIcaModel.es_vigente.is_(True),
                    )
                    .values(es_vigente=False)
                )
                self.db.flush()

            orm = ResultadoIcaModel(
                id_activo_biologico=resultado.id_activo_biologico,
                periodo_evaluacion=resultado.periodo_evaluacion.value,
                fecha_inicio_periodo=resultado.fecha_inicio_periodo,
                fecha_fin_periodo=resultado.fecha_fin_periodo,
                estado_resultado=resultado.estado_resultado.value,
                es_vigente=resultado.es_vigente,
                intento=resultado.intento,
                alimento_consumido_total_kg=resultado.alimento_consumido_total_kg,
                ganancia_peso_kg=resultado.ganancia_peso_kg,
                ca_calculado=resultado.ca_calculado,
                clasificacion_ca=resultado.clasificacion_ca.value if resultado.clasificacion_ca else None,
                data_quality_score=resultado.data_quality_score,
                causa_no_calculo=resultado.causa_no_calculo.value if resultado.causa_no_calculo else None,
                tipo_calculo=resultado.tipo_calculo.value,
                id_usuario=resultado.id_usuario,
            )
            self.db.add(orm)
            self.db.flush()
            self.db.refresh(orm)
        except Exception as exc:
            raise_from_db_error(exc, {})
        return self._a_entidad(orm)
