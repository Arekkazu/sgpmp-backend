"""Implementación SQLAlchemy de :class:`ReporteGastoRepository` (RF-77).

Persiste únicamente el snapshot (encabezado + totales) en
``modulo5.reporte_gastos_acumulados`` — el desglose temporal, la tendencia y
los registros sin costo no tienen columnas propias en esa tabla; se guardan
en ``resultado_json`` de ``ejecuciones_generacion_reportes_gastos`` (ver
``SqlAlchemyTrabajoReporteGastoRepository``) y se devuelven al cliente sin
persistir aparte en el flujo síncrono.
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from src.shared.db_error_translator import raise_from_db_error
from src.supplies.domain.entities.reporte_gasto import ReporteGasto
from src.supplies.domain.repositories.reporte_gasto_repository import ReporteGastoRepository
from src.supplies.infrastructure.models.reporte_gasto_acumulado_model import ReporteGastoAcumuladoModel


class SqlAlchemyReporteGastoRepository(ReporteGastoRepository):
    def __init__(self, db: Session) -> None:
        self.db = db

    @staticmethod
    def _a_entidad(orm: ReporteGastoAcumuladoModel) -> ReporteGasto:
        return ReporteGasto(
            id_reporte_gasto_acumulado=orm.id_reporte_gasto_acumulado,
            id_activo_biologico=orm.id_activo_biologico,
            id_infraestructura=orm.id_infraestructura,
            fecha_inicio=orm.fecha_incio_reporte,
            fecha_fin=orm.fecha_fin_report,
            tipo_periodo=orm.categoria or "CICLO_COMPLETO",
            gasto_total_acumulado=orm.total_costo_directo,
            id_usuario=orm.id_usuario,
            fecha_generacion=orm.fecha_generacion,
        )

    def guardar(self, reporte: ReporteGasto) -> ReporteGasto:
        try:
            orm = ReporteGastoAcumuladoModel(
                id_activo_biologico=reporte.id_activo_biologico,
                id_infraestructura=reporte.id_infraestructura,
                fecha_incio_reporte=reporte.fecha_inicio,
                fecha_fin_report=reporte.fecha_fin,
                categoria=reporte.tipo_periodo,
                total_costo_alimento=next(
                    (d.subtotal for d in reporte.desglose_categorias if d.categoria == "ALIMENTACION"),
                    0,
                ),
                total_costo_medicamento=next(
                    (d.subtotal for d in reporte.desglose_categorias if d.categoria == "MEDICACION"),
                    0,
                ),
                total_costo_directo=reporte.gasto_total_acumulado,
                id_usuario=reporte.id_usuario,
            )
            self.db.add(orm)
            self.db.flush()
            self.db.refresh(orm)
        except Exception as exc:
            raise_from_db_error(exc, {})
        reporte.id_reporte_gasto_acumulado = orm.id_reporte_gasto_acumulado
        reporte.fecha_generacion = orm.fecha_generacion
        return reporte

    def obtener(self, id_reporte_gasto_acumulado: int) -> Optional[ReporteGasto]:
        orm = self.db.get(ReporteGastoAcumuladoModel, id_reporte_gasto_acumulado)
        return self._a_entidad(orm) if orm else None

    def listar_historial(self, id_usuario: Optional[int], limite: int = 20) -> list[ReporteGasto]:
        query = self.db.query(ReporteGastoAcumuladoModel)
        if id_usuario is not None:
            query = query.filter(ReporteGastoAcumuladoModel.id_usuario == id_usuario)
        registros = (
            query.order_by(ReporteGastoAcumuladoModel.fecha_generacion.desc()).limit(limite).all()
        )
        return [self._a_entidad(o) for o in registros]
